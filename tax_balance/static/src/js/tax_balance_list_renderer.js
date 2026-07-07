/** @odoo-module **/

import { ListRenderer } from "@web/views/list/list_renderer";
import { useService } from "@web/core/utils/hooks";
import { onWillStart, onMounted, onPatched } from "@odoo/owl";

const MODEL = "account.tax.balance";
const COL_MARKER = "o_tax_balance_dyn_col";

export class TaxBalanceListRenderer extends ListRenderer {
    setup() {
        super.setup();
        this.orm = useService("orm");
        this.taxes = [];
        this.currencySymbol = '';
        this.currencyPosition = 'before';
        this.tryCurrencySymbol = '';
        this.tryCurrencyPosition = 'before';
        this._currentIsTrView = false;
        this.taxGroupAggregates = null;
        this._groupAggsCacheKey = null;

        onWillStart(async () => {
            const [taxes, currency, tryCurrencyResults] = await Promise.all([
                this.orm.call(MODEL, "get_used_taxes", []),
                this.orm.call(MODEL, "get_company_currency_symbol", []),
                this.orm.searchRead('res.currency', [['name', '=', 'TRY']], ['symbol', 'position'], { limit: 1 }),
            ]);
            this.taxes = taxes;
            this.currencySymbol = currency.symbol;
            this.currencyPosition = currency.position;
            const tryCurrencyInfo = tryCurrencyResults[0];
            this.tryCurrencySymbol = tryCurrencyInfo?.symbol || '₺';
            this.tryCurrencyPosition = tryCurrencyInfo?.position || 'before';
        });

        onMounted(() => {
            this._refreshTaxColumns();
            this._maybeFetchGroupAggregates();
        });

        onPatched(() => {
            this._refreshTaxColumns();
            this._maybeFetchGroupAggregates();
        });
    }

    _refreshTaxColumns() {
        const taxes = this.taxes;
        if (!taxes.length) return;

        const table = this.tableRef.el;
        if (!table) return;

        // Remove previously injected columns
        table.querySelectorAll(`.${COL_MARKER}`).forEach((el) => el.remove());

        // --- 1. Header ---
        const anchorTh = table.querySelector('thead th[data-name="amount_untaxed"]')
            || table.querySelector('thead th[data-name="amount_untaxed_try"]');
        if (!anchorTh) return;
        this._currentIsTrView = anchorTh.dataset.name === 'amount_untaxed_try';
        const anchorColName = anchorTh.dataset.name;
        const taxAmountField = this._currentIsTrView ? 'tax_amounts_try' : 'tax_amounts';

        for (let i = taxes.length - 1; i >= 0; i--) {
            const th = document.createElement("th");
            th.className = `${COL_MARKER} o_list_number_th fw-bold`;
            th.style.cssText = "white-space:nowrap; text-align:right; padding-right:8px; width:105px;";

            const inner = document.createElement("div");
            inner.className = "d-flex";

            const label = document.createElement("span");
            label.className = "d-block min-w-0 text-truncate flex-grow-1 flex-shrink-1 o_list_number_th";
            label.textContent = taxes[i].name;

            const spacer = document.createElement("div");
            spacer.className = "o_list_header_label_spacer";

            inner.appendChild(label);
            inner.appendChild(spacer);

            const resizeHandle = document.createElement("span");
            resizeHandle.className = "o_resize position-absolute top-0 end-0 bottom-0 ps-1 bg-black-25 opacity-0 opacity-50-hover z-1";

            th.appendChild(inner);
            th.appendChild(resizeHandle);
            anchorTh.insertAdjacentElement("afterend", th);
        }

        // --- 2. Compute column index for footer alignment ---
        const headerThs = Array.from(table.querySelectorAll("thead th"));
        const anchorThIndex = headerThs.indexOf(anchorTh);

        // --- 3. Data rows ---
        const taxSums = {};
        taxes.forEach((t) => { taxSums[t.id] = 0; });

        const dataRows = table.querySelectorAll("tbody tr.o_data_row");
        for (const row of dataRows) {
            const anchorTd = row.querySelector(`td[name="${anchorColName}"]`);
            if (!anchorTd) continue;

            const datapointId = row.dataset.id;
            const record = this.props.list.records.find((r) => r.id === datapointId);
            const taxAmounts = (record && record.data[taxAmountField]) || {};

            for (let i = taxes.length - 1; i >= 0; i--) {
                const tax = taxes[i];
                const amount = parseFloat(taxAmounts[String(tax.id)] || 0);
                taxSums[tax.id] += amount;

                const td = document.createElement("td");
                td.className = `${COL_MARKER} o_data_cell o_list_number`;
                td.style.cssText = "text-align:right; padding-right:8px;";
                td.textContent = this._formatAmount(amount);
                anchorTd.insertAdjacentElement("afterend", td);
            }
        }

        // --- 3.5. Group header rows ---
        const groupHeaderRows = Array.from(table.querySelectorAll("tbody tr.o_group_header"));
        const isSingleLevelGroup = this.props.list.groupBy?.length === 1;

        for (let gi = 0; gi < groupHeaderRows.length; gi++) {
            const groupRow = groupHeaderRows[gi];
            const firstGroupTd = groupRow.querySelector("td") || groupRow.querySelector("th.o_group_name");
            if (!firstGroupTd) continue;

            const sums = (isSingleLevelGroup && this.taxGroupAggregates)
                ? (this.taxGroupAggregates[gi] || {})
                : {};

            for (let i = taxes.length - 1; i >= 0; i--) {
                const tax = taxes[i];
                const sum = parseFloat(sums[String(tax.id)] || 0);
                const td = document.createElement("td");
                td.className = `${COL_MARKER} o_list_number fw-bold`;
                td.style.cssText = "text-align:right; padding-right:8px;";
                td.textContent = this._formatAmount(sum);
                firstGroupTd.insertAdjacentElement("afterend", td);
            }
        }

        // --- 4. Footer sums ---
        const footerRow = table.querySelector("tfoot tr");
        if (!footerRow || anchorThIndex === -1) return;

        const footerTds = Array.from(footerRow.querySelectorAll("td"));
        const footerAnchorTd = footerTds[anchorThIndex];
        if (!footerAnchorTd) return;

        for (let i = taxes.length - 1; i >= 0; i--) {
            const tax = taxes[i];
            const sum = taxSums[tax.id];

            const td = document.createElement("td");
            td.className = `${COL_MARKER} o_list_number fw-bold`;
            td.style.cssText = "text-align:right; padding-right:8px;";
            td.textContent = this._formatAmount(sum);
            footerAnchorTd.insertAdjacentElement("afterend", td);
        }
    }

    _formatAmount(amount) {
        if (!amount) return "";
        const n = amount.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        const symbol = this._currentIsTrView ? this.tryCurrencySymbol : this.currencySymbol;
        const pos = this._currentIsTrView ? this.tryCurrencyPosition : this.currencyPosition;
        return pos === 'before' ? `${symbol}${n}` : `${n} ${symbol}`;
    }

    get getEmptyRowIds() {
        return [];
    }

    _maybeFetchGroupAggregates() {
        const list = this.props.list;
        if (!list.isGrouped || !list.groups?.length || list.groupBy.length !== 1) {
            this.taxGroupAggregates = null;
            this._groupAggsCacheKey = null;
            return;
        }
        const groupDomains = list.groups.map(g => g.groupDomain);
        const cacheKey = JSON.stringify({ domains: groupDomains, isTr: this._currentIsTrView });
        if (this._groupAggsCacheKey === cacheKey) return;
        this._groupAggsCacheKey = cacheKey;

        this.orm.call(MODEL, "get_group_tax_aggregates", [groupDomains], { use_try: this._currentIsTrView }).then(result => {
            if (!this.tableRef.el) return;
            this.taxGroupAggregates = result;
            this._refreshTaxColumns();
        });
    }
}
