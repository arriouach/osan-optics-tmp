from odoo import models


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    def _compute_analytic_distribution(self):
        super()._compute_analytic_distribution()
        if analytical_account_ids := self.env.context.get("analytical_account_ids"):
            for line in self.filtered(lambda x: x.account_id.account_type in ('income', 'expense', 'expense_direct_cost')):
                line.analytic_distribution = {str(analytical_account_id): 100 for analytical_account_id in analytical_account_ids}
