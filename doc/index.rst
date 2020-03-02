Html Report Module
##################

Design your reports with HTML and Jinja2 template engine and create PDF documents
with WeasyPrint.

Sintax to use
-------------

- render: Render value with eval the type.

  {{ party.render.name }}

- raw: render value that is not eval the type.

   {{ party.raw.name}}

Filters
-------

The params of render filter are "digits", "lang" or "filename"

   {{ (line.raw.debit - line.raw.credit) | render(digits=line.raw.currency_digits) }}

Example HTML report
-------------------

.. code-block:: html

    {% extends 'html_report/report/base.html' %}
    {% block main %}
      {% for party in records %}
        {{ party.render.name }}
      {% endfor %}
    {% endblock %}

In case is single report:

.. code-block:: html

    {% extends 'html_report/report/base.html' %}
    {% block main %}
      {{ record.render.name }}
    {% endblock %}

Create XML report
-----------------

.. code-block:: xml

    <record model="ir.action.report" id="report_custom">
        <field name="name">Custom</field>
        <field name="model">custom</field>
        <field name="report_name">custom</field>
        <field name="report">my_module/report/custom.html</field>
        <field name="extension">pdf</field>
        <field name="template_extension">jinja</field>
        <field name="single" eval="True"/>
    </record>

Register your HTMLReport class
------------------------------

It is not necessary to register the class because trytond loads all classes when it is a report.

In case you need to register the class and calculate values, you could do:

.. code-block:: python

    from trytond.report import Report

    class CustomHTMLReport(Report):
        __name__ = 'custom.report.html_report'

        @classmethod
        def __setup__(cls):
            super(CustomHTMLReport, cls).__setup__()
            cls.__rpc__['execute'] = RPC(False)

    @classmethod
    def execute(cls, ids, data):
        return super(CustomHTMLReport, cls).execute(data['records'], {
                'name': 'custom.report.html_report',
                'model': data['model_name'],
                'report_name': report.rec_name,
                'records': records,
                'output_format': 'pdf',
                ...
                })
