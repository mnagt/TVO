from odoo import api, fields, models


class LogisticsDashboard(models.AbstractModel):
    _name = 'logistics.dashboard'
    _description = 'Logistics Dashboard'

    @api.model
    def get_dashboard_data(self):
        today = fields.Date.today()
        BL = self.env['logistics.bill.lading']
        Container = self.env['logistics.container']
        Req = self.env['purchase.requisition']

        deals_by_state = {
            state: Req.search_count([('logistics_state', '=', state)])
            for state in ('purchasing', 'oversea', 'at_port', 'arrived', 'completed')
        }

        upcoming = BL.search([
            ('state', 'in', ['shipped', 'in_transit']),
            ('arrival_date', '!=', False),
        ], order='arrival_date asc', limit=10)

        return {
            'kpis': {
                'deals_purchasing': deals_by_state['purchasing'],
                'deals_oversea': deals_by_state['oversea'],
                'deals_at_port': deals_by_state['at_port'],
                'deals_arrived': deals_by_state['arrived'],
                'deals_completed': deals_by_state['completed'],
                'containers_in_transit': Container.search_count(
                    [('state', 'in', ['shipped', 'in_transit'])]
                ),
                'overdue_arrivals': BL.search_count([
                    ('arrival_date', '<', today),
                    ('state', 'in', ['shipped', 'in_transit']),
                ]),
            },
            'upcoming_arrivals': upcoming.read(
                ['name', 'number', 'vessel', 'arrival_date',
                 'container_count', 'forwarder_id', 'port_of_discharge_id']
            ),
        }
