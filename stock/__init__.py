from trytond.pool import Pool
from . import stock

def register(module):
    Pool.register(
        stock.ShipmentOut,
        stock.ShipmentOutReturn,
        stock.ShipmentInReturn,
        stock.Move,
        module=module, type_='model', depends=['stock'])
