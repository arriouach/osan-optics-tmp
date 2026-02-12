from odoo import fields, models


class Warehouse(models.Model):
    _name = "stock.warehouse"
    _inherit = ["stock.warehouse", "limit.visibility.mixin"]
    _limit_domain = """
        ["|", ("user_ids", "in", [user.id]), ("user_ids", "=", False)]
    """

    user_ids = fields.Many2many("res.users", string="Allowed Users")

    def get_current_warehouses(self):
        self = self.with_context(
            limit_visibility=not self.env.user.has_group("base.group_system")
        )
        return super(Warehouse, self).get_current_warehouses()
