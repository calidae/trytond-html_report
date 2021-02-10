from trytond.model import fields
from trytond.pool import PoolMeta
from trytond.modules.html_report.html import HTMLPartyInfoMixin


class Production(HTMLPartyInfoMixin, metaclass=PoolMeta):
    __name__ = 'production'

    show_lots = fields.Function(fields.Boolean('Production'),
        'get_show_lots')

    def get_show_lots(self, name):
        for move in self.inputs:
            if getattr(move, 'lot'):
                return True
        return False

    def get_html_party(self, name):
        return
