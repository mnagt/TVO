/** @odoo-module **/
 import { patch } from "@web/core/utils/patch";
 import { formatMonetary } from "@web/views/fields/formatters";
 import { TaxTotalsComponent } from "@account/components/tax_totals/tax_totals";

 patch(TaxTotalsComponent.prototype, {
     formatTryMonetary(value) {
         return formatMonetary(value, { currencyId: this.totals.try_currency_id });
     },
 });
