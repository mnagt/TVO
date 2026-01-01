from odoo import api, models, fields, _
import base64
import requests


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def _get_nilvera_base_url(self):
        """Company environment'a göre Nilvera base URL döndür"""
        if self.company_id.l10n_tr_nilvera_environment == 'sandbox':
            return "https://apitest.nilvera.com"
        else:
            return "https://api.nilvera.com"

    def _get_dispatch_endpoint(self):
        """Fatura tipine göre doğru endpoint'i döndürür"""
        return "/edespatch/Sale/"

    def _get_despatch_pdf_data(self):
        """E-Invoice PDF verisini Nilvera API'den çeker"""
        if not self.sudo().l10n_tr_nilvera_response_uuid:
            return False, _("No Nilvera UUID found. Cannot download PDF.")

        api_key = self.sudo().company_id.l10n_tr_nilvera_api_key
        if not api_key:
            return False, _("No Nilvera API key configured in the company settings.")

        # Doğru endpoint'i belirle
        endpoint = self._get_dispatch_endpoint()

        try:
            response = requests.get(
                f"{self._get_nilvera_base_url()}/{endpoint}/{self.l10n_tr_nilvera_response_uuid}/pdf",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Accept": "*/*"
                },
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                return data, None
            elif response.status_code == 401:
                return False, _("Unauthorized: Check your Nilvera API key in company settings.")
            else:
                return False, _("Failed to download E-Invoice PDF from Nilvera. Status code: %s") % response.status_code

        except requests.exceptions.RequestException as e:
            return False, _("Network error while downloading PDF: %s") % str(e)

    def action_download_despatch_pdf(self):
        """PDF'i indirir ve attachment olarak ekler + dosya indirir"""
        pdf_data, error_msg = self._get_despatch_pdf_data()

        if not pdf_data:
            self.message_post(
                body=error_msg,
                subtype_xmlid='mail.mt_note'
            )
            return

        # Fatura tipine göre dosya adını belirle
        filename = f"Eirsaliye-{self.name}.pdf"

        # Attachment oluştur
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'type': 'binary',
            'datas': pdf_data,
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': 'application/pdf',
        })

        # Mesaj ekle
        self.message_post(
            body=_("%s PDF downloaded and attached from Nilvera.") % "E-Dispatch",
            attachment_ids=[attachment.id]
        )

        # Dosyayı indirmek için action return et
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }

