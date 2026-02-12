from odoo import models


class StockWarehouseOrderpoint(models.Model):
    _name = "stock.warehouse.orderpoint"
    _inherit = ["stock.warehouse.orderpoint", "limit.visibility.mixin"]
    _limit_domain = """
        [
            "|",
            ("location_id.user_ids", "in", [user.id]),
            ("location_id.user_ids", "=", False),
        ]
    """

    def _compute_warehouse_id(self):
        self = self.with_context(limit_visibility=not self.env.user.has_group("base.group_system"))
        super(StockWarehouseOrderpoint, self)._compute_warehouse_id()

    def _compute_location_id(self):
        self = self.with_context(limit_visibility=not self.env.user.has_group("base.group_system"))
        super(StockWarehouseOrderpoint, self)._compute_location_id()

    def _compute_allowed_location_ids(self):
        self = self.with_context(limit_visibility=not self.env.user.has_group("base.group_system"))
        super(StockWarehouseOrderpoint, self)._compute_allowed_location_ids()
