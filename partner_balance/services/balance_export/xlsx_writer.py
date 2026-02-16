# -*- coding: utf-8 -*-
"""Excel writer classes for balance exports."""

import io
import json
import datetime

from odoo.tools.misc import xlsxwriter
from odoo.tools import pycompat
from odoo.tools.translate import _
from odoo.exceptions import UserError
from odoo.http import request

from .xlsx_styles import ExportStyles
from .field_mapping import FieldMapping


class BalanceXlsxWriter:
    """Base writer for balance Excel exports."""

    def __init__(self, field_names, row_count=0):
        self.field_names = field_names
        self.output = io.BytesIO()
        self.workbook = xlsxwriter.Workbook(self.output, {'in_memory': True})
        self.worksheet = self.workbook.add_worksheet()
        self.value = False

        self._init_formats()
        self._validate_row_count(row_count)

    def _init_formats(self):
        """Initialize formatting from ExportStyles."""
        decimal_places = self._get_max_decimal_places()
        monetary_format = f'#,##0.{"0" * decimal_places}'

        self.styles = ExportStyles(self.workbook, monetary_format)
        self.monetary_format = monetary_format
        self.float_format = '#,##0.00'

    def _get_max_decimal_places(self):
        """Get maximum decimal places from currencies."""
        try:
            results = request.env['res.currency'].search_read([], ['decimal_places'])
            places = [r['decimal_places'] for r in results]
            return max(places) if places else 2
        except Exception:
            return 2

    def _validate_row_count(self, row_count):
        """Validate row count against Excel limits."""
        if row_count > self.worksheet.xls_rowmax:
            raise UserError(_(
                'Too many rows (%s rows, limit: %s) for Excel format. '
                'Consider splitting the export.'
            ) % (row_count, self.worksheet.xls_rowmax))

    def __enter__(self):
        self.write_header()
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        self.close()

    def close(self):
        """Close workbook and capture output."""
        self.workbook.close()
        with self.output:
            self.value = self.output.getvalue()

    def write(self, row, column, value, style=None):
        """Write a cell with safe value conversion."""
        value = self._safe_value(value)
        self.worksheet.write(row, column, value, style)

    def write_cell(self, row, column, value):
        """Write a cell with automatic style detection."""
        value, style = self._prepare_cell(value, column)
        self.write(row, column, value, style)

    def _prepare_cell(self, value, column):
        """Prepare cell value and determine style."""
        style = self.styles.base

        if isinstance(value, bytes):
            try:
                value = pycompat.to_text(value)
            except UnicodeDecodeError:
                raise UserError(_(
                    "Binary fields cannot be exported to Excel unless base64-encoded."
                ))

        if isinstance(value, str):
            if len(value) > self.worksheet.xls_strmax:
                value = _(
                    "Content too long for XLSX (more than %s characters).",
                    self.worksheet.xls_strmax
                )
            else:
                value = value.replace("\r", " ")
        elif isinstance(value, datetime.datetime):
            style = self.styles.datetime
        elif isinstance(value, datetime.date):
            style = self.styles.date
        elif isinstance(value, float):
            style = self.workbook.add_format({
                'text_wrap': True,
                'font_size': 8,
                'align': 'left',
                'valign': 'vcenter',
                'border': 1,
                'num_format': self.float_format,
            })

        return value, style

    @staticmethod
    def _safe_value(val):
        """Convert value to Excel-safe format."""
        if val is None:
            return ""
        if isinstance(val, (int, float, bool, datetime.datetime, datetime.date)):
            return val
        if isinstance(val, (bytes, bytearray)):
            try:
                return val.decode("utf-8")
            except Exception:
                return val.decode("latin-1", "ignore")
        if isinstance(val, tuple) and len(val) == 2 and isinstance(val[0], int):
            return "" if val[1] is None else str(val[1])
        if isinstance(val, (dict, list, set, tuple)):
            try:
                return json.dumps(val, ensure_ascii=False, default=str)
            except Exception:
                return str(val)
        return str(val)

    def write_header(self):
        """Write column headers."""
        for i, fieldname in enumerate(self.field_names):
            self.write(FieldMapping.HEADER_ROW, i, fieldname, self.styles.transaction_header)
        self.worksheet.set_column(0, len(self.field_names) - 1, 10)

    def write_metadata(self, ctx, data_service, summary_data=None):
        """Write header metadata section."""
        row = 0

        # Company name
        if data_service.partner_id:
            partner = request.env['res.partner'].sudo().browse(data_service.partner_id)
            if partner.exists() and partner.company_id:
                self.worksheet.merge_range(
                    row, 0, row, 7,
                    partner.company_id.name,
                    self.styles.company_header
                )
                row += 1

        # Report title
        action_name = ctx.get('action_name', '')
        title = action_name or "STATEMENT OF ACCOUNT - DETAILED ANALYSIS"
        self.worksheet.merge_range(row, 0, row, 7, title, self.styles.report_title)
        row += 2

        # Executive summary header
        self.worksheet.merge_range(
            row, 0, row, 7,
            _("EXECUTIVE SUMMARY"),
            self.styles.section_header
        )
        row += 1

        # Partner name
        partner_name = ctx.get('partner_name', '')
        if partner_name:
            self.write(row, 0, _("Partner:"), self.styles.partner_name)
            self.worksheet.merge_range(row, 1, row, 7, partner_name, self.styles.partner_name)
            row += 1

        # Date range and metadata
        oldest_date = data_service.get_oldest_date()
        start_date_str = str(data_service.date_from or oldest_date)
        end_date_str = data_service.date_to or datetime.datetime.now().strftime('%Y-%m-%d')

        try:
            start_date = datetime.datetime.strptime(start_date_str, '%Y-%m-%d')
            end_date = datetime.datetime.strptime(end_date_str, '%Y-%m-%d')
            days_diff = max(0, (end_date - start_date).days)
        except ValueError:
            days_diff = 0

        period = f"{start_date_str} to {end_date_str}"
        self.write(row, 0, _("Report Period:"), self.styles.summary_metric)
        self.worksheet.merge_range(row, 1, row, 2, period, self.styles.base)

        export_date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
        self.write(row, 3, _("Generated:"), self.styles.summary_metric)
        self.worksheet.merge_range(row, 4, row, 5, export_date, self.styles.base)

        self.write(row, 6, _("Days:"), self.styles.summary_metric)
        self.write(row, 7, str(days_diff), self.styles.base)
        row += 1

        return row

    def write_opening_balance_row(self, row, opening_data):
        """Write opening balance row if balance is non-zero."""
        if opening_data['balance'] == 0.0:
            return row, 0, 0

        opening_row = FieldMapping.create_opening_balance_row(opening_data)

        for cell_index, cell_value in enumerate(opening_row):
            if cell_index < len(self.field_names):
                self.write(row, cell_index, cell_value, self.styles.opening_balance)

        return row + 1, opening_row[FieldMapping.COLUMNS['debit']], opening_row[FieldMapping.COLUMNS['credit']]

    def write_data_rows(self, start_row, rows, opening_balance=0, product_lines=None, records=None):
        """Write data rows with optional product sub-tables."""
        current_row = start_row
        for row_index, row_data in enumerate(rows):
            row_data = list(row_data)
            for cell_index, cell_value in enumerate(row_data):
                if isinstance(cell_value, (list, tuple)):
                    cell_value = pycompat.to_text(cell_value)
                self.write_cell(current_row, cell_index, cell_value)
            current_row += 1

            # Insert product sub-rows if applicable
            if product_lines and records:
                record = records[row_index] if row_index < len(records) else None
                if record and record.move_id.id in product_lines:
                    current_row = self._write_product_block(
                        current_row, product_lines[record.move_id.id]
                    )

        return current_row
    
    def _write_product_block(self, row, lines):
        """Write product detail sub-rows under an invoice row."""
        # Product header row
        headers = ['', 'Product', 'Qty', 'UoM', 'Unit Price', 'Disc. %', 'Tax', 'Total']
        for col, header in enumerate(headers):
            self.write(row, col, header, self.styles.product_header)
        row += 1

        # Product detail rows
        for line in lines:
            self.write(row, 0, '', self.styles.product_cell)
            self.write(row, 1, line.product_id.display_name or '', self.styles.product_cell)
            self.write(row, 2, line.quantity, self.styles.product_cell)
            self.write(row, 3, line.product_uom_id.name or '', self.styles.product_cell)
            self.write(row, 4, line.price_unit, self.styles.product_cell_number)
            self.write(row, 5, line.discount or 0, self.styles.product_cell_number)
            self.write(row, 6, line.price_subtotal - line.price_total, self.styles.product_cell_number)
            self.write(row, 7, line.price_total, self.styles.product_cell_number)
            row += 1

        return row

    def write_totals(self, row, rows, opening_debit=0, opening_credit=0):
        """Write totals row."""
        total_debit = opening_debit
        total_credit = opening_credit

        debit_idx = FieldMapping.COLUMNS['debit']
        credit_idx = FieldMapping.COLUMNS['credit']

        for row_data in rows:
            total_debit += FieldMapping.get_numeric_value(row_data, 'debit')
            total_credit += FieldMapping.get_numeric_value(row_data, 'credit')

        total_balance = round(total_debit - total_credit, 2)
        total_debit = round(total_debit, 2)
        total_credit = round(total_credit, 2)

        for col in range(len(self.field_names)):
            if col == 0:
                self.write(row, col, _("Total"), self.styles.bold_bg)
            elif col == debit_idx:
                self.write(row, col, total_debit, self.styles.monetary)
            elif col == credit_idx:
                self.write(row, col, total_credit, self.styles.monetary)
            elif col == FieldMapping.COLUMNS['balance']:
                self.write(row, col, total_balance, self.styles.monetary)
            else:
                self.write(row, col, '', self.styles.bold_bg)

        return row + 2


class GroupedBalanceXlsxWriter(BalanceXlsxWriter):
    """Writer for grouped balance exports."""

    def __init__(self, fields, row_count=0):
        field_names = [f['label'].strip() for f in fields]
        super().__init__(field_names, row_count)
        self.fields = fields

    def write_header(self):
        """Override - don't write header for grouped exports."""
        pass

    def write_group_header_row(self, row):
        """Write column headers for a group."""
        for i, fieldname in enumerate(self.field_names):
            self.write(row, i, fieldname, self.styles.transaction_header)
        self.worksheet.set_column(0, len(self.field_names) - 1, 9)
        return row + 1

    def write_group(self, row, column, group_name, group, opening_balances, group_depth=0):
        """Write a complete group with header, data, and totals."""
        group_display = group_name[1] if isinstance(group_name, tuple) and len(group_name) > 1 else group_name
        if group._groupby_type[group_depth] != 'boolean':
            group_display = group_display or _("Undefined")

        # Group header
        row, column = self._write_group_label(row, column, group_display, group, group_depth)

        # Column headers
        row = self.write_group_header_row(row)

        # Opening balance
        opening_row = None
        balance_value = opening_balances.get(group_name, {}).get('balance', 0.0)

        if group_name in opening_balances and opening_balances[group_name]['balance'] != 0.0:
            opening_data = opening_balances[group_name]
            opening_row = FieldMapping.create_opening_balance_row(opening_data)

            for cell_index, cell_value in enumerate(opening_row):
                if cell_index < len(self.field_names):
                    self.write(row, cell_index, cell_value, self.styles.opening_balance)
            row += 1

        # Child groups
        for child_name, child_group in group.children.items():
            row, column = self.write_group(row, column, child_name, child_group, opening_balances, group_depth + 1)

        # Data rows
        for record in group.data:
            row, column, balance_value = self._write_data_row(row, column, record, balance_value)

        # Group totals
        row, column = self._write_group_totals(row, group, opening_row, balance_value)

        return row, column

    def _write_group_label(self, row, column, label, group, group_depth=0):
        """Write group label row."""
        label_text = '%s%s (%s)' % ('' * group_depth, label, group.count)

        self.write(row, column, label_text, self.styles.bold_bg)
        for col in range(1, len(self.fields)):
            self.write(row, col, '', self.styles.bold_bg)

        return row + 1, 0

    def _write_data_row(self, row, column, data, balance=None):
        """Write a single data row with running balance."""
        debit = FieldMapping.get_numeric_value(data, 'debit')
        credit = FieldMapping.get_numeric_value(data, 'credit')
        balance_value = debit - credit

        if balance is None:
            balance = balance_value
        else:
            balance += balance_value

        data = list(data)
        FieldMapping.set_value(data, 'balance', balance)

        for value in data:
            self.write_cell(row, column, value)
            column += 1

        return row + 1, 0, balance

    def _write_group_totals(self, row, group, opening_row=None, balance_value=None):
        """Write group totals row."""
        column = 0
        aggregates = group.aggregated_values

        self.write(row, column, _("Total"), self.styles.bold_bg)
        column += 1

        opening_debit = opening_row[FieldMapping.COLUMNS['debit']] if opening_row else 0
        opening_credit = opening_row[FieldMapping.COLUMNS['credit']] if opening_row else 0
        opening_balance = opening_row[FieldMapping.COLUMNS['balance']] if opening_row else 0

        calculated_fields = {
            'debit': lambda: aggregates.get('debit', 0) + opening_debit,
            'debit_amount': lambda: aggregates.get('debit_amount', 0) + opening_debit,
            'credit': lambda: aggregates.get('credit', 0) + opening_credit,
            'credit_amount': lambda: aggregates.get('credit_amount', 0) + opening_credit,
            'balance': lambda: balance_value if balance_value is not None else (
                aggregates.get('debit', 0) - abs(aggregates.get('credit', 0)) + opening_balance
            ),
            'balance_amount': lambda: balance_value if balance_value is not None else (
                aggregates.get('debit_amount', 0) - abs(aggregates.get('credit_amount', 0)) + opening_balance
            ),
            'cumulated_balance': lambda: balance_value if balance_value is not None else (
                aggregates.get('debit', 0) - abs(aggregates.get('credit', 0)) + opening_balance
            ),
            'amount_currency': lambda: '',
        }

        for field in self.fields[1:]:
            field_name = field['name']

            if field_name in calculated_fields:
                value = calculated_fields[field_name]()
            else:
                value = aggregates.get(field_name)

            if field.get('type') in ('monetary', 'float'):
                pass  # Keep numeric value
            else:
                value = str(value if value is not None else '')

            self.write(row, column, value, self.styles.monetary)
            column += 1

        return row + 2, 0
