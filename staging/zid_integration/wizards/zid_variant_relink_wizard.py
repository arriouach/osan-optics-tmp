from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class ZidVariantRelinkWizard(models.TransientModel):
    _name = 'zid.variant.relink.wizard'
    _description = 'Relink Zid Variant with Odoo Product'

    zid_variant_id = fields.Many2one(
        'zid.variant',
        string='Zid Variant',
        required=True,
        readonly=True
    )
    
    current_product_id = fields.Many2one(
        'product.product',
        string='Current Linked Product',
        readonly=True
    )
    
    new_product_id = fields.Many2one(
        'product.product',
        string='New Product to Link',
        required=True,
        help='Select the Odoo product to link with this Zid variant'
    )
    
    relink_stock_lines = fields.Boolean(
        string='Create Variant Lines',
        default=True,
        help='Create variant lines for each stock location'
    )
    
    show_warning = fields.Boolean(
        string='Show Warning',
        compute='_compute_show_warning'
    )
    
    warning_message = fields.Text(
        string='Warning',
        compute='_compute_show_warning'
    )
    
    # Display fields
    variant_sku = fields.Char(
        related='zid_variant_id.sku',
        string='Variant SKU',
        readonly=True
    )
    
    variant_name = fields.Char(
        related='zid_variant_id.display_name',
        string='Variant Name',
        readonly=True
    )
    
    stock_locations_count = fields.Integer(
        string='Stock Locations',
        compute='_compute_stock_info'
    )
    
    existing_lines_count = fields.Integer(
        string='Existing Lines',
        compute='_compute_stock_info'
    )
    
    @api.depends('current_product_id', 'new_product_id')
    def _compute_show_warning(self):
        for wizard in self:
            warning_parts = []
            
            # Check if current product has variant lines
            if wizard.current_product_id:
                existing_lines = self.env['zid.variant.line'].search_count([
                    ('product_id', '=', wizard.current_product_id.id),
                    ('zid_variant_id', '=', wizard.zid_variant_id.id)
                ])
                if existing_lines:
                    warning_parts.append(
                        _('This will remove %d variant lines from product "%s"') % 
                        (existing_lines, wizard.current_product_id.display_name)
                    )
            
            # Check if new product already has other variant lines
            if wizard.new_product_id:
                other_lines = self.env['zid.variant.line'].search_count([
                    ('product_id', '=', wizard.new_product_id.id),
                    ('zid_variant_id', '!=', wizard.zid_variant_id.id)
                ])
                if other_lines:
                    warning_parts.append(
                        _('Product "%s" already has %d variant lines from other Zid variants') % 
                        (wizard.new_product_id.display_name, other_lines)
                    )
            
            wizard.show_warning = bool(warning_parts)
            wizard.warning_message = '\n• '.join(warning_parts) if warning_parts else ''
    
    @api.depends('zid_variant_id')
    def _compute_stock_info(self):
        for wizard in self:
            wizard.stock_locations_count = len(wizard.zid_variant_id.stock_line_ids)
            wizard.existing_lines_count = self.env['zid.variant.line'].search_count([
                ('zid_variant_id', '=', wizard.zid_variant_id.id)
            ])
    
    @api.onchange('new_product_id')
    def _onchange_new_product_id(self):
        """Check for potential conflicts when selecting new product"""
        if self.new_product_id and self.zid_variant_id:
            # Check if product already linked to another Zid variant
            other_variant = self.env['zid.variant'].search([
                ('odoo_product_id', '=', self.new_product_id.id),
                ('id', '!=', self.zid_variant_id.id)
            ], limit=1)
            
            if other_variant:
                return {
                    'warning': {
                        'title': _('Product Already Linked'),
                        'message': _(
                            'This product is already linked to another Zid variant:\n'
                            '- Variant: %s\n'
                            '- SKU: %s\n\n'
                            'Linking it here will remove it from the other variant.'
                        ) % (other_variant.display_name, other_variant.sku)
                    }
                }
    
    def action_relink(self):
        """Execute the relinking process"""
        self.ensure_one()
        
        if not self.new_product_id:
            raise ValidationError(_('Please select a product to link'))
        
        if self.new_product_id == self.current_product_id:
            raise ValidationError(_('Please select a different product'))
        
        # Call the relink method on the variant with the new product ID
        return self.zid_variant_id.with_context(skip_wizard=True).relink_with_product(self.new_product_id.id)
    
    def action_cancel(self):
        """Cancel and close wizard"""
        return {'type': 'ir.actions.act_window_close'}


class ZidVariantBulkRelinkWizard(models.TransientModel):
    _name = 'zid.variant.bulk.relink.wizard'
    _description = 'Bulk Relink Zid Variants'
    
    line_ids = fields.One2many(
        'zid.variant.bulk.relink.line',
        'wizard_id',
        string='Variants to Relink'
    )
    
    auto_match_by_sku = fields.Boolean(
        string='Auto-match by SKU',
        default=True,
        help='Automatically match variants to products by SKU/Internal Reference'
    )
    
    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        
        # Get selected variants from context
        variant_ids = self.env.context.get('active_ids', [])
        if variant_ids:
            lines = []
            for variant in self.env['zid.variant'].browse(variant_ids):
                lines.append((0, 0, {
                    'variant_id': variant.id,
                    'current_product_id': variant.odoo_product_id.id if variant.odoo_product_id else False,
                }))
            res['line_ids'] = lines
        
        return res
    
    def action_auto_match(self):
        """Auto-match variants to products by SKU"""
        self.ensure_one()
        
        matched_count = 0
        for line in self.line_ids:
            if not line.new_product_id and line.variant_id.sku:
                # Try to find product by SKU
                product = self.env['product.product'].search([
                    ('default_code', '=', line.variant_id.sku)
                ], limit=1)
                
                if not product:
                    # Try barcode
                    product = self.env['product.product'].search([
                        ('barcode', '=', line.variant_id.sku)
                    ], limit=1)
                
                if product:
                    line.new_product_id = product
                    matched_count += 1
        
        if matched_count:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Auto-match Complete'),
                    'message': _('Matched %d variants to products') % matched_count,
                    'type': 'success',
                    'sticky': False,
                }
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('No Matches Found'),
                    'message': _('Could not find any products matching the variant SKUs'),
                    'type': 'warning',
                    'sticky': False,
                }
            }
    
    def action_relink_all(self):
        """Relink all variants"""
        self.ensure_one()
        
        # Prepare mapping
        product_mapping = {}
        skipped_lines = []
        
        for line in self.line_ids:
            if line.new_product_id:
                product_mapping[line.variant_id.id] = line.new_product_id.id
            else:
                skipped_lines.append(line.variant_id.display_name)
        
        if not product_mapping:
            raise ValidationError(_('Please select at least one product to link'))
        
        # Execute bulk relink
        variant_model = self.env['zid.variant']
        results = variant_model.bulk_relink_variants(
            list(product_mapping.keys()),
            product_mapping
        )
        
        # Prepare result message
        message_parts = []
        if results['success']:
            message_parts.append(_('Successfully relinked %d variants') % len(results['success']))
        if results['failed']:
            message_parts.append(_('Failed to relink %d variants') % len(results['failed']))
        if skipped_lines:
            message_parts.append(_('Skipped %d variants (no product selected)') % len(skipped_lines))
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Bulk Relink Complete'),
                'message': ' | '.join(message_parts),
                'type': 'success' if not results['failed'] else 'warning',
                'sticky': True,
            }
        }


class ZidVariantBulkRelinkLine(models.TransientModel):
    _name = 'zid.variant.bulk.relink.line'
    _description = 'Bulk Relink Line'
    
    wizard_id = fields.Many2one(
        'zid.variant.bulk.relink.wizard',
        string='Wizard',
        required=True,
        ondelete='cascade'
    )
    
    variant_id = fields.Many2one(
        'zid.variant',
        string='Zid Variant',
        required=True,
        readonly=True
    )
    
    variant_sku = fields.Char(
        related='variant_id.sku',
        string='SKU',
        readonly=True
    )
    
    variant_name = fields.Char(
        related='variant_id.display_name',
        string='Variant',
        readonly=True
    )
    
    current_product_id = fields.Many2one(
        'product.product',
        string='Current Product',
        readonly=True
    )
    
    new_product_id = fields.Many2one(
        'product.product',
        string='New Product',
        help='Select product to link with this variant'
    )
    
    stock_locations = fields.Integer(
        string='Locations',
        compute='_compute_stock_info'
    )
    
    @api.depends('variant_id')
    def _compute_stock_info(self):
        for line in self:
            line.stock_locations = len(line.variant_id.stock_line_ids)
