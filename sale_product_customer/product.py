# This file is part html_report module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from trytond.model import fields
from trytond.pool import PoolMeta


class ProductCustomer(metaclass=PoolMeta):
    __name__ = 'sale.product_customer'
    notes = fields.One2Many('ir.note', 'resource', 'Notes')
