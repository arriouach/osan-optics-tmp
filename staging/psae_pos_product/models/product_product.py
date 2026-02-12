from odoo import api, fields, models


class Product(models.Model):
    _inherit = 'product.product'

    is_preselected_in_pos = fields.Boolean(string='Is preselected in PoS')
    hide_on_pos_receipt = fields.Boolean(string='Hide on PoS Receipt')

    @api.model
    def _load_pos_data_fields(self, config_id):
        return super()._load_pos_data_fields(config_id) + ['is_preselected_in_pos', 'hide_on_pos_receipt']
