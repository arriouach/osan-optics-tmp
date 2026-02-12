# -*- coding: utf-8 -*-
from odoo import models, fields, api

class ZidLocationLine(models.Model):
    _name = 'zid.location.line'
    _description = 'Zid Product Location Line'
    _rec_name = 'location_id'
    
    # Relations
    product_id = fields.Many2one(
        'zid.product',
        string='Zid Product',
        required=True,
        ondelete='cascade'
    )
    
    location_id = fields.Many2one(
        'zid.location',
        string='Zid Location',
        required=True
    )
    
    # Stock Information
    quantity = fields.Float(
        string='Available Quantity',
        default=0.0
    )
    
    is_infinite = fields.Boolean(
        string='Infinite Stock',
        default=False,
        help='If checked, this location has unlimited stock'
    )
    
    # Additional fields from API
    stock_id = fields.Char(
        string='Stock ID',
        help='Stock ID from Zid API'
    )
    
    location_type = fields.Char(
        string='Location Type',
        related='location_id.location_type',
        store=True
    )
    
    # Computed fields for display
    display_quantity = fields.Char(
        string='Stock Status',
        compute='_compute_display_quantity'
    )
    
    @api.depends('quantity', 'is_infinite')
    def _compute_display_quantity(self):
        for line in self:
            if line.is_infinite:
                line.display_quantity = 'Unlimited'
            else:
                line.display_quantity = f"{line.quantity:.0f} units"
    
    # Unique constraint to prevent duplicate location lines for same product
    _sql_constraints = [
        ('unique_product_location', 
         'UNIQUE(product_id, location_id)', 
         'A product can only have one stock entry per location!')
    ]
