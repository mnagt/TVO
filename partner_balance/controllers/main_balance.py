# -*- coding: utf-8 -*-
"""Excel export controller for partner balance reports."""

import json
import operator
import functools
import logging
import werkzeug

from odoo import http
from odoo.http import content_disposition, request, serialize_exception as _serialize_exception
from odoo.tools import osutil
from odoo.addons.web.controllers.export import (
    ExportFormat as BaseExportFormat,
    GroupsTreeNode as BaseGroupsTreeNode,
)

from ..services.balance_export import (
    BalanceDataService,
    BalanceXlsxWriter,
    GroupedBalanceXlsxWriter,
    FieldMapping,
)

_logger = logging.getLogger(__name__)


def serialize_exception(f):
    """Decorator to serialize exceptions as JSON responses."""
    @functools.wraps(f)
    def wrap(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            _logger.exception("An exception occurred during an http request")
            se = _serialize_exception(e)
            error = {
                'code': 200,
                'message': "Odoo Server Error",
                'data': se
            }
            return werkzeug.exceptions.InternalServerError(json.dumps(error))
    return wrap


class BalanceExcelExport(BaseExportFormat, http.Controller):
    """Controller for exporting partner balance data to Excel."""

    @http.route('/web/balance_export/xlsx', type='http', auth="user")
    @serialize_exception
    def index(self, data):
        return self.base(data)

    @property
    def content_type(self):
        return 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

    @property
    def extension(self):
        return '.xlsx'

    def base(self, data):
        """Main export handler."""
        params = json.loads(data)
        model, fields, ids, domain, import_compat = operator.itemgetter(
            'model', 'fields', 'ids', 'domain', 'import_compat'
        )(params)

        Model = request.env[model].with_context(
            import_compat=import_compat,
            **params.get('context', {})
        )

        if not Model._is_an_ordinary_table():
            fields = [f for f in fields if f['name'] != 'id']

        field_names = [f['name'] for f in fields]
        columns_headers = (
            field_names if import_compat
            else [f['label'].strip() for f in fields]
        )

        groupby = params.get('groupby')

        if not import_compat and groupby:
            response_data = self._export_grouped(Model, fields, field_names, ids, domain, groupby, params)
        else:
            response_data = self._export_flat(Model, field_names, columns_headers, ids, domain, params)

        return request.make_response(
            response_data,
            headers=[
                ('Content-Disposition', content_disposition(
                    osutil.clean_filename(self.filename(model) + self.extension)
                )),
                ('Content-Type', self.content_type),
            ],
        )

    def _export_flat(self, Model, field_names, columns_headers, ids, domain, params):
        """Export non-grouped data."""
        records = Model.browse(ids) if ids else Model.search(domain, offset=0, limit=False, order=False)
        export_data = records.export_data(field_names).get('datas', [])

        ctx = params.get('context', {})
        data_service = BalanceDataService.from_params(request.env, params)

        show_products = ctx.get('show_products', False)
        product_lines_by_move = {}

        if show_products:
            # Get all move_ids from records that are invoices
            invoice_types = ('out_invoice', 'in_invoice', 'out_refund', 'in_refund')
            move_ids = records.filtered(
                lambda r: r.type_key in invoice_types
            ).mapped('move_id').ids

            if move_ids:
                aml = request.env['account.move.line'].sudo().search([
                    ('move_id', 'in', move_ids),
                    ('display_type', '=', 'product'),
                ])
                for line in aml:
                    product_lines_by_move.setdefault(line.move_id.id, []).append(line)

        opening_data = data_service.get_opening_balance()

        with BalanceXlsxWriter(columns_headers, len(export_data)) as writer:
            writer.write_metadata(ctx, data_service)

            # Write opening balance
            if opening_data['balance'] != 0.0:
                period_start_row, opening_debit, opening_credit = writer.write_opening_balance_row(
                    FieldMapping.DATA_START_ROW, opening_data
                )
            else:
                period_start_row = FieldMapping.DATA_START_ROW
                opening_debit = opening_credit = 0
                opening_data['balance'] = 0.0

            # Write data rows
            writer.write_data_rows(period_start_row, export_data, opening_data['balance'],
                        product_lines=product_lines_by_move, records=records)

            product_row_count = sum(len(v) + 1 for v in product_lines_by_move.values())  # +1 for header per group
            # Write totals
            totals_row = period_start_row + len(export_data) + product_row_count + 1
            writer.write_totals(totals_row, export_data, opening_debit, opening_credit)

        return writer.value

    def _export_grouped(self, Model, fields, field_names, ids, domain, groupby, params):
        """Export grouped data."""
        groupby_type = [Model._fields[x.split(':')[0]].type for x in groupby]
        domain = [('id', 'in', ids)] if ids else domain

        groups_data = Model.read_group(
            domain,
            [x if x != '.id' else 'id' for x in field_names],
            groupby,
            lazy=False
        )

        tree = BaseGroupsTreeNode(Model, field_names, groupby, groupby_type)
        for leaf in groups_data:
            tree.insert_leaf(leaf)

        ctx = params.get('context', {})
        data_service = BalanceDataService.from_params(request.env, params)

        show_products = ctx.get('show_products', False)
        product_lines_by_move = {}

        if show_products:
            # For grouped export, search records from domain to get move_ids
            invoice_types = ('out_invoice', 'in_invoice', 'out_refund', 'in_refund')
            all_records = Model.search(domain, offset=0, limit=False, order=False)
            move_ids = all_records.filtered(
                lambda r: r.type_key in invoice_types
            ).mapped('move_id').ids

            if move_ids:
                aml = request.env['account.move.line'].sudo().search([
                    ('move_id', 'in', move_ids),
                    ('display_type', '=', 'product'),
                ])
                for line in aml:
                    product_lines_by_move.setdefault(line.move_id.id, []).append(line)

        # Determine groupby field
        groupby_field = groupby[0].split(':')[0] if groupby else ''

        # Calculate opening balances for each group
        opening_balances = data_service.get_opening_balances_by_group(tree, groupby_field)

        # Update running balances
        data_service.update_group_running_balances(tree, opening_balances)

        with GroupedBalanceXlsxWriter(fields, tree.count) as writer:
            summary = data_service.get_period_summary(tree)
            opening_data = data_service.get_opening_balance()

            writer.write_metadata(ctx, data_service, summary)


            # Write groups starting at row 9
            x, y = 9, 0
            for group_name, group in tree.children.items():
                x, y = writer.write_group(x, y, group_name, group, opening_balances)

        return writer.value
