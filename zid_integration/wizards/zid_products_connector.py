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

    # Advanced Options
    update_prices = fields.Boolean(
        string='Update Prices',
        default=True,
        help='Update prices for existing products'
    )

    update_stock = fields.Boolean(
        string='Update Stock',
        default=True,
        help='Update stock quantities for existing products'
    )

    update_images = fields.Boolean(
        string='Update Images',
        default=False,
        help='Update product images (may take longer)'
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

    def action_import_products(self):
        """Start the import process"""
        self.ensure_one()

        if not self.zid_connector_id:
            raise UserError(_('Please select a Zid connector'))

        if not self.zid_connector_id.is_connected:
            raise UserError(_('Selected connector is not connected to Zid'))

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
                product_model.create_or_update_from_zid(
                    product_data,
                    self.zid_connector_id.id
                )
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
        """Update existing product based on settings"""
        update_vals = {}

        # Always update basic info
        name_data = product_data.get('name', {})
        if isinstance(name_data, dict):
            update_vals['name'] = name_data.get('en', product.name)
            update_vals['name_ar'] = name_data.get('ar', product.name_ar)

        # Update prices if configured
        if self.update_prices:
            update_vals.update({
                'price': float(product_data.get('price', 0) or 0),
                'sale_price': float(product_data.get('sale_price', 0) or 0),
                'cost': float(product_data.get('cost', 0) or 0),
                'formatted_price': product_data.get('formatted_price', ''),
                'formatted_sale_price': product_data.get('formatted_sale_price', ''),
            })

        # Update stock if configured
        if self.update_stock:
            update_vals.update({
                'quantity': float(product_data.get('quantity', 0) or 0),
                'is_infinite': product_data.get('is_infinite', False),
                'stocks_data': json.dumps(product_data.get('stocks', []), ensure_ascii=False),
            })

        # Update images if configured
        if self.update_images:
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

        # Always update sync date and raw response
        update_vals.update({
            'last_sync_date': fields.Datetime.now(),
            'raw_response': json.dumps(product_data, ensure_ascii=False),
            'zid_updated_at': product_data.get('updated_at'),
        })

        product.write(update_vals)
        
        # Update location lines after updating product
        if self.update_stock:
            product._update_location_lines(product_data)

    def _generate_summary(self):
        """Generate import summary HTML"""
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
                        <li>Update Prices: {'Yes' if self.update_prices else 'No'}</li>
                        <li>Update Stock: {'Yes' if self.update_stock else 'No'}</li>
                        <li>Update Images: {'Yes' if self.update_images else 'No'}</li>
                    </ul>
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