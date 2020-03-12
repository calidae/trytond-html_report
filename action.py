# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.model import fields
from trytond.pyson import Eval
from trytond.exceptions import UserError
from trytond.i18n import gettext
from trytond.tools import file_open
import os

__all__ = ['ActionReport']


class ActionReport(metaclass=PoolMeta):
    __name__ = 'ir.action.report'
    html_template = fields.Many2One('html.template', 'Template',
        domain=[
            ('type', 'in', ['base', 'extension']),
            ],
        states={
            'invisible': Eval('template_extension') != 'jinja',
            },
        depends=['template_extension'])
    html_templates = fields.One2Many('html.report.template', 'report', 'Templates',
        states={
            'invisible': Eval('template_extension') != 'jinja',
            },
        depends=['template_extension'])
    html_content = fields.Function(fields.Text('Content',
        states={
                'invisible': Eval('template_extension') != 'jinja',
        },
        depends=['template_extension']), 'get_content')

    html_header_report = fields.Char('Header')
    html_footer_report = fields.Char('Footer')
    html_header_content = fields.Function(fields.Binary('Header Content',
        states={
                'invisible': Eval('template_extension') != 'jinja',
        },
        depends=['template_extension']), 'get_content')

    html_footer_content = fields.Function(fields.Binary('Footer Content',
        states={
                'invisible': Eval('template_extension') != 'jinja',
        },
        depends=['template_extension']), 'get_content')

    @classmethod
    def __setup__(cls):
        super(ActionReport, cls).__setup__()

        jinja_option = ('jinja', 'Jinja')
        if not jinja_option in cls.template_extension.selection:
            cls.template_extension.selection.append(jinja_option)

    @classmethod
    def view_attributes(cls):
        return super(ActionReport, cls).view_attributes() + [
            ('//page[@id="html_report"]', 'states', {
                    'invisible': Eval('template_extension') != 'jinja',
                    })]

    def get_content(self, name):
        if name == 'html_content':
            if not self.html_template:
                return
            content = [self.html_template.all_content]
            for template in self.html_templates:
                if template.template.all_content:
                    content.append(template.template.all_content)
            return '\n\n'.join(content)
        if name in ('html_header_content', 'html_footer_content'):
            path_field_name = name.replace('content', 'report')
            path = getattr(self, path_field_name, None)
            if not path:
                return
            path = path.replace('/', os.sep)
            try:
                with file_open(path, mode='rb') as fp:
                    data = fp.read()
            except FileNotFoundError:
                data = None

            return data

    @classmethod
    def validate(cls, reports):
        for report in reports:
            report.check_template_jinja()

    def check_template_jinja(self):
        if self.template_extension == 'jinja':
            return
        missing, unused = self.get_missing_unused_signatures()
        if missing:
            raise UserError(gettext('html_report.missing_signatures', {
                        'template': self.rec_name,
                        'missing': '\n'.join(sorted([x.rec_name for x in
                                    missing]))
                        }))
        if unused:
            raise UserError(gettext('html_report.unused_signatures', {
                        'template': self.rec_name,
                        'unused': '\n'.join(sorted([x.rec_name for x in
                                    unused]))
                        }))

    def get_missing_unused_signatures(self):
        existing = {x.signature for x in self.html_templates}
        required = self.required_signatures()
        missing = required - existing
        unused = existing - required
        return missing, unused

    def required_signatures(self):
        if not self.html_template:
            return set()
        signatures = {x for x in self.html_template.uses}
        for template in self.html_templates:
            if not template.template:
                continue
            signatures |= {x for x in template.template.uses}
        return signatures

    @fields.depends('html_template', 'html_templates')
    def on_change_html_template(self):
        pool = Pool()
        Template = pool.get('html.template')
        ReportTemplate = pool.get('html.report.template')

        missing, unused = self.get_missing_unused_signatures()

        templates = list(self.html_templates)
        for signature in missing:
            record = ReportTemplate()
            record.signature = signature
            implementors = Template.search([('implements', '=', signature)])
            if len(implementors) == 1:
                record.template, = implementors
            templates.append(record)

        self.html_templates = templates
