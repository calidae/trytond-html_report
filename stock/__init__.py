from trytond.pool import Pool
from . import stock

def register(module):
    Pool.register(
        stock.ShipmnentOut,
        stock.ShipmnentOutReturn,
        stock.ShipmnentInReturn,
        stock.Move,
        module=module, type_='model', depends=['stock'])
