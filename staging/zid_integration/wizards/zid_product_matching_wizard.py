# -*- coding: utf-8 -*-

from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class ZidProductMatchingWizard(models.TransientModel):
    _name = 'zid.product.matching.wizard'
    _description = 'Zid Product Matching Configuration Wizard'

    connector_id = fields.Many2one('zid.connector', string='Zid Connector', required=True)
    
    # Current settings (readonly)
    current_priority = fields.Selection(related='connector_id.product_match_priority', readonly=True)
    current_method = fields.Selection(related='connector_id.product_match_by', readonly=True)
    
    # New settings
    new_priority = fields.Selection([
        ('mapping_first', 'Zid Mapping First (Recommended)'),
        ('direct_only', 'Direct SKU/Barcode Only'),
        ('mapping_only', 'Zid Mapping Only')
    ], string='New Product Matching Priority', required=True)
    
    new_method = fields.Selection([
        ('sku', 'Match by SKU'),
        ('barcode', 'Match by Barcode'),
        ('name', 'Match by Name'),
        ('create_if_not_found', 'Create if Not Found')
    ], string='New Product Matching Method', required=True)
    
    # Statistics
    total_zid_products = fields.Integer(string='Total Zid Products', compute='_compute_statistics')
    mapped_zid_products = fields.Integer(string='Mapped Zid Products', compute='_compute_statistics')
    total_odoo_products = fields.Integer(string='Total Odoo Products', compute='_compute_statistics')
    odoo_products_with_sku = fields.Integer(string='Odoo Products with SKU', compute='_compute_statistics')
    odoo_products_with_barcode = fields.Integer(string='Odoo Products with Barcode', compute='_compute_statistics')
    
    recommendation = fields.Html(string='Recommendation', compute='_compute_recommendation')

    @api.depends('connector_id')
    def _compute_statistics(self):
        for record in self:
            if record.connector_id:
                # Zid products
                zid_products = self.env['zid.product'].search([('zid_connector_id', '=', record.connector_id.id)])
                mapped_products = zid_products.filtered('odoo_product_id')
                
                # Odoo products (simplified - no company filter)
                odoo_products = self.env['product.product'].search([])
                products_with_sku = odoo_products.filtered('default_code')
                products_with_barcode = odoo_products.filtered('barcode')
                
                record.total_zid_products = len(zid_products)
                record.mapped_zid_products = len(mapped_products)
                record.total_odoo_products = len(odoo_products)
                record.odoo_products_with_sku = len(products_with_sku)
                record.odoo_products_with_barcode = len(products_with_barcode)
            else:
                record.total_zid_products = 0
                record.mapped_zid_products = 0
                record.total_odoo_products = 0
                record.odoo_products_with_sku = 0
                record.odoo_products_with_barcode = 0

    @api.depends('new_priority', 'new_method', 'total_zid_products', 'mapped_zid_products', 'odoo_products_with_sku', 'odoo_products_with_barcode')
    def _compute_recommendation(self):
        for record in self:
            html = "<div class='alert alert-info'>"
            
            if record.new_priority == 'mapping_first':
                html += "<h5>✓ Recommended Strategy</h5>"
                html += "<p>This strategy tries Zid product mappings first, then falls back to SKU/Barcode matching. This gives you the best of both worlds.</p>"
                
                if record.mapped_zid_products < record.total_zid_products:
                    unmapped = record.total_zid_products - record.mapped_zid_products
                    html += f"<p><strong>Note:</strong> You have {unmapped} unmapped Zid products. They will use SKU/Barcode matching.</p>"
                
            elif record.new_priority == 'direct_only':
                html += "<h5>⚠ Direct Matching Only</h5>"
                html += "<p>This strategy ignores all Zid product mappings and only uses SKU/Barcode matching.</p>"
                
                if record.new_method == 'sku' and record.odoo_products_with_sku == 0:
                    html += "<p class='text-danger'><strong>Warning:</strong> No Odoo products have SKU set, but you selected SKU matching!</p>"
                elif record.new_method == 'barcode' and record.odoo_products_with_barcode == 0:
                    html += "<p class='text-danger'><strong>Warning:</strong> No Odoo products have Barcode set, but you selected Barcode matching!</p>"
                
            elif record.new_priority == 'mapping_only':
                html += "<h5>⚠ Mapping Only</h5>"
                html += "<p>This strategy only uses Zid product mappings. Products without mappings will be skipped.</p>"
                
                if record.mapped_zid_products < record.total_zid_products:
                    unmapped = record.total_zid_products - record.mapped_zid_products
                    html += f"<p class='text-danger'><strong>Warning:</strong> {unmapped} Zid products are not mapped and will be skipped in orders!</p>"
            
            html += "</div>"
            record.recommendation = html

    @api.onchange('connector_id')
    def _onchange_connector_id(self):
        if self.connector_id:
            self.new_priority = self.connector_id.product_match_priority
            self.new_method = self.connector_id.product_match_by

    def action_apply_settings(self):
        """Apply the new product matching settings"""
        if self.connector_id:
            self.connector_id.write({
                'product_match_priority': self.new_priority,
                'product_match_by': self.new_method,
            })
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Settings Applied',
                    'message': f'Product matching strategy updated to: {dict(self._fields["new_priority"].selection)[self.new_priority]}',
                    'type': 'success',
                    'sticky': False,
                }
            }

    def action_test_matching(self):
        """Test the current matching strategy with recent orders"""
        # This could be expanded to actually test matching logic
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Test Complete',
                'message': 'Check the logs for detailed matching results.',
                'type': 'info',
                'sticky': True,
            }
        }