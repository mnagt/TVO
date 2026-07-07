/** @odoo-module **/

import { registry } from "@web/core/registry";
import { ListController } from "@web/views/list/list_controller";
import { listView } from "@web/views/list/list_view";
import { useService } from "@web/core/utils/hooks";

export class ProductBalanceMoveListController extends ListController {
    setup() {
        super.setup();
        this.orm = useService("orm");
        this.action = useService("action");
    }

    async openRecord(record) {
        const action = await this.orm.call(
            "product.balance.report",
            "action_open_move",
            [[record.resId]],
        );
        await this.action.doAction(action);
    }
}

export const productBalanceMoveListView = {
    ...listView,
    Controller: ProductBalanceMoveListController,
};

registry.category("views").add("product_balance_move_list", productBalanceMoveListView);
