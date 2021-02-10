from trytond.pool import PoolMeta
from trytond.modules.html_report.html import HTMLPartyInfoMixin


class Purchase(HTMLPartyInfoMixin, metaclass=PoolMeta):
    __name__ = 'purchase.purchase'

    def get_html_address(self, name):
        return (self.invoice_address and self.invoice_address.id
            or super().get_html_address(name))
