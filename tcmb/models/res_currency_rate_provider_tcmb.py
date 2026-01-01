# Copyright 2009 Camptocamp
# Copyright 2009 Grzegorz Grzelak
# Copyright 2019 Brainbean Apps (https://brainbeanapps.com)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

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
        content = tcmb_handler.content
        if invert_calculation:
            for k in content.keys():
                base_rate = float(content[k][base_currency])
                for rate in content[k].keys():
                    content[k][rate] = str(base_rate / float(content[k][rate]))
                content[k]["TRY"] = str(base_rate)
        return content

class TcmbRatesHandler(xml.sax.ContentHandler):
    def __init__(self, currencies, date_from, date_to):
        self.currencies = currencies
        self.date_from = date_from
        self.date_to = date_to
        self.date = None
        self.currency_code = None
        self.current_text = ""
        self.content = defaultdict(dict)

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
        if name == "ForexBuying" and self.currency_code in self.currencies:
            if self.date_from <= self.date <= self.date_to:
                self.content[self.date.isoformat()][self.currency_code] = self.current_text.strip()

