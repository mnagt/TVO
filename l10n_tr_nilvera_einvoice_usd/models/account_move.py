
import logging
from odoo import _, models
from odoo.exceptions import UserError
from odoo.addons.l10n_tr_nilvera.lib.nilvera_client import _get_nilvera_client

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _name = 'account.move'
    _inherit = 'account.move'


    def _l10n_tr_nilvera_submit_document(self, xml_file, endpoint, post_series=True):
        with _get_nilvera_client(self.env.company) as client:
            xml_content = xml_file.read()
            xml_file.seek(0)
            
            # Log REQUEST
            _logger.info(f"=== NILVERA REQUEST ===")
            _logger.info(f"Endpoint: {endpoint}")
            _logger.info(f"File: {xml_file.name}")
            # _logger.info(f"XML:\n{xml_content.decode('utf-8')}")  # Changed to .info
            
            response = client.request(
                "POST",
                endpoint,
                files={'file': (xml_file.name, xml_file, 'application/xml')},
                handle_response=False,
            )
            
            # Log RESPONSE
            _logger.info(f"=== NILVERA RESPONSE ===")
            _logger.info(f"Status: {response.status_code}")
            _logger.info(f"Headers: {dict(response.headers)}")
            _logger.info(f"Body: {response.text}")
            _logger.info(f"======================")

            if response.status_code == 200:
                self.is_move_sent = True
                self.l10n_tr_nilvera_send_status = 'sent'
                self.message_post(body=_("Invoice sent successfully."))
                
            elif response.status_code == 409:
                error_message, error_codes = self._l10n_tr_nilvera_einvoice_get_error_messages_from_response(response)
                
                if 1001 in error_codes:
                    _logger.warning(f"Invoice already in system (ETTN exists): {error_message}")
                    self.is_move_sent = True
                    self.l10n_tr_nilvera_send_status = 'sent'
                    self.message_post(body=_("Invoice already submitted."))
                    return
                else:
                    raise UserError(error_message)
                    
            elif response.status_code in {401, 403}:
                raise UserError(_("Oops, seems like you're unauthorised to do this. Try another API key with more rights or contact Nilvera."))
                
            elif 400 <= response.status_code < 500:
                error_message, error_codes = self._l10n_tr_nilvera_einvoice_get_error_messages_from_response(response)
                _logger.error(f"Error codes: {error_codes}")
                
                if 3009 in error_codes and post_series:
                    self._l10n_tr_nilvera_post_series(endpoint, client)
                    return self._l10n_tr_nilvera_submit_document(xml_file, endpoint, post_series=False)
                raise UserError(error_message)
                
            elif response.status_code == 500:
                raise UserError(_("Server error from Nilvera, please try again later."))
    
            self.message_post(body=_("The invoice has been successfully sent to Nilvera."))

    def button_draft(self):
        super().button_draft

