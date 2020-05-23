from trytond.pool import Pool
from . import stock

def register(module):
    Pool.register(
        stock.ShipmnentOut,
        stock.Move,
        module=module, type_='model', depends=['stock'])
