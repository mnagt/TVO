import base64
import json
import logging
from io import BytesIO

import requests
from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    l10n_tr_nilvera_send_status = fields.Selection([
        ('draft', 'Draft'),
        ('sending', 'Sending'),
        ('sent', 'Sent'),
        ('error', 'Error'),
    ], string='Nilvera Send Status', default='draft', tracking=True)

    l10n_tr_nilvera_response = fields.Text('Nilvera Response', readonly=True)
    l10n_tr_nilvera_response_uuid = fields.Char('Nilvera Response UUID', readonly=True)
    l10n_tr_nilvera_ettn = fields.Char('ETTN', readonly=True)

    def action_send_to_nilvera(self):
        """Send e-Dispatch XML to Nilvera"""
        for picking in self:
            if picking.country_code != 'TR' or picking.picking_type_code != 'outgoing':
                continue

            if picking.l10n_tr_nilvera_dispatch_state != 'to_send':
                if len(self) == 1:
                    raise UserError(_('This dispatch is not ready to send.'))
                continue

            # Validate fields before sending
            if picking._l10n_tr_validate_edispatch_fields():
                if len(self) == 1:
                    raise UserError(_('Please fix the validation errors before sending.'))
                continue

            # Get or generate XML attachment
            attachment = self.env['ir.attachment'].search([
                ('res_model', '=', picking._name),
                ('res_id', '=', picking.id),
                ('name', 'like', '_e_Dispatch.xml')
            ], limit=1, order='id desc')

            if not attachment:
                # Generate XML if not exists
                picking._l10n_tr_generate_edispatch_xml()
                attachment = self.env['ir.attachment'].search([
                    ('res_model', '=', picking._name),
                    ('res_id', '=', picking.id),
                    ('name', 'like', '_e_Dispatch.xml')
                ], limit=1)

            if not attachment:
                if len(self) == 1:
                    raise UserError(_('Failed to generate e-Dispatch XML.'))
                continue

            try:
                picking.l10n_tr_nilvera_send_status = 'sending'
                picking.with_context(no_new_invoice=True).message_post(
                    body=_("Sending e-Dispatch to Nilvera...")
                )

                result = picking._send_xml_to_nilvera(attachment)

                if result.get('success'):
                    picking.write({
                        'l10n_tr_nilvera_send_status': 'sent',
                        'l10n_tr_nilvera_dispatch_state': 'sent',
                        'l10n_tr_nilvera_response_uuid': result.get('uuid'),
                        'l10n_tr_nilvera_ettn': result.get('ettn'),
                        'l10n_tr_nilvera_response': json.dumps(result, indent=2),
                    })
                    picking.with_context(no_new_invoice=True).message_post(
                        body=_("e-Dispatch successfully sent to Nilvera. UUID: %s, ETTN: %s") % (
                            result.get('uuid'), result.get('ettn')
                        )
                    )
                else:
                    error_msg = result.get('error', 'Unknown error')
                    picking.write({
                        'l10n_tr_nilvera_send_status': 'error',
                        'l10n_tr_nilvera_response': json.dumps(result, indent=2),
                    })
                    picking.with_context(no_new_invoice=True).message_post(
                        body=_("Error sending e-Dispatch to Nilvera: %s") % error_msg
                    )
                    if len(self) == 1:
                        raise UserError(_("Error sending to Nilvera: %s") % error_msg)

            except Exception as e:
                error_msg = str(e)
                picking.write({
                    'l10n_tr_nilvera_send_status': 'error',
                    'l10n_tr_nilvera_response': error_msg,
                })
                _logger.error("Error sending picking %s to Nilvera: %s", picking.name, error_msg)
                if len(self) == 1:
                    raise UserError(_("Error sending to Nilvera: %s") % error_msg)

    def _get_nilvera_base_url(self):
        if self.company_id.l10n_tr_nilvera_environment == 'sandbox':
            return "https://apitest.nilvera.com"
        else:
            return "https://api.nilvera.com"

    def _send_xml_to_nilvera(self, attachment):
        """Send XML to Nilvera API"""
        self.ensure_one()

        # Get company's API key
        api_key = self.company_id.l10n_tr_nilvera_api_key
        if not api_key:
            raise UserError(_('Nilvera API key not configured for company %s.') % self.company_id.name)

        base_url = self._get_nilvera_base_url()

        xml_content = base64.b64decode(attachment.datas)

        files = {
            'file': ('dispatch.xml', BytesIO(xml_content), 'text/xml')
        }

        headers = {
            'Authorization': f'Bearer {api_key}',
        }

        params = {}

        is_einvoice = getattr(self.partner_id, 'l10n_tr_nilvera_customer_status', None) == 'einvoice'

        if not is_einvoice:
            params['vat'] = '3900892152'
            params['Alias'] = 'urn:mail:irsaliyepk@gib.gov.tr'
        else:
            if self.partner_id.l10n_tr_nilvera_despatch_alias_id:
                if self.partner_id.l10n_tr_nilvera_despatch_alias_id:
                    params['Alias'] = self.partner_id.l10n_tr_nilvera_despatch_alias_id.name
                else:
                    params['Alias'] = 'urn:mail:irsaliyepk@gib.gov.tr'
            else:
                params['Alias'] = 'urn:mail:irsaliyepk@gib.gov.tr'

        try:
            response = requests.post(
                f"{base_url}/edespatch/Send/Xml",
                headers=headers,
                files=files,
                params=params,
                timeout=60
            )

            response_data = {}
            try:
                response_data = response.json()
            except:
                response_data = {'response_text': response.text}

            if response.status_code in [200, 201]:
                # Success
                return {
                    'success': True,
                    'uuid': response_data.get('UUID'),
                    'ettn': response_data.get('DespatchNumber'),
                    'status_code': response.status_code,
                    'response': response_data
                }
            else:
                # Error
                error_message = response_data.get('error', {}).get('message', response.text)
                return {
                    'success': False,
                    'error': error_message,
                    'status_code': response.status_code,
                    'response': response_data
                }

        except requests.exceptions.RequestException as e:
            _logger.error("Request error: %s", str(e))
            return {
                'success': False,
                'error': f"Connection error: {str(e)}"
            }
        except Exception as e:
            _logger.error("Unexpected error: %s", str(e))
            return {
                'success': False,
                'error': f"Unexpected error: {str(e)}"
            }

    def action_retry_nilvera_send(self):
        """Retry sending failed dispatches"""
        failed_pickings = self.filtered(
            lambda p: p.l10n_tr_nilvera_send_status == 'error' and p.l10n_tr_nilvera_dispatch_state == 'to_send'
        )
        if failed_pickings:
            failed_pickings.action_send_to_nilvera()



    @api.model
    def _cron_send_pending_edispatch(self):
        """Cron job to send pending e-Dispatch files"""
        # Find pending pickings
        pending_pickings = self.search([
            ('country_code', '=', 'TR'),
            ('picking_type_code', '=', 'outgoing'),
            ('state', '=', 'done'),
            ('l10n_tr_nilvera_dispatch_state', '=', 'to_send'),
            ('l10n_tr_nilvera_send_status', 'in', ['draft', 'error']),
        ], limit=50)  # Process 50 at a time

        for picking in pending_pickings:
            try:
                picking.with_context(is_cron=True).action_send_to_nilvera()
                self.env.cr.commit()  # Commit after each successful send
            except Exception as e:
                self.env.cr.rollback()  # Rollback on error
                _logger.error("Failed to send picking %s via cron: %s", picking.name, str(e))