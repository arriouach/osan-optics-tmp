from odoo import api, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    @api.model
    def _load_pos_data_fields(self, config_id):
        fields = super()._load_pos_data_fields(config_id)
        fields.extend(
            [
                'can_refund',
                'can_discount',
                'can_change_price',
                'can_see_cost_margin',
                'can_change_quantity',
                'can_remove_line',
                'can_change_price_list',
            ]
        )
        return fields
