# This file is part html_report module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
try:
    from trytond.modules.html_report.tests.test_html_report import suite
except ImportError:
    from .test_html_report import suite

__all__ = ['suite']
