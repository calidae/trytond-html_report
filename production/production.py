from trytond.model import fields
from trytond.pool import PoolMeta


class Production(metaclass=PoolMeta):
    __name__ = 'production'

    show_lots = fields.Function(fields.Boolean('Production'),
        'get_show_lots')

    def get_show_lots(self, name):
        for move in self.inputs:
            if getattr(move, 'lot'):
                return True
        return False
