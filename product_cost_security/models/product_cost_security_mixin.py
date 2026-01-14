# Copyright 2024 Moduon Team S.L.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0)

from odoo import api, fields, models
from odoo.exceptions import AccessError


class ProductCostSecurityMixin(models.AbstractModel):
    """Automatic security for models related with product costs.

    Access control:
    - No group: Field hidden from UI, blocked from export/API, system writes allowed
    - Read group: Field visible but readonly, export/API allowed
    - Edit group: Field visible and editable
    """

    _name = "product.cost.security.mixin"
    _description = "Product cost access control mixin"

    user_can_update_cost = fields.Boolean(compute="_compute_user_can_update_cost")

    @api.depends_context("uid")
    def _compute_user_can_update_cost(self):
        """Let views know if users can edit product costs."""
        self.user_can_update_cost = self._user_can_update_cost()

    @api.model
    def _user_can_read_cost(self):
        """Know if current user can read product costs."""
        return self.env.user.has_group("product_cost_security.group_product_cost")

    @api.model
    def _user_can_update_cost(self):
        """Know if current user can update product costs."""
        return self.env.user.has_group("product_cost_security.group_product_edit_cost")

    @api.model
    def _product_cost_security_fields(self):
        """Fields protected by cost security."""
        return {"standard_price"}

    def read(self, fields=None, load="_classic_read"):
        """Strip cost fields from results for unauthorized users."""
        result = super().read(fields, load)
        if self.env.su or self._user_can_read_cost():
            return result
        cost_fields = self._product_cost_security_fields()
        for record in result:
            for cost_field in cost_fields:
                record.pop(cost_field, None)
        return result

    @api.model
    def check_field_access_rights(self, operation, fields):
        """Control cost field access based on user permissions.

        - No group: can't see field, writes must be system ops → allow
        - Read group: can see field, might try direct edit → block writes
        - Edit group: full access → allow
        """
        valid_fields = super().check_field_access_rights(operation, fields)
        if self.env.su or operation == "read":
            return valid_fields
        product_cost_fields = self._product_cost_security_fields().intersection(
            set(valid_fields) if valid_fields else set()
        )
        if not product_cost_fields:
            return valid_fields
        can_read = self._user_can_read_cost()
        can_edit = self._user_can_update_cost()
        # No group - can't see field, write must be system operation
        if not can_read:
            return valid_fields
        # Read group but no Edit - block direct writes
        if not can_edit:
            description = self.env["ir.model"]._get(self._name).name
            raise AccessError(
                self.env._(
                    'You do not have enough rights to access the fields "%(fields)s"'
                    " on %(document_kind)s (%(document_model)s). "
                    "Please contact your system administrator."
                    "\n\n(Operation: %(operation)s)",
                    fields=",".join(sorted(product_cost_fields)),
                    document_kind=description,
                    document_model=self._name,
                    operation=operation,
                )
            )
        return valid_fields

    @api.model
    def fields_get(self, allfields=None, attributes=None):
        """Control cost field visibility in UI."""
        result = super().fields_get(allfields, attributes)
        cost_fields = self._product_cost_security_fields()
        can_read = self._user_can_read_cost()
        can_edit = self._user_can_update_cost()
        for field_name in cost_fields:
            if field_name not in result:
                continue
            if not can_read:
                # Hide field but keep definition for frontend
                result[field_name]["invisible"] = True
            elif not can_edit:
                result[field_name]["readonly"] = True
        return result
