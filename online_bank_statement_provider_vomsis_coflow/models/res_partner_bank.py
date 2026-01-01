# Copyright 2023 Kıta Yazılım
# License LGPLv3 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import _, api, fields, models


class ResPartnerBank(models.Model):

    _inherit = "res.partner.bank"

    vomsis_id = fields.Integer('Vomsis ID')