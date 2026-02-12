from odoo.addons.web.controllers.export import CSVExport, ExcelExport
from odoo.http import request
import json


class ExtendedCSVExport(CSVExport):
    def base(self, data):
        params = json.loads(data)
        params["context"] = {
            "limit_visibility": not request.env.user.sudo().has_group(
                "base.group_system"
            ),
            **params.get("context", {}),
        }
        return super().base(json.dumps(params))


class ExtendedExcelExport(ExcelExport):
    def base(self, data):
        params = json.loads(data)
        params["context"] = {
            "limit_visibility": not request.env.user.sudo().has_group(
                "base.group_system"
            ),
            **params.get("context", {}),
        }
        return super().base(json.dumps(params))
