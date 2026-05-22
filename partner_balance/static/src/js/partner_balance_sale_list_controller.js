/** @odoo-module **/

import { ListController } from "@web/views/list/list_controller";
import { useService } from "@web/core/utils/hooks";

// Controller for the Partner Balance summary list (res.partner).
// Overrides row-click to open the Statement of Account for the selected partner,
// matching the behavior of the Balance stat button on the partner form.
export class PartnerBalanceSaleListController extends ListController {
    setup() {
        super.setup();
        this.orm = useService("orm");
        this.action = useService("action");
    }

    async openRecord(record) {
        const action = await this.orm.call(
            "res.partner",
            "action_view_move_line_report",
            [[record.resId]]
        );
        await this.action.doAction(action);
    }
}
