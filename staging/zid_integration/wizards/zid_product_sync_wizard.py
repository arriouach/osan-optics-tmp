from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ZidProductSyncWizard(models.TransientModel):
    _name = 'zid.product.sync.wizard'
    _description = 'Zid Product Sync Wizard'

    zid_connector_id = fields.Many2one('zid.connector', string='Zid Connector', required=True)
    sync_images = fields.Boolean(string='Sync Product Images', default=True)
    update_existing = fields.Boolean(string='Update Existing Products', default=True)

    def action_sync_products(self):
        """Sync products from Zid - delegates to products_connector wizard"""
        self.ensure_one()
        
        if not self.zid_connector_id.is_connected:
            raise UserError(_('Please connect to Zid first'))
        
        # Open the full products connector wizard with pre-filled values
        return {
            'type': 'ir.actions.act_window',
            'name': _('Import Products from Zid'),
            'res_model': 'zid.products.connector',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_zid_connector_id': self.zid_connector_id.id,
                'default_import_mode': 'new_and_update' if self.update_existing else 'new',
                'default_update_images': self.sync_images,
            }
        }
