from trytond.pool import Pool


def register(module):
    Pool.register(
        module=module, type_='model', depends=['sale'])
