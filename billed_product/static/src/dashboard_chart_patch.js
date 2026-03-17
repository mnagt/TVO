/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import * as spreadsheet from "@odoo/o-spreadsheet";
import { Domain } from "@web/core/domain";

// Module-level boot log — if this is absent from the console,
// the asset bundle is stale (module needs to be upgraded on the server).
console.log("[billed_product] dashboard_chart_patch.js loaded. FigureComponent:", spreadsheet.components?.FigureComponent);

function getAccountMoveFieldMatching(filter) {
    if (filter.type === "date") {
        return { chain: "invoice_date", type: "date", offset: 0 };
    }
    if (filter.type === "relation") {
        if (filter.modelName === "product.category") {
            return { chain: "line_ids.product_id.categ_id", type: "many2one" };
        }
        if (filter.modelName === "product.product") {
            return { chain: "line_ids.product_id", type: "many2one" };
        }
        if (filter.modelName === "res.partner") {
            return { chain: "partner_id", type: "many2one" };
        }
    }
    return null;
}

function buildFilterDomainForAccountMove(model) {
    const filters = model.getters.getGlobalFilters();
    console.log("[billed_product] Global filters:", filters);
    const domains = filters.map((filter) => {
        const fieldMatching = getAccountMoveFieldMatching(filter);
        console.log("[billed_product] Filter:", filter.id, filter.type, "→ fieldMatching:", fieldMatching);
        if (!fieldMatching) return new Domain();
        const domain = model.getters.getGlobalFilterDomain(filter.id, fieldMatching);
        console.log("[billed_product] Filter domain:", domain.toString());
        return domain;
    });
    return Domain.and(domains);
}

const FigureComponent = spreadsheet.components?.FigureComponent;
if (!FigureComponent) {
    console.error("[billed_product] FigureComponent not found in @odoo/o-spreadsheet — patch skipped");
} else {
    patch(FigureComponent.prototype, {
        setup() {
            super.setup();
            this.actionService = useService("action");
            this.notificationService = useService("notification");
        },

        async onClick() {
            console.log("[billed_product] FigureComponent.onClick called, hasOdooMenu:", this.hasOdooMenu);
            if (!this.hasOdooMenu) return;

            const menu = this.env.model.getters.getChartOdooMenu(this.props.figure.id);
            console.log("[billed_product] menu:", menu, "actionID:", menu?.actionID);

            if (!menu?.actionID) {
                this.notificationService.add(
                    "The menu linked to this chart doesn't have a corresponding action.",
                    { type: "danger" }
                );
                return;
            }

            const action = await this.actionService.loadAction(menu.actionID);
            console.log("[billed_product] action loaded:", action?.type, "res_model:", action?.res_model, "domain:", action?.domain);

            if (!action || action.res_model !== "account.move") {
                console.log("[billed_product] Fallback: not account.move, doing plain doAction");
                await this.actionService.doAction(menu.actionID);
                return;
            }

            const filterDomain = buildFilterDomainForAccountMove(this.env.model);
            console.log("[billed_product] filterDomain:", filterDomain.toString());

            const baseDomain = Domain.and([new Domain(action.domain || []), filterDomain]);
            console.log("[billed_product] final domain:", baseDomain.toList());

            await this.actionService.doAction({
                ...action,
                domain: baseDomain.toList(),
            });
        },
    });
}