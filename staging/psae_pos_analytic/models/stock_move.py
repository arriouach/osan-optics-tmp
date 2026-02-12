from odoo import models


class StockMove(models.Model):
    _inherit = "stock.move"

    def _generate_valuation_lines_data(
        self, partner_id, qty, debit_value, credit_value, debit_account_id, credit_account_id, svl_id, description
    ):
        rslt = super()._generate_valuation_lines_data(
            partner_id, qty, debit_value, credit_value, debit_account_id, credit_account_id, svl_id, description
        )
        svl = self.env["stock.valuation.layer"].browse(svl_id)
        analytical_account_ids = svl.stock_move_id.picking_id.pos_order_id.config_id.analytic_account_ids.ids
        if not analytical_account_ids:
            return rslt
        account_domain = ("expense", "expense_direct_cost")
        if self.env["account.account"].browse(rslt["debit_line_vals"]["account_id"]).account_type in account_domain:
            rslt["debit_line_vals"]["analytic_distribution"] = {
                str(analytical_account_id): 100 for analytical_account_id in analytical_account_ids
            }
        if self.env["account.account"].browse(rslt["credit_line_vals"]["account_id"]).account_type in account_domain:
            rslt["credit_line_vals"]["analytic_distribution"] = {
                str(analytical_account_id): 100 for analytical_account_id in analytical_account_ids
            }
        return rslt
