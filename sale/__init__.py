from trytond.pool import Pool
from . import sale

def register(module):
    Pool.register(
        sale.Sale,
        module=module, type_='model', depends=['sale'])
