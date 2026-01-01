from odoo import api, models, fields, _
import base64
import requests


class AccountMove(models.Model):
    _inherit = 'account.move'



    e_invoice_mail_send = fields.Boolean(string="E-Fatura PDF Mail Gönderildi", default=False)

    def _get_nilvera_base_url(self):
        """Company environment'a göre Nilvera base URL döndür"""
        if self.company_id.l10n_tr_nilvera_environment == 'sandbox':
            return "https://apitest.nilvera.com"
        else:
            return "https://api.nilvera.com"

    def _is_earchive_invoice(self):
        """Faturanın e-arşiv olup olmadığını kontrol eder"""
        if not self.partner_id:
            return True

        customer_status = self.partner_id.l10n_tr_nilvera_customer_status


        if customer_status == 'einvoice':
            return False  # E-fatura
        else:
            return True  # E-arşiv

    def _get_einvoice_endpoint(self):
        """Fatura tipine göre doğru endpoint'i döndürür"""
        if self._is_earchive_invoice():
            return "earchive/Invoices"
        else:
            return "einvoice/Sale"

    def _get_einvoice_pdf_data(self):
        """E-Invoice PDF verisini Nilvera API'den çeker ve base64 olarak döndürür.

        Returns:
            (datas_base64, None) on success
            (False, error_message) on failure
        """
        if not self.sudo().l10n_tr_nilvera_uuid:
            return False, _("No Nilvera UUID found. Cannot download PDF.")

        api_key = self.sudo().company_id.l10n_tr_nilvera_api_key
        if not api_key:
            return False, _("No Nilvera API key configured in the company settings.")

        # Doğru endpoint'i belirle
        endpoint = self._get_einvoice_endpoint()

        try:
            response = requests.get(
                f"{self._get_nilvera_base_url()}/{endpoint}/{self.l10n_tr_nilvera_uuid}/pdf",
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

    def action_download_einvoice_pdf(self):
        """PDF'i indirir ve attachment olarak ekler + dosya indirir"""
        pdf_data, error_msg = self._get_einvoice_pdf_data()

        if not pdf_data:
            self.message_post(
                body=error_msg,
                subtype_xmlid='mail.mt_note'
            )
            return

        # Fatura tipine göre dosya adını belirle
        invoice_type = "E-Archive" if self._is_earchive_invoice() else "E-Invoice"
        filename = f"{invoice_type}-{self.name}.pdf"

        # Attachment oluştur (invoice'a bağlı)
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
            body=_('%s PDF downloaded and attached from Nilvera.') % invoice_type,
            attachment_ids=[attachment.id]
        )

        # Dosyayı indirmek için action return et
        # return {
        #     'type': 'ir.actions.act_url',
        #     'url': f'/web/content/{attachment.id}?download=true',
        #     'target': 'self',
        # }

    def action_send_einvoice_pdf_email(self):
        """E-Invoice PDF'ini email ile gönderir (tek invoice -> composer açar)"""
        pdf_data, error_msg = self._get_einvoice_pdf_data()

        if not pdf_data:
            self.message_post(
                body=error_msg,
                subtype_xmlid='mail.mt_note'
            )
            return

        # Fatura tipine göre dosya adını belirle
        invoice_type = "E-Archive" if self._is_earchive_invoice() else "E-Invoice"
        filename = f"{invoice_type}-{self.name}.pdf"
        self.e_invoice_mail_send=True
        # Attachment oluştur (fatura kaydına bağla)
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'type': 'binary',
            'datas': pdf_data,
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': 'application/pdf',
        })

        # Mail composer wizard'ı aç
        compose_form = self.env.ref('mail.email_compose_message_wizard_form', False)

        # Default değerler
        default_subject = _("E-Fatura PDF - %s") % self.name
        default_body = _("""
Merhaba , \n
İlgili %s faturasını ekte bulabilirsiniz. \n

Saygılarımla, \n
%s
        """) % (self.name, self.company_id.name)

        ctx = {
            'default_model': 'account.move',
            'default_res_ids': [self.id],
            'default_use_template': False,
            'default_composition_mode': 'comment',
            'default_subject': default_subject,
            'default_body': default_body,
            'default_attachment_ids': [(6, 0, [attachment.id])],
            'force_email': True,
        }

        return {
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'mail.compose.message',
            'views': [(compose_form.id, 'form')],
            'view_id': compose_form.id,
            'target': 'new',
            'context': ctx,
        }

    def action_send_einvoice_pdf_bulk(self):
        """Her fatura için farklı e-posta adresine gönderim.

        Kullanım:
        - Context içinde 'email_map' adında dict sağlayın: {invoice_id: 'email@example.com', ...}
        - veya context içinde 'emails' listesi verin; seçili faturalarla aynı sırada olmalıdır.

        Eğer mapping verilmezse, varsayılan olarak invoice.partner_id.email kullanılır.
        """
        Email = self.env['mail.mail']
        Attachment = self.env['ir.attachment']

        # email_map: {invoice_id: email}
        email_map = self.env.context.get('email_map') or {}
        emails_list = self.env.context.get('emails') or None

        records = self
        pairs = []

        if emails_list:
            # emails_list should have same length as records
            if len(emails_list) != len(records):
                raise ValueError(_('Length of context `emails` must match the number of selected invoices.'))
            pairs = list(zip(records, emails_list))
        else:
            for inv in records.filtered(lambda m: not m.e_invoice_mail_send):
                email = email_map.get(inv.id) or (inv.partner_id.email if inv.partner_id else False)
                if not email:
                    inv.message_post(body=_('No recipient email found for this invoice; skipped.'))
                    continue
                pairs.append((inv, email))

        sent = 0
        for inv, to_email in pairs:
            pdf_data, err = inv._get_einvoice_pdf_data()
            if not pdf_data:
                inv.message_post(body=err or _('PDF not available; skipped.'))
                continue

            invoice_type = 'E-Archive' if inv._is_earchive_invoice() else 'E-Invoice'
            filename = f"{invoice_type}-{inv.name}.pdf"

            # create attachment attached to the invoice
            attachment = Attachment.create({
                'name': filename,
                'type': 'binary',
                'datas': pdf_data,
                'res_model': inv._name,
                'res_id': inv.id,
                'mimetype': 'application/pdf',
            })

            mail_vals = {
                'subject': _('E-Fatura PDF - %s') % inv.name,
                'body_html': _('<p>Merhaba,</p><p>İlgili faturanız ektedir.</p><p>Saygılarımızla,<br/>%s</p>') % (inv.company_id.name or ''),
                'email_to': to_email,
                'attachment_ids': [(4, attachment.id)],
                'auto_delete': True,
            }
            mail = Email.create(mail_vals)
            inv.e_invoice_mail_send = True
            #mail.send()
            sent += 1

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('E-Fatura gönderimi'),
                'message': _('%d e-posta gönderildi.') % sent,
                'sticky': False,
            }
        }
