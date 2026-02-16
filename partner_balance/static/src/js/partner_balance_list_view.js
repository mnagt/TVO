/** @odoo-module **/

import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { PartnerBalanceListController } from "./partner_balance_list_controller";

export const partnerBalanceListView = {
    ...listView,
    Controller: PartnerBalanceListController,
};

registry.category("views").add("partner_balance", partnerBalanceListView);
