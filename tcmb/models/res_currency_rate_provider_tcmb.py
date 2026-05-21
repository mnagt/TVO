# -*- coding: utf-8 -*-

import xml.sax

from collections import defaultdict
from datetime import datetime, time
from datetime import date, timedelta
from urllib.request import urlopen
from xml.sax import make_parser

from odoo import fields, models


class ResCurrencyRateProviderTCMB(models.Model):
    _inherit = "res.currency.rate.provider"

    service = fields.Selection(
        selection_add=[
            ("TCMB", "Central Bank of Turkey")
        ],
        ondelete={
            "TCMB": "set default"
        },
    )

    

    def _get_supported_currencies(self):
        self.ensure_one()
        if self.service != "TCMB":
            return super()._get_supported_currencies()  # pragma: no cover

        # List of currencies
        return [
            "USD",
            "TRY",
            "EUR",
        ]

    def _obtain_rates(self, base_currency, currencies, date_from, date_to):
        self.ensure_one()
        if self.service != "TCMB":
            return super()._obtain_rates(
                base_currency, currencies, date_from, date_to
            )  # pragma: no cover
        invert_calculation = False
        if base_currency != "TRY":
            invert_calculation = True
            if base_currency not in currencies:
                currencies.append(base_currency)

        # Depending on the date range, different URLs are used
        tcmb_url = "https://www.tcmb.gov.tr/kurlar/today.xml"
        tcmb_handler = TcmbRatesHandler(currencies, date_from, date_to)
        with urlopen(tcmb_url, timeout=10) as response:
            parser = make_parser()
            parser.setContentHandler(tcmb_handler)
            parser.parse(response)
        
        # Collect all 4 rate types
        forex_buying = dict(tcmb_handler.content)
        forex_selling = dict(tcmb_handler.forex_selling)
        banknote_buying = dict(tcmb_handler.banknote_buying)
        banknote_selling = dict(tcmb_handler.banknote_selling)
        
        if invert_calculation:
            # Apply inversion to all 4 rate dictionaries
            for rate_dict in [forex_buying, forex_selling, banknote_buying, banknote_selling]:
                for k in rate_dict.keys():
                    if base_currency in rate_dict[k]:
                        base_rate = float(rate_dict[k][base_currency])
                        for rate in rate_dict[k].keys():
                            rate_dict[k][rate] = str(base_rate / float(rate_dict[k][rate]))
                        rate_dict[k]["TRY"] = str(base_rate)
        
        return {
            'forex_buying': forex_buying,
            'forex_selling': forex_selling,
            'banknote_buying': banknote_buying,
            'banknote_selling': banknote_selling,
        }

class TcmbRatesHandler(xml.sax.ContentHandler):
    def __init__(self, currencies, date_from, date_to):
        self.currencies = currencies
        self.date_from = date_from
        self.date_to = date_to
        self.date = None
        self.currency_code = None
        self.current_text = ""
        self.content = defaultdict(dict)  # ForexBuying
        self.forex_selling = defaultdict(dict)
        self.banknote_buying = defaultdict(dict)
        self.banknote_selling = defaultdict(dict)

    def startElement(self, name, attrs):
        if name == "Tarih_Date":
            # Convert MM/DD/YYYY to YYYY-MM-DD
            date_str = attrs["Date"]  # "12/03/2025"
            date_obj = datetime.strptime(date_str, "%m/%d/%Y").date()
            self.date = date_obj
        elif name == "Currency":
            self.currency_code = attrs["Kod"]
        self.current_text = ""
    
    def characters(self, content):
        self.current_text += content
    
    def endElement(self, name):
        if not self.date or not self.currency_code:
            return
        if self.currency_code not in self.currencies:
            return
        if not (self.date_from <= self.date <= self.date_to):
            return
        if name == "ForexBuying":
            self.content[self.date.isoformat()][self.currency_code] = self.current_text.strip()
        elif name == "ForexSelling":
            self.forex_selling[self.date.isoformat()][self.currency_code] = self.current_text.strip()
        elif name == "BanknoteBuying":
            self.banknote_buying[self.date.isoformat()][self.currency_code] = self.current_text.strip()
        elif name == "BanknoteSelling":
            self.banknote_selling[self.date.isoformat()][self.currency_code] = self.current_text.strip()

