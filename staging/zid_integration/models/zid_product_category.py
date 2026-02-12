from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class ZidProductCategory(models.Model):
    _name = 'zid.product.category'
    _description = 'Zid Product Category'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'display_name'
    _parent_name = 'parent_id'
    _parent_store = True
    _order = 'sequence, name_en'

    # Connection
    zid_connector_id = fields.Many2one(
        'zid.connector',
        string='Zid Connector',
        required=True,
        ondelete='cascade'
    )

    # Basic Info
    zid_category_id = fields.Char(
        string='Zid Category ID',
        required=True,
        index=True,
        help='ID of the category in Zid'
    )

    name_ar = fields.Char(
        string='Name (Arabic)',
        required=True,
        tracking=True
    )

    name_en = fields.Char(
        string='Name (English)',
        required=True,
        tracking=True
    )
    
    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True,
        recursive=True
    )

    # Hierarchy
    parent_id = fields.Many2one(
        'zid.product.category',
        string='Parent Category',
        index=True,
        ondelete='cascade'
    )
    
    parent_path = fields.Char(index=True, unaccent=False)
    
    child_ids = fields.One2many(
        'zid.product.category', 
        'parent_id', 
        string='Child Categories'
    )

    # Details
    description_ar = fields.Text(string='Description (Arabic)')
    description_en = fields.Text(string='Description (English)')
    
    image_url = fields.Char(string='Image URL')
    
    sequence = fields.Integer(string='Sequence', default=10)
    
    is_active = fields.Boolean(
        string='Is Active',
        default=True,
        tracking=True
    )

    # Odoo Mapping
    odoo_category_id = fields.Many2one(
        'product.public.category',
        string='Odoo Website Category',
        help='Mapped Odoo e-commerce category'
    )

    # Computed
    @api.depends('name_ar', 'name_en', 'parent_id.display_name')
    def _compute_display_name(self):
        for rec in self:
            name = rec.name_en or rec.name_ar
            if rec.parent_id:
                rec.display_name = f"{rec.parent_id.display_name} / {name}"
            else:
                rec.display_name = name

    # Constraints
    _sql_constraints = [
        ('unique_zid_category', 
         'UNIQUE(zid_connector_id, zid_category_id)', 
         'Zid Category ID must be unique per connector!')
    ]

    def action_sync_subcategories(self):
        """Sync subcategories for this category from Zid"""
        self.ensure_one()
        
        if not self.zid_connector_id.is_connected:
            raise UserError(_('Connector is not connected to Zid'))
        
        try:
            # Fetch category details including subcategories
            response = self.zid_connector_id.api_request(
                endpoint=f'categories/{self.zid_category_id}',
                method='GET'
            )
            
            if response and 'subcategories' in response:
                subcategories = response.get('subcategories', [])
                
                if not subcategories:
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': _('Info'),
                            'message': _('No subcategories found for this category'),
                            'type': 'info',
                        }
                    }
                
                # Create/update subcategories
                for subcat_data in subcategories:
                    self.create_or_update_from_zid(
                        subcat_data,
                        self.zid_connector_id.id,
                        parent_id=self.id
                    )
                
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Success'),
                        'message': _('Synced %d subcategories') % len(subcategories),
                        'type': 'success',
                    }
                }
            else:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Info'),
                        'message': _('No subcategories found or not supported by API'),
                        'type': 'info',
                    }
                }
                
        except Exception as e:
            _logger.error(f"Failed to sync subcategories: {str(e)}")
            raise UserError(_('Failed to sync subcategories: %s') % str(e))

    @api.model
    def create_or_update_from_zid(self, category_data, connector_id, parent_id=False):
        """Create or update category from Zid data recursively"""
        if not category_data.get('id'):
            return False

        zid_id = str(category_data.get('id'))
        
        # Prepare values
        vals = {
            'zid_connector_id': connector_id,
            'zid_category_id': zid_id,
            'name_ar': category_data.get('name_ar') or category_data.get('name', {}).get('ar', 'Unknown'),
            'name_en': category_data.get('name_en') or category_data.get('name', {}).get('en'),
            'description_ar': category_data.get('description_ar') or category_data.get('description', {}).get('ar'),
            'description_en': category_data.get('description_en') or category_data.get('description', {}).get('en'),
            'image_url': category_data.get('image', {}).get('url') if isinstance(category_data.get('image'), dict) else category_data.get('image'),
            'parent_id': parent_id,
            'sequence': category_data.get('display_order', 10)
        }
        
        # Fallback for name
        if not vals['name_en']:
            vals['name_en'] = vals['name_ar']

        # Find or Create
        category = self.search([
            ('zid_category_id', '=', zid_id),
            ('zid_connector_id', '=', connector_id)
        ], limit=1)

        if category:
            category.write(vals)
        else:
            category = self.create(vals)
            
        # Process subcategories recursively
        sub_categories = category_data.get('sub_categories', [])
        for sub_data in sub_categories:
            self.create_or_update_from_zid(sub_data, connector_id, parent_id=category.id)
            
        return category
