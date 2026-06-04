from odoo import fields, models


class LogisticsPreNotification(models.Model):
    _name = 'logistics.pre.notification'
    _description = 'Pre-Notification'
    _order = 'id desc'

    importer_id = fields.Many2one('res.partner', string='Importer')
    exporter_id = fields.Many2one('res.partner', string='Exporter')
    manufacturer_id = fields.Many2one('res.partner', string='Manufacturer')
    product_name = fields.Char(string='Product Name')
    notification_code = fields.Char(string='Notification Code')
    product_ids = fields.Many2many('product.product', string='Products')
