from odoo import api, fields, models


class StockScrap(models.Model):
    _name = "stock.scrap"
    _inherit = ["stock.scrap", "limit.visibility.mixin"]
    _limit_domain = """
        ["|", ("user_ids", "in", [user.id]), ("user_ids", "=", False)]
    """

    user_ids = fields.Many2many(
        "res.users",
        compute="_compute_user_ids",
        string="Allowed Users",
        store=True,
        readonly=False,
    )

    @api.depends("location_id.user_ids")
    def _compute_user_ids(self):
        for scrap in self:
            scrap.user_ids = scrap.location_id.user_ids

    def _compute_location_id(self):
        return super(StockScrap, self.with_context(limit_visibility=not self.env.user.has_group("base.group_system")))._compute_location_id()
