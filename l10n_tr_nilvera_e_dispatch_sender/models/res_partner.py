# Copyright 2025 Rasard
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models


from odoo.addons.l10n_tr_nilvera.lib.nilvera_client import _get_nilvera_client
import urllib.parse


class ResPartner(models.Model):
    _inherit = "res.partner"


    l10n_tr_nilvera_despatch_alias_id = fields.Many2one('l10n_tr.nilvera.despatch.alias','Despatch Alias',domain="[('partner_id', '=', id)]")

    l10n_tr_nilvera_despatch_alias_ids = fields.Many2many('l10n_tr.nilvera.despatch.alias',string='Despatch Alias')


    def check_nilvera_customer(self):
        res = super(ResPartner,self).check_nilvera_customer()
        if not self.vat:
            return res

        with _get_nilvera_client(self.env.company) as client:
            params={'globalUserType':'DespatchAdvice'}
            response = client.request("GET", "/general/GlobalCompany/Check/TaxNumber/" + urllib.parse.quote(self.vat),params=params, handle_response=False)
            if response.status_code == 200:
                query_result = response.json()

                if not query_result:
                    self.l10n_tr_nilvera_despatch_alias_id = False
                else:
                    # We need to sync the data from the API with the records in database.
                    aliases = {result.get('Name') for result in query_result}
                    persisted_aliases = self.l10n_tr_nilvera_despatch_alias_ids
                    # Find aliases to add (in query result but not in database).
                    aliases_to_add = aliases - set(persisted_aliases.mapped('name'))
                    # Find aliases to remove (in database but not in query result).
                    aliases_to_remove = set(persisted_aliases.mapped('name')) - aliases

                    newly_persisted_aliases = self.env['l10n_tr.nilvera.despatch.alias'].create([{
                        'name': alias_name,
                        'partner_id': self.id,
                    } for alias_name in aliases_to_add])
                    to_keep = persisted_aliases.filtered(lambda a: a.name not in aliases_to_remove)
                    (persisted_aliases - to_keep).unlink()

                    # If no alias was previously selected, automatically select the first alias.
                    remaining_aliases = newly_persisted_aliases | to_keep
                    if not self.l10n_tr_nilvera_despatch_alias_id and remaining_aliases:
                        self.l10n_tr_nilvera_despatch_alias_id = remaining_aliases[0]




class L10ntrNilveraDespetchAlias(models.Model):
    _name = 'l10n_tr.nilvera.despatch.alias'
    _description = "Despatch Alias on Nilvera"

    name = fields.Char()
    partner_id = fields.Many2one('res.partner')