from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class ZidVariantStockLine(models.Model):
    _name = 'zid.variant.stock.line'
    _description = 'Zid Variant Stock by Location'
    _rec_name = 'display_name'
    _order = 'variant_id, location_id'

    # ==================== Relations ====================
    variant_id = fields.Many2one(
        'zid.variant',
        string='Variant',
        required=True,
        ondelete='cascade',
        index=True
    )

    location_id = fields.Many2one(
        'zid.location',
        string='Location',
        required=True,
        index=True
    )

    # ==================== Stock Information ====================
    stock_id = fields.Char(
        string='Stock ID',
        help='Stock ID from Zid API',
        readonly=True
    )

    available_quantity = fields.Float(
        string='Available Quantity',
        default=0.0,
        digits='Product Unit of Measure'
    )

    is_infinite = fields.Boolean(
        string='Infinite Stock',
        default=False,
        help='If checked, this location has unlimited stock'
    )

    # ==================== Related Fields ====================
    connector_id = fields.Many2one(
        related='variant_id.zid_connector_id',
        string='Connector',
        store=True,
        readonly=True
    )

    parent_product_id = fields.Many2one(
        related='variant_id.parent_product_id',
        string='Parent Product',
        store=True,
        readonly=True
    )

    location_type = fields.Char(
        related='location_id.location_type',
        string='Location Type',
        store=True,
        readonly=True
    )

    location_name = fields.Char(
        related='location_id.display_name',
        string='Location Name',
        readonly=True
    )

    is_default_location = fields.Boolean(
        related='location_id.is_default',
        string='Is Default Location',
        readonly=True
    )

    variant_sku = fields.Char(
        related='variant_id.sku',
        string='Variant SKU',
        store=True,
        readonly=True
    )

    variant_name = fields.Char(
        related='variant_id.display_name',
        string='Variant Name',
        readonly=True
    )

    # ==================== Computed Fields ====================
    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True
    )

    display_quantity = fields.Char(
        string='Stock Status',
        compute='_compute_display_quantity'
    )

    stock_level = fields.Selection([
        ('out_of_stock', 'Out of Stock'),
        ('low', 'Low Stock'),
        ('medium', 'Medium Stock'),
        ('high', 'High Stock'),
        ('infinite', 'Unlimited')
    ], string='Stock Level', compute='_compute_stock_level', store=True)

    # ==================== Status Fields ====================
    is_active = fields.Boolean(
        string='Active',
        default=True
    )

    last_update = fields.Datetime(
        string='Last Update',
        default=fields.Datetime.now
    )

    # ==================== Computed Methods ====================
    @api.depends('variant_id', 'location_id')
    def _compute_display_name(self):
        for line in self:
            variant_name = line.variant_id.display_name or 'Unknown Variant'
            location_name = line.location_id.display_name or 'Unknown Location'
            line.display_name = f"{variant_name} @ {location_name}"

    @api.depends('available_quantity', 'is_infinite')
    def _compute_display_quantity(self):
        for line in self:
            if line.is_infinite:
                line.display_quantity = _('Unlimited')
            else:
                line.display_quantity = f"{line.available_quantity:.0f} units"

    @api.depends('available_quantity', 'is_infinite')
    def _compute_stock_level(self):
        for line in self:
            if line.is_infinite:
                line.stock_level = 'infinite'
            elif line.available_quantity <= 0:
                line.stock_level = 'out_of_stock'
            elif line.available_quantity <= 10:
                line.stock_level = 'low'
            elif line.available_quantity <= 50:
                line.stock_level = 'medium'
            else:
                line.stock_level = 'high'

    # ==================== Constraints ====================
    _sql_constraints = [
        ('unique_variant_location',
         'UNIQUE(variant_id, location_id)',
         'A variant can only have one stock entry per location!'),
        ('check_positive_quantity',
         'CHECK(available_quantity >= 0 OR is_infinite = TRUE)',
         'Available quantity must be positive!')
    ]

    @api.constrains('available_quantity')
    def _check_quantity(self):
        for line in self:
            if not line.is_infinite and line.available_quantity < 0:
                raise ValidationError(_('Available quantity cannot be negative!'))

    # ==================== Business Methods ====================
    def update_stock(self, new_quantity, is_infinite=False):
        """Update stock quantity for this location"""
        self.ensure_one()

        old_quantity = self.available_quantity

        self.write({
            'available_quantity': new_quantity,
            'is_infinite': is_infinite,
            'last_update': fields.Datetime.now()
        })

        # Log the change
        _logger.info(
            f"Stock updated for {self.variant_id.sku} at {self.location_id.display_name}: "
            f"{old_quantity} -> {new_quantity} (Infinite: {is_infinite})"
        )

        # Create activity log if significant change
        if abs(old_quantity - new_quantity) > 10 and not is_infinite:
            self.variant_id.message_post(
                body=_(
                    "Stock level changed at %(location)s: "
                    "%(old_qty).0f → %(new_qty).0f units",
                    location=self.location_id.display_name,
                    old_qty=old_quantity,
                    new_qty=new_quantity
                )
            )

        return True

    def sync_from_zid(self, stock_data):
        """Update stock line from Zid API data"""
        self.ensure_one()

        if not isinstance(stock_data, dict):
            _logger.warning(f"Invalid stock data for sync: {stock_data}")
            return False

        new_quantity = float(stock_data.get('available_quantity', 0) or 0)
        is_infinite = stock_data.get('is_infinite', False)

        self.update_stock(new_quantity, is_infinite)

        # Update stock ID if provided
        if stock_data.get('id'):
            self.stock_id = str(stock_data['id'])

        return True

    @api.model
    def create_from_zid(self, variant, location, stock_data):
        """Create stock line from Zid API data"""
        values = {
            'variant_id': variant.id,
            'location_id': location.id,
            'stock_id': str(stock_data.get('id', '')),
            'available_quantity': float(stock_data.get('available_quantity', 0) or 0),
            'is_infinite': stock_data.get('is_infinite', False),
            'last_update': fields.Datetime.now()
        }

        return self.create(values)

    def action_view_variant(self):
        """Action to view the variant"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'zid.variant',
            'res_id': self.variant_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_location(self):
        """Action to view the location"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'zid.location',
            'res_id': self.location_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    # ==================== Batch Operations ====================
    @api.model
    def update_all_stock_levels(self, connector_id=None):
        """Update all stock levels from Zid API"""
        domain = []
        if connector_id:
            domain.append(('connector_id', '=', connector_id))

        stock_lines = self.search(domain)

        updated_count = 0
        error_count = 0

        for line in stock_lines:
            try:
                # This would call Zid API to get updated stock
                # For now, just log
                _logger.info(f"Would update stock for {line.display_name}")
                updated_count += 1
            except Exception as e:
                _logger.error(f"Failed to update stock for {line.display_name}: {str(e)}")
                error_count += 1

        return {
            'updated': updated_count,
            'errors': error_count
        }

    def get_total_stock_by_variant(self):
        """Get total stock across all locations for variants"""
        self.ensure_one()

        # Get all stock lines for this variant
        all_lines = self.search([
            ('variant_id', '=', self.variant_id.id)
        ])

        total_stock = 0
        has_infinite = False

        for line in all_lines:
            if line.is_infinite:
                has_infinite = True
                break
            total_stock += line.available_quantity

        return {
            'total_stock': total_stock,
            'is_infinite': has_infinite,
            'locations_count': len(all_lines)
        }

    # ==================== Reporting Methods ====================
    def get_stock_summary(self):
        """Get stock summary for reporting"""
        self.ensure_one()

        return {
            'variant_sku': self.variant_sku,
            'variant_name': self.variant_name,
            'location': self.location_name,
            'location_type': self.location_type,
            'quantity': self.available_quantity,
            'is_infinite': self.is_infinite,
            'stock_level': self.stock_level,
            'last_update': self.last_update,
        }

    @api.model
    def get_low_stock_items(self, threshold=10, connector_id=None):
        """Get all items with low stock"""
        domain = [
            ('is_infinite', '=', False),
            ('available_quantity', '<=', threshold)
        ]

        if connector_id:
            domain.append(('connector_id', '=', connector_id))

        low_stock_lines = self.search(domain)

        result = []
        for line in low_stock_lines:
            result.append({
                'variant': line.variant_id.display_name,
                'location': line.location_id.display_name,
                'quantity': line.available_quantity,
                'sku': line.variant_sku,
            })

        return result