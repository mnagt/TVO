/** @odoo-module **/

import { useService } from "@web/core/utils/hooks";
import { ListController } from "@web/views/list/list_controller";

export class GeneralLedgerListController extends ListController {
    static template = "account_extension_tl_gl.GeneralLedgerListView";
    static components = {
        ...ListController.components,
    };

    setup() {
        super.setup();
        this.action = useService("action");
        // Toolbar always visible when this module is installed
    }

    get context() {
        return this.props.context || {};
    }

    get isTlView() {
        return !!(this.context.tl_gl_view);
    }

    onTlReport() {
        this.action.doAction(
            'account_extension_tl_gl.action_account_moves_ledger_general_tl'
        );
    }

    onUsdReport() {
        this.action.doAction(
            'accounting_pdf_reports.action_account_moves_ledger_general'
        );
    }
}