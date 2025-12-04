# Copyright 2023 Kıta Yazılım
# License LGPLv3 or later (https://www.gnu.org/licenses/lgpl-3.0).
import requests
import itertools
import pytz
import dateutil.parser
from decimal import Decimal
import json
import logging
from datetime import datetime
from dateutil.relativedelta import relativedelta
from odoo.addons.account_statement_import_online.models.online_bank_statement_provider import OnlineBankStatementProvider as ProviderVomsis

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

TIMEOUT = 20
VOMSIS_API_BASE = "https://developers.vomsis.com/api/v2"

class ProviderVomsis(models.Model):
    _inherit = "online.bank.statement.provider"

    api_key = fields.Char('Api Anahtarı')
    api_secret = fields.Char('Api Gizli Anahtarı')

    @api.model
    def _get_available_services(self):
        return super()._get_available_services() + [
            ("vomsis", "Vomsis.com"),
        ]
    
    def _obtain_statement_data(self, date_since, date_until):
        self.ensure_one()
        if self.service != "vomsis":
            return super()._obtain_statement_data(
                date_since, date_until,
            ) 

        # MULTI-COMPANY FIX: Bank account kontrolü
        bank_account = self.journal_id.bank_account_id
        if not bank_account:
            raise UserError('Bu journal\'ın bank account\'u bulunamadı!')
            
        account_vomsis_id = bank_account.vomsis_id
        if account_vomsis_id == 0:
            _logger.exception("%s adlı banka hesabının vomsiste kaydı bulunamadı!", bank_account.bank_name)
            return False
            #raise UserError('Bu banka hesabının vomsisde bir kaydı bulunamadı!')

        currency = (self.currency_id or self.company_id.currency_id).name

        if date_since.tzinfo:
            date_since = date_since.astimezone(pytz.utc).replace(tzinfo=None)
        if date_until.tzinfo:
            date_until = date_until.astimezone(pytz.utc).replace(tzinfo=None)

        # Geriye dönük vomsisten ne kadar sürelik data çekilebilecek?
        #if date_since < datetime.utcnow() - relativedelta(days=7):
        #    raise UserError(
        #        _(
        #            "Vomsis sadece 7 günlük kayıtları veriyor"
        #        )
        #    )

        token = self._vomsis_get_token()
        transactions = self._vomsis_get_transactions(
            token, currency, date_since, date_until
        )
        if not transactions:
            balance = self._vomsis_get_account_balance(account_vomsis_id)
            return [], {"balance_start": balance, "balance_end_real": balance}

        transactions = list(
            sorted(
                transactions,
                key=lambda transaction: self._vomsis_get_transaction_date(transaction),
            )
        )
        lines = list(
            itertools.chain.from_iterable(
                map(lambda x: self._vomsis_transaction_to_lines(x), transactions)
            )
        )

        if transactions:
            first_transaction = transactions[0]
            first_transaction_id = first_transaction["id"]
            first_transaction_date = self._vomsis_get_transaction_date(first_transaction)

            if not first_transaction:
                raise UserError(
                    _("Başlangıç kaydı bulunamadı %s (%s)")
                    % (first_transaction_id, first_transaction_date)
                )
            balance_start = self._vomsis_get_transaction_ending_balance(first_transaction)
            balance_start -= self._vomsis_get_transaction_total_amount(first_transaction)

            last_transaction = transactions[-1]
            last_transaction_id = last_transaction["id"]
            last_transaction_date = self._vomsis_get_transaction_date(last_transaction)

            if not last_transaction:
                raise UserError(
                    _("Son ekstre kaydı bulunamadı %s (%s)")
                    % (last_transaction_id, last_transaction_date)
                )
            balance_end = self._vomsis_get_transaction_ending_balance(last_transaction)
            return lines, {"balance_start": balance_start, "balance_end_real": balance_end}

    def _vomsis_get_token(self):
        self.ensure_one()
        url = self.api_base or VOMSIS_API_BASE + "/authenticate"
        payload = self._prepare_vomsis_payload()
        request = requests.post(url, json=payload)
        response = json.loads(request.text)
        if not response.get('status') == 'success':
            raise UserError(response.get('message'))
        return f"Bearer {response.get('token')}"

    def _prepare_vomsis_payload(self):
        data={
            "app_key"    : self.api_key,
            "app_secret" : self.api_secret,
        }
        return data

    def _vomsis_get_transactions(self, token, currency, since, until, lastId=None, dateType=None, types=None, bankName=None):
        self.ensure_one()
        interval_step = relativedelta(days=7)
        interval_start = since
        transactions = []
        while interval_start < until:
            interval_end = min(interval_start + interval_step, until)
            try:
                url = self.api_base or VOMSIS_API_BASE + "/accounts/"+str(self.journal_id.bank_account_id.vomsis_id)+"/transactions"
                headers = {
                    'Authorization': token
                }
                params = {
                    'beginDate': since.strftime("%d-%m-%Y %H:%M:%S"),
                    'endDate': until.strftime("%d-%m-%Y %H:%M:%S"),
                    'lastId': lastId,
                    'dateType': dateType,
                    'types': types,
                    'bankName': bankName,
                }                

                status, response, asktime = self._do_request(url, params=params, headers=headers, type='GET')
                interval_transactions = map(
                    lambda transaction: self._vomsis_preparse_transaction(transaction),
                    response['transactions'],
                )
                transactions += list(
                    filter(
                        lambda transaction: interval_start
                        <= self._vomsis_get_transaction_date(transaction)
                        < interval_end,
                        interval_transactions,
                    )
                )
                interval_start += interval_step
                return transactions
            except requests.HTTPError as e:
                try:
                    response = e.response.json()
                    error = response.get('errors', [])[0].get('message')
                except Exception:
                    error = None
                if not error:
                    raise e
                message = _("Hata oluştu. %s") % (error)
                raise UserError(message)

    @api.model
    def _vomsis_get_transaction_date(self, transaction):
        return transaction["system_date"]

    @api.model
    def _vomsis_get_transaction_total_amount(self, transaction):
        transaction_amount = transaction.get("amount")
        if not transaction_amount:
            return Decimal()
        return Decimal(transaction_amount)

    @api.model
    def _vomsis_preparse_transaction(self, transaction):
        date = (
            dateutil.parser.parse(self._vomsis_get_transaction_date(transaction))
            .astimezone(pytz.utc)
            .replace(tzinfo=None)
        )
        transaction["system_date"] = date
        return transaction

    @api.model
    def _vomsis_get_transaction_ending_balance(self, transaction):
        transaction_amount = transaction["current_balance"]
        if not transaction_amount:
            return Decimal()
        return Decimal(transaction_amount)

    @api.model
    def _vomsis_get_transaction_total_amount(self, transaction):
        transaction_amount = transaction["amount"]
        if not transaction_amount:
            return Decimal()
        return Decimal(transaction_amount)

    @api.model
    def _vomsis_transaction_to_lines(self, transaction):
        transaction_id = transaction["id"]
        bank_account_id = transaction["bank_account_id"]
        transaction_type = transaction["transaction_type"]
        system_date = self._vomsis_get_transaction_date(transaction)
        sender_identity_number = transaction["sender_identity_number"]
        sender_name = transaction["sender_name"]
        sender_branch = transaction["sender_branch"]
        sender_title = transaction["sender_title"]
        sender_iban = transaction["sender_iban"]
        sender_taxno = transaction["sender_taxno"]
        fis_no = transaction["fis_no"]
        payer_tax_no = transaction["payer_tax_no"]
        description = transaction["description"]
        amount = self._vomsis_get_transaction_total_amount(transaction)
        type = transaction["type"]
        note = transaction["note"]

        if fis_no:
            fis_no = _("Evrak %s %s") % (fis_no, str(transaction_id))
            note = "{}: {}".format(note or '', fis_no)

        name = (
            fis_no
            or note
            or description
            or ""
        )

        # Odoo 18 için lines_widget_json alanını doğru formata göre düzenleyelim
        # Burada boş bir değer veriyoruz, _post_process_imported_lines fonksiyonunda doldurulacak
        lines_widget_json = None

        line = {
            #"name": name,
            "amount": str(amount),
            "date": system_date,
            "payment_ref": description or note,
            "narration": f'''{description} {note} {fis_no}''',
            "journal_id": self.journal_id.id,
            "unique_import_id": str(transaction_id),
            "lines_widget_json": lines_widget_json,
        }
        
        sender_info = ''
        partner_id = False
        if sender_title:
            sender_info += f'''{sender_title} '''

        if sender_name:
            sender_info += f'''{sender_name} '''

        # MULTI-COMPANY FIX: Partner search'leri company-aware yap
        if sender_taxno or payer_tax_no:
            sender_info += f'''Vergi No: {sender_taxno or payer_tax_no} '''
            partner_id = self.env['res.partner'].search([
                ('vat', '=', sender_taxno or payer_tax_no),
                '|', ('company_id', '=', self.journal_id.company_id.id), ('company_id', '=', False)
            ], limit=1)
        
        if sender_iban:
            sender_info += f'''Iban: {sender_iban}'''
            if not partner_id:
                res_partner_bank_id = self.env['res.partner.bank'].search([
                    ('acc_number', '=', sender_iban),
                    '|', ('company_id', '=', self.journal_id.company_id.id), ('company_id', '=', False)
                ], limit=1)
                partner_id = (res_partner_bank_id and res_partner_bank_id.partner_id) or False
        
        if partner_id:
            # MULTI-COMPANY FIX: Partner ID list problemi çöz
            if hasattr(partner_id, 'commercial_partner_id'):
                line.update({"partner_id": partner_id.commercial_partner_id.id})
            else:
                line.update({"partner_id": partner_id.id})

        if sender_info:
            line.update({"partner_name": sender_info})

        lines = [line]
        return lines

    @api.model
    def _do_request(self, uri, params={}, headers={}, type='POST'):

        _logger.debug("Uri: %s - Type : %s - Headers: %s - Params : %s !", (uri, type, headers, params))
        ask_time = fields.Datetime.now()
        try:
            if type.upper() in ('GET', 'DELETE'):
                res = requests.request(type.lower(), uri, headers=headers, params=params, timeout=TIMEOUT)
            elif type.upper() in ('POST', 'PATCH', 'PUT'):
                res = requests.request(type.lower(), uri, json=params, headers=headers, timeout=TIMEOUT)
            else:
                raise Exception(_('Desteklenmeyen Metod [%s] not in [GET, POST, PUT, PATCH or DELETE]!') % (type))
            res.raise_for_status()
            status = res.status_code

            content_type = res.headers.get('Content-type')
            if int(status) in (204, 404):
                response = False
            elif 'application/json' in content_type:
                response = res.json()
            elif 'text/plain' in content_type:
                response = res.text
            else:
                raise Exception('Desteklenmeyen içerik türü(Content-type)!')

            try:
                ask_time = datetime.strptime(res.headers.get('date'), "%a, %d %b %Y %H:%M:%S %Z")
            except:
                pass
        except requests.HTTPError as error:
            if error.response.status_code in (204, 404):
                status = error.response.status_code
                response = ""
            else:
                _logger.exception("Bad request Vomsis : %s !", error.response.text)
                if error.response.status_code in (400, 401, 403, 410):
                    raise error
                raise UserError(_("Bilinmeyen hata oluştu"))
        return (status, response, ask_time)

    def _vomsis_get_account_balance(self, account_vomsis_id):
        try:
            url = self.api_base or VOMSIS_API_BASE + "/accounts/"+str(account_vomsis_id)
            headers = {
                'Authorization': self._vomsis_get_token()
            }
            status, response, asktime = self._do_request(url, headers=headers, type='GET')
            if not response['status'] == 'success':
                raise UserError('Hesap Bakiyesi Alınırken Hata Oluştu!')
            account_balance = response['account'][0].get('balance')
            if not account_balance:
                return Decimal()
            return Decimal(account_balance)
        except requests.HTTPError as e:
            try:
                response = e.response.json()
                error = response.get('errors', [])[0].get('message')
            except Exception:
                error = None
            if not error:
                raise e
            message = _("Hata oluştu. %s") % (error)
            raise UserError(message)

    def get_vomsis_account_data(self):
        try:
            url = self.api_base or VOMSIS_API_BASE + "/accounts"
            headers = {
                'Authorization': self._vomsis_get_token()
            }

            status, response, asktime = self._do_request(url, headers=headers, type='GET')
            #Hesaplar Listelenecek
            vomsis_accounts = response['accounts']
            if not response['status'] == 'success':
                raise UserError('Hesaplar Alınırken Hata Oluştu!')

            # MULTI-COMPANY FIX: Company context'i tutarlı şekilde belirle
            target_company = self.journal_id.company_id if self.journal_id else self.env.company
            target_company_id = target_company.id

            for account in vomsis_accounts:
                # MULTI-COMPANY FIX: Önce aynı şirkette ara
                partner_account = self.env['res.partner.bank'].search([
                    ('acc_number','=', account.get('iban')),
                    ('company_id', '=', target_company_id)
                ], limit=1)
                
                # Bulamazsa global ara
                if not partner_account:
                    partner_account = self.env['res.partner.bank'].search([
                        ('acc_number','=', account.get('iban')),
                        ('company_id', '=', False)
                    ], limit=1)

                # MULTI-COMPANY FIX: Yeni kayıt oluştururken company_id ekle
                if not partner_account:
                    currency_name =  account.get('fec_name')
                    if currency_name == 'TL':
                        currency_name = 'TRY'
                    currency_id = self.env['res.currency'].search([('name', '=', currency_name)])
                    
                    partner_account = self.env['res.partner.bank'].create({
                        'acc_number': account.get('iban'),
                        'vomsis_id': account.get('id'),
                        'acc_type': 'bank',
                        'currency_id': currency_id.id if currency_id else False,
                        'partner_id': target_company.partner_id.id,  # TUTARLI COMPANY PARTNER
                        'company_id': target_company_id,  # COMPANY_ID EKLENDİ
                    })
                # MULTI-COMPANY FIX: ensure_one problemi çözüldü
                elif partner_account and (not partner_account.vomsis_id or partner_account.vomsis_id != account.get('id')):
                    partner_account.write({'vomsis_id': account.get('id')})
                    
        except requests.HTTPError as e:
            try:
                response = e.response.json()
                error = response.get('errors', [])[0].get('message')
            except Exception:
                error = None
            if not error:
                raise e
            message = _("Hata oluştu. %s") % (error)
            raise UserError(message)
        
    def action_online_bank_statements_pull_wizard(self):
        self.ensure_one()
        WIZARD_MODEL = "online.bank.statement.pull.wizard"
        wizard = self.env[WIZARD_MODEL].create([])
        return {
            "type": "ir.actions.act_window",
            "res_model": WIZARD_MODEL,
            "res_id": wizard.id,
            "view_mode": "form",
            "target": "new",
        }
    
    def _create_or_update_statement(self, data, statement_date_since, statement_date_until):
        """Create or update bank statement with the data retrieved from provider."""
        statement = super()._create_or_update_statement(data, statement_date_since, statement_date_until)
        if statement:
            self._post_process_imported_lines(statement)
        return statement
    
    def _post_process_imported_lines(self, statement):
        """İçe aktarılan ekstre satırlarını işleyerek uzlaştırma (reconciliation) verilerini ekler."""
        for line in statement.line_ids:
            # Halihazırda uzlaştırma verisi olan satırları kontrol et
            if line.lines_widget_json:
                continue  # Eğer zaten veri varsa, işleme gerek yok
                
            # MULTI-COMPANY FIX: Company context ekle
            domain = [
                ('account_id.reconcile', '=', True),
                ('reconciled', '=', False),
                ('amount_residual', '!=', 0),
                ('company_id', '=', statement.company_id.id),  # COMPANY FILTER EKLENDİ
            ]
            
            # Tutar işaretine göre domain'i düzenle
            if line.amount > 0:
                domain.append(('amount_residual', '<', 0))
            else:
                domain.append(('amount_residual', '>', 0))
            
            # Tutar mutlak değer olarak aynı olmalı
            domain.append(('amount_residual', 'in', [line.amount, -line.amount]))
            
            # Partner varsa partner'a göre de filtrele
            if line.partner_id:
                domain.append(('partner_id', '=', line.partner_id.id))
            
            # En iyi eşleşen kaydı bul (örneğin en yakın tarihli)
            matching_line = self.env['account.move.line'].search(domain, order='date desc', limit=1)
            
            if matching_line:
                # Odoo 18 formatına uygun tek bir kayıt oluştur
                currency = matching_line.currency_id
                match_data = {
                    "id": matching_line.id,
                    "account_id": matching_line.account_id.id,
                    "account_name": matching_line.account_id.name,
                    "account_code": matching_line.account_id.code,
                    "partner_id": f"res.partner({matching_line.partner_id.id})" if matching_line.partner_id else "res.partner()",
                    "partner_name": matching_line.partner_id.name if matching_line.partner_id else False,
                    "date": matching_line.date.strftime('%Y-%m-%d'),
                    "move_id": f"account.move({matching_line.move_id.id},)",
                    "move_name": matching_line.move_id.name,
                    "name": matching_line.name,
                    "amount_residual_currency": int(matching_line.amount_residual_currency) if matching_line.amount_residual_currency else matching_line.amount_residual,
                    "amount_residual": float(matching_line.amount_residual),
                    "currency_id": currency.id,
                    "currency_symbol": currency.symbol
                }
                
                # JSON formatındaki veriyi satıra ekle
                line.write({'lines_widget_json': json.dumps(match_data)})