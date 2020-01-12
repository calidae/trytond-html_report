import os
from trytond.model import ModelSQL, ModelView, fields
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval
from trytond.transaction import Transaction
from trytond.exceptions import UserError
from trytond.i18n import gettext
from . import engine


class HTMLReport(engine.HTMLReport):
    'HTML Report'
    __name__ = 'html.report'

    @classmethod
    def get_html_report(cls):
        Report = Pool().get('html.report')

        report_name = Transaction().context.get('email').get('subject')
        report, = Report.search([('name', '=', report_name)], limit=1)
        return report

    @classmethod
    def get_template(cls, action):
        return cls.get_html_report().content

    @classmethod
    def get_name(cls, action):
        return cls.get_html_report().name

    @classmethod
    def execute(cls, ids, data):
        context = Transaction().context
        context['report_translations'] = os.path.join(
            '/home/albert/d/audioson/modules/account_invoice_html_report',
            #os.path.dirname(__file__),
            'report', 'translations')
        with Transaction().set_context(**context):
            result = super().execute(ids, data)
            return result


class ActionKeyword(metaclass=PoolMeta):
    __name__ = 'ir.action.keyword'

    @classmethod
    def get_keyword(cls, keyword, value):
        Report = Pool().get('html.report')

        keywords = super().get_keyword(keyword, value)
        if keyword == 'form_print':
            model, _ = value
            reports = Report.search([('model.model', '=', model)])
            for report in reports:
                keywords.append(report.get_action_values())
        return keywords


class Signature(ModelSQL, ModelView):
    'HTML Template Signature'
    __name__ = 'html.template.signature'
    name = fields.Char('Name', required=True)


class Template(ModelSQL, ModelView):
    'HTML Template'
    __name__ = 'html.template'
    name = fields.Char('Name', required=True)
    type = fields.Selection([
            ('base', 'Base'),
            ('extension', 'Extension'),
            ('block', 'Block'),
            ('macro', 'Macro'),
            ], 'Type', required=True)
    implements = fields.Many2One('html.template.signature', 'Signature',
        states={
            'required': Eval('type') == 'macro',
            'invisible': Eval('type') != 'macro',
            })
    uses = fields.Many2Many('html.template.usage', 'template', 'signature',
        'Uses')
    parent = fields.Many2One('html.template', 'Parent', domain=[
            ('type', 'in', ['base', 'extension']),
            ], states={
            'required': Eval('type') == 'extension',
            'invisible': Eval('type') != 'extension',
            }, depends=['type'])
    content = fields.Text('Content')
    all_content = fields.Function(fields.Text('All Content'),
        'get_all_content')

    def get_rec_name(self, name):
        res = self.name
        if self.implements:
            res += ' / ' + self.implements.rec_name
        return res

    def get_all_content(self, name):
        if self.type == 'base':
            return self.content
        elif self.type == 'extension':
            return '{%% extends "%s" %%}\n\n%s' % (self.parent.name, self.content)
        elif self.type == 'macro':
            return '{%% macro %s %%}\n%s\n{%% endmacro %%}' % (
                self.implements.name, self.content)


class TemplateUsage(ModelSQL):
    'HTML Template Usage'
    __name__ = 'html.template.usage'
    template = fields.Many2One('html.template', 'Template', required=True)
    signature = fields.Many2One('html.template.signature', 'Signature',
        required=True)


class Report(ModelSQL, ModelView):
    'HTML Report'
    __name__ = 'html.report'
    name = fields.Char('Name', translate=True)
    model = fields.Many2One('ir.model', 'Model', required=True)
    template = fields.Many2One('html.template', 'Template', required=True,
        domain=[
            ('type', 'in', ['base', 'extension']),
            ])
    templates = fields.One2Many('html.report.template', 'report', 'Templates')
    content = fields.Function(fields.Text('Content'), 'get_content')

    def get_action_values(self):
        Data = Pool().get('ir.model.data')
        return {
            'id': Data.get_id('html_report', 'report_html'),
            'type': 'ir.action.report',
            'name': self.name,
            'model': self.model.model,
            'report_name': 'html.report',
            'direct_print': False,
            'email_print': False,
            'email': None,
            'context': "{'filigrana': True}",
            'html_report_id': self.id,
            }

    def get_content(self, name):
        content = [self.template.all_content]
        for template in self.templates:
            content.append(template.template.all_content)
        return '\n\n'.join(content)

    @classmethod
    def validate(cls, reports):
        for report in reports:
            report.check_templates()

    def check_templates(self):
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
        existing = {x.signature for x in self.templates}
        required = self.required_signatures()
        missing = required - existing
        unused = existing - required
        return missing, unused

    def required_signatures(self):
        if not self.template:
            return set()
        signatures = {x for x in self.template.uses}
        for template in self.templates:
            if not template.template:
                continue
            signatures |= {x for x in template.template.uses}
        return signatures

    @fields.depends('template', 'templates')
    def on_change_template(self):
        pool = Pool()
        Template = pool.get('html.template')
        ReportTemplate = pool.get('html.report.template')

        missing, unused = self.get_missing_unused_signatures()

        templates = list(self.templates)
        for signature in missing:
            record = ReportTemplate()
            record.signature = signature
            implementors = Template.search([('implements', '=', signature)])
            if len(implementors) == 1:
                record.template, = implementors
            templates.append(record)

        print('TEMPS: ', templates)
        self.templates = templates


class ReportTemplate(ModelSQL, ModelView):
    'HTML Report - Template'
    __name__ = 'html.report.template'
    report = fields.Many2One('html.report', 'Report', required=True)
    signature = fields.Many2One('html.template.signature', 'Signature',
        required=True)
    template = fields.Many2One('html.template', 'Template', required=True)
