from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import json
import logging
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)


class ZidProductsConnector(models.TransientModel):
    _name = 'zid.products.connector'
    _description = 'Zid Products Import Wizard'

    # Connector Selection
    zid_connector_id = fields.Many2one(
        'zid.connector',
        string='Zid Connector',
        required=True,
        default=lambda self: self._get_default_connector(),
        domain=[('authorization_status', '=', 'connected')]
    )

    # Import Options
    import_mode = fields.Selection([
        ('all', 'Import All Products'),
        ('new', 'Import New Products Only'),
        ('update', 'Update Existing Products Only'),
        ('new_and_update', 'Import New and Update Existing')
    ], string='Import Mode', default='new_and_update', required=True)

    page_size = fields.Integer(
        string='Products per Page',
        default=50,
        help='Number of products to fetch per API call (max 50)'
    )

    max_pages = fields.Integer(
        string='Maximum Pages',
        default=0,
        help='Maximum number of pages to import (0 for all)'
    )

    # Filters
    filter_by_attributes = fields.Boolean(
        string='Filter by Attributes',
        default=False
    )

    attribute_values = fields.Char(
        string='Attribute Values',
        help='Comma-separated values (e.g., nike,black,large)'
    )

    filter_published_only = fields.Boolean(
        string='Published Products Only',
        default=False
    )

    filter_in_stock_only = fields.Boolean(
        string='In Stock Only',
        default=False
    )

    # Granular Update Options - Basic Information
    update_basic_info = fields.Boolean(
        string='Update Basic Info',
        default=False,
        help='Update product name, description, SKU, and basic details'
    )
    
    update_name = fields.Boolean(
        string='Update Name & Descriptions',
        default=False,
        help='Update product name and descriptions (main and short)'
    )
    
    update_sku_barcode = fields.Boolean(
        string='Update SKU & Barcode',
        default=False,
        help='Update product SKU and barcode'
    )

    # Pricing Options
    update_prices = fields.Boolean(
        string='Update Prices',
        default=False,
        help='Update all pricing information'
    )
    
    update_main_price = fields.Boolean(
        string='Update Main Price',
        default=False,
        help='Update main product price only'
    )
    
    update_sale_price = fields.Boolean(
        string='Update Sale Price',
        default=False,
        help='Update sale/discounted price only'
    )
    
    update_cost_price = fields.Boolean(
        string='Update Cost Price',
        default=False,
        help='Update cost price only'
    )

    # Stock & Inventory Options
    update_stock = fields.Boolean(
        string='Update Stock',
        default=False,
        help='Update all stock-related information'
    )
    
    update_quantities = fields.Boolean(
        string='Update Quantities Only',
        default=False,
        help='Update stock quantities without location data'
    )
    
    update_location_lines = fields.Boolean(
        string='Update Location Lines',
        default=False,
        help='Update stock by location (warehouse/store data)'
    )

    # Images & Media Options
    update_images = fields.Boolean(
        string='Update Images',
        default=False,
        help='Update all image-related data'
    )
    
    update_main_image = fields.Boolean(
        string='Update Main Image Only',
        default=False,
        help='Update only the main product image'
    )
    
    update_gallery_images = fields.Boolean(
        string='Update Gallery Images',
        default=False,
        help='Update product gallery/additional images'
    )

    # Categories & Classification
    update_categories = fields.Boolean(
        string='Update Categories',
        default=False,
        help='Update product categories and classifications'
    )

    # Product Attributes & Variants
    update_attributes = fields.Boolean(
        string='Update Attributes',
        default=False,
        help='Update product attributes and variant data'
    )

    # SEO & Marketing
    update_seo = fields.Boolean(
        string='Update SEO Data',
        default=False,
        help='Update SEO titles, descriptions, and keywords'
    )
    
    update_seo_titles = fields.Boolean(
        string='Update SEO Titles Only',
        default=False,
        help='Update SEO titles without descriptions'
    )
    
    update_seo_descriptions = fields.Boolean(
        string='Update SEO Descriptions Only',
        default=False,
        help='Update SEO descriptions without titles'
    )
    
    update_keywords = fields.Boolean(
        string='Update Keywords',
        default=False,
        help='Update product keywords and tags'
    )

    # Status & Publishing
    update_status = fields.Boolean(
        string='Update Status',
        default=False,
        help='Update product status (published/draft/active)'
    )
    
    update_publish_status = fields.Boolean(
        string='Update Publish Status Only',
        default=False,
        help='Update published/unpublished status only'
    )
    
    update_draft_status = fields.Boolean(
        string='Update Draft Status Only',
        default=False,
        help='Update draft status only'
    )

    # Weight & Shipping
    update_weight_shipping = fields.Boolean(
        string='Update Weight & Shipping',
        default=False,
        help='Update weight and shipping requirements'
    )

    # Badge & Promotional
    update_badge = fields.Boolean(
        string='Update Badge',
        default=False,
        help='Update product badge and promotional text'
    )

    # Advanced Data
    update_metadata = fields.Boolean(
        string='Update Metadata',
        default=False,
        help='Update advanced metadata and custom fields'
    )
    
    update_raw_data = fields.Boolean(
        string='Update Raw JSON Data',
        default=False,
        help='Update all raw JSON data fields (variants, options, etc.)'
    )

    skip_drafts = fields.Boolean(
        string='Skip Draft Products',
        default=True,
        help='Do not import products marked as draft'
    )

    # Progress Information
    state = fields.Selection([
        ('draft', 'Draft'),
        ('importing', 'Importing'),
        ('done', 'Done'),
        ('error', 'Error')
    ], string='Status', default='draft', readonly=True)

    progress_text = fields.Text(
        string='Progress',
        readonly=True
    )

    current_page = fields.Integer(
        string='Current Page',
        default=0,
        readonly=True
    )

    total_pages = fields.Integer(
        string='Total Pages',
        readonly=True
    )

    total_products = fields.Integer(
        string='Total Products',
        readonly=True
    )

    imported_count = fields.Integer(
        string='Imported',
        readonly=True
    )

    updated_count = fields.Integer(
        string='Updated',
        readonly=True
    )

    skipped_count = fields.Integer(
        string='Skipped',
        readonly=True
    )

    error_count = fields.Integer(
        string='Errors',
        readonly=True
    )

    # Results
    import_summary = fields.Html(
        string='Import Summary',
        readonly=True
    )

    error_log = fields.Text(
        string='Error Log',
        readonly=True
    )

    # Last Import Info
    last_import_date = fields.Datetime(
        string='Last Import Date',
        compute='_compute_last_import',
        store=False
    )

    last_import_count = fields.Integer(
        string='Last Import Count',
        compute='_compute_last_import',
        store=False
    )

    @api.model
    def _get_default_connector(self):
        """Get default connector if only one exists and is connected"""
        connectors = self.env['zid.connector'].search([
            ('authorization_status', '=', 'connected')
        ])
        if len(connectors) == 1:
            return connectors.id
        return False

    @api.depends('zid_connector_id')
    def _compute_last_import(self):
        for wizard in self:
            if wizard.zid_connector_id:
                products = self.env['zid.product'].search([
                    ('zid_connector_id', '=', wizard.zid_connector_id.id)
                ], order='create_date desc', limit=1)

                if products:
                    wizard.last_import_date = products.create_date
                    wizard.last_import_count = self.env['zid.product'].search_count([
                        ('zid_connector_id', '=', wizard.zid_connector_id.id)
                    ])
                else:
                    wizard.last_import_date = False
                    wizard.last_import_count = 0
            else:
                wizard.last_import_date = False
                wizard.last_import_count = 0

    @api.constrains('page_size')
    def _check_page_size(self):
        for wizard in self:
            if wizard.page_size <= 0 or wizard.page_size > 50:
                raise ValidationError(_('Page size must be between 1 and 50'))

    def _validate_update_options(self):
        """Validate that at least some update options are selected for existing products"""
        self.ensure_one()
        
        if self.import_mode in ['update', 'new_and_update']:
            # Check if any update option is selected
            update_options = [
                self.update_basic_info, self.update_name, self.update_sku_barcode,
                self.update_prices, self.update_main_price, self.update_sale_price, self.update_cost_price,
                self.update_stock, self.update_quantities, self.update_location_lines,
                self.update_images, self.update_main_image, self.update_gallery_images,
                self.update_categories, self.update_attributes,
                self.update_seo, self.update_seo_titles, self.update_seo_descriptions, self.update_keywords,
                self.update_status, self.update_publish_status, self.update_draft_status,
                self.update_weight_shipping, self.update_badge, self.update_metadata, self.update_raw_data
            ]
            
            if not any(update_options):
                raise ValidationError(_(
                    'You must select at least one update option when updating existing products. '
                    'If you don\'t want to update anything, use "Import New Products Only" mode.'
                ))

    def action_import_products(self):
        """Start the import process"""
        self.ensure_one()

        if not self.zid_connector_id:
            raise UserError(_('Please select a Zid connector'))

        if not self.zid_connector_id.is_connected:
            raise UserError(_('Selected connector is not connected to Zid'))

        # Validate update options
        self._validate_update_options()

        # Reset counters
        self.write({
            'state': 'importing',
            'current_page': 0,
            'imported_count': 0,
            'updated_count': 0,
            'skipped_count': 0,
            'error_count': 0,
            'error_log': '',
            'progress_text': _('Starting import...'),
        })

        # Commit the wizard state
        self.env.cr.commit()

        try:
            # Start import
            self._import_products()

            # Generate summary
            self._generate_summary()

            self.write({
                'state': 'done',
                'progress_text': _('Import completed successfully!')
            })

            # Final commit to ensure everything is saved
            self.env.cr.commit()

        except Exception as e:
            _logger.error(f"Import failed: {str(e)}")
            self.write({
                'state': 'error',
                'progress_text': _('Import failed: %s') % str(e),
                'error_log': self.error_log + f"\n\nFatal Error: {str(e)}"
            })
            self.env.cr.commit()
            raise UserError(_('Import failed: %s') % str(e))

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'zid.products.connector',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def _import_products(self):
        """Main import logic"""
        self.ensure_one()

        page = 1
        total_fetched = 0
        has_next = True

        # Prepare filters
        params = {
            'page_size': self.page_size,
            'page': page
        }

        if self.filter_by_attributes and self.attribute_values:
            params['attribute_values'] = self.attribute_values.strip()

        while has_next:
            # Check if we reached max pages limit
            if self.max_pages > 0 and page > self.max_pages:
                _logger.info(f"Reached maximum pages limit: {self.max_pages}")
                break

            # Update progress
            self.write({
                'current_page': page,
                'progress_text': _('Fetching page %d...') % page
            })

            try:
                # Fetch products from API
                params['page'] = page
                response = self.zid_connector_id.api_request(
                    endpoint='products/',
                    method='GET',
                    params=params
                )

                # Handle response
                products_list = self._extract_products_from_response(response)

                if not products_list:
                    _logger.info("No more products to fetch")
                    has_next = False
                    break

                # Process products
                for product_data in products_list:
                    try:
                        self._process_single_product(product_data)
                        # Product is committed inside create_or_update_from_zid
                    except Exception as e:
                        _logger.error(f"Error processing product {product_data.get('id')}: {str(e)}")
                        self.error_log += f"\nProduct {product_data.get('id')}: {str(e)}"
                        self.error_count += 1

                    total_fetched += 1

                # Check for next page
                if isinstance(response, dict):
                    # Check different pagination formats
                    has_next = bool(
                        response.get('next') or
                        (response.get('count', 0) > page * self.page_size)
                    )

                    # Update total if available
                    if 'count' in response and not self.total_products:
                        self.total_products = response.get('count', 0)
                else:
                    # If response is a list, check if we got full page
                    has_next = len(products_list) == self.page_size

                page += 1

            except Exception as e:
                _logger.error(f"Error fetching page {page}: {str(e)}")
                self.error_log += f"\nError on page {page}: {str(e)}"
                self.error_count += 1

                # Don't rollback everything - products may have been committed individually
                # Just continue with next page or stop based on error
                if "401" in str(e) or "authentication" in str(e).lower():
                    raise  # Stop on authentication errors
                else:
                    page += 1  # Continue with next page

        _logger.info(f"Import completed. Total fetched: {total_fetched}")

    def _extract_products_from_response(self, response):
        """Extract products list from API response"""
        products_list = []

        if isinstance(response, dict):
            # Try different response formats
            if 'results' in response:
                products_list = response.get('results', [])
            elif 'products' in response:
                products_list = response.get('products', [])
            elif 'data' in response:
                products_list = response.get('data', [])
            elif response.get('id'):
                # Single product response
                products_list = [response]
            else:
                # Look for any list in response
                for key, value in response.items():
                    if isinstance(value, list) and value:
                        # Check if it looks like product data
                        if isinstance(value[0], dict) and 'id' in value[0]:
                            products_list = value
                            break
        elif isinstance(response, list):
            products_list = response

        return products_list

    def _process_single_product(self, product_data):
        """Process a single product"""
        # Check if we should skip this product
        if self._should_skip_product(product_data):
            self.skipped_count += 1
            return

        # Get or create product
        product_model = self.env['zid.product']
        product_id = str(product_data.get('id', ''))

        if not product_id:
            _logger.warning("Product has no ID, skipping")
            self.skipped_count += 1
            return

        existing = product_model.search([
            ('zid_product_id', '=', product_id),
            ('zid_connector_id', '=', self.zid_connector_id.id)
        ], limit=1)

        if existing:
            # Update existing product based on mode
            if self.import_mode in ['update', 'new_and_update']:
                self._update_product(existing, product_data)
                self.updated_count += 1
            else:
                self.skipped_count += 1
        else:
            # Create new product based on mode
            if self.import_mode in ['all', 'new', 'new_and_update']:
                # Create product with controlled updates based on wizard settings
                self._create_new_product(product_data)
                self.imported_count += 1
            else:
                self.skipped_count += 1

        # Update progress
        total_processed = self.imported_count + self.updated_count + self.skipped_count
        if total_processed % 10 == 0:  # Update every 10 products
            self.write({
                'progress_text': _('Processed %d products...') % total_processed
            })

    def _should_skip_product(self, product_data):
        """Check if product should be skipped based on filters"""
        # Skip drafts if configured
        if self.skip_drafts and product_data.get('is_draft'):
            return True

        # Skip unpublished if configured
        if self.filter_published_only and not product_data.get('is_published'):
            return True

        # Skip out of stock if configured
        if self.filter_in_stock_only:
            quantity = product_data.get('quantity', 0)
            is_infinite = product_data.get('is_infinite', False)
            if not is_infinite and quantity <= 0:
                return True

        return False

    def _update_product(self, product, product_data):
        """Update existing product based on granular settings"""
        update_vals = {}

        # Update basic info (name, descriptions) if configured
        if self.update_basic_info or self.update_name:
            name_data = product_data.get('name', {})
            if isinstance(name_data, dict):
                update_vals['name'] = name_data.get('en', product.name)
                update_vals['name_ar'] = name_data.get('ar', product.name_ar)
            
            # Update descriptions
            desc_data = product_data.get('description', {})
            if isinstance(desc_data, dict):
                update_vals['description'] = desc_data.get('en', product.description)
                update_vals['description_ar'] = desc_data.get('ar', product.description_ar)
            
            short_desc_data = product_data.get('short_description', {})
            if isinstance(short_desc_data, dict):
                update_vals['short_description'] = short_desc_data.get('en', product.short_description)
                update_vals['short_description_ar'] = short_desc_data.get('ar', product.short_description_ar)

        # Update SKU and barcode if configured
        if self.update_basic_info or self.update_sku_barcode:
            update_vals.update({
                'sku': product_data.get('sku', product.sku),
                'barcode': product_data.get('barcode', product.barcode),
            })

        # Update pricing based on granular options
        if self.update_prices:
            # Update all prices
            update_vals.update({
                'price': float(product_data.get('price', 0) or 0),
                'sale_price': float(product_data.get('sale_price', 0) or 0),
                'cost': float(product_data.get('cost', 0) or 0),
                'formatted_price': product_data.get('formatted_price', ''),
                'formatted_sale_price': product_data.get('formatted_sale_price', ''),
            })
        else:
            # Update individual price components
            if self.update_main_price:
                update_vals['price'] = float(product_data.get('price', 0) or 0)
                update_vals['formatted_price'] = product_data.get('formatted_price', '')
            
            if self.update_sale_price:
                update_vals['sale_price'] = float(product_data.get('sale_price', 0) or 0)
                update_vals['formatted_sale_price'] = product_data.get('formatted_sale_price', '')
            
            if self.update_cost_price:
                update_vals['cost'] = float(product_data.get('cost', 0) or 0)

        # Update stock based on granular options
        if self.update_stock:
            # Update all stock data
            update_vals.update({
                'quantity': float(product_data.get('quantity', 0) or 0),
                'is_infinite': product_data.get('is_infinite', False),
                'stocks_data': json.dumps(product_data.get('stocks', []), ensure_ascii=False),
            })
        elif self.update_quantities:
            # Update only quantities
            update_vals.update({
                'quantity': float(product_data.get('quantity', 0) or 0),
                'is_infinite': product_data.get('is_infinite', False),
            })

        # Update images based on granular options
        if self.update_images:
            # Update all image data
            images = product_data.get('images', [])
            main_image_url = ''
            main_image_binary = False
            
            if images and isinstance(images, list):
                # Sort by display order
                images = sorted(images, key=lambda x: x.get('display_order', 0))
                first_image = images[0]
                if isinstance(first_image, dict):
                    # Zid nested image object structure
                    image_obj = first_image.get('image', {})
                    if isinstance(image_obj, dict):
                        main_image_url = image_obj.get('full_size') or image_obj.get('large') or image_obj.get('medium')
                    
                    # Fallback
                    if not main_image_url:
                        main_image_url = first_image.get('url', '') or first_image.get('thumbnail', '')

                # Download image
                if main_image_url:
                    try:
                        import requests
                        import base64
                        response = requests.get(main_image_url, timeout=10)
                        if response.status_code == 200:
                            main_image_binary = base64.b64encode(response.content)
                    except Exception as e:
                        _logger.warning(f"Failed to download image: {str(e)}")

            update_vals.update({
                'main_image_url': main_image_url,
                'main_image': main_image_binary,
                'images_data': json.dumps(images, ensure_ascii=False),
            })
        elif self.update_main_image:
            # Update only main image
            images = product_data.get('images', [])
            main_image_url = ''
            main_image_binary = False
            
            if images and isinstance(images, list):
                images = sorted(images, key=lambda x: x.get('display_order', 0))
                first_image = images[0]
                if isinstance(first_image, dict):
                    image_obj = first_image.get('image', {})
                    if isinstance(image_obj, dict):
                        main_image_url = image_obj.get('full_size') or image_obj.get('large') or image_obj.get('medium')
                    
                    if not main_image_url:
                        main_image_url = first_image.get('url', '') or first_image.get('thumbnail', '')

                if main_image_url:
                    try:
                        import requests
                        import base64
                        response = requests.get(main_image_url, timeout=10)
                        if response.status_code == 200:
                            main_image_binary = base64.b64encode(response.content)
                    except Exception as e:
                        _logger.warning(f"Failed to download image: {str(e)}")

            update_vals.update({
                'main_image_url': main_image_url,
                'main_image': main_image_binary,
            })

        # Update categories if configured
        if self.update_categories:
            update_vals['categories_data'] = json.dumps(product_data.get('categories', []), ensure_ascii=False)

        # Update attributes if configured
        if self.update_attributes:
            update_vals.update({
                'attributes_data': json.dumps(product_data.get('attributes', []), ensure_ascii=False),
                'variants_data': json.dumps(product_data.get('variants', []), ensure_ascii=False),
                'options_data': json.dumps(product_data.get('options', []), ensure_ascii=False),
                'has_options': product_data.get('has_options', False),
                'has_fields': product_data.get('has_fields', False),
            })

        # Update SEO based on granular options
        if self.update_seo:
            # Update all SEO data
            seo_data = product_data.get('seo', {})
            seo_title_data = seo_data.get('title', {}) if isinstance(seo_data, dict) else {}
            seo_desc_data = seo_data.get('description', {}) if isinstance(seo_data, dict) else {}

            if isinstance(seo_title_data, dict):
                update_vals['seo_title'] = seo_title_data.get('en', '')
                update_vals['seo_title_ar'] = seo_title_data.get('ar', '')

            if isinstance(seo_desc_data, dict):
                update_vals['seo_description'] = seo_desc_data.get('en', '')
                update_vals['seo_description_ar'] = seo_desc_data.get('ar', '')
            
            update_vals['keywords_data'] = json.dumps(product_data.get('keywords', []), ensure_ascii=False)
        else:
            # Update individual SEO components
            if self.update_seo_titles:
                seo_data = product_data.get('seo', {})
                seo_title_data = seo_data.get('title', {}) if isinstance(seo_data, dict) else {}
                if isinstance(seo_title_data, dict):
                    update_vals['seo_title'] = seo_title_data.get('en', '')
                    update_vals['seo_title_ar'] = seo_title_data.get('ar', '')
            
            if self.update_seo_descriptions:
                seo_data = product_data.get('seo', {})
                seo_desc_data = seo_data.get('description', {}) if isinstance(seo_data, dict) else {}
                if isinstance(seo_desc_data, dict):
                    update_vals['seo_description'] = seo_desc_data.get('en', '')
                    update_vals['seo_description_ar'] = seo_desc_data.get('ar', '')
            
            if self.update_keywords:
                update_vals['keywords_data'] = json.dumps(product_data.get('keywords', []), ensure_ascii=False)

        # Update status based on granular options
        if self.update_status:
            # Update all status fields
            update_vals.update({
                'is_published': product_data.get('is_published', True),
                'is_draft': product_data.get('is_draft', False),
                'is_taxable': product_data.get('is_taxable', False),
                'requires_shipping': product_data.get('requires_shipping', True),
            })
        else:
            # Update individual status components
            if self.update_publish_status:
                update_vals['is_published'] = product_data.get('is_published', True)
            
            if self.update_draft_status:
                update_vals['is_draft'] = product_data.get('is_draft', False)

        # Update weight and shipping if configured
        if self.update_weight_shipping:
            weight_data = product_data.get('weight', {})
            if isinstance(weight_data, dict):
                update_vals['weight_value'] = float(weight_data.get('value', 0) or 0)
                update_vals['weight_unit'] = weight_data.get('unit', 'kg')
            update_vals['requires_shipping'] = product_data.get('requires_shipping', True)

        # Update badge if configured
        if self.update_badge:
            badge_data = product_data.get('badge', {})
            if isinstance(badge_data, dict):
                badge_body_data = badge_data.get('body', {})
                if isinstance(badge_body_data, dict):
                    update_vals['badge_body'] = badge_body_data.get('en', '')
                    update_vals['badge_body_ar'] = badge_body_data.get('ar', '')
                badge_icon_data = badge_data.get('icon', {})
                if isinstance(badge_icon_data, dict):
                    update_vals['badge_icon_code'] = badge_icon_data.get('code', '')

        # Update metadata if configured
        if self.update_metadata:
            update_vals.update({
                'metafields': json.dumps(product_data.get('metafields', {}), ensure_ascii=False) if product_data.get('metafields') else '',
                'meta': json.dumps(product_data.get('meta', {}), ensure_ascii=False) if product_data.get('meta') else '',
                'custom_user_input_fields_data': json.dumps(product_data.get('custom_user_input_fields', []), ensure_ascii=False),
                'custom_option_fields_data': json.dumps(product_data.get('custom_option_fields', []), ensure_ascii=False),
            })

        # Update raw JSON data if configured
        if self.update_raw_data:
            update_vals.update({
                'group_products_data': json.dumps(product_data.get('group_products', []), ensure_ascii=False),
                'variants_data': json.dumps(product_data.get('variants', []), ensure_ascii=False),
                'options_data': json.dumps(product_data.get('options', []), ensure_ascii=False),
            })

        # Always update sync date and raw response
        update_vals.update({
            'last_sync_date': fields.Datetime.now(),
            'raw_response': json.dumps(product_data, ensure_ascii=False),
            'zid_updated_at': product_data.get('updated_at'),
        })

        product.write(update_vals)
        
        # Update location lines only if stock update is enabled
        if self.update_stock or self.update_location_lines:
            product._update_location_lines(product_data)
        
        # Update gallery images only if image update is enabled
        if self.update_images or self.update_gallery_images:
            product._update_gallery_images(product_data)

    def _create_new_product(self, product_data):
        """Create new product with controlled updates based on wizard settings"""
        product_model = self.env['zid.product']
        
        # Prepare basic product values (always include basic structure)
        values = product_model._prepare_product_values(product_data, self.zid_connector_id.id)
        
        # Override values based on wizard settings - if user doesn't want certain data, remove it
        if not (self.update_basic_info or self.update_name):
            # Keep only essential name, remove descriptions
            name_data = product_data.get('name', {})
            if isinstance(name_data, dict):
                values['name'] = name_data.get('en', 'Unknown Product')
                values['name_ar'] = name_data.get('ar', '')
            # Remove descriptions
            values.update({
                'description': '',
                'description_ar': '',
                'short_description': '',
                'short_description_ar': '',
            })
        
        if not (self.update_basic_info or self.update_sku_barcode):
            # Remove SKU and barcode
            values.update({
                'sku': '',
                'barcode': '',
            })
        
        if not (self.update_prices or self.update_main_price or self.update_sale_price or self.update_cost_price):
            # Remove all pricing
            values.update({
                'price': 0.0,
                'sale_price': 0.0,
                'cost': 0.0,
                'formatted_price': '',
                'formatted_sale_price': '',
            })
        elif not self.update_prices:
            # Selective pricing updates
            if not self.update_main_price:
                values.update({
                    'price': 0.0,
                    'formatted_price': '',
                })
            if not self.update_sale_price:
                values.update({
                    'sale_price': 0.0,
                    'formatted_sale_price': '',
                })
            if not self.update_cost_price:
                values['cost'] = 0.0
        
        if not (self.update_stock or self.update_quantities):
            # Remove stock data
            values.update({
                'quantity': 0.0,
                'is_infinite': False,
                'stocks_data': '[]',
            })
        
        if not (self.update_images or self.update_main_image):
            # Remove image data
            values.update({
                'main_image_url': '',
                'main_image': False,
                'images_data': '[]',
            })
        
        if not self.update_categories:
            # Remove category data
            values.update({
                'categories_data': '[]',
                'zid_category_ids': False,
            })
        
        if not self.update_attributes:
            # Remove attribute data
            values.update({
                'attributes_data': '[]',
                'variants_data': '[]',
                'options_data': '[]',
                'has_options': False,
                'has_fields': False,
            })
        
        if not (self.update_seo or self.update_seo_titles or self.update_seo_descriptions or self.update_keywords):
            # Remove SEO data
            values.update({
                'seo_title': '',
                'seo_title_ar': '',
                'seo_description': '',
                'seo_description_ar': '',
                'keywords_data': '[]',
            })
        elif not self.update_seo:
            # Selective SEO updates
            if not self.update_seo_titles:
                values.update({
                    'seo_title': '',
                    'seo_title_ar': '',
                })
            if not self.update_seo_descriptions:
                values.update({
                    'seo_description': '',
                    'seo_description_ar': '',
                })
            if not self.update_keywords:
                values['keywords_data'] = '[]'
        
        if not (self.update_status or self.update_publish_status or self.update_draft_status):
            # Keep default status values
            values.update({
                'is_published': True,
                'is_draft': False,
                'is_taxable': False,
                'requires_shipping': True,
            })
        elif not self.update_status:
            # Selective status updates
            if not self.update_publish_status:
                values['is_published'] = True
            if not self.update_draft_status:
                values['is_draft'] = False
        
        if not self.update_weight_shipping:
            # Remove weight and shipping data
            values.update({
                'weight_value': 0.0,
                'weight_unit': 'kg',
                'requires_shipping': True,
            })
        
        if not self.update_badge:
            # Remove badge data
            values.update({
                'badge_body': '',
                'badge_body_ar': '',
                'badge_icon_code': '',
            })
        
        if not self.update_metadata:
            # Remove metadata
            values.update({
                'metafields': '',
                'meta': '',
                'custom_user_input_fields_data': '[]',
                'custom_option_fields_data': '[]',
            })
        
        if not self.update_raw_data:
            # Keep essential raw data but remove optional ones
            values.update({
                'group_products_data': '[]',
            })
        
        # Create the product
        product = product_model.create(values)
        _logger.info(f"Created new Zid product {product_data.get('id')}, DB ID: {product.id}")
        
        # Update location lines only if stock update is enabled
        if self.update_stock or self.update_location_lines:
            try:
                product._update_location_lines(product_data)
            except Exception as e:
                _logger.error(f"Error updating location lines for product {product_data.get('id')}: {str(e)}")
        
        # Update gallery images only if image update is enabled
        if self.update_images or self.update_gallery_images:
            try:
                product._update_gallery_images(product_data)
            except Exception as e:
                _logger.error(f"Error updating gallery for product {product_data.get('id')}: {str(e)}")
        
        return product

    def _generate_summary(self):
        """Generate import summary HTML"""
        # Collect enabled update options
        update_options = []
        if self.update_basic_info:
            update_options.append("Basic Info (All)")
        else:
            if self.update_name:
                update_options.append("Names & Descriptions")
            if self.update_sku_barcode:
                update_options.append("SKU & Barcode")
        
        if self.update_prices:
            update_options.append("Prices (All)")
        else:
            price_parts = []
            if self.update_main_price:
                price_parts.append("Main Price")
            if self.update_sale_price:
                price_parts.append("Sale Price")
            if self.update_cost_price:
                price_parts.append("Cost Price")
            if price_parts:
                update_options.append(f"Prices ({', '.join(price_parts)})")
        
        if self.update_stock:
            update_options.append("Stock (All)")
        else:
            stock_parts = []
            if self.update_quantities:
                stock_parts.append("Quantities")
            if self.update_location_lines:
                stock_parts.append("Location Lines")
            if stock_parts:
                update_options.append(f"Stock ({', '.join(stock_parts)})")
        
        if self.update_images:
            update_options.append("Images (All)")
        else:
            image_parts = []
            if self.update_main_image:
                image_parts.append("Main Image")
            if self.update_gallery_images:
                image_parts.append("Gallery")
            if image_parts:
                update_options.append(f"Images ({', '.join(image_parts)})")
        
        if self.update_categories:
            update_options.append("Categories")
        if self.update_attributes:
            update_options.append("Attributes")
        
        if self.update_seo:
            update_options.append("SEO (All)")
        else:
            seo_parts = []
            if self.update_seo_titles:
                seo_parts.append("Titles")
            if self.update_seo_descriptions:
                seo_parts.append("Descriptions")
            if self.update_keywords:
                seo_parts.append("Keywords")
            if seo_parts:
                update_options.append(f"SEO ({', '.join(seo_parts)})")
        
        if self.update_status:
            update_options.append("Status (All)")
        else:
            status_parts = []
            if self.update_publish_status:
                status_parts.append("Published")
            if self.update_draft_status:
                status_parts.append("Draft")
            if status_parts:
                update_options.append(f"Status ({', '.join(status_parts)})")
        
        if self.update_weight_shipping:
            update_options.append("Weight & Shipping")
        if self.update_badge:
            update_options.append("Badge")
        if self.update_metadata:
            update_options.append("Metadata")
        if self.update_raw_data:
            update_options.append("Raw Data")
        
        update_options_text = ', '.join(update_options) if update_options else 'None (Basic structure only)'

        summary = f"""
        <div class="row">
            <div class="col-md-12">
                <h4>Import Summary</h4>
                <table class="table table-sm">
                    <tbody>
                        <tr>
                            <td><strong>Total Products Processed:</strong></td>
                            <td>{self.imported_count + self.updated_count + self.skipped_count}</td>
                        </tr>
                        <tr>
                            <td><strong>New Products Imported:</strong></td>
                            <td><span class="badge badge-success">{self.imported_count}</span></td>
                        </tr>
                        <tr>
                            <td><strong>Products Updated:</strong></td>
                            <td><span class="badge badge-info">{self.updated_count}</span></td>
                        </tr>
                        <tr>
                            <td><strong>Products Skipped:</strong></td>
                            <td><span class="badge badge-warning">{self.skipped_count}</span></td>
                        </tr>
                        <tr>
                            <td><strong>Errors:</strong></td>
                            <td><span class="badge badge-danger">{self.error_count}</span></td>
                        </tr>
                        <tr>
                            <td><strong>Pages Processed:</strong></td>
                            <td>{self.current_page}</td>
                        </tr>
                    </tbody>
                </table>

                <div class="mt-3">
                    <strong>Import Settings:</strong>
                    <ul>
                        <li>Mode: {dict(self._fields['import_mode'].selection).get(self.import_mode)}</li>
                        <li>Page Size: {self.page_size}</li>
                        <li>Updated Components: {update_options_text}</li>
                    </ul>
                </div>
                
                <div class="mt-3">
                    <strong>Granular Update Control:</strong>
                    <p class="text-muted">
                        This import used granular update control, meaning only the selected components were updated. 
                        Unchecked options remained unchanged, giving you complete control over the synchronization process.
                    </p>
                </div>
            </div>
        </div>
        """

        self.import_summary = summary

    def action_view_products(self):
        """View imported products"""
        self.ensure_one()

        if not self.zid_connector_id:
            raise UserError(_('No connector selected'))

        # Get the imported/updated products in this session
        domain = [('zid_connector_id', '=', self.zid_connector_id.id)]
        
        # If we just finished importing, show recently imported products
        if self.state == 'done' and (self.imported_count > 0 or self.updated_count > 0):
            # Get products created/updated in the last hour (during this import session)
            from datetime import datetime, timedelta
            recent_time = datetime.now() - timedelta(hours=1)
            domain.append('|')
            domain.append(('create_date', '>=', recent_time))
            domain.append(('write_date', '>=', recent_time))

        return {
            'name': _('Zid Products'),
            'type': 'ir.actions.act_window',
            'res_model': 'zid.product',
            'view_mode': 'list,kanban,form',
            'domain': domain,
            'context': {
                'default_zid_connector_id': self.zid_connector_id.id,
                'search_default_group_connector': 1,
            },
            'target': 'current',
        }

    def action_select_all_updates(self):
        """Select all update options"""
        self.ensure_one()
        self.write({
            'update_basic_info': True,
            'update_name': True,
            'update_sku_barcode': True,
            'update_prices': True,
            'update_main_price': True,
            'update_sale_price': True,
            'update_cost_price': True,
            'update_stock': True,
            'update_quantities': True,
            'update_location_lines': True,
            'update_images': True,
            'update_main_image': True,
            'update_gallery_images': True,
            'update_categories': True,
            'update_attributes': True,
            'update_seo': True,
            'update_seo_titles': True,
            'update_seo_descriptions': True,
            'update_keywords': True,
            'update_status': True,
            'update_publish_status': True,
            'update_draft_status': True,
            'update_weight_shipping': True,
            'update_badge': True,
            'update_metadata': True,
            'update_raw_data': True,
        })
        return {'type': 'ir.actions.do_nothing'}

    def action_select_none_updates(self):
        """Deselect all update options"""
        self.ensure_one()
        self.write({
            'update_basic_info': False,
            'update_name': False,
            'update_sku_barcode': False,
            'update_prices': False,
            'update_main_price': False,
            'update_sale_price': False,
            'update_cost_price': False,
            'update_stock': False,
            'update_quantities': False,
            'update_location_lines': False,
            'update_images': False,
            'update_main_image': False,
            'update_gallery_images': False,
            'update_categories': False,
            'update_attributes': False,
            'update_seo': False,
            'update_seo_titles': False,
            'update_seo_descriptions': False,
            'update_keywords': False,
            'update_status': False,
            'update_publish_status': False,
            'update_draft_status': False,
            'update_weight_shipping': False,
            'update_badge': False,
            'update_metadata': False,
            'update_raw_data': False,
        })
        return {'type': 'ir.actions.do_nothing'}

    def action_select_safe_updates(self):
        """Select only safe update options (basic info, prices, stock quantities)"""
        self.ensure_one()
        # First clear all
        self.action_select_none_updates()
        # Then select safe ones
        self.write({
            'update_basic_info': True,
            'update_prices': True,
            'update_quantities': True,
        })
        return {'type': 'ir.actions.do_nothing'}

    def action_select_essential_updates(self):
        """Select only essential update options (names, prices, stock)"""
        self.ensure_one()
        # First clear all
        self.action_select_none_updates()
        # Then select essential ones
        self.write({
            'update_name': True,
            'update_main_price': True,
            'update_sale_price': True,
            'update_quantities': True,
        })
        return {'type': 'ir.actions.do_nothing'}

    def action_view_errors(self):
        """View error log in a popup"""
        self.ensure_one()

        if not self.error_log:
            raise UserError(_('No errors to display'))

        return {
            'name': _('Import Errors'),
            'type': 'ir.actions.act_window',
            'res_model': 'zid.products.connector',
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': False,
            'target': 'new',
        }