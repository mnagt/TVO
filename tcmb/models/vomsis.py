# -*- coding: utf-8 -*-

import requests
from odoo.exceptions import UserError
from odoo import fields, models

api_url = "https://developers.vomsis.com/api/v2"

class ResCurrencyRateProviderTCMB(models.Model):
    _inherit = "res.currency.rate.provider"

    api_key = 'VTNxWFRQam9CZHVhb0x1QTFDN0tGNStwbFFYQyt4M25QNnp0eU8zczZMYz06OmE97BvV7OK9Rshy8T9ED3g='
    api_secret = 'NDdsQ083bTZhNGdramx4MHRaUk12WnFLdVRSdXJtaDBuRG56WlAybS9END06Os09RoBiSSktrg8qVSHkMIg='
    token = fields.Char(string="Token", compute="authenticate", store=True)

    def authenticate(self):
        self.ensure_one()
        url = f"{api_url}/authenticate"
        payload = {"app_key": self.api_key, "app_secret": self.api_secret}
        
        try:
            response = requests.post(url, json=payload, timeout=10).json()
            if response.get('status') != 'success':
                raise UserError(response.get('message'))
            self.token = f"Bearer {response['token']}"
        except requests.RequestException as e:
            raise UserError(f"Authentication failed: {str(e)}")
        
    
    def get_data(self):
        url = f"{api_url}/banks"
        headers = {"Authorization": self.token}  # Bearer token
        
        try:
            response = requests.get(url, headers=headers, timeout=10).json()
            self.result = response.get('banks', [])
            return response
        except requests.RequestException as e:
            raise UserError(f"Request failed: {str(e)}")
        