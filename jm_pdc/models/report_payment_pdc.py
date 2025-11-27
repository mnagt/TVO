from odoo import models, fields

class PaymentPDC(models.Model):
    _name = 'report.payment.pdc'
    _description = 'Payment PDC'

    name = fields.Char(string='Payment Reference', required=True)
    amount = fields.Float(string='Amount')
    due_date = fields.Date(string='Due Date')
    partner_id = fields.Many2one('res.partner', string='Partner')
    status = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('done', 'Done'),
    ], string='Status', default='draft')