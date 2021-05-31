import os
import io
import binascii
import mimetypes
import zipfile
import qrcode
import qrcode.image.svg
import barcode
from barcode.writer import SVGWriter
from io import BytesIO
from functools import partial
from decimal import Decimal
from datetime import date, datetime

import jinja2
import jinja2.ext
from babel import dates, numbers, support

import weasyprint
from .generator import PdfGenerator
from trytond.model.fields.selection import TranslatedSelection
from trytond.tools import file_open
from trytond.pool import Pool
from trytond.transaction import Transaction
from trytond.i18n import gettext
from trytond.model.modelstorage import _record_eval_pyson
from trytond.config import config
from trytond.exceptions import UserError
from trytond.tools import slugify

MEDIA_TYPE = config.get('html_report', 'type', default='screen')
RAISE_USER_ERRORS = config.getboolean('html_report', 'raise_user_errors',
    default=False)
DEFAULT_MIME_TYPE = config.get('html_report', 'mime_type', default='image/png')


class DualRecordError(Exception):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return self.message


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


class Formatter:
    def __init__(self):
        self.__langs = {}

    def format(self, record, field, value):
        formatter = '_formatted_%s' % field._type
        method = getattr(self, formatter, self._formatted_raw)
        return method(record, field, value)

    def _get_lang(self):
        Lang = Pool().get('ir.lang')
        locale = Transaction().context.get('report_lang', Transaction().language)
        lang = self.__langs.get(locale)
        if lang:
            return lang
        lang, = Lang.search([('code', '=', locale or 'en')], limit=1)
        self.__langs[locale] = lang
        return lang

    def _formatted_raw(self, record, field, value):
        return value

    def _formatted_many2one(self, record, field, value):
        if not value:
            return value
        return FormattedRecord(value, self)

    def _formatted_one2one(self, record, field, value):
        return self._formatted_many2one(record, field, value)

    def _formatted_reference(self, record, field, value):
        return self._formatted_many2one(record, field, value)

    def _formatted_one2many(self, record, field, value):
        if not value:
            return value
        return [FormattedRecord(x) for x in value]

    def _formatted_many2many(self, record, field, value):
        return self._formatted_one2many(record, field, value)

    def _formatted_boolean(self, record, field, value):
        return (gettext('html_report.msg_yes') if value else
            gettext('html_report.msg_no'))

    def _formatted_date(self, record, field, value):
        if value is None:
            return ''
        return self._get_lang().strftime(value)

    def _formatted_datetime(self, record, field, value):
        if value is None:
            return ''
        return (self._get_lang().strftime(value) + ' '
            + value.strftime('%H:%M:%S'))

    def _formatted_timestamp(self, record, field, value):
        return self._formatted_datetime(record, field, value)

    def _formatted_timedelta(self, record, field, value):
        if value is None:
            return ''
        return '%.2f' % value.total_seconds()

    def _formatted_char(self, record, field, value):
        if value is None:
            return ''
        Model = Pool().get(record.__name__)
        value = getattr(Model(record.id), field.name)
        return value.replace('\n', '<br/>')

    def _formatted_text(self, record, field, value):
        return self._formatted_char(record, field, value)

    def _formatted_integer(self, record, field, value):
        if value is None:
            return ''
        return str(value)

    def _formatted_float(self, record, field, value):
        if value is None:
            return ''
        digits = field.digits
        if digits is None:
            digits = 2
        else:
            digits = digits[1]
        if not isinstance(digits, int):
            digits = _record_eval_pyson(record, digits,
                encoded=False)
        return self._get_lang().format('%.*f', (digits, value), grouping=True)

    def _formatted_numeric(self, record, field, value):
        return self._formatted_float(record, field, value)

    def _formatted_binary(self, record, field, value):
        if not value:
            return
        value = binascii.b2a_base64(value)
        value = value.decode('ascii')
        filename = field.filename
        mimetype = DEFAULT_MIME_TYPE
        if filename:
            mimetype = mimetypes.guess_type(filename)[0]
        return ('data:%s;base64,%s' % (mimetype, value)).strip()

    def _formatted_selection(self, record, field, value):
        if value is None:
            return ''

        Model = Pool().get(record.__name__)
        record = Model(record.id)
        t  = TranslatedSelection(field.name)
        return t.__get__(record, record).replace('\n', '<br/>')

    # TODO: Implement: dict, multiselection


class FormattedRecord:
    def __init__(self, record, formatter=None):
        self._raw_record = record
        if formatter:
            self.__formatter = formatter
        else:
            self.__formatter = Formatter()

    def __getattr__(self, name):
        value = getattr(self._raw_record, name)
        field = self._raw_record._fields.get(name)
        if not field:
            return value
        return self.__formatter.format(self._raw_record, field, value)


class DualRecord:
    def __init__(self, record, formatter=None):
        self.raw = record
        if not formatter:
            formatter = Formatter()
        self.render = FormattedRecord(record, formatter)

    def __getattr__(self, name):
        field = self.raw._fields.get(name)
        if not field:
            raise DualRecordError('Field "%s" not found in record of model '
                '"%s".' % (name, self.raw.__name__))
        if field._type not in {'many2one', 'one2one', 'reference', 'one2many',
                'many2many'}:
            raise DualRecordError('You are trying to access field "%s" of type '
                '"%s" in a DualRecord of model "%s". You must use "raw." or '
                '"format." before the field name.' % (name, field._type,
                    self.raw.__name__))
        value = getattr(self.raw, name)
        if not value:
            return value
        if field._type in {'many2one', 'one2one', 'reference'}:
            return DualRecord(value)
        return [DualRecord(x) for x in value]

    @property
    def _attachments(self):
        pool = Pool()
        Attachment = pool.get('ir.attachment')
        return [DualRecord(x) for x in
            Attachment.search([('resource', '=', str(self.raw))])]

    @property
    def _notes(self):
        pool = Pool()
        Note = pool.get('ir.note')
        return [DualRecord(x) for x in
            Note.search([('resource', '=', str(self.raw))])]


class HTMLReportMixin:
    babel_domain = 'messages'

    @classmethod
    def _get_dual_records(cls, ids, model, data):
        records = cls._get_records(ids, model, data)
        return [DualRecord(x) for x in records]

    @classmethod
    def get_templates_jinja(cls, action):
        header = (action.html_header_content and
            action.html_header_content) # decode('utf-8'))
        content = (action.report_content
            and action.report_content.decode("utf-8") or action.html_content) #.decode('utf-8'))
        footer = (action.html_footer_content and
            action.html_footer_content) #.decode('utf-8'))
        last_footer = (action.html_last_footer_content and
            action.html_last_footer_content) #.decode('utf-8'))
        if not content:
            if not action.html_content:
                raise Exception('Error', 'Missing jinja report file!')
            content = action.html_content
        return header, content, footer, last_footer

    @classmethod
    def execute(cls, ids, data):
        if not ids:
            return

        cls.check_access()
        action, model = cls.get_action(data)
        # in case is not jinja, call super()
        if action.template_extension != 'jinja':
            return super().execute(ids, data)
        action_name = slugify(cls.get_name(action))

        # use DualRecord when template extension is jinja
        data['html_dual_record'] = True
        records = []
        with Transaction().set_context(html_report=action.id,
            address_with_party=False):
            if model:
                records = cls._get_dual_records(ids, model, data)

            # report single and len > 1, return zip file
            if action.single and len(ids) > 1:
                content = BytesIO()
                with zipfile.ZipFile(content, 'w') as content_zip:
                    for record in records:
                        oext, rcontent = cls._execute_html_report([record],
                            data, action)
                        rfilename = '%s-%s.%s' % (
                            action_name,
                            slugify(record.render.rec_name),
                            oext)
                        content_zip.writestr(rfilename, rcontent)
                content = content.getvalue()
                return ('zip', content, False, action_name)

            oext, content = cls._execute_html_report(records, data, action)
            if not isinstance(content, str):
                content = bytearray(content) if bytes == str else bytes(content)
        return oext, content, cls.get_direct_print(action), action_name

    @classmethod
    def _execute_html_report(cls, records, data, action):
        header_template, main_template, footer_template, last_footer_template = \
                cls.get_templates_jinja(action)
        extension = data.get('output_format', action.extension or 'pdf')
        if action.single:
            # If document requires a page counter for each record we need to
            # render records individually
            documents = []
            for record in records:
                content = cls.render_template_jinja(action, main_template,
                    record=record, records=[record], data=data)
                header = header_template and cls.render_template_jinja(action,
                    header_template, record=record, records=[record],
                    data=data)
                footer = footer_template and cls.render_template_jinja(action,
                    footer_template, record=record, records=[record],
                    data=data)
                last_footer = last_footer_template and cls.render_template_jinja(action,
                    last_footer_template, record=record, records=[record],
                    data=data)
                if extension == 'pdf':
                    documents.append(PdfGenerator(content, header_html=header,
                            footer_html=footer, last_footer_html=last_footer).render_html())
                else:
                    documents.append(content)
            if extension == 'pdf':
                document = documents[0].copy([page for doc in documents
                    for page in doc.pages])
                document = document.write_pdf()
            else:
                document = ''.join(documents)
        else:
            content = cls.render_template_jinja(action, main_template,
                records=records, data=data)
            header = header_template and cls.render_template_jinja(action,
                header_template, records=records, data=data)
            footer = footer_template and cls.render_template_jinja(action,
                footer_template, records=records, data=data)
            last_footer = last_footer_template and cls.render_template_jinja(action,
                last_footer_template, records=records, data=data)
            if extension == 'pdf':
                document = PdfGenerator(content, header_html=header,
                    footer_html=footer, last_footer_html=last_footer).render_html().write_pdf()
            else:
                document = content
        return extension, document

    @classmethod
    def get_action(cls, data):
        pool = Pool()
        ActionReport = pool.get('ir.action.report')

        action_id = data.get('action_id')
        if action_id is None:
            action_reports = ActionReport.search([
                    ('report_name', '=', cls.__name__)
                    ])
            assert action_reports, '%s not found' % cls
            action = action_reports[0]
        else:
            action = ActionReport(action_id)

        return action, action.model or data.get('model')

    @classmethod
    def get_name(cls, action):
        return action.name

    @classmethod
    def get_direct_print(cls, action):
        return action.direct_print

    @classmethod
    def jinja_loader_func(cls, name):
        """
        Return the template from the module directories or ID from other template.

        The name is expected to be in the format:

            <module_name>/path/to/template

        for example, if the account_invoice_html_report module had a base
        template in its reports folder, then you should be able to use:

            {% extends 'html_report/report/base.html' %}
        """
        Template = Pool().get('html.template')

        if '/' in name:
            module, path = name.split('/', 1)
            try:
                with file_open(os.path.join(module, path)) as f:
                    return f.read()
            except IOError:
                return None
        else:
            template, = Template.search([('id', '=', name)], limit=1)
            return template.all_content

    @classmethod
    def get_jinja_filters(cls):
        """
        Returns filters that are made available in the template context.
        By default, the following filters are available:

        * render: Renders value depending on its type
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

        def base64(name):
            module, path = name.split('/', 1)
            with file_open(os.path.join(module, path), 'rb') as f:
                value = binascii.b2a_base64(f.read())
                value = value.decode('ascii')
                mimetype = mimetypes.guess_type(f.name)[0]
                return ('data:%s;base64,%s' % (mimetype, value)).strip()

        def render(value, digits=2, lang=None, filename=None):
            if not lang:
                lang, = Lang.search([('code', '=', 'en')], limit=1)
            if isinstance(value, (float, Decimal)):
                return lang.format('%.*f', (digits, value),
                    grouping=True)
            if value is None or value == '':
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
                mimetype = DEFAULT_MIME_TYPE
                if filename:
                    mimetype = mimetypes.guess_type(filename)[0]
                return ('data:%s;base64,%s' % (mimetype, value)).strip()
            return value

        locale = Transaction().context.get('report_lang',
            Transaction().language).split('_')[0]
        lang, = Lang.search([
                ('code', '=', locale or 'en'),
                ])
        return {
            'modulepath': module_path,
            'base64': base64,
            'render': partial(render, lang=lang),
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
    def label(cls, model, field=None, lang=None):

        Translation = Pool().get('ir.translation')
        if not lang:
            lang = Transaction().language

        if not model:
            return ''

        if field == None:
            Model = Pool().get('ir.model')
            model, = Model.search([('model', '=', model)])
            return model.name
        else:
            translation = Translation.search([
                    ('name', '=', "%s,%s" % (model, field)),
                    ('lang', '=', lang),
                    ], limit=1)

            if translation:
                translation, = translation
                return translation.value or translation.src
            else:
                translation = Translation.search([
                        ('name', '=', "%s,%s" % (model, field)),
                        ('lang', '=', 'en'),
                        ], limit=1)
                if translation:
                    translation, = translation
                    return translation.value or translation.src

            return field

    @classmethod
    def qrcode(cls, value):
        qr_code = qrcode.make(value, image_factory=qrcode.image.svg.SvgImage)
        stream = io.BytesIO()
        qr_code.save(stream=stream)
        return cls.to_base64(stream.getvalue())

    @classmethod
    def barcode(cls, _type, value):
        ean_class = barcode.get_barcode_class(_type)
        ean_code = ean_class(value, writer=SVGWriter()).render()
        return cls.to_base64(ean_code)

    def to_base64(image):
        value = binascii.b2a_base64(image)
        value = value.decode('ascii')
        mimetype = "image/svg+xml"
        return ('data:%s;base64,%s' % (mimetype, value)).strip()

    @classmethod
    def render_template_jinja(cls, action, template_string, record=None,
            records=None, data=None):
        """
        Render the template using Jinja2
        """
        pool = Pool()
        User = pool.get('res.user')
        try:
            Company = pool.get('company.company')
        except:
            Company = None

        env = cls.get_environment()

        if records is None:
            records = []

        context = {
            'report': DualRecord(action),
            'record': record,
            'records': records,
            'data': data,
            'time': datetime.now(),
            'user': DualRecord(User(Transaction().user)),
            'Decimal': Decimal,
            'label': cls.label,
            'qrcode': cls.qrcode,
            'barcode': cls.barcode,
            }
        if Company:
            context['company'] = DualRecord(Company(
                    Transaction().context.get('company')))
        context.update(cls.local_context())
        try:
            report_template = env.from_string(template_string)
        except jinja2.exceptions.TemplateSyntaxError as e:
            if RAISE_USER_ERRORS or action.html_raise_user_error:
                raise UserError(gettext('html_report.template_error',
                        report=action.rec_name, error=repr(e)))
            raise
        try:
            res = report_template.render(**context)
        except Exception as e:
            if RAISE_USER_ERRORS or action.html_raise_user_error:
                raise UserError(gettext('html_report.render_error',
                        report=action.rec_name, error=repr(e)))
            raise
        return res

    @classmethod
    def local_context(cls):
        return {}

    @classmethod
    def weasyprint_render(cls, content):
        return weasyprint.HTML(string=content, media_type=MEDIA_TYPE).render()
