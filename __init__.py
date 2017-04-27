# This file is part html_report module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from trytond.pool import Pool
from . import company


def register():
    Pool.register(
        company.Company,
        module='html_report', type_='model')
    # Pool.register(
    #     module='html_report', type_='wizard')
    # Pool.register(
    #     module='html_report', type_='report')
