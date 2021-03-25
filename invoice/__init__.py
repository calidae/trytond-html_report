from trytond.pool import Pool
from . import invoice


def register(module):
    Pool.register(
        invoice.Invoice,
        invoice.InvoiceLine,
        module=module, type_='model', depends=['account_invoice'])
    Pool.register(
        invoice.InvoiceReport,
        module=module, type_='report', depends=['account_invoice'])
