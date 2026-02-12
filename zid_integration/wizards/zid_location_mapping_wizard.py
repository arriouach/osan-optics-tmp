from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class ZidLocationMappingWizard(models.TransientModel):
    _name = 'zid.location.mapping.wizard'
    _description = 'Setup Location Mapping for Zid Stock Sync'

    product_id = fields.Many2one(
        'product.template',
        string='Product',
        required=True,
        readonly=True
    )

    zid_connector_id = fields.Many2one(
        'zid.connector',
        string='Zid Connector',
        related='product_id.zid_connector_id',
        readonly=True
    )

    mapping_line_ids = fields.One2many(
        'zid.location.mapping.wizard.line',
        'wizard_id',
        string='Location Mappings'
    )

    @api.model
    def default_get(self, fields_list):
        """Load existing mappings"""
        result = super().default_get(fields_list)
        
        if self.env.context.get('active_id'):
            product = self.env['product.template'].browse(self.env.context['active_id'])
            result['product_id'] = product.id
            
            # Load existing mappings
            existing_mappings = self.env['zid.location.mapping'].search([
                ('product_id', '=', product.id)
            ])
            
            mapping_lines = []
            for mapping in existing_mappings:
                mapping_lines.append((0, 0, {
                    'odoo_location_id': mapping.odoo_location_id.id,
                    'zid_location_id': mapping.zid_location_id.id,
                    'is_active': mapping.is_active,
                    'existing_mapping_id': mapping.id,
                }))
            
            result['mapping_line_ids'] = mapping_lines
            
        return result

    def action_save_mappings(self):
        """Save location mappings"""
        self.ensure_one()
        
        # Delete removed mappings
        existing_ids = self.mapping_line_ids.filtered('existing_mapping_id').mapped('existing_mapping_id')
        all_existing = self.env['zid.location.mapping'].search([
            ('product_id', '=', self.product_id.id)
        ])
        to_delete = all_existing - existing_ids
        to_delete.unlink()
        
        # Create or update mappings
        for line in self.mapping_line_ids:
            if line.existing_mapping_id:
                # Update existing
                line.existing_mapping_id.write({
                    'odoo_location_id': line.odoo_location_id.id,
                    'zid_location_id': line.zid_location_id.id,
                    'is_active': line.is_active,
                })
            else:
                # Create new
                self.env['zid.location.mapping'].create({
                    'product_id': self.product_id.id,
                    'odoo_location_id': line.odoo_location_id.id,
                    'zid_location_id': line.zid_location_id.id,
                    'is_active': line.is_active,
                })
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Location mappings saved successfully'),
                'type': 'success',
            }
        }


class ZidLocationMappingWizardLine(models.TransientModel):
    _name = 'zid.location.mapping.wizard.line'
    _description = 'Location Mapping Line'

    wizard_id = fields.Many2one('zid.location.mapping.wizard', required=True)
    
    odoo_location_id = fields.Many2one(
        'stock.location',
        string='Odoo Location',
        required=True,
        domain=[('usage', '=', 'internal')]
    )
    
    zid_location_id = fields.Many2one(
        'zid.location',
        string='Zid Location',
        required=True
    )
    
    is_active = fields.Boolean(
        string='Active',
        default=True
    )
    
    existing_mapping_id = fields.Many2one(
        'zid.location.mapping',
        string='Existing Mapping'
    )
    
    @api.onchange('wizard_id')
    def _onchange_wizard_id(self):
        """Set domain for zid locations"""
        if self.wizard_id and self.wizard_id.zid_connector_id:
            return {
                'domain': {
                    'zid_location_id': [
                        ('zid_connector_id', '=', self.wizard_id.zid_connector_id.id),
                        ('is_enabled', '=', True)
                    ]
                }
            }
