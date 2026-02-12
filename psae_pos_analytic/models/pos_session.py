from odoo import models


class PosSession(models.Model):
    _inherit = 'pos.session'

    def _create_account_move(self, balancing_account=False, amount_to_balance=0, bank_payment_method_diffs=None):
        return super(PosSession, self.with_context(analytical_account_ids=self.config_id.analytic_account_ids.ids))._create_account_move(
            balancing_account, amount_to_balance, bank_payment_method_diffs)

    def _create_combine_account_payment(self, payment_method, amounts, diff_amount):
        return super(PosSession, self.with_context(analytical_account_ids=self.config_id.analytic_account_ids.ids))._create_combine_account_payment(payment_method, amounts, diff_amount)

    def _post_statement_difference(self, amount):
        return super(PosSession, self.with_context(analytical_account_ids=self.config_id.analytic_account_ids.ids))._post_statement_difference(amount)
