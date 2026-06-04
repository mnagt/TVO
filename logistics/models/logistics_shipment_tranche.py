from odoo import fields, models


class LogisticsShipmentTranche(models.Model):
    _name = 'logistics.shipment.tranche'
    _description = 'Shipment Tranche'
    _order = 'sequence, date'

    requisition_line_id = fields.Many2one(
        'purchase.requisition.line', string='Requisition Line',
        required=True, ondelete='cascade',
    )
    sequence = fields.Integer(string='Sequence', default=10)
    quantity = fields.Float(
        string='Quantity', digits='Product Unit of Measure',
    )
    date = fields.Date(string='Shipment Date')
    invoice_no = fields.Char(string='Invoice No.')
