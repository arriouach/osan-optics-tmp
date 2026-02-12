from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import json
import logging
from datetime import datetime

_logger = logging.getLogger(__name__)


class ZidVariant(models.Model):
    _name = 'zid.variant'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Zid Product Variant'
    _rec_name = 'display_name'
    _order = 'parent_product_id, sequence, id'

    # ==================== Connection & Identity Fields ====================
    zid_connector_id = fields.Many2one(
        'zid.connector',
        string='Zid Connector',
        required=True,
        ondelete='cascade',
        tracking=True
    )

    zid_variant_id = fields.Char(
        string='Zid Variant ID',
        required=True,
        readonly=True,
        copy=False,
        tracking=True
    )

    parent_product_id = fields.Many2one(
        'zid.product',
        string='Parent Product',
        required=True,
        ondelete='cascade',
        tracking=True
    )

    # ==================== Basic Information ====================
    sku = fields.Char(
        string='SKU',
        required=True,
        tracking=True,
        index=True
    )

    barcode = fields.Char(
        string='Barcode',
        tracking=True
    )

    name_ar = fields.Char(
        string='Name (Arabic)',
        tracking=True
    )

    name_en = fields.Char(
        string='Name (English)',
        tracking=True
    )

    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True
    )

    slug = fields.Char(
        string='URL Slug',
        readonly=True
    )

    short_description = fields.Text(
        string='Short Description'
    )

    sequence = fields.Integer(
        string='Sequence',
        default=10
    )

    # ==================== Pricing ====================
    price = fields.Float(
        string='Price',
        digits='Product Price',
        tracking=True
    )

    sale_price = fields.Float(
        string='Sale Price',
        digits='Product Price',
        tracking=True
    )

    cost = fields.Float(
        string='Cost',
        digits='Product Price'
    )

    formatted_price = fields.Char(
        string='Formatted Price',
        readonly=True
    )

    formatted_sale_price = fields.Char(
        string='Formatted Sale Price',
        readonly=True
    )

    currency_code = fields.Char(
        string='Currency Code',
        readonly=True
    )

    currency_symbol = fields.Char(
        string='Currency Symbol',
        readonly=True
    )

    # ==================== Inventory ====================
    quantity = fields.Float(
        string='Total Quantity',
        digits='Product Unit of Measure',
        tracking=True
    )

    is_infinite = fields.Boolean(
        string='Infinite Stock',
        default=False,
        tracking=True
    )

    # Stock Lines (by location)
    stock_line_ids = fields.One2many(
        'zid.variant.stock.line',
        'variant_id',
        string='Stock by Location'
    )

    # ==================== Attributes ====================
    attributes_data = fields.Text(
        string='Attributes JSON',
        readonly=True
    )

    # Common attributes as computed fields
    color = fields.Char(
        string='Color',
        compute='_compute_common_attributes',
        store=True
    )

    size = fields.Char(
        string='Size',
        compute='_compute_common_attributes',
        store=True
    )

    # ==================== Images ====================
    images_data = fields.Text(
        string='Images JSON',
        readonly=True
    )

    zid_image_ids = fields.One2many(
        'zid.product.image',
        'variant_id',
        string='Gallery Images'
    )

    main_image_url = fields.Char(
        string='Main Image URL',
        compute='_compute_main_image',
        store=True
    )

    main_image = fields.Image(
        string='Main Image',
        compute='_compute_main_image',
        store=True
    )

    # ==================== Weight & Shipping ====================
    weight_value = fields.Float(
        string='Weight Value'
    )

    weight_unit = fields.Selection([
        ('g', 'Gram'),
        ('kg', 'Kilogram'),
        ('lb', 'Pound'),
        ('oz', 'Ounce')
    ], string='Weight Unit', default='g')

    requires_shipping = fields.Boolean(
        string='Requires Shipping',
        default=True
    )

    # ==================== Status ====================
    is_published = fields.Boolean(
        string='Published',
        default=True,
        tracking=True
    )

    is_draft = fields.Boolean(
        string='Draft',
        default=False,
        tracking=True
    )

    is_available = fields.Boolean(
        string='Available for Sale',
        compute='_compute_availability',
        store=True
    )

    # ==================== Purchase Restrictions ====================
    min_quantity_per_cart = fields.Integer(
        string='Min Quantity per Cart'
    )

    max_quantity_per_cart = fields.Integer(
        string='Max Quantity per Cart'
    )

    availability_period_start = fields.Datetime(
        string='Availability Start'
    )

    availability_period_end = fields.Datetime(
        string='Availability End'
    )

    # ==================== Tax & Other Settings ====================
    is_taxable = fields.Boolean(
        string='Taxable',
        default=True
    )

    html_url = fields.Char(
        string='Product URL',
        readonly=True
    )

    display_order = fields.Integer(
        string='Display Order'
    )

    # ==================== Metadata ====================
    meta_data = fields.Text(
        string='Meta Data',
        readonly=True
    )

    metafields = fields.Text(
        string='Meta Fields',
        readonly=True
    )

    # ==================== Timestamps ====================
    zid_created_at = fields.Datetime(
        string='Created at Zid',
        readonly=True
    )

    zid_updated_at = fields.Datetime(
        string='Updated at Zid',
        readonly=True
    )

    last_sync_date = fields.Datetime(
        string='Last Sync Date',
        readonly=True,
        tracking=True
    )

    # ==================== Raw Data ====================
    raw_response = fields.Text(
        string='Raw API Response',
        readonly=True
    )

    # ==================== Odoo Link ====================
    odoo_product_id = fields.Many2one(
        'product.product',
        string='Odoo Product Variant',
        help='Linked Odoo product variant if mapped'
    )

    # ==================== Computed Methods ====================
    @api.depends('name_en', 'name_ar', 'sku')
    def _compute_display_name(self):
        for record in self:
            name = record.name_en or record.name_ar or 'Unknown Variant'
            if record.sku:
                record.display_name = f"[{record.sku}] {name}"
            else:
                record.display_name = name

    @api.depends('attributes_data')
    def _compute_common_attributes(self):
        for record in self:
            color = False
            size = False

            if record.attributes_data:
                try:
                    attributes = json.loads(record.attributes_data)
                    for attr in attributes:
                        if isinstance(attr, dict):
                            attr_name = attr.get('name', {})
                            attr_value = attr.get('value', {})

                            # Get attribute name
                            if isinstance(attr_name, dict):
                                name_en = attr_name.get('en', '').lower()
                                name_ar = attr_name.get('ar', '')
                            else:
                                name_en = str(attr_name).lower()
                                name_ar = ''

                            # Get attribute value
                            if isinstance(attr_value, dict):
                                value_en = attr_value.get('en', '')
                                value_ar = attr_value.get('ar', '')
                                value = value_en or value_ar
                            else:
                                value = str(attr_value)

                            # Check for color
                            if name_en in ['color', 'colour'] or name_ar == 'اللون':
                                color = value
                            # Check for size
                            elif name_en in ['size'] or name_ar in ['الحجم', 'المقاس']:
                                size = value
                except Exception as e:
                    _logger.warning(f"Error parsing attributes: {str(e)}")

            record.color = color
            record.size = size

    @api.depends('images_data')
    def _compute_main_image(self):
        for record in self:
            main_image_url = False
            main_image_binary = False

            if record.images_data:
                try:
                    images = json.loads(record.images_data)
                    if images and isinstance(images, list):
                        # Sort by display order if possible
                        images = sorted(images, key=lambda x: x.get('display_order', 0))
                        
                        # Look for default image first
                        target_image = images[0]
                        for img in images:
                            if isinstance(img, dict) and img.get('is_default'):
                                target_image = img
                                break
                        
                        if isinstance(target_image, dict):
                            # Handle Zid nested image object
                            image_obj = target_image.get('image', {})
                            if isinstance(image_obj, dict):
                                main_image_url = image_obj.get('full_size') or image_obj.get('large') or image_obj.get('medium')
                            
                            # Fallback
                            if not main_image_url:
                                main_image_url = target_image.get('url') or target_image.get('thumbnail')

                        # Download image
                        if main_image_url:
                            try:
                                import requests
                                import base64
                                response = requests.get(main_image_url, timeout=10)
                                if response.status_code == 200:
                                    main_image_binary = base64.b64encode(response.content)
                            except Exception as e:
                                _logger.warning(f"Failed to download variant image: {str(e)}")

                except Exception as e:
                    _logger.warning(f"Error parsing images: {str(e)}")

            record.main_image_url = main_image_url
            record.main_image = main_image_binary

    @api.depends('is_published', 'is_draft', 'quantity', 'is_infinite')
    def _compute_availability(self):
        for record in self:
            record.is_available = (
                    record.is_published and
                    not record.is_draft and
                    (record.is_infinite or record.quantity > 0)
            )

    # ==================== Constraints ====================
    _sql_constraints = [
        ('unique_zid_variant',
         'UNIQUE(zid_connector_id, zid_variant_id)',
         'Zid Variant ID must be unique per connector!'),
        ('unique_sku_per_connector',
         'UNIQUE(zid_connector_id, sku)',
         'SKU must be unique per connector!')
    ]

    @api.constrains('min_quantity_per_cart', 'max_quantity_per_cart')
    def _check_quantity_constraints(self):
        for record in self:
            if record.min_quantity_per_cart and record.max_quantity_per_cart:
                if record.min_quantity_per_cart > record.max_quantity_per_cart:
                    raise ValidationError(_('Minimum quantity cannot be greater than maximum quantity!'))

    @api.constrains('price', 'sale_price')
    def _check_prices(self):
        for record in self:
            if record.price < 0:
                raise ValidationError(_('Price cannot be negative!'))
            if record.sale_price and record.sale_price < 0:
                raise ValidationError(_('Sale price cannot be negative!'))
            if record.sale_price and record.sale_price > record.price:
                raise ValidationError(_('Sale price cannot be greater than regular price!'))

    # ==================== CRUD Methods ====================
    @api.model
    def create_or_update_from_zid(self, variant_data, parent_product, connector_id):
        """Create or update variant from Zid API data"""
        variant_id = str(variant_data.get('id', ''))

        if not variant_id:
            _logger.warning("Variant data has no ID, skipping")
            return False

        # Search for existing variant
        existing = self.search([
            ('zid_variant_id', '=', variant_id),
            ('zid_connector_id', '=', connector_id)
        ], limit=1)

        # Prepare values
        values = self._prepare_variant_values(variant_data, parent_product, connector_id)

        if existing:
            existing.write(values)
            _logger.info(f"Updated Zid variant {variant_id}")
            # Update stock and gallery
            existing._update_stock_lines(variant_data)
            existing._update_gallery_images(variant_data)
            return existing
        else:
            variant = self.create(values)
            _logger.info(f"Created new Zid variant {variant_id}")
            # Create stock and gallery
            variant._update_stock_lines(variant_data)
            variant._update_gallery_images(variant_data)
            return variant

    @api.model
    def _prepare_variant_values(self, variant_data, parent_product, connector_id):
        """Prepare variant values from API response"""
        # Get name
        name_data = variant_data.get('name', {})
        if isinstance(name_data, dict):
            name_en = name_data.get('en', '')
            name_ar = name_data.get('ar', '')
        else:
            name_en = str(name_data) if name_data else ''
            name_ar = ''

        # Get weight
        weight_data = variant_data.get('weight', {})
        if isinstance(weight_data, dict):
            weight_value = float(weight_data.get('value', 0) or 0)
            weight_unit = weight_data.get('unit', 'g')
        else:
            weight_value = 0.0
            weight_unit = 'g'

        # Get purchase restrictions
        restrictions = variant_data.get('purchase_restrictions', {})
        if isinstance(restrictions, dict):
            min_qty = restrictions.get('min_quantity_per_cart')
            max_qty = restrictions.get('max_quantity_per_cart')
            avail_start = self._parse_datetime(restrictions.get('availability_period_start'))
            avail_end = self._parse_datetime(restrictions.get('availability_period_end'))
        else:
            min_qty = max_qty = avail_start = avail_end = None

        values = {
            'zid_connector_id': connector_id,
            'zid_variant_id': str(variant_data.get('id', '')),
            'parent_product_id': parent_product.id,
            'sku': variant_data.get('sku', ''),
            'barcode': variant_data.get('barcode', ''),
            'name_en': name_en,
            'name_ar': name_ar,
            'slug': variant_data.get('slug', ''),
            'short_description': variant_data.get('short_description'),
            'price': float(variant_data.get('price', 0) or 0),
            'sale_price': float(variant_data.get('sale_price', 0) or 0),
            'cost': float(variant_data.get('cost', 0) or 0),
            'formatted_price': variant_data.get('formatted_price', ''),
            'formatted_sale_price': variant_data.get('formatted_sale_price', ''),
            'currency_code': variant_data.get('currency', ''),
            'currency_symbol': variant_data.get('currency_symbol', ''),
            'quantity': float(variant_data.get('quantity', 0) or 0),
            'is_infinite': variant_data.get('is_infinite', False),
            'attributes_data': json.dumps(variant_data.get('attributes', []), ensure_ascii=False),
            'images_data': json.dumps(variant_data.get('images', []), ensure_ascii=False),
            'weight_value': weight_value,
            'weight_unit': weight_unit,
            'requires_shipping': variant_data.get('requires_shipping', True),
            'is_published': variant_data.get('is_published', True),
            'is_draft': variant_data.get('is_draft', False),
            'min_quantity_per_cart': int(min_qty) if min_qty else None,
            'max_quantity_per_cart': int(max_qty) if max_qty else None,
            'availability_period_start': avail_start,
            'availability_period_end': avail_end,
            'is_taxable': variant_data.get('is_taxable', True),
            'html_url': variant_data.get('html_url', ''),
            'display_order': int(variant_data.get('display_order', 0) or 0),
            'meta_data': json.dumps(variant_data.get('meta', {}), ensure_ascii=False) if variant_data.get(
                'meta') else '',
            'metafields': json.dumps(variant_data.get('metafields'), ensure_ascii=False) if variant_data.get(
                'metafields') else '',
            'zid_created_at': self._parse_datetime(variant_data.get('created_at')),
            'zid_updated_at': self._parse_datetime(variant_data.get('updated_at')),
            'last_sync_date': fields.Datetime.now(),
            'raw_response': json.dumps(variant_data, ensure_ascii=False),
        }

        return values

    def _update_stock_lines(self, variant_data):
        """Update stock lines from API data"""
        self.ensure_one()

        # Get stocks data
        stocks = variant_data.get('stocks', [])

        if not stocks:
            _logger.info(f"No stocks data for variant {self.zid_variant_id}")
            return

        # Delete existing stock lines
        self.stock_line_ids.unlink()

        # Create new stock lines
        for stock in stocks:
            if not isinstance(stock, dict):
                continue

            # Get location data
            location_data = stock.get('location', {})
            if not location_data or not isinstance(location_data, dict):
                continue

            location_id_str = str(location_data.get('id', ''))
            if not location_id_str:
                continue

            # Find or create the Zid location
            zid_location = self.env['zid.location'].search([
                ('zid_location_id', '=', location_id_str),
                ('zid_connector_id', '=', self.zid_connector_id.id)
            ], limit=1)

            if not zid_location:
                # Create location if doesn't exist
                location_name = location_data.get('name', {})
                if isinstance(location_name, dict):
                    name_ar = location_name.get('ar', '')
                    name_en = location_name.get('en', '')
                else:
                    name_ar = str(location_name) if location_name else 'Unknown Location'
                    name_en = name_ar

                zid_location = self.env['zid.location'].create({
                    'zid_connector_id': self.zid_connector_id.id,
                    'zid_location_id': location_id_str,
                    'name_en': name_en or name_ar or 'Unknown Location',
                    'name_ar': name_ar or name_en or 'Unknown Location',
                    'location_type': location_data.get('type', 'warehouse'),
                    'is_enabled': True,
                })

            # Create stock line
            self.env['zid.variant.stock.line'].create({
                'variant_id': self.id,
                'location_id': zid_location.id,
                'stock_id': str(stock.get('id', '')),
                'available_quantity': float(stock.get('available_quantity', 0) or 0),
                'is_infinite': stock.get('is_infinite', False),
            })

    def _update_gallery_images(self, variant_data):
        """Update variant gallery images from API response"""
        self.ensure_one()
        images = variant_data.get('images', [])
        if not images:
            return

        # Keep track of existing image IDs
        existing_zid_ids = self.zid_image_ids.mapped('zid_image_id')
        
        # Sort images
        images = sorted(images, key=lambda x: x.get('display_order', 0))

        image_model = self.env['zid.product.image']
        import requests
        import base64

        for img_data in images:
            zid_img_id = str(img_data.get('id', ''))
            if not zid_img_id or zid_img_id in existing_zid_ids:
                continue

            # Get URL
            image_obj = img_data.get('image', {})
            img_url = ''
            if isinstance(image_obj, dict):
                img_url = image_obj.get('full_size') or image_obj.get('large') or image_obj.get('medium')
            
            if not img_url:
                img_url = img_data.get('url', '') or img_data.get('thumbnail', '')

            if img_url:
                try:
                    response = requests.get(img_url, timeout=10)
                    if response.status_code == 200:
                        image_binary = base64.b64encode(response.content)
                        image_model.create({
                            'variant_id': self.id,
                            'zid_image_id': zid_img_id,
                            'image': image_binary,
                            'image_url': img_url,
                            'sequence': img_data.get('display_order', 10)
                        })
                except Exception as e:
                    _logger.warning(f"Failed to download variant gallery image {zid_img_id}: {str(e)}")

    @api.model
    def _parse_datetime(self, datetime_str):
        """Parse datetime from Zid API format"""
        if not datetime_str:
            return False

        try:
            if isinstance(datetime_str, str):
                if datetime_str.endswith('Z'):
                    datetime_str = datetime_str[:-1]
                if '.' in datetime_str:
                    datetime_str = datetime_str.split('.')[0]
                dt = datetime.strptime(datetime_str, '%Y-%m-%dT%H:%M:%S')
                return dt.strftime('%Y-%m-%d %H:%M:%S')
            return datetime_str
        except Exception as e:
            _logger.warning(f"Could not parse datetime {datetime_str}: {str(e)}")
            return False


    def server_action_link_with_odoo_products(self):
        """Server action to relink selected variants with products"""
        # If only one record, open single wizard
        if len(self) == 1:
            return self.action_relink_odoo_product()
        
        # If multiple records, open bulk wizard
        return {
            'name': _('Bulk Relink Zid Variants'),
            'type': 'ir.actions.act_window',
            'res_model': 'zid.variant.bulk.relink.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'active_ids': self.ids,
                'active_model': 'zid.variant',
            }
        }

    def action_relink_odoo_product(self):
        """Re-link Zid variant with a different Odoo product and sync variant lines"""
        self.ensure_one()
        
        # If called with a product_id in context, execute directly
        if self.env.context.get('direct_product_id'):
            return self.relink_with_product(self.env.context.get('direct_product_id'))
        
        # Otherwise, open wizard to select new product
        return {
            'name': _('Relink Zid Variant to Odoo Product'),
            'type': 'ir.actions.act_window',
            'res_model': 'zid.variant.relink.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_zid_variant_id': self.id,
                'default_current_product_id': self.odoo_product_id.id if self.odoo_product_id else False,
            }
        }
    
    def relink_with_product(self, new_product_id):
        """
        Internal method to relink variant with new product
        This handles:
        1. Removing old variant lines from previous product
        2. Linking variant to new product
        3. Creating/updating variant lines in new product
        4. Syncing stock lines
        """
        self.ensure_one()
        
        if not new_product_id:
            raise ValidationError(_('Please select a product to link with this variant'))
        
        new_product = self.env['product.product'].browse(new_product_id)
        old_product = self.odoo_product_id
        
        _logger.info(f"Relinking Zid variant {self.zid_variant_id} from product {old_product.name if old_product else 'None'} to {new_product.name}")
        
        # Step 1: Remove old variant lines from previous product if exists
        if old_product:
            old_lines = self.env['zid.variant.line'].search([
                ('product_id', '=', old_product.id),
                ('zid_variant_id', '=', self.id)
            ])
            if old_lines:
                _logger.info(f"Removing {len(old_lines)} old variant lines from product {old_product.name}")
                old_lines.unlink()
        
        # Step 2: Check if any other product has lines for this variant (cleanup)
        existing_lines = self.env['zid.variant.line'].search([
            ('zid_variant_id', '=', self.id)
        ])
        if existing_lines:
            _logger.warning(f"Found {len(existing_lines)} orphaned variant lines, removing them")
            existing_lines.unlink()
        
        # Step 3: Link variant to new product
        self.odoo_product_id = new_product
        _logger.info(f"Linked variant {self.zid_variant_id} to product {new_product.name}")
        
        # Step 4: Create variant lines for each stock location
        created_lines = []
        for stock_line in self.stock_line_ids:
            # Check if we need to create a variant line for this location
            variant_line_vals = {
                'product_id': new_product.id,
                'zid_connector_id': self.zid_connector_id.id,
                'zid_location_id': stock_line.location_id.id,
                'zid_variant_id': self.id,
                'zid_sku': self.sku,
                'is_published': self.is_published,
                'zid_price': self.price,
                'zid_compare_price': self.sale_price,
                'zid_quantity': int(stock_line.available_quantity),
                'track_inventory': not stock_line.is_infinite,
                'last_sync_date': fields.Datetime.now(),
                'sync_status': 'synced',
                'location_name': stock_line.location_id.display_name,
                'active': True,
            }
            
            variant_line = self.env['zid.variant.line'].create(variant_line_vals)
            created_lines.append(variant_line)
            _logger.info(f"Created variant line for location {stock_line.location_id.display_name} with quantity {stock_line.available_quantity}")
        
        # Step 5: Update product with Zid information if needed
        if not new_product.default_code and self.sku:
            new_product.default_code = self.sku
        
        if not new_product.barcode and self.barcode:
            new_product.barcode = self.barcode
        
        # Step 6: Log the change
        message = _(
            "Zid variant relinked:<br/>"
            "- Variant ID: %(variant_id)s<br/>"
            "- SKU: %(sku)s<br/>"
            "- Previous Product: %(old_product)s<br/>"
            "- New Product: %(new_product)s<br/>"
            "- Created %(lines_count)d variant lines",
            variant_id=self.zid_variant_id,
            sku=self.sku,
            old_product=old_product.display_name if old_product else 'None',
            new_product=new_product.display_name,
            lines_count=len(created_lines)
        )
        
        self.message_post(body=message)
        new_product.message_post(body=message)
        
        _logger.info(f"Successfully relinked variant {self.zid_variant_id} with {len(created_lines)} variant lines")
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Variant successfully relinked to %s') % new_product.display_name,
                'type': 'success',
                'sticky': False,
            }
        }
    
    @api.model
    def bulk_relink_variants(self, variant_ids, product_mapping):
        """
        Bulk relink multiple variants to products
        :param variant_ids: list of variant IDs to relink
        :param product_mapping: dict {variant_id: product_id}
        :return: dict with results
        """
        results = {
            'success': [],
            'failed': []
        }
        
        for variant_id in variant_ids:
            try:
                variant = self.browse(variant_id)
                new_product_id = product_mapping.get(variant_id)
                
                if not new_product_id:
                    results['failed'].append({
                        'variant_id': variant_id,
                        'error': 'No product mapping found'
                    })
                    continue
                
                variant.relink_with_product(new_product_id)
                results['success'].append(variant_id)
                
            except Exception as e:
                _logger.error(f"Failed to relink variant {variant_id}: {str(e)}")
                results['failed'].append({
                    'variant_id': variant_id,
                    'error': str(e)
                })
        
        return results
    
    def action_sync_stock_from_odoo(self):
        """Sync stock from Odoo to Zid for this variant"""
        self.ensure_one()
        
        if not self.odoo_product_id:
            raise ValidationError(_('This variant is not linked to any Odoo product'))
        
        synced_locations = []
        failed_locations = []
        
        # First, check if variant lines exist, if not create them from stock lines
        variant_lines = self.env['zid.variant.line'].search([
            ('zid_variant_id', '=', self.id)
        ])
        
        # If no variant lines exist, create them from stock lines
        if not variant_lines and self.stock_line_ids:
            _logger.info(f"No variant lines found, creating from {len(self.stock_line_ids)} stock lines")
            for stock_line in self.stock_line_ids:
                variant_line_vals = {
                    'product_id': self.odoo_product_id.id,
                    'zid_connector_id': self.zid_connector_id.id,
                    'zid_location_id': stock_line.location_id.id,
                    'zid_variant_id': self.id,
                    'zid_sku': self.sku,
                    'is_published': self.is_published,
                    'zid_price': self.price,
                    'zid_compare_price': self.sale_price,
                    'zid_quantity': int(stock_line.available_quantity),
                    'track_inventory': not stock_line.is_infinite,
                    'last_sync_date': fields.Datetime.now(),
                    'sync_status': 'not_synced',
                    'location_name': stock_line.location_id.display_name,
                    'active': True,
                }
                self.env['zid.variant.line'].create(variant_line_vals)
                _logger.info(f"Created variant line for location {stock_line.location_id.display_name}")
            
            # Re-search for the newly created lines
            variant_lines = self.env['zid.variant.line'].search([
                ('zid_variant_id', '=', self.id)
            ])
        
        # If still no variant lines, work directly with stock lines
        if not variant_lines:
            _logger.info("Working directly with stock lines as no variant lines exist")
            for stock_line in self.stock_line_ids:
                try:
                    # Find corresponding Odoo location
                    odoo_location = self.env['stock.location'].search([
                        ('zid_location_id', '=', stock_line.location_id.id)
                    ], limit=1)
                    
                    if not odoo_location:
                        _logger.warning(f"No Odoo location found for Zid location {stock_line.location_id.display_name}")
                        # Try to match by name as fallback
                        odoo_location = self.env['stock.location'].search([
                            '|',
                            ('name', 'ilike', stock_line.location_id.name_en),
                            ('name', 'ilike', stock_line.location_id.name_ar)
                        ], limit=1)
                        
                        if not odoo_location:
                            failed_locations.append(stock_line.location_id.display_name)
                            continue
                    
                    # Calculate quantity from stock.quant
                    quants = self.env['stock.quant'].search([
                        ('product_id', '=', self.odoo_product_id.id),
                        ('location_id', '=', odoo_location.id)
                    ])
                    
                    total_qty = sum(quants.mapped('quantity'))
                    
                    # Update the stock line directly
                    old_qty = stock_line.available_quantity
                    stock_line.available_quantity = total_qty
                    
                    synced_locations.append(f"{stock_line.location_id.display_name} ({old_qty:.0f} → {total_qty:.0f})")
                    _logger.info(f"Synced stock for location {stock_line.location_id.display_name}: {old_qty} → {total_qty}")
                    
                except Exception as e:
                    _logger.error(f"Failed to sync stock for location {stock_line.location_id.display_name}: {str(e)}")
                    failed_locations.append(stock_line.location_id.display_name)
        else:
            # Work with variant lines as before
            _logger.info(f"Syncing {len(variant_lines)} variant lines")
            for line in variant_lines:
                try:
                    # Find corresponding Odoo location
                    odoo_location = self.env['stock.location'].search([
                        ('zid_location_id', '=', line.zid_location_id.id)
                    ], limit=1)
                    
                    if not odoo_location:
                        _logger.warning(f"No Odoo location found for Zid location {line.zid_location_id.display_name}")
                        # Try to match by name as fallback
                        odoo_location = self.env['stock.location'].search([
                            '|',
                            ('name', 'ilike', line.zid_location_id.name_en),
                            ('name', 'ilike', line.zid_location_id.name_ar)
                        ], limit=1)
                        
                        if not odoo_location:
                            failed_locations.append(line.zid_location_id.display_name)
                            continue
                    
                    # Calculate quantity from stock.quant
                    quants = self.env['stock.quant'].search([
                        ('product_id', '=', self.odoo_product_id.id),
                        ('location_id', '=', odoo_location.id)
                    ])
                    
                    total_qty = sum(quants.mapped('quantity'))
                    
                    # Update the variant line
                    old_qty = line.zid_quantity
                    line.write({
                        'zid_quantity': int(total_qty),
                        'last_sync_date': fields.Datetime.now(),
                        'sync_status': 'synced'
                    })
                    
                    # Update the corresponding stock line
                    stock_line = self.stock_line_ids.filtered(
                        lambda s: s.location_id.id == line.zid_location_id.id
                    )
                    if stock_line:
                        stock_line.available_quantity = total_qty
                    
                    synced_locations.append(f"{line.zid_location_id.display_name} ({old_qty} → {int(total_qty)})")
                    _logger.info(f"Synced stock for location {line.zid_location_id.display_name}: {old_qty} → {total_qty}")
                    
                except Exception as e:
                    _logger.error(f"Failed to sync stock for location {line.zid_location_id.display_name}: {str(e)}")
                    failed_locations.append(line.zid_location_id.display_name)
        
        # Prepare message
        message_parts = []
        if synced_locations:
            message_parts.append(_('Successfully synced %d location(s):\n%s') % (len(synced_locations), '\n'.join(synced_locations)))
        if failed_locations:
            message_parts.append(_('Failed to sync %d location(s):\n%s') % (len(failed_locations), '\n'.join(failed_locations)))
        
        if not synced_locations and not failed_locations:
            message = _('No locations found to sync. Please check location mappings.')
        else:
            message = '\n\n'.join(message_parts)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Stock Sync Complete'),
                'message': message,
                'type': 'success' if not failed_locations else 'warning' if synced_locations else 'danger',
                'sticky': True if failed_locations else False,
            }
        }
