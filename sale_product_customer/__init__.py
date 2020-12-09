# This file is part html_report module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from trytond.pool import Pool
from . import product

def register(module):
    Pool.register(
        product.ProductCustomer,
        module=module, type_='model', depends=['sale_product_customer'])
