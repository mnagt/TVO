from odoo import fields, models


class ProductRegistration(models.Model):
    _name = 'product.registration'
    _description = 'Product Registration'
    _order = 'product_tmpl_id, country_id'

    product_tmpl_id = fields.Many2one(
        'product.template', string='Product', required=True,
    )
    country_id = fields.Many2one(
        'res.country', string='Country', required=True,
    )
    status = fields.Selection(
        selection=[
            ('registered', 'Registered'),
            ('pending', 'Pending'),
            ('to_be_registered', 'To Be Registered'),
            ('not_registered', 'Not Registered'),
        ],
        string='Status', default='not_registered',
    )
    registration_file = fields.Char(string='Registration File URL')
    registration_date = fields.Date(string='Registration Date')
    market_ids = fields.Many2many('res.country', string='Target Markets')
