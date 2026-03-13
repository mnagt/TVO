/** @odoo-module **/

import { useService } from "@web/core/utils/hooks";
import { ListController } from "@web/views/list/list_controller";
import { onWillStart } from "@odoo/owl";

export class StockFlowListController extends ListController {
    setup() {
        super.setup();
        this.orm = useService("orm");
        onWillStart(async () => {
            await this.orm.call(
                'stock.product.flow.report',
                'refresh_materialized_view',
                []
            );
        });
    }
}
