from trytond.model import ModelSQL, ModelView, fields
from trytond.pyson import Eval


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
            return '{%% extends "%s" %%} {# %s #}\n\n%s' % (self.parent.id, self.parent.name, self.content)
        elif self.type == 'macro':
            return '{%% macro %s %%}\n%s\n{%% endmacro %%}' % (
                self.implements.name, self.content)


class TemplateUsage(ModelSQL):
    'HTML Template Usage'
    __name__ = 'html.template.usage'
    template = fields.Many2One('html.template', 'Template', required=True,
        ondelete='CASCADE')
    signature = fields.Many2One('html.template.signature', 'Signature',
        required=True)


class ReportTemplate(ModelSQL, ModelView):
    'HTML Report - Template'
    __name__ = 'html.report.template'
    report = fields.Many2One('ir.action.report', 'Report', required=True,
        domain=[('template_extension', '=', 'jinja')], ondelete='CASCADE')
    signature = fields.Many2One('html.template.signature', 'Signature',
        required=True)
    template = fields.Many2One('html.template', 'Template', required=True,
        domain=[
            ('implements', '=', Eval('signature')),
            ])
