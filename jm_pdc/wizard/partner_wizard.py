from odoo import api, fields, models
from odoo.exceptions import UserError

class PartnerWizard(models.TransientModel):
    _name = "partner.wizard"
    _description = "Wizard for Showing Partners from pdc.wizard model"

    from_date = fields.Date(string='From Date')
    to_date = fields.Date(string='To Date')
    partner_ids = fields.Many2many("res.partner", string="Partners", domain="[('id', 'in', allowed_partner_ids)]")
    allowed_partner_ids = fields.Many2many("res.partner", compute="_compute_allowed_partners")
    selected_state = fields.Selection([('draft', 'Draft'), ('registered', 'Registered'), ('returned', 'Returned'),
                                      ('deposited', 'Deposited'), ('bounced', 'Bounced'), ('done', 'Done'), ('cancel', 'Cancelled')], string="State")

    @api.depends('partner_ids')
    def _compute_allowed_partners(self):
        pdc_wizard_records = self.env['pdc.wizard'].search([])
        self.allowed_partner_ids = [(6, 0, [record.partner_id.id for record in pdc_wizard_records if record.partner_id])]

    @api.depends('partner_ids')
    def _compute_allowed_partners(self):
        pdc_wizard_records = self.env['pdc.wizard'].search([])
        self.allowed_partner_ids = [
            (6, 0, [record.partner_id.id for record in pdc_wizard_records if record.partner_id])]

    def button_print_report(self):
        self.ensure_one()

        domain = []

        if self.partner_ids:
            domain.append(('partner_id', 'in', self.partner_ids.ids))

        if self.selected_state:
            domain.append(('state', '=', self.selected_state))

        if self.from_date and self.to_date:
            domain.append(('due_date', '>=', self.from_date))
            domain.append(('due_date', '<=', self.to_date))

        pdc_wizard_records = self.env['pdc.wizard'].search(domain)

        # Check if records exist, if not raise UserError
        if not pdc_wizard_records:
            raise UserError("No record found.")

        return self.env.ref('jm_pdc.pdc_wizard').report_action(pdc_wizard_records.ids)


class PDCWizardReport(models.AbstractModel):
    _name = 'report.jm_pdc.report_pdc_payment'

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['pdc.wizard'].browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'pdc.wizard',
            'docs': docs,
        }
