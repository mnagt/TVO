/** @odoo-module **/

import { ListController } from "@web/views/list/list_controller";
import { ListRenderer } from "@web/views/list/list_renderer";
import { listView } from "@web/views/list/list_view";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { useState, onMounted } from "@odoo/owl";
import { download } from "@web/core/network/download";
import { TaxBalanceListRenderer } from "./tax_balance_list_renderer";

// Action xmlids per (currency, grouping) combination, keyed "isTr:isGrouped"
const ACTIONS = {
    "false:false": "tax_balance.action_tax_balance",
    "true:false": "tax_balance.action_tax_balance_tr",
    "false:true": "tax_balance.action_tax_balance_by_tax",
    "true:true": "tax_balance.action_tax_balance_tr_by_tax",
};

class TaxBalanceListController extends ListController {
    static template = "tax_balance.TaxBalanceListView";

    setup() {
        super.setup();
        this.orm = useService("orm");
        this.action = useService("action");

        this.userConfig = useState({ show_tl: false, show_usd: false });
        onMounted(async () => {
            const cfg = await this.orm.call('partner.balance.user.config', 'get_user_config', []);
            Object.assign(this.userConfig, cfg);
        });
    }

    get isTrReport() {
        return (this.props.context?.action_name || '').includes('TL');
    }

    get isGroupedReport() {
        return (this.props.context?.action_name || '').includes('by Tax');
    }

    async _switchTo(isTr, isGrouped) {
        await this.action.doAction(ACTIONS[`${isTr}:${isGrouped}`]);
    }

    async onTrReport() {
        await this._switchTo(true, this.isGroupedReport);
    }

    async onUsdReport() {
        await this._switchTo(false, this.isGroupedReport);
    }

    async onToggleGroupByTax() {
        await this._switchTo(this.isTrReport, !this.isGroupedReport);
    }

    async openRecord(record) {
        const action = await this.orm.call(record.resModel, "action_open_invoice", [[record.resId]]);
        await this.action.doAction(action);
    }

    async onExcelExport() {
        let ids = false;
        if (!this.model.root.isDomainSelected) {
            const resIds = await this.model.root.getResIds(true);
            ids = resIds.length > 0 && resIds;
        }

        await download({
            data: {
                data: JSON.stringify({
                    domain: this.model.root.domain,
                    ids: ids,
                    context: this.props.context || {},
                }),
            },
            url: "/web/tax_balance_export/xlsx",
        });
    }
}

registry.category("views").add("tax_balance", {
    ...listView,
    Controller: TaxBalanceListController,
    Renderer: TaxBalanceListRenderer,
});

// Grouped-by-tax view: no dynamic pivot columns needed since tax_id is a
// real groupable field and native Odoo group sums handle totals.
registry.category("views").add("tax_balance_by_tax", {
    ...listView,
    Controller: TaxBalanceListController,
    Renderer: ListRenderer,
});
