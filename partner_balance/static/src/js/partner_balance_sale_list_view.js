/** @odoo-module **/

import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { PartnerBalanceSaleListController } from "./partner_balance_sale_list_controller";

// Registers the partner_balance_sale js_class used by the Partner Balance summary list view.
export const partnerBalanceSaleListView = {
    ...listView,
    Controller: PartnerBalanceSaleListController,
};

registry.category("views").add("partner_balance_sale", partnerBalanceSaleListView);
