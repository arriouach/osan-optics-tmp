from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import json
import logging

_logger = logging.getLogger(__name__)


class ZidProduct(models.Model):
    _name = 'zid.product'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Zid Product'
    _rec_name = 'name'
    _order = 'sequence, name'

    # Connection Info
    zid_connector_id = fields.Many2one(
        'zid.connector',
        string='Zid Connector',
        required=True,
        ondelete='cascade'
    )

    # Basic Product Info
    zid_product_id = fields.Char(
        string='Zid Product ID',
        required=True,
        readonly=True,
        copy=False
    )

    parent_id = fields.Char(
        string='Parent Product ID',
        readonly=True,
        help='If this is a variant, this is the parent product ID'
    )

    name = fields.Char(
        string='Product Name',
        required=True,
        tracking=True
    )

    name_ar = fields.Char(
        string='Product Name (Arabic)',
        tracking=True
    )

    slug = fields.Char(
        string='URL Slug',
        readonly=True
    )

    sku = fields.Char(
        string='SKU',
        tracking=True
    )

    barcode = fields.Char(
        string='Barcode',
        tracking=True
    )

    # Pricing
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
        string='Currency',
        readonly=True
    )

    currency_symbol = fields.Char(
        string='Currency Symbol',
        readonly=True
    )

    # Product Type & Status
    product_class = fields.Selection([
        ('simple', 'Simple Product'),
        ('grouped_product', 'Grouped Product'),
        ('variant', 'Product Variant')
    ], string='Product Type', default='simple', required=True)

    is_external_product = fields.Boolean(
        string='External Product',
        default=False,
        readonly=True
    )

    is_draft = fields.Boolean(
        string='Is Draft',
        default=False,
        tracking=True
    )

    is_published = fields.Boolean(
        string='Is Published',
        default=True,
        tracking=True
    )

    # Inventory
    quantity = fields.Float(
        string='Quantity',
        digits='Product Unit of Measure'
    )

    is_infinite = fields.Boolean(
        string='Infinite Stock',
        default=False,
        help='Product has unlimited stock'
    )

    # Product Details
    description = fields.Html(
        string='Description'
    )

    description_ar = fields.Html(
        string='Description (Arabic)'
    )

    short_description = fields.Text(
        string='Short Description'
    )

    short_description_ar = fields.Text(
        string='Short Description (Arabic)'
    )

    # Weight & Shipping
    weight_value = fields.Float(
        string='Weight Value',
        digits='Stock Weight'
    )

    weight_unit = fields.Selection([
        ('kg', 'Kilogram'),
        ('g', 'Gram'),
        ('lb', 'Pound'),
        ('oz', 'Ounce')
    ], string='Weight Unit', default='kg')

    requires_shipping = fields.Boolean(
        string='Requires Shipping',
        default=True
    )

    is_taxable = fields.Boolean(
        string='Is Taxable',
        default=False
    )

    # Display & Organization
    sequence = fields.Integer(
        string='Sequence',
        default=10
    )

    display_order = fields.Integer(
        string='Display Order'
    )

    # Options & Variants
    has_options = fields.Boolean(
        string='Has Options',
        default=False,
        readonly=True
    )

    has_fields = fields.Boolean(
        string='Has Custom Fields',
        default=False,
        readonly=True
    )

    # URLs & Links
    html_url = fields.Char(
        string='Product URL',
        readonly=True
    )

    # Images
    main_image_url = fields.Char(
        string='Main Image URL'
    )
    
    main_image = fields.Image(
        string='Main Image',
        max_width=1024,
        max_height=1024,
        store=True
    )

    images_data = fields.Text(
        string='Images JSON Data',
        readonly=True
    )

    zid_image_ids = fields.One2many(
        'zid.product.image',
        'product_id',
        string='Gallery Images'
    )

    # Categories
    categories_data = fields.Text(
        string='Categories JSON Data',
        readonly=True
    )

    zid_category_ids = fields.Many2many(
        'zid.product.category',
        string='Zid Categories',
        help='Linked Zid Categories'
    )

    # Attributes
    attributes_data = fields.Text(
        string='Attributes JSON Data',
        readonly=True
    )

    # SEO
    seo_title = fields.Char(
        string='SEO Title'
    )

    seo_title_ar = fields.Char(
        string='SEO Title (Arabic)'
    )

    seo_description = fields.Text(
        string='SEO Description'
    )

    seo_description_ar = fields.Text(
        string='SEO Description (Arabic)'
    )

    keywords_data = fields.Text(
        string='Keywords JSON Data',
        readonly=True
    )

    # Rating
    rating_average = fields.Float(
        string='Average Rating',
        digits=(2, 1),
        readonly=True
    )

    rating_count = fields.Integer(
        string='Total Ratings',
        readonly=True
    )

    # Purchase Restrictions
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

    sale_price_period_start = fields.Datetime(
        string='Sale Price Start'
    )

    sale_price_period_end = fields.Datetime(
        string='Sale Price End'
    )

    # Statistics
    sold_products_count = fields.Integer(
        string='Sold Count',
        readonly=True
    )

    waiting_customers_count = fields.Integer(
        string='Waiting Customers',
        readonly=True
    )

    # Related Products
    related_products_settings = fields.Char(
        string='Related Products Settings'
    )

    related_products_title = fields.Char(
        string='Related Products Title'
    )

    # Group Products (for grouped products)
    group_products_data = fields.Text(
        string='Group Products JSON Data',
        readonly=True
    )

    # Stock Locations
    stocks_data = fields.Text(
        string='Stocks JSON Data',
        readonly=True
    )
    
    # Location Lines
    zid_location_ids = fields.One2many(
        'zid.location.line',
        'product_id',
        string='Stock by Location',
        readonly=True
    )

    # Variants & Options
    variants_data = fields.Text(
        string='Variants JSON Data',
        readonly=True
    )

    options_data = fields.Text(
        string='Options JSON Data',
        readonly=True
    )

    # Custom Fields
    custom_user_input_fields_data = fields.Text(
        string='Custom User Input Fields JSON',
        readonly=True
    )

    custom_option_fields_data = fields.Text(
        string='Custom Option Fields JSON',
        readonly=True
    )

    # Metadata
    metafields = fields.Text(
        string='Metafields',
        readonly=True
    )

    meta = fields.Text(
        string='Meta Data',
        readonly=True
    )

    # Badge
    badge_body = fields.Char(
        string='Badge Text'
    )

    badge_body_ar = fields.Char(
        string='Badge Text (Arabic)'
    )

    badge_icon_code = fields.Char(
        string='Badge Icon Code'
    )

    # Timestamps
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
        readonly=True
    )

    # Odoo Product Link (optional)
    odoo_product_id = fields.Many2one(
        'product.product',
        string='Odoo Product',
        help='Linked Odoo product if mapped'
    )

    # Raw Response
    raw_response = fields.Text(
        string='Raw API Response',
        readonly=True
    )

    # Computed Fields
    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True
    )

    @api.depends('name', 'sku')
    def _compute_display_name(self):
        for product in self:
            if product.sku:
                product.display_name = f"[{product.sku}] {product.name}"
            else:
                product.display_name = product.name or ''
    
    def _update_location_lines(self, product_data):
        """Update location lines from stocks data in API response"""
        self.ensure_one()
        
        # Get stocks data from API response
        stocks = product_data.get('stocks', [])
        
        if not stocks:
            _logger.info(f"No stocks data for product {self.zid_product_id}")
            # return  # Don't return, as we might need to update categories even if no stock data
        
        # Only process location lines if we have stock data
        if stocks:
            # Delete existing location lines
            self.zid_location_ids.unlink()
        
        location_line_model = self.env['zid.location.line']
        zid_location_model = self.env['zid.location']
        
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
            zid_location = zid_location_model.search([
                ('zid_location_id', '=', location_id_str),
                ('zid_connector_id', '=', self.zid_connector_id.id)
            ], limit=1)
            
            if not zid_location:
                # Create new location if it doesn't exist
                location_name = location_data.get('name', {})
                if isinstance(location_name, dict):
                    name_ar = location_name.get('ar', '')
                    name_en = location_name.get('en', '')
                else:
                    name_ar = str(location_name) if location_name else 'Unknown Location'
                    name_en = name_ar
                
                zid_location = zid_location_model.create({
                    'zid_connector_id': self.zid_connector_id.id,
                    'zid_location_id': location_id_str,
                    'name_en': name_en or name_ar or 'Unknown Location',
                    'name_ar': name_ar or name_en or 'Unknown Location',
                    'location_type': location_data.get('type', 'warehouse'),
                    'is_enabled': True,
                    'has_stocks': True,
                })
                _logger.info(f"Created new Zid location {location_id_str} - {name_en or name_ar}")
            
            # Create location line
            line_vals = {
                'product_id': self.id,
                'location_id': zid_location.id,
                'stock_id': str(stock.get('id', '')),
                'quantity': float(stock.get('available_quantity', 0) or 0),
                'is_infinite': stock.get('is_infinite', False),
            }
            
            location_line = location_line_model.create(line_vals)
            _logger.info(f"Created location line for product {self.zid_product_id} at location {zid_location.display_name}: {line_vals['quantity']} units")
        
        _logger.info(f"Updated {len(self.zid_location_ids)} location lines for product {self.zid_product_id}")

    def _update_gallery_images(self, product_data):
        """Update gallery images from API response"""
        self.ensure_one()
        images = product_data.get('images', [])
        if not images:
            return

        # Keep track of existing image IDs to avoid duplicates
        existing_zid_ids = self.zid_image_ids.mapped('zid_image_id')
        
        # Sort images by display order
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
                            'product_id': self.id,
                            'zid_image_id': zid_img_id,
                            'image': image_binary,
                            'image_url': img_url,
                            'sequence': img_data.get('display_order', 10)
                        })
                except Exception as e:
                    _logger.warning(f"Failed to download gallery image {zid_img_id}: {str(e)}")

    _sql_constraints = [
        ('unique_zid_product',
         'UNIQUE(zid_connector_id, zid_product_id)',
         'Zid Product ID must be unique per connector!')
    ]

    @api.model
    def create_or_update_from_zid(self, product_data, connector_id):
        """Create or update product from Zid API data"""
        # Use a new cursor to ensure commits persist
        with self.env.cr.savepoint():
            try:
                # Convert product_data to string if it's a dict for logging
                if isinstance(product_data, dict):
                    product_id = str(product_data.get('id', ''))
                else:
                    product_id = str(product_data)

                if not product_id:
                    _logger.warning("Product data has no ID, skipping")
                    return False

                # Search for existing product
                existing = self.search([
                    ('zid_product_id', '=', product_id),
                    ('zid_connector_id', '=', connector_id)
                ], limit=1)

                # Prepare values
                values = self._prepare_product_values(product_data, connector_id)

                if existing:
                    existing.write(values)
                    _logger.info(f"Updated Zid product {product_id}")
                    # Update location lines after updating product
                    try:
                        existing._update_location_lines(product_data)
                        existing._update_gallery_images(product_data)
                    except Exception as e:
                        _logger.error(f"Error updating location/gallery for product {product_id}: {str(e)}")
                    return existing
                else:
                    product = self.create(values)
                    _logger.info(f"Created new Zid product {product_id}, DB ID: {product.id}")
                    # Verify creation
                    if product.id:
                        _logger.info(f"Product {product_id} successfully saved with ID {product.id}")
                        # Create location lines after creating product
                        try:
                            product._update_location_lines(product_data)
                            product._update_gallery_images(product_data)
                        except Exception as e:
                            _logger.error(f"Error updating location/gallery for product {product_id}: {str(e)}")
                    return product

            except Exception as e:
                _logger.error(f"Failed to create/update product: {str(e)}")
                raise

    @api.model
    def _parse_datetime(self, datetime_str):
        """Parse datetime from Zid API format to Odoo format"""
        if not datetime_str:
            return False

        try:
            # Handle ISO format with Z timezone
            if isinstance(datetime_str, str):
                # Remove Z and microseconds for simpler parsing
                if datetime_str.endswith('Z'):
                    datetime_str = datetime_str[:-1]
                # Split by dot to handle microseconds
                if '.' in datetime_str:
                    datetime_str = datetime_str.split('.')[0]
                # Parse the datetime
                from datetime import datetime
                dt = datetime.strptime(datetime_str, '%Y-%m-%dT%H:%M:%S')
                return dt.strftime('%Y-%m-%d %H:%M:%S')
            return datetime_str
        except Exception as e:
            _logger.warning(f"Could not parse datetime {datetime_str}: {str(e)}")
            return False

    @api.model
    def _prepare_product_values(self, product_data, connector_id):
        """Prepare product values from Zid API response"""

        # Get name translations
        name_data = product_data.get('name', {})
        if isinstance(name_data, dict):
            name_en = name_data.get('en', '')
            name_ar = name_data.get('ar', '')
        else:
            name_en = str(name_data) if name_data else ''
            name_ar = ''

        # Get description translations
        desc_data = product_data.get('description', {})
        if isinstance(desc_data, dict):
            desc_en = desc_data.get('en', '')
            desc_ar = desc_data.get('ar', '')
        else:
            desc_en = str(desc_data) if desc_data else ''
            desc_ar = ''

        # Get short description translations
        short_desc_data = product_data.get('short_description', {})
        if isinstance(short_desc_data, dict):
            short_desc_en = short_desc_data.get('en', '')
            short_desc_ar = short_desc_data.get('ar', '')
        else:
            short_desc_en = str(short_desc_data) if short_desc_data else ''
            short_desc_ar = ''

        # Get weight data
        weight_data = product_data.get('weight', {})
        weight_value = 0.0
        weight_unit = 'kg'
        if isinstance(weight_data, dict):
            weight_value = float(weight_data.get('value', 0) or 0)
            weight_unit = weight_data.get('unit', 'kg')

        # Get SEO data
        seo_data = product_data.get('seo', {})
        seo_title_data = seo_data.get('title', {}) if isinstance(seo_data, dict) else {}
        seo_desc_data = seo_data.get('description', {}) if isinstance(seo_data, dict) else {}

        if isinstance(seo_title_data, dict):
            seo_title_en = seo_title_data.get('en', '')
            seo_title_ar = seo_title_data.get('ar', '')
        else:
            seo_title_en = str(seo_title_data) if seo_title_data else ''
            seo_title_ar = ''

        if isinstance(seo_desc_data, dict):
            seo_desc_en = seo_desc_data.get('en', '')
            seo_desc_ar = seo_desc_data.get('ar', '')
        else:
            seo_desc_en = str(seo_desc_data) if seo_desc_data else ''
            seo_desc_ar = ''

        # Get rating data
        rating_data = product_data.get('rating', {})
        if isinstance(rating_data, dict):
            rating_avg = float(rating_data.get('average', 0) or 0)
            rating_count = int(rating_data.get('total_count', 0) or 0)
        else:
            rating_avg = 0.0
            rating_count = 0

        # Get purchase restrictions
        restrictions = product_data.get('purchase_restrictions', {})
        if isinstance(restrictions, dict):
            min_qty = restrictions.get('min_quantity_per_cart')
            max_qty = restrictions.get('max_quantity_per_cart')
            avail_start = self._parse_datetime(restrictions.get('availability_period_start'))
            avail_end = self._parse_datetime(restrictions.get('availability_period_end'))
            sale_start = self._parse_datetime(restrictions.get('sale_price_period_start'))
            sale_end = self._parse_datetime(restrictions.get('sale_price_period_end'))
        else:
            min_qty = max_qty = avail_start = avail_end = sale_start = sale_end = None

        # Get badge data
        badge_data = product_data.get('badge', {})
        badge_body = badge_body_ar = badge_icon = ''
        if isinstance(badge_data, dict):
            badge_body_data = badge_data.get('body', {})
            if isinstance(badge_body_data, dict):
                badge_body = badge_body_data.get('en', '')
                badge_body_ar = badge_body_data.get('ar', '')
            badge_icon_data = badge_data.get('icon', {})
            if isinstance(badge_icon_data, dict):
                badge_icon = badge_icon_data.get('code', '')

        # Get main image
        images = product_data.get('images', [])
        main_image_url = ''
        if isinstance(images, list) and images:
            # Sort by display order if available
            images = sorted(images, key=lambda x: x.get('display_order', 0))
            first_image = images[0]
            if isinstance(first_image, dict):
                # Zid nested image object structure
                image_obj = first_image.get('image', {})
                if isinstance(image_obj, dict):
                    main_image_url = image_obj.get('full_size') or image_obj.get('large') or image_obj.get('medium')
                
                # Fallback to direct url/thumbnail
                if not main_image_url:
                    main_image_url = first_image.get('url', '') or first_image.get('thumbnail', '')
        
        # Download image if URL exists
        main_image_binary = False
        if main_image_url:
            try:
                import requests
                import base64
                response = requests.get(main_image_url, timeout=10)
                if response.status_code == 200:
                    main_image_binary = base64.b64encode(response.content)
            except Exception as e:
                _logger.warning(f"Failed to download image from {main_image_url}: {str(e)}")

        # Get product class - handle None/null values
        product_class = product_data.get('product_class')
        if not product_class:  # This handles None, empty string, etc.
            product_class = 'simple'

        values = {
            'zid_connector_id': connector_id,
            'zid_product_id': str(product_data.get('id', '')),
            'parent_id': str(product_data.get('parent_id', '') or ''),
            'name': name_en or 'Unknown Product',
            'name_ar': name_ar,
            'slug': product_data.get('slug', ''),
            'sku': product_data.get('sku', ''),
            'barcode': product_data.get('barcode', ''),
            'product_class': product_class,
            'is_external_product': product_data.get('is_external_product', False),
            'is_draft': product_data.get('is_draft', False),
            'is_published': product_data.get('is_published', True),

            # Pricing
            'price': float(product_data.get('price', 0) or 0),
            'sale_price': float(product_data.get('sale_price', 0) or 0),
            'cost': float(product_data.get('cost', 0) or 0),
            'formatted_price': product_data.get('formatted_price', ''),
            'formatted_sale_price': product_data.get('formatted_sale_price', ''),
            'currency_code': product_data.get('currency', ''),
            'currency_symbol': product_data.get('currency_symbol', ''),

            # Inventory
            'quantity': float(product_data.get('quantity', 0) or 0),
            'is_infinite': product_data.get('is_infinite', False),

            # Descriptions
            'description': desc_en,
            'description_ar': desc_ar,
            'short_description': short_desc_en,
            'short_description_ar': short_desc_ar,

            # Weight & Shipping
            'weight_value': weight_value,
            'weight_unit': weight_unit,
            'requires_shipping': product_data.get('requires_shipping', True),
            'is_taxable': product_data.get('is_taxable', False),

            # Display
            'sequence': int(product_data.get('display_order', 10) or 10),
            'display_order': int(product_data.get('display_order', 0) or 0),

            # Options
            'has_options': product_data.get('has_options', False),
            'has_fields': product_data.get('has_fields', False),

            # URLs
            'html_url': product_data.get('html_url', ''),
            'main_image_url': main_image_url,
            'main_image': main_image_binary,

            # JSON Data Storage
            'images_data': json.dumps(product_data.get('images', []), ensure_ascii=False),
            'categories_data': json.dumps(product_data.get('categories', []), ensure_ascii=False),
            'zid_category_ids': self._get_category_ids(product_data.get('categories', []), connector_id),
            'attributes_data': json.dumps(product_data.get('attributes', []), ensure_ascii=False),
            'keywords_data': json.dumps(product_data.get('keywords', []), ensure_ascii=False),
            'group_products_data': json.dumps(product_data.get('group_products', []), ensure_ascii=False),
            'stocks_data': json.dumps(product_data.get('stocks', []), ensure_ascii=False),
            'variants_data': json.dumps(product_data.get('variants', []), ensure_ascii=False),
            'options_data': json.dumps(product_data.get('options', []), ensure_ascii=False),
            'custom_user_input_fields_data': json.dumps(product_data.get('custom_user_input_fields', []),
                                                        ensure_ascii=False),
            'custom_option_fields_data': json.dumps(product_data.get('custom_option_fields', []), ensure_ascii=False),

            # SEO
            'seo_title': seo_title_en,
            'seo_title_ar': seo_title_ar,
            'seo_description': seo_desc_en,
            'seo_description_ar': seo_desc_ar,

            # Rating
            'rating_average': rating_avg,
            'rating_count': rating_count,

            # Purchase Restrictions
            'min_quantity_per_cart': int(min_qty) if min_qty else None,
            'max_quantity_per_cart': int(max_qty) if max_qty else None,
            'availability_period_start': avail_start,
            'availability_period_end': avail_end,
            'sale_price_period_start': sale_start,
            'sale_price_period_end': sale_end,

            # Statistics
            'sold_products_count': int(product_data.get('sold_products_count', 0) or 0),
            'waiting_customers_count': int(product_data.get('waiting_customers_count', 0) or 0),

            # Related Products
            'related_products_settings': product_data.get('related_products_settings', ''),
            'related_products_title': product_data.get('related_products_title', ''),

            # Metadata
            'metafields': json.dumps(product_data.get('metafields', {}), ensure_ascii=False) if product_data.get(
                'metafields') else '',
            'meta': json.dumps(product_data.get('meta', {}), ensure_ascii=False) if product_data.get('meta') else '',

            # Badge
            'badge_body': badge_body,
            'badge_body_ar': badge_body_ar,
            'badge_icon_code': badge_icon,

            # Timestamps
            'zid_created_at': self._parse_datetime(product_data.get('created_at')),
            'zid_updated_at': self._parse_datetime(product_data.get('updated_at')),
            'last_sync_date': fields.Datetime.now(),

            # Raw Response
            'raw_response': json.dumps(product_data, ensure_ascii=False),
        }

        return values

    def action_view_raw_data(self):
        """View raw JSON data in a popup"""
        self.ensure_one()
        return {
            'name': _('Raw Product Data'),
            'type': 'ir.actions.act_window',
            'res_model': 'zid.product',
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': self.env.ref('your_module.view_zid_product_raw_data_form').id,
            'target': 'new',
        }

    def _get_category_ids(self, categories_data, connector_id):
        """Resolve Zid category IDs to Odoo records"""
        if not categories_data:
            return False
            
        category_obj = self.env['zid.product.category']
        category_ids = []
        
        for cat_data in categories_data:
            if not isinstance(cat_data, dict):
                continue
                
            zid_cat_id = str(cat_data.get('id', ''))
            if not zid_cat_id:
                continue
                
            # Find existing category
            category = category_obj.search([
                ('zid_category_id', '=', zid_cat_id),
                ('zid_connector_id', '=', connector_id)
            ], limit=1)
            
            # If not found, create it recursively
            if not category:
                category = category_obj.create_or_update_from_zid(cat_data, connector_id)
                
            if category:
                category_ids.append(category.id)
                
        return [(6, 0, category_ids)]

    def create_or_update_odoo_product(self):
        """Create or update Odoo product from Zid product data"""
        self.ensure_one()

        product_template = self.env['product.template']
        product_product = self.env['product.product']

        # Check if already linked
        if self.odoo_product_id:
            # Update existing product
            self._update_odoo_product(self.odoo_product_id)
            return self.odoo_product_id

        # Search for existing product by SKU or barcode
        existing_product = False
        if self.sku:
            existing_product = product_product.search([
                ('default_code', '=', self.sku)
            ], limit=1)

        if not existing_product and self.barcode:
            existing_product = product_product.search([
                ('barcode', '=', self.barcode)
            ], limit=1)

        if existing_product:
            # Link to existing product
            self.odoo_product_id = existing_product
            self._update_odoo_product(existing_product)
            return existing_product

        # Create new product
        vals = self._prepare_odoo_product_values()

        # Create product template first
        template = product_template.create(vals)

        # Get the product variant
        product = template.product_variant_ids[0] if template.product_variant_ids else False

        if product:
            # Link the Zid product to Odoo product
            self.odoo_product_id = product

            # Update Zid fields in product template
            template.write({
                'zid_product_id': self.zid_product_id,
                'zid_connector_id': self.zid_connector_id.id,
                'zid_sku': self.sku,
                'zid_barcode': self.barcode,
                'zid_price': self.price,
                'zid_sale_price': self.sale_price,
                'zid_quantity': self.quantity,
                'zid_is_infinite': self.is_infinite,
                'zid_is_published': self.is_published,
                'zid_is_draft': self.is_draft,
                'zid_last_sync': fields.Datetime.now(),
                'zid_sync_status': 'synced',
                'zid_exists': True,
            })

            _logger.info(f"Created Odoo product {product.display_name} from Zid product {self.zid_product_id}")

        return product

    def _prepare_odoo_product_values(self):
        """Prepare values for creating Odoo product"""
        self.ensure_one()

        # Determine product type based on Zid data
        if not self.requires_shipping:
            detailed_type = 'service'
        elif self.is_infinite:
            detailed_type = 'consu'  # Consumable (no stock tracking)
        else:
            detailed_type = 'product'  # Storable product

        # Prepare basic values
        vals = {
            'name': self.name or 'Unknown Product',
            'image_1920': self.main_image,
            'default_code': self.sku,
            'barcode': self.barcode if self.barcode else False,
            'list_price': self.sale_price if self.sale_price > 0 else self.price,
            'standard_price': self.cost if self.cost > 0 else 0.0,
            'type': 'product' if detailed_type == 'product' else 'consu',
            'detailed_type': detailed_type,
            'sale_ok': self.is_published and not self.is_draft,
            'purchase_ok': True,
            'active': True,
            'weight': self.weight_value if self.weight_value > 0 else 0.0,
            'volume': 0.0,
            'description': self.description or '',
            'description_sale': self.short_description or '',
            'description_purchase': self.short_description or '',

            # Zid specific fields
            'zid_product_id': self.zid_product_id,
            'zid_connector_id': self.zid_connector_id.id,
            'zid_sku': self.sku,
            'zid_barcode': self.barcode,
            'zid_price': self.price,
            'zid_sale_price': self.sale_price,
            'zid_quantity': self.quantity,
            'zid_is_infinite': self.is_infinite,
            'zid_is_published': self.is_published,
            'zid_is_draft': self.is_draft,
            'zid_is_taxable': self.is_taxable,
            'zid_requires_shipping': self.requires_shipping,
            'zid_has_options': self.has_options,
            'zid_has_fields': self.has_fields,
            'zid_html_url': self.html_url,
            'zid_slug': self.slug,
            'zid_product_class': self.product_class,
            'zid_currency': self.currency_code,
            'zid_currency_symbol': self.currency_symbol,
            'zid_formatted_price': self.formatted_price,
            'zid_formatted_sale_price': self.formatted_sale_price,
            'zid_created_at': self.zid_created_at,
            'zid_updated_at': self.zid_updated_at,
            'zid_last_sync': fields.Datetime.now(),
            'zid_sync_status': 'synced',
            'zid_exists': True,
        }

        # Set tax based on is_taxable
        if self.is_taxable:
            # Get default tax for sales
            taxes = self.env['account.tax'].search([
                ('type_tax_use', '=', 'sale'),
                ('company_id', '=', self.env.company.id)
            ], limit=1)
            if taxes:
                vals['taxes_id'] = [(6, 0, taxes.ids)]

        # Set product category if exists
        if self.categories_data:
            try:
                categories = json.loads(self.categories_data)
                if categories and isinstance(categories, list):
                    # Try to find or create category
                    first_cat = categories[0]
                    if isinstance(first_cat, dict):
                        cat_name = first_cat.get('name', {})
                        if isinstance(cat_name, dict):
                            cat_name = cat_name.get('en') or cat_name.get('ar')
                        else:
                            cat_name = str(cat_name)

                        if cat_name:
                            category = self.env['product.category'].search([
                                ('name', '=', cat_name)
                            ], limit=1)

                            if not category:
                                category = self.env['product.category'].create({
                                    'name': cat_name
                                })

                            vals['categ_id'] = category.id
            except:
                pass

        return vals

    def _update_odoo_product(self, product):
        """Update existing Odoo product with Zid data"""
        self.ensure_one()

        template = product.product_tmpl_id

        # Update product template
        update_vals = {
            'list_price': self.sale_price if self.sale_price > 0 else self.price,
            'standard_price': self.cost if self.cost > 0 else template.standard_price,
            'weight': self.weight_value if self.weight_value > 0 else template.weight,
            'active': True,
            'image_1920': self.main_image if not template.image_1920 else template.image_1920,

            # Update Zid fields
            'zid_price': self.price,
            'zid_sale_price': self.sale_price,
            'zid_quantity': self.quantity,
            'zid_is_infinite': self.is_infinite,
            'zid_is_published': self.is_published,
            'zid_is_draft': self.is_draft,
            'zid_last_sync': fields.Datetime.now(),
            'zid_sync_status': 'synced',
        }

        # Only update name if not already customized
        if not template.name or template.name == 'Unknown Product':
            update_vals['name'] = self.name or template.name

        # Only update SKU if empty
        if not template.default_code:
            update_vals['default_code'] = self.sku

        # Only update barcode if empty
        if not template.barcode and self.barcode:
            update_vals['barcode'] = self.barcode

        template.write(update_vals)

        if template.detailed_type == 'product' and not self.is_infinite:
            self._update_odoo_stock(product)

        # Sync gallery images
        self._sync_odoo_gallery_images(template)

        _logger.info(f"Updated Odoo product {product.display_name} from Zid product {self.zid_product_id}")

    def _sync_odoo_gallery_images(self, template, force=False):
        """Sync Zid gallery images to Odoo product template extra images"""
        self.ensure_one()
        if not self.zid_image_ids:
            return

        # Check if native Odoo product.image model exists (requires website_sale)
        if 'product.image' in self.env:
            odoo_image_model = self.env['product.image']
            
            if force:
                template.product_template_image_ids.unlink()
            
            existing_odoo = template.product_template_image_ids
            
            # Simple sync: if Odoo has no images, add them all
            if not existing_odoo:
                for zid_img in self.zid_image_ids:
                    odoo_image_model.create({
                        'name': f"{template.name} - Image {zid_img.sequence}",
                        'image_1920': zid_img.image,
                        'product_tmpl_id': template.id,
                    })
        
        # Link our custom images to the template for display regardless of website_sale
        for zid_img in self.zid_image_ids:
            zid_img.product_tmpl_id = template.id

    def _update_odoo_stock(self, product):
        """Update Odoo product stock from Zid quantity"""
        self.ensure_one()

        # Get default location
        location = self.env['stock.location'].search([
            ('usage', '=', 'internal'),
            ('company_id', '=', self.env.company.id)
        ], limit=1)

        if not location:
            _logger.warning("No internal location found for stock update")
            return

        # Get current stock
        quant = self.env['stock.quant'].search([
            ('product_id', '=', product.id),
            ('location_id', '=', location.id)
        ], limit=1)

        current_qty = quant.quantity if quant else 0.0

        # Calculate difference
        diff = self.quantity - current_qty

        if diff != 0:
            # Create stock adjustment
            inventory = self.env['stock.quant'].with_context(inventory_mode=True)

            if quant:
                quant.with_context(inventory_mode=True).write({
                    'inventory_quantity': self.quantity
                })
                quant.action_apply_inventory()
            else:
                inventory.create({
                    'product_id': product.id,
                    'location_id': location.id,
                    'inventory_quantity': self.quantity,
                })

            _logger.info(f"Updated stock for {product.display_name}: {current_qty} -> {self.quantity}")

    @api.model
    def sync_all_to_odoo(self, connector_id=None):
        """Sync all Zid products to Odoo products"""
        domain = [('odoo_product_id', '=', False)]
        if connector_id:
            domain.append(('zid_connector_id', '=', connector_id))

        zid_products = self.search(domain)

        created_count = 0
        updated_count = 0
        error_count = 0

        for zid_product in zid_products:
            try:
                product = zid_product.create_or_update_odoo_product()
                if product:
                    if zid_product.odoo_product_id:
                        updated_count += 1
                    else:
                        created_count += 1
            except Exception as e:
                _logger.error(f"Failed to sync Zid product {zid_product.zid_product_id}: {str(e)}")
                error_count += 1

        _logger.info(f"Sync completed: Created {created_count}, Updated {updated_count}, Errors {error_count}")

        return {
            'created': created_count,
            'updated': updated_count,
            'errors': error_count
        }

    def action_create_odoo_product(self):
        """Action to create/update Odoo product from form view"""
        self.ensure_one()

        product = self.create_or_update_odoo_product()

        if product:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'product.product',
                'res_id': product.id,
                'view_mode': 'form',
                'target': 'current',
            }
        else:
            raise UserError(_('Failed to create Odoo product'))

    def action_view_odoo_product(self):
        """Action to view linked Odoo product"""
        self.ensure_one()

        if not self.odoo_product_id:
            raise UserError(_('No Odoo product linked'))

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'product.product',
            'res_id': self.odoo_product_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_bulk_create_odoo_products(self):
        """Bulk action to create Odoo products for selected Zid products"""
        unmapped_products = self.filtered(lambda p: not p.odoo_product_id)
        
        if not unmapped_products:
            raise UserError(_('All selected products are already mapped to Odoo products'))
        
        created_count = 0
        failed_count = 0
        errors = []
        
        for zid_product in unmapped_products:
            try:
                product = zid_product.create_or_update_odoo_product()
                if product:
                    created_count += 1
                else:
                    failed_count += 1
                    errors.append(f"{zid_product.name}: Failed to create")
            except Exception as e:
                failed_count += 1
                errors.append(f"{zid_product.name}: {str(e)}")
                _logger.error(f"Failed to create Odoo product for {zid_product.name}: {str(e)}")
        
        # Show result notification
        message = _('Created %d Odoo products') % created_count
        if failed_count > 0:
            message += _('\n%d products failed') % failed_count
            if errors:
                message += '\n\nErrors:\n' + '\n'.join(errors[:5])  # Show first 5 errors
                if len(errors) > 5:
                    message += f'\n... and {len(errors) - 5} more errors'
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Bulk Create Products'),
                'message': message,
                'type': 'success' if failed_count == 0 else 'warning',
                'sticky': True,
            }
        }

    def server_action_link_with_odoo_products(self):
        """Server action to relink selected products with Odoo products"""
        # If only one record, open single wizard
        if len(self) == 1:
            return self.action_relink_odoo_product()
            
        # If multiple records, open bulk wizard
        return {
            'name': _('Bulk Link to Odoo Products'),
            'type': 'ir.actions.act_window',
            'res_model': 'zid.product.bulk.relink.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'active_ids': self.ids,
            }
        }

    def action_relink_odoo_product(self):
        """Open the relink wizard for Zid product"""
        self.ensure_one()
        return {
            'name': _('Link to Odoo Product'),
            'type': 'ir.actions.act_window',
            'res_model': 'zid.product.relink.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_zid_product_id': self.id,
                'default_current_product_id': self.odoo_product_id.id if self.odoo_product_id else False,
                'default_new_product_id': self.odoo_product_id.id if self.odoo_product_id else False,
            }
        }
    
    def action_open_record(self):
        """Open the form view for this record"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'zid.product',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }



