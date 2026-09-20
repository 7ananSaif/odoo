from odoo import api, fields, models


class IotDevice(models.Model):
    _name = 'iot.device'
    _description = 'IOT Device'

    iot_id = fields.Many2one('iot.box', string='IoT Box', required=True, index=True, ondelete='cascade')
    name = fields.Char('Name')
    identifier = fields.Char(string='Identifier', readonly=True)
    type = fields.Selection([
            ('printer', 'Printer'),
            ('camera', 'Camera'),
            ('keyboard', 'Keyboard'),
            ('scanner', 'Barcode Scanner'),
            ('device', 'Device'),
            ('payment', 'Payment Terminal'),
            ('scale', 'Scale'),
            ('display', 'Display'),
            ('fiscal_data_module', 'Fiscal Data Module'),
            ('unsupported', 'Unsupported'),
        ],
        readonly=True,
        default='device',
        string='Type',
        help="Type of device.",
    )
    manufacturer = fields.Char(string='Manufacturer', readonly=True)
    connection = fields.Selection([
            ('network', 'Network'),
            ('direct', 'USB'),
            ('bluetooth', 'Bluetooth'),
            ('serial', 'Serial'),
            ('hdmi', 'HDMI'),
        ],
        readonly=True,
        string="Connection",
        help="Type of connection.",
    )
    report_ids = fields.Many2many('ir.actions.report', string='Reports')
    iot_ip = fields.Char(related="iot_id.ip")
    company_id = fields.Many2one('res.company', 'Company', related="iot_id.company_id")
    connected_status = fields.Selection([
            ('disconnected', 'Disconnected'),
            ('connected', 'Connected'),
        ],
        default='disconnected',
        readonly=True
    )
    keyboard_layout = fields.Many2one('iot.keyboard.layout', string='Keyboard Layout')
    display_url = fields.Char(
        'Display URL',
        help=(
            "URL of the page that will be displayed by the device, "
            "leave empty to use the customer facing display of the POS."
        )
    )
    manual_measurement = fields.Boolean(
        'Manual Measurement',
        compute="_compute_manual_measurement",
        help="Manually read the measurement from the device"
    )
    is_scanner = fields.Boolean(
        string='Is Scanner',
        compute="_compute_is_scanner",
        inverse="_set_scanner",
        help="Manually switch the device type between keyboard and scanner"
    )
    subtype = fields.Selection([
            ('receipt_printer', 'Receipt Printer'),
            ('label_printer', 'Label Printer'),
            ('office_printer', 'Office Printer'),
            ('', '')
        ],
        default='',
        help='Subtype of device.',
    )

    @api.depends('name', 'iot_id', 'connection')
    @api.depends_context('formatted_display_name')
    def _compute_display_name(self):
        connection_display_values = dict(self._fields['connection'].selection)
        for device in self:
            if device.env.context.get("formatted_display_name"):
                connection = connection_display_values.get(device.connection, device.connection) if device.connection else ''
                device.display_name = f"{device.name} \t --{connection}-- \t --{device.iot_id.name}--"
            else:
                device.display_name = f"{device.name}"

    @api.depends('type')
    def _compute_is_scanner(self):
        for device in self:
            device.is_scanner = device.type == 'scanner'

    def _set_scanner(self):
        for device in self:
            device.type = 'scanner' if device.is_scanner else 'keyboard'

    @api.depends('manufacturer')
    def _compute_manual_measurement(self):
        for device in self:
            device.manual_measurement = device.manufacturer == 'Adam'


class IotKeyboardLayout(models.Model):
    _name = 'iot.keyboard.layout'
    _description = 'Keyboard Layout'

    name = fields.Char('Name')
    layout = fields.Char('Layout')
    variant = fields.Char('Variant')
