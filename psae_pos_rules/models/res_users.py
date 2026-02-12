from odoo import api, fields, models


class Users(models.Model):
    _inherit = "res.users"

    pos_config_ids = fields.Many2many("pos.config", string="Allowed PoS Shops")

    @api.model
    def _get_invalidation_fields(self):
        return {
            'pos_config_ids',
            *super()._get_invalidation_fields()
        }
