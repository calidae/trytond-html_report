from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from trytond.rpc import RPC
from trytond.modules.html_report.html import HTMLPartyInfoMixin
from trytond.modules.html_report.html_report import HTMLReport


class Invoice(HTMLPartyInfoMixin, metaclass=PoolMeta):
    __name__ = 'account.invoice'
    sorted_keys = fields.Function(fields.Char('Sorted Key'),
        'get_sorted_keys')

    def get_sorted_keys(self, name):
        lines = []
        for x in self.lines:
            if x.sort_key in lines:
                continue
            lines.append(x.sort_key)
        return lines

    def get_html_address(self, name):
        return (self.invoice_address and self.invoice_address.id
            or super().get_html_address(name))


class InvoiceLine(metaclass=PoolMeta):
    __name__ = 'account.invoice.line'
    sort_key = fields.Function(fields.Char('Sorted Key'),
        'get_sorted_key')

    def get_sorted_key(self, name):
        key = []
        if hasattr(self, 'stock_moves'):
            for move in self.stock_moves:
                shipment = move.shipment
                if shipment in key:
                    continue
                key.append(shipment)
        if self.origin and 'sale.line' in str(self.origin):
            sale = self.origin.sale
            if sale not in key:
                key.append(sale)

        if self.origin and 'purchase.line' in str(self.origin):
            purchase = self.origin.purchase
            if purchase not in key:
                key.append(purchase)

        return key


class InvoiceReport(HTMLReport):
    __name__ = 'account.invoice'

    @classmethod
    def __setup__(cls):
        super(InvoiceReport, cls).__setup__()
        cls.__rpc__['execute'] = RPC(False)

    @classmethod
    def execute(cls, ids, data):
        pool = Pool()
        Invoice = pool.get('account.invoice')

        if len(ids) == 1:
            # Re-instantiate because records are TranslateModel
            invoice, = Invoice.browse(ids)
            if invoice.invoice_report_cache:
                return (
                    invoice.invoice_report_format,
                    bytes(invoice.invoice_report_cache))

        result = super(InvoiceReport, cls).execute(ids, data)

        if (len(ids) == 1 and invoice.state in {'posted', 'paid'}
                and invoice.type == 'out'):
            format_, data = result[0], result[1]
            invoice.invoice_report_format = format_
            invoice.invoice_report_cache = \
                Invoice.invoice_report_cache.cast(data)
            invoice.save()

        return result
