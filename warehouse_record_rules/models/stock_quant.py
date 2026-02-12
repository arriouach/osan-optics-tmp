from odoo import api, models


class Quant(models.Model):
    _inherit = "stock.quant"

    @api.model
    def _get_quants_action(self, domain=None, extend=False):
        if not self.env.user.has_group("base.group_system"):
            domain = (domain or []) + [
                "|",
                ("location_id.user_ids", "in", [self.env.user.id]),
                ("location_id.user_ids", "=", False),
            ]
        return super()._get_quants_action(domain, extend)

    def action_view_inventory(self):
        action = super().action_view_inventory()
        if not self.env.user.has_group("base.group_system"):
            ndomain = [
                "|",
                ("location_id.user_ids", "in", [self.env.user.id]),
                ("location_id.user_ids", "=", False),
            ]
            action["domain"] += ndomain
        return action

    def _set_view_context(self):
        self = self.with_context(limit_visibility=not self.env.user.has_group("base.group_system"))
        return super(Quant, self)._set_view_context()

    @api.onchange('product_id', 'company_id')
    def _onchange_product_id(self):
        self = self.with_context(limit_visibility=not self.env.user.has_group("base.group_system"))
        return super(Quant, self)._onchange_product_id()
