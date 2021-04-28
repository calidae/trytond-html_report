import os
from datetime import datetime

import jinja2
import jinja2.ext
from babel import support

import weasyprint

from trytond.tools import file_open
from trytond.pool import Pool
from trytond.transaction import Transaction
from trytond.report import Report


class SwitchableTranslations:
    '''
    Class that implements ugettext() and ngettext() as expected by
    jinja2.ext.i18n but also adds the ability to switch the language
    at any point in a template.

    The class is used by SwitchableLanguageExtension
    '''
    def __init__(self, lang='en', dirname=None, domain=None):
        self.dirname = dirname
        self.domain = domain
        self.cache = {}
        self.env = None
        self.current = None
        self.language = lang
        self.report = None
        self.set_language(lang)

    # TODO: We should implement a context manager

    def set_language(self, lang='en'):
        self.language = lang
        if lang in self.cache:
            self.current = self.cache[lang]
            return

        context = Transaction().context
        if context.get('report_translations'):
            report_translations = context['report_translations']
            if os.path.isdir(report_translations):
                self.current = support.Translations.load(
                    dirname=report_translations,
                    locales=[lang],
                    domain=self.domain,
                    )
                self.cache[lang] = self.current
        else:
            self.report = context.get('html_report', -1)

    def ugettext(self, message):
        Report = Pool().get('ir.action.report')

        if self.current:
            return self.current.ugettext(message)
        elif self.report:
            return Report.gettext(self.report, message, self.language)
        return message

    def ngettext(self, singular, plural, n):
        Report = Pool().get('ir.action.report')

        if self.current:
            return self.current.ugettext(singular, plural, n)
        elif self.report:
            return Report.gettext(self.report, singular, self.language)
        return singular



# Based on
# https://stackoverflow.com/questions/44882075/switch-language-in-jinja-template/45014393#45014393

class SwitchableLanguageExtension(jinja2.ext.Extension):
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
        return jinja2.ext.nodes.CallBlock(self.call_method('_switch_language',
                args), [], [], body).set_lineno(lineno)

    def _switch_language(self, language_code, caller):
        if self.translations:
            self.translations.set_language(language_code)
        with Transaction().set_context(language=language_code):
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
    def get_environment(cls):
        """
        Create and return a jinja environment to render templates

        Downstream modules can override this method to easily make changes
        to environment
        """
        extensions = ['jinja2.ext.i18n', 'jinja2.ext.autoescape',
            'jinja2.ext.with_', 'jinja2.ext.loopcontrols', 'jinja2.ext.do',
            SwitchableLanguageExtension]
        env = jinja2.Environment(extensions=extensions,
            loader=jinja2.FunctionLoader(cls.jinja_loader_func))
        env.filters.update(cls.get_jinja_filters())

        context = Transaction().context
        locale = context.get(
            'report_lang', Transaction().language or 'en').split('_')[0]
        report_translations = context.get('report_translations')
        if report_translations and os.path.isdir(report_translations):
            translations = SwitchableTranslations(
                locale, report_translations, cls.babel_domain)
        else:
            translations = SwitchableTranslations(locale)
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
