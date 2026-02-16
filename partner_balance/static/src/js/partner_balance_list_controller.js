/** @odoo-module **/

import { evaluateBooleanExpr } from "@web/core/py_js/py";
import { _t } from "@web/core/l10n/translation";
import { download } from "@web/core/network/download";
import { useService } from "@web/core/utils/hooks";
import { ListController } from "@web/views/list/list_controller";
import { useState, onMounted, onPatched } from "@odoo/owl";
import { PartnerBalanceToolbar } from "./components/partner_balance_toolbar";

export class PartnerBalanceListController extends ListController {
    static template = "partner_balance.PartnerBalanceListView";
    static components = {
        ...ListController.components,
        PartnerBalanceToolbar,
    };

    setup() {
        super.setup();

        // Services
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        // State
        this.state = useState({
            dateFrom: null,
            dateTo: null,
            currencyBalances: {},
            showSummary: false,
            initialBalance: 0,
        });
        this.state.showProducts = false;

        onPatched(() => {
            if (this.state.showProducts && this._productData) {
                setTimeout(() => this._renderProductSubTables(), 0);
            }
        });

        onMounted(() => {
            this.setupSummaryDisplay();
        });
    }

    // -------------------------------------------------------------------------
    // Getters
    // -------------------------------------------------------------------------

    get context() {
        return this.props.context || {};
    }

    get partnerId() {
        return this.context.default_partner_id;
    }

    get isTrReport() {
        return this.context.action_name === 'Statement in TRY';
    }


    get toolbarProps() {
        return {
            dateFrom: this.state.dateFrom,
            dateTo: this.state.dateTo,
            currencyBalances: this.state.currencyBalances,
            showSummary: this.state.showSummary,
            isTrReport: this.isTrReport,
            showProducts: this.state.showProducts,
            onToggleProducts: this.onToggleProducts.bind(this),
            onTrReport: this.onTrReport.bind(this),
            onDateChange: this.onDateChange.bind(this),
            onExcelExport: this.onExcelExport.bind(this),
        };
    }


    onTrReport() {
        if (!this.partnerId) return;

        this.action.doAction('partner_balance.action_partner_move_line_tr_value', {
            additionalContext: {
                active_id: this.partnerId,
                active_ids: [this.partnerId],
                active_model: 'res.partner',
                default_partner_id: this.partnerId,
                partner_name: this.context.partner_name || '',
                action_name: 'Statement in TRY',
            },
        });
    }

    // -------------------------------------------------------------------------
    // Date Handling
    // -------------------------------------------------------------------------

    async onDateChange({ dateFrom, dateTo, originalEvent }) {
        if (!dateFrom) {
            this.state.showSummary = false;
            await this.updateViewWithDates(null, dateTo);
            return;
        }

        if (dateTo && new Date(dateTo) <= new Date(dateFrom)) {
            if (originalEvent) {
                originalEvent.target.value = '';
            }
            this.state.showSummary = false;
            this.notification.add(_t("End date must be after start date"), { type: "warning" });
            return;
        }

        await this.updateViewWithDates(dateFrom, dateTo);
        const balances = await this.getCurrencyBalance();
        this.state.currencyBalances = balances;
        const tryBalance = balances['TRY'] || {};
        this.state.initialBalance = tryBalance.opening || 0;
        this.state.showSummary = true;
    }

    async updateViewWithDates(dateFrom, dateTo) {
        let domain = [...(this.props.domain || [])];

        // Remove existing date filters only (NOT line_type)
        domain = domain.filter(filter =>
            !Array.isArray(filter) ||
            (filter[0] !== 'date' && filter[0] !== 'date_from' && filter[0] !== 'date_to')
        );

        // Add new date filters
        if (dateFrom) {
            domain.push(['date', '>=', dateFrom]);
        }
        if (dateTo) {
            domain.push(['date', '<=', dateTo]);
        }

        this.state.dateFrom = dateFrom;
        this.state.dateTo = dateTo;

        await this.model.load({
            domain,
            context: {
                ...this.context,
                date_from: dateFrom || null,
                date_to: dateTo || null,
            },
        });

        if (this.state.showProducts) {
            await this._fetchProductData();
        }
    }

    async onToggleProducts() {
        this.state.showProducts = !this.state.showProducts;
        if (this.state.showProducts) {
            await this._fetchProductData();
            this._renderProductSubTables();
        } else {
            this._productData = null;
            this._removeProductSubTables();
        }
    }

    async _fetchProductData() {
        const records = this.model.root.records;
        const invoiceTypes = ['out_invoice', 'in_invoice', 'out_refund', 'in_refund'];
        const moveIds = [...new Set(
            records
                .filter(r => {
                    return invoiceTypes.includes(r.data.type_key);
                })
                .map(r => r.data.move_id && r.data.move_id[0])
                .filter(Boolean)
        )];


        if (!moveIds.length) {
            this._productData = {};
            return;
        }

        const lines = await this.orm.searchRead(
            'account.move.line',
            [['move_id', 'in', moveIds], ['display_type', '=', 'product']],
            ['move_id', 'product_id', 'quantity', 'product_uom_id', 'price_unit', 'discount', 'price_total', 'price_subtotal']
        );


        this._productData = {};
        for (const line of lines) {
            const moveId = line.move_id[0];
            if (!this._productData[moveId]) this._productData[moveId] = [];
            this._productData[moveId].push(line);
        }
    }

    _renderProductSubTables() {
        this._removeProductSubTables();
        if (!this._productData) return;

        const tableBody = document.querySelector('.o_list_view .o_list_table tbody');
        if (!tableBody) return;

        const rows = tableBody.querySelectorAll(':scope > .o_data_row');
        for (const row of rows) {
            const datapointId = row.dataset.id;
            const record = this.model.root.records.find(r => r.id === datapointId);
            if (!record) continue;

            const moveId = record.data.move_id && record.data.move_id[0];
            if (!moveId || !this._productData[moveId]) continue;

            const lines = this._productData[moveId];
            const colSpan = row.cells.length;

            const subRow = document.createElement('tr');
            subRow.classList.add('o_product_subtable_row');
            subRow.innerHTML = `
                <td colspan="${colSpan}" style="padding: 4px 8px 4px 40px; background-color: #f0f9ff; border-top: none;">
                    <table class="table table-sm table-bordered mb-0" style="font-size: 0.85em;">
                        <thead>
                            <tr style="background-color: #e0f2fe;">
                                <th>Product</th>
                                <th class="text-end">Qty</th>
                                <th>UoM</th>
                                <th class="text-end">Unit Price</th>
                                <th class="text-end">Disc. %</th>
                                <th class="text-end">Tax</th>
                                <th class="text-end">Total</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${lines.map(l => `
                                <tr>
                                    <td>${l.product_id ? l.product_id[1] : ''}</td>
                                    <td class="text-end">${l.quantity}</td>
                                    <td>${l.product_uom_id ? l.product_uom_id[1] : ''}</td>
                                    <td class="text-end">${Number(l.price_unit).toFixed(2)}</td>
                                    <td class="text-end">${l.discount || 0}</td>
                                    <td class="text-end">${Number(l.price_total - l.price_subtotal).toFixed(2)}</td>
                                    <td class="text-end">${Number(l.price_total).toFixed(2)}</td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </td>
            `;
            row.after(subRow);
        }
    }

    _removeProductSubTables() {
        document.querySelectorAll('.o_product_subtable_row').forEach(el => el.remove());
    }

    // -------------------------------------------------------------------------
    // Summary Display
    // -------------------------------------------------------------------------

    setupSummaryDisplay() {
        // Logic handled by template conditionals
    }


    async getCurrencyBalance() {
        if (!this.partnerId || !this.state.dateFrom) return {};

        const result = await this.orm.call(
            'account.move.line.report',
            'get_opening_balance_value',
            [this.partnerId, this.state.dateFrom]
        );
        return result;
    }


    formatCurrency(value) {
        return Number(value || 0).toLocaleString('en-US', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        });
    }

    // -------------------------------------------------------------------------
    // Export
    // -------------------------------------------------------------------------

    async onExcelExport() {
        const columns = this.props.archInfo.columns
            .filter(col => col.type === 'field')
            .filter(col => !col.optional || this.optionalActiveFields[col.name])
            .filter(col => !evaluateBooleanExpr(col.column_invisible, this.props.context))
            .filter(col => this.props.fields[col.name]?.exportable !== false);

        const exportedFields = columns.map(col => ({
            name: col.name,
            label: this.props.fields[col.name].string,
            store: this.props.fields[col.name].store,
            type: this.props.fields[col.name].type,
        }));

        let ids = false;
        if (!this.model.root.isDomainSelected) {
            const resIds = await this.model.root.getResIds(true);
            ids = resIds.length > 0 && resIds;
        }

        await download({
            data: {
                data: JSON.stringify({
                    model: this.model.root.resModel,
                    fields: exportedFields,
                    ids: ids,
                    domain: this.model.root.domain,
                    groupby: this.model.root.groupBy,
                    context: {
                        ...this.context,
                        date_from: this.state.dateFrom || null,
                        date_to: this.state.dateTo || null,
                        show_products: this.state.showProducts,  // <-- add this
                    },
                    import_compat: false,
                }),
            },
            url: '/web/balance_export/xlsx',
        });
    }
}
