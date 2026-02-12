from odoo import api, fields, models

class PickingType(models.Model):
    _name = "stock.picking.type"
    _inherit = ["stock.picking.type", "limit.visibility.mixin"]
    _limit_domain = """
        ["|", ("user_ids", "in", [user.id]), ("user_ids", "=", False)]
    """

    user_ids = fields.Many2many("res.users", compute="_compute_user_ids", store=True)

    @api.depends(
        "default_location_src_id.user_ids",
        "default_location_dest_id.user_ids",
        "warehouse_id.user_ids",
    )
    def _compute_user_ids(self):
        for record in self:
            record.user_ids = (
                record.default_location_src_id.user_ids
                + record.default_location_dest_id.user_ids
                + record.warehouse_id.user_ids
            )


class Picking(models.Model):
    _name = "stock.picking"
    _inherit = ["stock.picking", "limit.visibility.mixin"]
    _limit_domain = """
        ["|", ("user_ids", "in", [user.id]), ("user_ids", "=", False)]
    """

    user_ids = fields.Many2many("res.users", compute="_compute_user_ids", store=True)

    @api.depends("location_id.user_ids", "location_dest_id.user_ids")
    def _compute_user_ids(self):
        for record in self:
            record.user_ids = (
                record.location_id.user_ids + record.location_dest_id.user_ids
            )

    def default_get(self, fields_list):
        self = self.with_context(limit_visibility=not self.env.user.has_group("base.group_system"))
        return super(Picking, self).default_get(fields_list)

    def _get_next_transfers(self):
        next_pickings = super()._get_next_transfers()
        return next_pickings.filtered(lambda p: self.env.user in p.location_dest_id.user_ids)
