import os
from trytond.model import ModelSQL, ModelView, fields, sequence_ordered
from trytond.pyson import Eval
from trytond.tools import file_open
from trytond.pool import Pool


class Signature(ModelSQL, ModelView):
    'HTML Template Signature'
    __name__ = 'html.template.signature'
    name = fields.Char('Name', required=True)


class Template(sequence_ordered(), ModelSQL, ModelView):
    'HTML Template'
    __name__ = 'html.template'
    name = fields.Char('Name', required=True)
    type = fields.Selection([
            ('base', 'Base'),
            ('header', 'Header'),
            ('footer', 'Footer'),
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
    filename = fields.Char('Template path')
    content = fields.Text('Content')
    all_content = fields.Function(fields.Text('All Content'),
        'get_all_content')

    def get_rec_name(self, name):
        res = self.name
        if self.implements:
            res += ' / ' + self.implements.rec_name
        return res

    def get_base_content(self):
        if not self.filename:
            return self.content
        value = None
        try:
            with file_open(self.filename, subdir='modules', mode='r',
                    encoding='utf-8') as fp:
                value = fp.read()
        except IOError:
            pass
        return value

    def get_all_content(self, name):
        if self.type in ('base', 'header', 'footer'):
            return self.get_base_content()
        elif self.type == 'extension':
            return '{%% extends "%s" %%} {# %s #}\n\n%s' % (self.parent.id,
                self.parent.name, self.content)
        elif self.type == 'macro':
            return '{%% macro %s %%}\n%s\n{%% endmacro %%}' % (
                self.implements.name, self.get_base_content())

    @classmethod
    def copy(cls, templates, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        res = []
        default.setdefault('filename', None)
        for template in templates:
            default.setdefault('content', template.all_content)
            res += super(Template, cls).copy([template], default=default)
        return res



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
    template = fields.Many2One('html.template', 'Template',
        domain=[
            ('implements', '=', Eval('signature')),
            ])
    template_used = fields.Function(
        fields.Many2One('html.template', 'Template Used'), 'get_template_used')


    def get_template_used(self, name):
        Template = Pool().get('html.template')
        if self.template:
            return self.template.id
        templates = Template.search([('implements', '=', self.signature)])
        if templates:
            return templates[0].id
