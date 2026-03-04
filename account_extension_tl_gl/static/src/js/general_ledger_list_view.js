/** @odoo-module **/

import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { GeneralLedgerListController } from "./general_ledger_list_controller";

export const generalLedgerListView = {
    ...listView,
    Controller: GeneralLedgerListController,
};

registry.category("views").add("general_ledger_tl", generalLedgerListView);