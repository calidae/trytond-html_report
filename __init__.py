# This file is part html_report module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from trytond.pool import Pool
from . import action
from . import translation
from . import html


def register():
    Pool.register(
        action.ActionReport,
        html.ActionKeyword,
        html.Signature,
        html.Template,
        html.TemplateUsage,
        html.Report,
        html.ReportTemplate,
        module='html_report', type_='model')
    Pool.register(
        translation.ReportTranslationSet,
        module='html_report', type_='wizard')
    Pool.register(
        html.HTMLReport,
        module='html_report', type_='report')
