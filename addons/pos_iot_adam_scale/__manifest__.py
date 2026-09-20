{
    'name': 'PoS IoT Adam Equipment Scales',
    'category': 'Point of Sale',
    'summary': 'Adds an IoT driver for Adam Equipment Scales',
    'description': """
This module adds support to the IoT box for Adam Equipment electronic scales
connected via serial. This driver is not installed on the IoT box by default
due to conflicts with other serial devices - only install it if you need it.
    """,
    'author': "Odoo S.A.",
    'license': "OEEL-1",
    'depends': ['pos_iot'],
}
