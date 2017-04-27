# This file is part html_report module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.model import fields

__all__ = ['Company']


class Company:
    __name__ = 'company.company'
    __metaclass__ = PoolMeta
    header_html = fields.Text('Header Html')
    footer_html = fields.Text('Footer Html')
