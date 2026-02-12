from odoo import api, fields, models


class Location(models.Model):
    _name = "stock.location"
    _inherit = ["stock.location", "limit.visibility.mixin"]
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

    @api.depends("warehouse_id.user_ids", "usage")
    def _compute_user_ids(self):
        for location in self:
            location.user_ids = (
                location.warehouse_id.user_ids
                if location.usage in ("internal", "view")
                else False
            )
