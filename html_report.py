import os
import binascii
import mimetypes
from functools import partial
from decimal import Decimal
from datetime import date, datetime

from jinja2 import Environment, FunctionLoader
from jinja2.ext import Extension, nodes
from babel import dates, numbers, support

import weasyprint

from trytond.tools import file_open
from trytond.pool import Pool
from trytond.transaction import Transaction
from trytond.report import Report
from trytond.i18n import gettext


class SwitchableTranslations:
    '''
    Class that implements ugettext() and ngettext() as expected by
    jinja2.ext.i18n but also adds the ability to switch the language
    at any point in a template.

    The class is used by SwitchableLanguageExtension
    '''
    def __init__(self, dirname, domain, code=None):
        self.dirname = dirname
        self.domain = domain
        self.cache = {}
        self.env = None
        self.set_language(code)

    def set_language(self, code):
        if not code:
            self.current = None
            return
        if code in self.cache:
            self.current = self.cache[code]
            return
        context = Transaction().context
        if context.get('report_translations'):
            report_translations = context['report_translations']
            if os.path.isdir(report_translations):
                self.current = support.Translations.load(
                    dirname=report_translations,
                    locales=[code],
                    domain=self.domain,
                    )
                self.cache[code] = self.current

    def ugettext(self, message):
        if not self.current:
            return message
        return self.current.ugettext(message)

    def ngettext(self, singular, plural, n):
        if not self.current:
            return singular
        return self.current.ugettext(singular, plural, n)


# Based on
# https://stackoverflow.com/questions/44882075/switch-language-in-jinja-template/45014393#45014393

class SwitchableLanguageExtension(Extension):
    '''
    This Jinja2 Extension allows the user to use the folowing tag:

    {% language 'en' %}
    {% endlanguage %}

    All gettext() calls within the block will return the text in the language
    defined thanks to the use of SwitchableTranslations class.
    '''
    tags = {'language'}

    def __init__(self, env):
        self.env = env
        env.extend(
            install_switchable_translations=self._install,
            )
        self.translations = None

    def _install(self, translations):
        self.env.install_gettext_translations(translations)
        self.translations = translations

    def parse(self, parser):
        lineno = next(parser.stream).lineno
        # Parse the language code argument
        args = [parser.parse_expression()]
        # Parse everything between the start and end tag:
        body = parser.parse_statements(['name:endlanguage'], drop_needle=True)
        # Call the _switch_language method with the given language code and body
        return nodes.CallBlock(self.call_method('_switch_language', args), [],
            [], body).set_lineno(lineno)

    def _switch_language(self, language_code, caller):
        if self.translations:
            self.translations.set_language(language_code)
        output = caller()
        return output


class HTMLReport(Report):
    render_method = "weasyprint"
    babel_domain = 'messages'
    report_translations = None

    @classmethod
    def execute(cls, ids, data):
        with Transaction().set_context({
                    'html_report_ids': ids,
                    'html_report_data': data,
                    }):
            return super().execute(ids, data)

    @classmethod
    def render(cls, report, report_context):
        pool = Pool()
        Company = pool.get('company.company')

        # Convert to str as buffer from DB is not supported by StringIO
        report_content = (report.report_content if report.report_content
                          else False)
        if not report.report_content:
            raise Exception('Error', 'Missing report file!')
        report_content = report.report_content.decode('utf-8')

        # Make the report itself available n the report context
        report_context['report'] = report
        company_id = Transaction().context.get('company')
        report_context['company'] = Company(company_id)

        company_id = Transaction().context.get('company')

        ids = Transaction().context.get('html_report_ids')
        data = Transaction().context.get('html_report_data')
        if ids and data.get('model'):
            Model = pool.get(data['model'])
            report_context['record'] = Model(data['id'])
            report_context['records'] = Model.browse(ids)
        return cls.render_template(report_content, report_context)

    @classmethod
    def convert(cls, report, data):
        # Convert the report to PDF if the output format is PDF
        # Do not convert when report is generated in tests, as it takes
        # time to convert to PDF due to which tests run longer.
        # Pool.test is True when running tests.
        output_format = report.extension or report.template_extension

        if Pool.test:
            return output_format, data
        elif cls.render_method == "weasyprint" and output_format == "pdf":
            return output_format, cls.weasyprint(data)

        return output_format, data

    @classmethod
    def jinja_loader_func(cls, name):
        """
        Return the template from the module directories using the logic below:

        The name is expected to be in the format:

            <module_name>/path/to/template

        for example, if the account_invoice_html_report module had a base
        template in its reports folder, then you should be able to use:

            {% extends 'html_report/report/base.html' %}
        """
        module, path = name.split('/', 1)
        try:
            with file_open(os.path.join(module, path)) as f:
                return f.read()
        except IOError:
            return None

    @classmethod
    def get_jinja_filters(cls):
        """
        Returns filters that are made available in the template context.
        By default, the following filters are available:

        * dateformat: Formats a date using babel
        * datetimeformat: Formats a datetime using babel
        * currencyformat: Formats the given number as currency
        * modulepath: Returns the absolute path of a file inside a
            tryton-module (e.g. sale/sale.css)

        For additional arguments that can be passed to these filters,
        refer to the Babel `Documentation
        <http://babel.edgewall.org/wiki/Documentation>`_.
        """
        Lang = Pool().get('ir.lang')

        def module_path(name):
            module, path = name.split('/', 1)
            with file_open(os.path.join(module, path)) as f:
                return 'file://' + f.name

        def render_field(value, decimal_digits=2, lang=None, filename=None):
            if isinstance(value, (float, Decimal)):
                return lang.format('%.*f', (decimal_digits, value),
                    grouping=True)
            if value is None:
                return ''
            if isinstance(value, bool):
                return (gettext('html_report.msg_yes') if value else
                    gettext('html_report.msg_no'))
            if isinstance(value, int):
                return lang.format('%d', value, grouping=True)
            if hasattr(value, 'rec_name'):
                return value.rec_name
            if isinstance(value, datetime):
                return lang.strftime(value) + ' ' + value.strftime('%H:%M:%S')
            if isinstance(value, date):
                return lang.strftime(value)
            if isinstance(value, str):
                return value.replace('\n', '<br/>')
            if isinstance(value, bytes):
                value = binascii.b2a_base64(value)
                value = value.decode('ascii')
                # TODO: image/png should not be hardcoded
                mimetype = 'image/png'
                if filename:
                    mimetype = mimetypes.guess_type(filename)[0]
                return ('data:%s;base64,%s' % (mimetype, value)).strip()
            return value

        def type_field(record):
            return type(record).__name__

        locale = Transaction().context.get(
            'report_lang', Transaction().language).split('_')[0]
        lang, = Lang.search([
                ('code', '=', locale or 'en'),
                ])
        return {
            'dateformat': partial(dates.format_date, locale=locale),
            'datetimeformat': partial(dates.format_datetime, locale=locale),
            'timeformat': partial(dates.format_time, locale=locale),
            'timedeltaformat': partial(dates.format_timedelta, locale=locale),
            'numberformat': partial(numbers.format_number, locale=locale),
            'decimalformat': partial(numbers.format_decimal, locale=locale),
            'currencyformat': partial(numbers.format_currency, locale=locale),
            'percentformat': partial(numbers.format_percent, locale=locale),
            'scientificformat': partial(
                numbers.format_scientific, locale=locale),
            'modulepath': module_path,
            'render_field': partial(render_field, lang=lang),
            'type_field': type_field,
        }

    @classmethod
    def get_environment(cls):
        """
        Create and return a jinja environment to render templates

        Downstream modules can override this method to easily make changes
        to environment
        """
        extensions = ['jinja2.ext.i18n', 'jinja2.ext.autoescape',
            'jinja2.ext.with_', 'jinja2.ext.loopcontrols', 'jinja2.ext.do',
            SwitchableLanguageExtension]
        env = Environment(extensions=extensions,
            loader=FunctionLoader(cls.jinja_loader_func))
        env.filters.update(cls.get_jinja_filters())

        context = Transaction().context
        if context.get('report_translations'):
            report_translations = context['report_translations']
            if os.path.isdir(report_translations):
                locale = context.get(
                    'report_lang', Transaction().language).split('_')[0]

                translations = SwitchableTranslations(report_translations,
                    cls.babel_domain, locale)
                env.install_switchable_translations(translations)
        return env

    @classmethod
    def render_template(cls, template_string, localcontext):
        """
        Render the template using Jinja2
        """
        env = cls.get_environment()

        # Update header and footer in context
        company = localcontext['company']
        localcontext.update({
                'header': env.from_string(company.header_html or ''),
                'footer': env.from_string(company.footer_html or ''),
                'time': datetime.now(),
                })
        report_template = env.from_string(template_string)
        return report_template.render(**localcontext)

    @classmethod
    def weasyprint(cls, data, options=None):
        return weasyprint.HTML(string=data).write_pdf()
