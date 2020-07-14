# This file is part html_report module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
import unittest
import doctest
from trytond.tests.test_tryton import ModuleTestCase, with_transaction
from trytond.tests.test_tryton import suite as test_suite
from trytond.pool import Pool
from trytond.tools import file_open
from trytond.transaction import Transaction
from trytond.tests.test_tryton import doctest_setup, doctest_teardown

SCENARIOS = [
    'stock_dependency_scenario.rst',
    'account_invoice_dependency_scenario.rst',
    'sale_dependency_scenario.rst',
    'sale_discount_dependency_scenario.rst',
    'stock_valued_dependency_scenario.rst',
    'production_dependency_scenario.rst',
    'account_payment_type_dependency_scenario.rst',
    'account_bank_dependency_scenario.rst',
    'stock_valued_carrier_dependency_scenario.rst',
    'stock_carrier_dependency_scenario.rst',
    'purchase_dependency_scenario.rst',
]

class HtmlReportTestCase(ModuleTestCase):
    'Test Html Report module'
    module = 'html_report'

    @with_transaction()
    def test_html_report(self):
        'Create HTML Report'
        pool = Pool()
        ActionReport = pool.get('ir.action.report')
        Template = pool.get('html.template')
        HTMLTemplateTranslation = pool.get('html.template.translation')
        Model = pool.get('ir.model')

        model, = Model.search([('model', '=', 'ir.model')], limit=1)

        with file_open('html_report/tests/base.html') as f:
            tpl_base, = Template.create([{
                        'name': 'Base',
                        'type': 'base',
                        'content': f.read(),
                        }])

        with file_open('html_report/tests/models.html') as f:
            tpl_models, = Template.create([{
                        'name': 'Modules',
                        'type': 'extension',
                        'content': f.read(),
                        'parent': tpl_base,
                        }])

        report, = ActionReport.create([{
            'name': 'Models',
            'model': 'ir.model',
            'report_name': 'ir.model.report',
            'template_extension': 'jinja',
            'extension': 'html',
            'html_template': tpl_models,
            }])

        models = Model.search([('model', 'like', 'ir.model%')])

        self.assertTrue(report.id)
        self.assertTrue('block body' in report.html_content, True)

        HTMLTemplateTranslation.create([{
                'lang': 'es',
                'src': 'Name',
                'value': 'Nombre',
                'report': report.id,
                }, {
                'lang': 'es',
                'src': 'Model',
                'value': 'Modelo',
                'report': report.id,
                }])

        with Transaction().set_context(language='es'):
            ModelReport = Pool().get('ir.model.report', type='report')
            ext, content, _, _ = ModelReport.execute([m.id for m in models], {})
            self.assertTrue(ext, 'html')
            self.assertTrue('ir.model' in content, True)
            self.assertTrue('Nombre' in content, True)
            self.assertTrue('Modelo' in content, True)

def suite():
    suite = test_suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
            HtmlReportTestCase))
    for scenario in SCENARIOS:
        suite.addTests(doctest.DocFileSuite(scenario, setUp=doctest_setup,
            tearDown=doctest_teardown, encoding='utf-8',
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    return suite
