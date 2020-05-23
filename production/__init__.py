from trytond.pool import Pool
from . import production

def register(module):
    Pool.register(
        production.Production,
        module=module, type_='model', depends=['production'])
