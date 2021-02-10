from trytond.pool import PoolMeta
from trytond.modules.html_report.html import HTMLPartyInfoMixin


class Sale(HTMLPartyInfoMixin, metaclass=PoolMeta):
    __name__ = 'sale.sale'

    def get_html_address(self, name):
        return (self.invoice_address and self.invoice_address.id
            or super().get_html_address(name))

    def get_html_second_address(self, name):
        return (self.shipment_address and self.shipment_address.id
            or super().get_html_second_address(name))

    def get_html_second_address_label(self, name):
        return self.__name__, 'shipment_address'
