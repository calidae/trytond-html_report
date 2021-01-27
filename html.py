import re
from trytond.model import ModelSQL, ModelView, fields, sequence_ordered
from trytond.pyson import Eval, Bool
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
    uses = fields.Function(fields.Many2Many('html.template.usage', 'template',
        'signature', 'Uses'), 'get_uses')
    parent = fields.Many2One('html.template', 'Parent', domain=[
            ('type', 'in', ['base', 'extension']),
            ], states={
            'required': Eval('type') == 'extension',
            'invisible': Eval('type') != 'extension',
            }, depends=['type'])
    filename = fields.Char('Template path', states={
            'readonly': Bool(Eval('filename')),
            'invisible': ~Bool(Eval('filename')),
            })
    data = fields.Text('Content')
    content = fields.Function(fields.Text('Content', states={
            'readonly': Bool(Eval('filename')),
            }, depends=['filename']), 'get_content',
            setter='set_content')
    all_content = fields.Function(fields.Text('All Content'),
        'get_all_content')

    @classmethod
    def __register__(cls, module_name):
        table_h = cls.__table_handler__(module_name)

        if table_h.column_exist('content'):
            table_h.column_rename('content', 'data')
        super().__register__(module_name)

    def get_content(self, name):
        value = None
        if not self.filename:
            return self.data
        try:
            with file_open(self.filename, subdir='modules', mode='r',
                    encoding='utf-8') as fp:
                filename_value = fp.read()
                value = value+"\n"+filename_value if value else filename_value
        except IOError:
            pass
        return value

    @classmethod
    def set_content(cls, views, name, value):
        cls.write(views, {'data': value})

    def get_uses(self, name):
        Signature = Pool().get('html.template.signature')

        res = []
        match = re.findall("show_.*\(", self.content)
        for name in match:
            res += Signature.search([('name', 'like', name + '%')])
        return [x.id for x in res]

    def get_rec_name(self, name):
        res = self.name
        if self.implements:
            res += ' / ' + self.implements.rec_name
        return res

    def get_all_content(self, name):
        if self.type in ('base', 'header', 'footer'):
            return self.content
        elif self.type == 'extension':
            return '{%% extends "%s" %%} {# %s #}\n\n%s' % (self.parent.id,
                self.parent.name, self.content)
        elif self.type == 'macro':
            return '{%% macro %s %%}\n%s\n{%% endmacro %%}' % (
                self.implements.name, self.content)

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
            ], depends=['signature'])
    template_used = fields.Function(
        fields.Many2One('html.template', 'Template Used'), 'get_template_used')


    def get_template_used(self, name):
        Template = Pool().get('html.template')
        if self.template:
            return self.template.id
        templates = Template.search([('implements', '=', self.signature)])
        if templates:
            return templates[0].id
