/** @odoo-module **/

import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { StockFlowListController } from "./stock_flow";

export const stockFlowListView = {
    ...listView,
    Controller: StockFlowListController,
};

registry.category("views").add("stock_flow", stockFlowListView);