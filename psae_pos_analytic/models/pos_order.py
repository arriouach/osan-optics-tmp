from odoo import models


class PosOrder(models.Model):
    _inherit = 'pos.order'

    def _create_invoice(self, move_vals):
        return super(PosOrder, self.with_context(analytical_account_ids=self.config_id.analytic_account_ids.ids))._create_invoice(move_vals)

    def _create_misc_reversal_move(self, payment_moves):
        return super(PosOrder, self.with_context(analytical_account_ids=self.config_id.analytic_account_ids.ids))._create_misc_reversal_move(payment_moves)
