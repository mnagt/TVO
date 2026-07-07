# -*- coding: utf-8 -*-

import json
import datetime

from odoo import http
from odoo.http import content_disposition, request
from odoo.tools import osutil

from odoo.addons.partner_balance.services.balance_export import BalanceXlsxWriter


class TaxBalanceExport(http.Controller):

    CONTENT_TYPE = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

    def _filename(self):
        today = datetime.date.today().strftime('%Y-%m-%d')
        return osutil.clean_filename(f"Tax Balance - {today}")

    @http.route('/web/tax_balance_export/xlsx', type='http', auth='user', methods=['POST'])
    def export(self, data='{}'):
        params = json.loads(data)
        domain = params.get('domain', [])
        ids = params.get('ids', False)

        Model = request.env['account.tax.balance']
        taxes = Model.get_used_taxes()

        # Build column headers
        fixed_headers = ['Number', 'Partner', 'Date', 'Reference', 'Tax Excluded']
        tax_headers = [t['name'] for t in taxes]
        all_headers = fixed_headers + tax_headers + ['Total']

        # Fetch records
        if ids:
            records = Model.browse(ids)
        else:
            records = Model.search(domain, order='date desc, id desc')

        row_count = len(records)

        with BalanceXlsxWriter(all_headers, row_count) as writer:
            # Company header
            company = request.env.company
            ncols = len(all_headers)
            writer.worksheet.merge_range(
                0, 0, 0, ncols - 1,
                company.name,
                writer.styles.company_header,
            )
            writer.worksheet.merge_range(
                1, 0, 1, ncols - 1,
                'TAX BALANCE REPORT',
                writer.styles.report_title,
            )

            # Column headers at row 2
            data_start = writer.write_header(row=2)

            # Data rows
            row = data_start
            tax_sums = {t['id']: 0.0 for t in taxes}
            total_untaxed = 0.0
            total_grand = 0.0

            for rec in records:
                tax_amounts = rec.tax_amounts or {}
                col = 0

                writer.write_cell(row, col, rec.name or ''); col += 1
                writer.write_cell(row, col, rec.partner_id.name if rec.partner_id else ''); col += 1
                writer.write_cell(row, col, rec.date); col += 1
                writer.write_cell(row, col, rec.ref or ''); col += 1
                writer.write(row, col, rec.amount_untaxed, writer.styles.monetary); col += 1

                for tax in taxes:
                    amount = float(tax_amounts.get(str(tax['id']), 0.0))
                    tax_sums[tax['id']] += amount
                    writer.write(row, col, amount, writer.styles.monetary); col += 1

                writer.write(row, col, rec.amount_total, writer.styles.monetary)

                total_untaxed += rec.amount_untaxed
                total_grand += rec.amount_total
                row += 1

            # Totals row
            row += 1
            writer.write(row, 0, 'TOTAL', writer.styles.transaction_header)
            writer.write(row, 4, total_untaxed, writer.styles.monetary)
            for i, tax in enumerate(taxes):
                writer.write(row, 5 + i, tax_sums[tax['id']], writer.styles.monetary)
            writer.write(row, 5 + len(taxes), total_grand, writer.styles.monetary)

        return request.make_response(
            writer.value,
            headers=[
                ('Content-Disposition', content_disposition(self._filename() + '.xlsx')),
                ('Content-Type', self.CONTENT_TYPE),
            ],
        )
