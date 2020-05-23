from trytond.model import fields
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction

class Production(metaclass=PoolMeta):
    __name__ = 'production'

    show_lots = fields.Function(fields.Boolean('Production'),
        'get_show_lots')

    def get_show_lots(self, name):
        show = False
        for move in self.inputs:
            if getattr(move, 'lot'):
                return True
        return False
