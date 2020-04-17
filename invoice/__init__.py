from trytond.pool import Pool
from . import invoice


def register(module):
    Pool.register(
        invoice.Invoice,
        module=module, type_='model', depends=['account_invoice'])
