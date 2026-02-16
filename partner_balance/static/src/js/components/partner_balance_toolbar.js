/** @odoo-module **/

import { Component, useRef } from "@odoo/owl";

export class PartnerBalanceToolbar extends Component {
    static template = "partner_balance.PartnerBalanceToolbar";

    static props = {
        dateFrom: { type: [String, { value: null }], optional: true },
        dateTo: { type: [String, { value: null }], optional: true },
        currencyBalances: { type: Object, optional: true },
        showSummary: { type: Boolean, optional: true },
        isTrReport: { type: Boolean, optional: true },
        onTrReport: { type: Function },
        onDateChange: { type: Function },
        onExcelExport: { type: Function },
        showProducts: { type: Boolean, optional: true }, onToggleProducts: { type: Function }
    };

    setup() {
        this.dateFromRef = useRef("dateFrom");
        this.dateToRef = useRef("dateTo");
    }

    // -------------------------------------------------------------------------
    // Handlers
    // -------------------------------------------------------------------------

    handleDateChange(ev) {
        this.props.onDateChange({
            dateFrom: this.dateFromRef.el?.value || null,
            dateTo: this.dateToRef.el?.value || null,
            originalEvent: ev,
        });
    }

    handleExcelExport() {
        this.props.onExcelExport();
    }

    handleTrReport() {
        this.props.onTrReport();
    }

    handleToggleProducts() { 
        this.props.onToggleProducts(); 
    }

    // -------------------------------------------------------------------------
    // Helpers
    // -------------------------------------------------------------------------

    formatCurrency(value) {
        return Number(value || 0).toLocaleString('en-US', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        });
    }

    get currencyEntries() {
        return Object.entries(this.props.currencyBalances || {});
    }
}
