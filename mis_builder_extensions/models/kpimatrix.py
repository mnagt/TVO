# Copyright 2026 Yaser Akhras
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

from collections import OrderedDict, defaultdict
from odoo.addons.mis_builder.models.kpimatrix import KpiMatrix


def __init__(self, env, multi_company=False, account_model="account.account"):
        # cache language id for faster rendering
        lang_model = env["res.lang"]
        self.lang = lang_model._lang_get(env.user.lang)
        self._style_model = env["mis.report.style"]
        self._account_model = env[account_model]
        # data structures
        # { kpi: KpiMatrixRow }
        self._kpi_rows = OrderedDict()
        # { kpi: {account_id: KpiMatrixRow} }
        self._detail_rows = {}
        # { col_key: KpiMatrixCol }
        self._cols = OrderedDict()
        # { col_key (left of comparison): [(col_key, base_col_key)] }
        self._comparison_todo = defaultdict(list)
        # { col_key (left of sum): (col_key, [(sign, sum_col_key)])
        self._sum_todo = {}
        # { account_id: account_name }
        self._account_names = {}
        self._multi_company = multi_company
        self._env = env


def _get_account_name(self, account):
    result = f"{account.code} {account.name}"
    if not account.code:
        account = account.with_company(account.company_ids[0])
        result = f"{account.code} {account.name}"
    if self._multi_company and account.company_ids and len(self._env.companies) > 1:
        company_names = ", ".join(account.company_ids.mapped("name"))
        result = f"{result} [{company_names}]"
    return result
    
KpiMatrix._get_account_name = _get_account_name
KpiMatrix.__init__ = __init__