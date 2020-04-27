from trytond.model import fields
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction

class ShipmnentOut(metaclass=PoolMeta):
    __name__ = 'stock.shipment.out'

    sorted_lines = fields.Function(fields.One2Many('account.invoice.line',
        'line', 'Sorted Lines'), 'get_sorted_lines')
    sorted_keys = fields.Function(fields.Char('Sorted Key'),
        'get_sorted_keys')

    def get_sorted_lines(self, name):
        lines = [x for x in self.inventory_moves]
        return lines
        with Transaction().set_context(_check_access=False):
            lines.sort(key=lambda k: k.sort_key, reverse=True)
        return [x.id for x in lines]

    def get_sorted_keys(self, name):
        keys = []
        return keys
        with Transaction().set_context(_check_access=False):
            for x in self.sorted_lines:
                if x.sort_key in keys:
                    continue
                keys.append(x.sort_key)
        return keys


class Move(metaclass=PoolMeta):
    __name__ = 'stock.move'

    sort_key = fields.Function(fields.Char('Sorted Key'),
        'get_sorted_key')


    def get_sorted_key(self, name):
        pool = Pool()
        ShipmentOut = pool.get('stock.shipment.out')
        ShipmentIn = pool.get('stock.shipment.in')

        key = []
        if self.shipment and isinstance(self.shipment, ShipmentOut) :
            if self.origin and self.origin.origin:
                sale = self.origin.origin.sale
                if sale not in key:
                    key.append(sale)

        elif self.shipment_in and isinstance(self.shipment, ShipmentIn):
            if self.origin and 'purchase.line' in str(self.origin):
                purchase = self.origin.purchase
                if purchase in key:
                    key.append(purchase)

        return key
