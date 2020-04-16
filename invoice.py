from trytond.model import fields
from trytond.pool import PoolMeta


class Invoice(metaclass=PoolMeta):
    __name__ = 'account.invoice'

    sorted_lines = fields.Function(fields.One2Many('account.invoice.line',
        'line', 'Sorted Lines'), 'get_sorted_lines')
    sorted_keys = fields.Function(fields.Char('Sorted Key'),
        'get_sorted_keys')

    def get_sorted_lines(self, name):
        lines = [x for x in self.lines]
        lines.sort(key=lambda k: k.sort_key, reverse=True)
        return [x.id for x in lines]

    def get_sorted_keys(self, name):
        lines = []
        for x in self.sorted_lines:
            if x.sort_key in lines:
                continue
            lines.append(x.sort_key)
        print("l:", lines)
        return lines


class InvoiceLine(metaclass=PoolMeta):
    __name__ = 'account.invoice.line'

    sort_key = fields.Function(fields.Char('Sorted Key'),
        'get_sorted_key')

    def get_sorted_key(self, name):
        key = []
        if self.origin and 'sale.line' in str(self.origin):
            sale = self.origin.sale
            if sale not in key:
                key.append(sale)

        if self.origin and 'purchase.line' in str(self.origin):
            purchase = self.origin.purchase
            if purchase in key:
                key.append(purchase)

        for move in self.stock_moves:
            shipment = move.shipment
            if shipment in key:
                continue
            key.append(shipment)

        return key
