from odoo import api, fields, models


class LogisticsTransitTrip(models.Model):
    _name = 'logistics.transit.trip'
    _description = 'Transit Trip'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'departure_date desc, id desc'

    name = fields.Char(
        string='Reference', required=True, copy=False,
        readonly=True, default='New',
    )
    plaka_no = fields.Char(string='Plaka No.', tracking=True)

    container_line_ids = fields.One2many(
        'logistics.container.line', 'transit_trip_id',
        string='Container Lines',
    )
    company_id = fields.Many2one(
        'res.company', string='Company', required=True,
        default=lambda self: self.env.company,
    )

    departure_date = fields.Date(string='Departure Date', tracking=True)
    arrival_date = fields.Date(string='Arrival Date', tracking=True)

    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('in_transit', 'In Transit'),
            ('delivered', 'Delivered'),
        ],
        string='Status', default='draft', required=True,
        copy=False, tracking=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'logistics.transit.trip') or 'New'
        return super().create(vals_list)

    def action_start(self):
        self.write({'state': 'in_transit'})

    def action_deliver(self):
        self.write({'state': 'delivered'})
        today = fields.Date.today()
        for rec in self:
            lines = rec.container_line_ids.filtered(lambda l: not l.wh_arriving_date)
            if lines:
                lines.write({'wh_arriving_date': today})
