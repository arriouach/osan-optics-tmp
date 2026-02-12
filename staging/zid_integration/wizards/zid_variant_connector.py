from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import requests
import json
import logging
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)


class ZidVariantConnector(models.TransientModel):
    _name = 'zid.variant.connector'
    _description = 'Zid Variant Import Wizard'

    # ==================== Configuration Fields ====================
    zid_connector_id = fields.Many2one(
        'zid.connector',
        string='Zid Connector',
        required=True,
        default=lambda self: self._get_default_connector()
    )

    operation_type = fields.Selection([
        ('import_all', 'Import All Variants'),
        ('import_product', 'Import Variants for Specific Product'),
        ('sync_stock', 'Sync Stock Levels Only'),
        ('update_prices', 'Update Prices Only'),
    ], string='Operation Type', default='import_all', required=True)

    # ==================== Product Selection ====================
    product_id = fields.Many2one(
        'zid.product',
        string='Zid Product',
        help='Select product to import variants for'
    )

    product_ids = fields.Many2many(
        'zid.product',
        string='Products',
        help='Select multiple products to import variants'
    )

    # ==================== Import Options ====================
    update_existing = fields.Boolean(
        string='Update Existing Variants',
        default=True,
        help='Update variants that already exist in the system'
    )

    create_new = fields.Boolean(
        string='Create New Variants',
        default=True,
        help='Create variants that do not exist in the system'
    )

    sync_images = fields.Boolean(
        string='Sync Images',
        default=True,
        help='Download and sync product images'
    )

    sync_stock = fields.Boolean(
        string='Sync Stock Levels',
        default=True,
        help='Update stock quantities from Zid'
    )

    sync_prices = fields.Boolean(
        string='Sync Prices',
        default=True,
        help='Update prices from Zid'
    )

    # ==================== Filters ====================
    filter_by_sku = fields.Boolean(
        string='Filter by SKU Pattern',
        default=False
    )

    sku_pattern = fields.Char(
        string='SKU Pattern',
        help='Import only variants with SKU containing this pattern'
    )

    filter_by_stock = fields.Boolean(
        string='Filter by Stock',
        default=False
    )

    stock_filter = fields.Selection([
        ('in_stock', 'In Stock Only'),
        ('out_of_stock', 'Out of Stock Only'),
        ('low_stock', 'Low Stock (< 10 units)'),
    ], string='Stock Filter')

    filter_published = fields.Boolean(
        string='Published Only',
        default=False,  # Changed from True to False
        help='Import only published variants'
    )

    # ==================== Date Filters ====================
    filter_by_date = fields.Boolean(
        string='Filter by Date',
        default=False
    )

    date_from = fields.Datetime(
        string='Modified After',
        default=lambda self: fields.Datetime.now() - timedelta(days=7)
    )

    date_to = fields.Datetime(
        string='Modified Before',
        default=fields.Datetime.now
    )

    # ==================== Progress Fields ====================
    state = fields.Selection([
        ('draft', 'Draft'),
        ('importing', 'Importing'),
        ('done', 'Done'),
        ('error', 'Error')
    ], string='State', default='draft', readonly=True)

    progress_text = fields.Text(
        string='Progress',
        readonly=True
    )

    total_variants = fields.Integer(
        string='Total Variants',
        readonly=True
    )

    imported_variants = fields.Integer(
        string='Imported Variants',
        readonly=True
    )

    updated_variants = fields.Integer(
        string='Updated Variants',
        readonly=True
    )

    failed_variants = fields.Integer(
        string='Failed Variants',
        readonly=True
    )

    error_log = fields.Text(
        string='Error Log',
        readonly=True
    )

    # ==================== Default Methods ====================
    @api.model
    def _get_default_connector(self):
        """Get default connector if only one exists"""
        _logger.info("Getting default connector...")
        connectors = self.env['zid.connector'].search([
            ('authorization_status', '=', 'connected')
        ])
        _logger.info(f"Found {len(connectors)} connected connectors")

        if len(connectors) == 1:
            _logger.info(f"Using default connector ID: {connectors.id}")
            return connectors.id

        _logger.warning("No single default connector found")
        return False

    # ==================== Onchange Methods ====================
    @api.onchange('operation_type')
    def _onchange_operation_type(self):
        _logger.debug(f"Operation type changed to: {self.operation_type}")

        if self.operation_type == 'import_product':
            self.product_ids = False
            _logger.debug("Cleared product_ids for import_product operation")

        elif self.operation_type == 'import_all':
            self.product_id = False
            self.product_ids = False
            _logger.debug("Cleared all product selections for import_all operation")

        elif self.operation_type == 'sync_stock':
            self.sync_stock = True
            self.sync_prices = False
            self.sync_images = False
            self.create_new = False
            _logger.debug("Configured settings for sync_stock operation")

        elif self.operation_type == 'update_prices':
            self.sync_prices = True
            self.sync_stock = False
            self.sync_images = False
            self.create_new = False
            _logger.debug("Configured settings for update_prices operation")

    @api.onchange('filter_by_sku')
    def _onchange_filter_by_sku(self):
        _logger.debug(f"Filter by SKU changed to: {self.filter_by_sku}")
        if not self.filter_by_sku:
            self.sku_pattern = False
            _logger.debug("Cleared SKU pattern")

    @api.onchange('filter_by_stock')
    def _onchange_filter_by_stock(self):
        _logger.debug(f"Filter by stock changed to: {self.filter_by_stock}")
        if not self.filter_by_stock:
            self.stock_filter = False
            _logger.debug("Cleared stock filter")

    @api.onchange('filter_by_date')
    def _onchange_filter_by_date(self):
        _logger.debug(f"Filter by date changed to: {self.filter_by_date}")
        if not self.filter_by_date:
            self.date_from = False
            self.date_to = False
            _logger.debug("Cleared date filters")

    # ==================== Main Import Method ====================
    def action_import_variants(self):
        """Main method to start import process"""
        self.ensure_one()
        _logger.info("=" * 60)
        _logger.info(f"Starting variant import - Operation: {self.operation_type}")
        _logger.info(f"Connector ID: {self.zid_connector_id.id}")
        _logger.info(f"Update existing: {self.update_existing}, Create new: {self.create_new}")
        _logger.info(f"Sync: Images={self.sync_images}, Stock={self.sync_stock}, Prices={self.sync_prices}")

        if not self.zid_connector_id.is_connected:
            _logger.error(f"Zid connector {self.zid_connector_id.id} is not connected!")
            raise UserError(_('Zid connector is not connected!'))

        self.state = 'importing'
        self.progress_text = _('Starting import...\n')
        self.imported_variants = 0
        self.updated_variants = 0
        self.failed_variants = 0
        self.error_log = ''

        try:
            _logger.info(f"Executing operation: {self.operation_type}")

            if self.operation_type == 'import_all':
                self._import_all_variants()
            elif self.operation_type == 'import_product':
                self._import_product_variants()
            elif self.operation_type == 'sync_stock':
                self._sync_stock_levels()
            elif self.operation_type == 'update_prices':
                self._update_prices()

            self.state = 'done'
            self._add_progress(_('\n✓ Import completed successfully!'))

            _logger.info("=" * 60)
            _logger.info("Import completed successfully!")
            _logger.info(
                f"Results: Imported={self.imported_variants}, Updated={self.updated_variants}, Failed={self.failed_variants}")
            _logger.info("=" * 60)

        except Exception as e:
            self.state = 'error'
            self.error_log += f"\n\nFatal Error: {str(e)}"
            self._add_progress(_('\n✗ Import failed with errors!'))

            _logger.error("=" * 60)
            _logger.error(f"Variant import failed: {str(e)}", exc_info=True)
            _logger.error(f"Failed variants count: {self.failed_variants}")
            _logger.error("=" * 60)

            raise UserError(_('Import failed: %s') % str(e))

        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': self.env.context,
        }

    # ==================== Import Methods ====================
    def _import_all_variants(self):
        """Import all variants from all products"""
        _logger.info("Starting import_all_variants operation")
        self._add_progress(_('Fetching all products...\n'))

        # Get all products
        products = self._fetch_all_products()

        if not products:
            _logger.warning("No products found to import")
            self._add_progress(_('No products found.\n'))
            return

        _logger.info(f"Found {len(products)} products to process")
        self._add_progress(_('Found %d products.\n') % len(products))

        # Process each product
        for idx, product_data in enumerate(products, 1):
            product_id = product_data.get('id')
            _logger.info(f"Processing product {idx}/{len(products)}: ID={product_id}")

            # Check if this is just summary data
            variants = product_data.get('variants', [])
            _logger.debug(f"Product data has {len(variants) if variants else 0} variants in list response")

            # If no variants in list data, fetch full product details
            if not variants:
                _logger.info(f"No variants in list data for product {product_id}, fetching full details...")
                full_product_data = self._fetch_product_details(product_id)

                if full_product_data:
                    _logger.debug(f"Full product data fetched, checking for variants...")
                    # Log the structure to understand the response
                    if 'variants' in full_product_data:
                        _logger.info(
                            f"Found {len(full_product_data.get('variants', []))} variants in detailed response")
                    else:
                        _logger.warning(f"No 'variants' key in detailed product response")
                        _logger.debug(f"Available keys in product response: {list(full_product_data.keys())}")

                    self._process_product_variants(full_product_data)
                else:
                    _logger.error(f"Failed to fetch full details for product {product_id}")
            else:
                # Use the data we already have
                self._process_product_variants(product_data)

    def _import_product_variants(self):
        """Import variants for selected products"""
        _logger.info("Starting import_product_variants operation")

        if not self.product_id and not self.product_ids:
            _logger.error("No products selected for import")
            raise UserError(_('Please select at least one product!'))

        products = self.product_ids if self.product_ids else self.product_id
        _logger.info(f"Processing {len(products)} selected products")

        for product in products:
            _logger.info(
                f"Processing product: {product.display_name} (ID: {product.id}, Zid ID: {product.zid_product_id})")
            self._add_progress(_('Processing product: %s\n') % product.display_name)

            # Fetch product details from API
            product_data = self._fetch_product_details(product.zid_product_id)

            if product_data:
                _logger.info(f"Successfully fetched data for product {product.zid_product_id}")
                self._process_product_variants(product_data)
            else:
                _logger.warning(f"Failed to fetch data for product {product.zid_product_id}")

    def _process_product_variants(self, product_data):
        """Process variants for a single product"""
        product_id = str(product_data.get('id', ''))
        product_name = product_data.get('name', {})

        if isinstance(product_name, dict):
            product_name = product_name.get('en', product_name.get('ar', 'Unknown'))

        _logger.info(f"Processing product variants - ID: {product_id}, Name: {product_name}")
        _logger.debug(f"Product data keys: {list(product_data.keys())}")
        self._add_progress(_('Processing product: %s\n') % product_name)

        # Find or create parent product
        parent_product = self.env['zid.product'].search([
            ('zid_product_id', '=', product_id),
            ('zid_connector_id', '=', self.zid_connector_id.id)
        ], limit=1)

        if not parent_product:
            _logger.info(f"Parent product not found, creating new product {product_id}")
            # Create parent product first
            parent_product = self.env['zid.product'].create_or_update_from_zid(
                product_data,
                self.zid_connector_id.id
            )
            _logger.info(f"Created parent product with ID: {parent_product.id}")
        else:
            _logger.info(f"Found existing parent product ID: {parent_product.id}")

        # Check different possible variant locations in the response
        variants = []

        # Try standard 'variants' key
        if 'variants' in product_data:
            variants = product_data.get('variants', [])
            _logger.debug(f"Found variants in 'variants' key: {len(variants)}")

        # Try 'options' or 'variations' keys (some APIs use different names)
        elif 'options' in product_data:
            variants = product_data.get('options', [])
            _logger.debug(f"Found variants in 'options' key: {len(variants)}")

        elif 'variations' in product_data:
            variants = product_data.get('variations', [])
            _logger.debug(f"Found variants in 'variations' key: {len(variants)}")

        # Check if the product itself is the variant (single variant products)
        elif 'sku' in product_data and 'price' in product_data:
            _logger.info("Product appears to be a single variant product, treating product as variant")

            # Calculate total quantity from stocks array if available
            total_quantity = 0
            is_infinite = product_data.get('is_infinite', False)

            if 'stocks' in product_data:
                stocks = product_data.get('stocks', [])
                _logger.debug(f"Product has {len(stocks)} stock locations")

                for stock in stocks:
                    if stock.get('is_infinite'):
                        is_infinite = True
                        _logger.debug(
                            f"Stock location {stock.get('location', {}).get('name', {}).get('en', 'Unknown')} has infinite stock")
                    else:
                        qty = stock.get('available_quantity', 0) or 0
                        total_quantity += qty
                        location_name = stock.get('location', {}).get('name', {})
                        if isinstance(location_name, dict):
                            location_name = location_name.get('en', location_name.get('ar', 'Unknown'))
                        _logger.debug(f"Stock location {location_name}: {qty} units")
            else:
                # Fallback to quantity field if stocks not available
                total_quantity = product_data.get('quantity', 0) or 0

            # Create a variant from the product data itself
            variant_data = {
                'id': product_data.get('id'),
                'sku': product_data.get('sku'),
                'price': product_data.get('price'),
                'sale_price': product_data.get('sale_price'),
                'cost': product_data.get('cost'),
                'quantity': total_quantity,  # Use calculated total
                'is_infinite': is_infinite,
                'is_published': product_data.get('is_published', True),
                'updated_at': product_data.get('updated_at'),
                'formatted_price': product_data.get('formatted_price', ''),
                'formatted_sale_price': product_data.get('formatted_sale_price', ''),
                'stocks': product_data.get('stocks', []),  # Include stocks array
            }
            variants = [variant_data]
            _logger.debug(f"Created single variant from product data with total quantity: {total_quantity}")

        if not variants:
            _logger.warning(f"No variants found for product {product_id}")
            _logger.debug(f"Available product data keys: {list(product_data.keys())}")

            # Log some sample data to understand the structure better
            for key in ['sku', 'price', 'quantity', 'stock', 'inventory', 'stocks']:
                if key in product_data:
                    _logger.debug(f"Product has '{key}': {product_data.get(key)}")

            self._add_progress(_('  No variants found for this product.\n'))
            return

        _logger.info(f"Found {len(variants)} variants for product {product_id}")
        self.total_variants += len(variants)

        # Process each variant
        for idx, variant_data in enumerate(variants, 1):
            variant_id = str(variant_data.get('id', ''))
            sku = variant_data.get('sku', '')

            _logger.info(f"=== Processing Variant {idx}/{len(variants)} ===")
            _logger.info(f"Variant ID: {variant_id}, SKU: {sku}")

            # Log ALL variant data for debugging
            if idx == 1:  # Log complete data for first variant
                _logger.debug(f"First variant complete data structure:")
                for key, value in variant_data.items():
                    if key == 'stocks' and isinstance(value, list):
                        _logger.debug(f"  {key}: [List with {len(value)} items]")
                        for i, stock in enumerate(value):
                            _logger.debug(f"    Stock {i + 1}: {stock}")
                    elif isinstance(value, dict):
                        _logger.debug(f"  {key}: [Dict with keys: {list(value.keys())}]")
                    elif isinstance(value, list):
                        _logger.debug(f"  {key}: [List with {len(value)} items]")
                    else:
                        _logger.debug(f"  {key}: {value}")

            # Process stocks for variant if not already included
            if 'stocks' not in variant_data and 'stocks' in product_data:
                # Some APIs might have stocks at product level for all variants
                variant_data['stocks'] = product_data.get('stocks', [])
                _logger.info(f"Variant inheriting {len(variant_data['stocks'])} stock locations from product")

            # Calculate total quantity from stocks if available
            if 'stocks' in variant_data and variant_data.get('stocks'):
                total_qty = 0
                is_infinite = False
                stocks_info = variant_data.get('stocks', [])

                _logger.info(f"Variant has {len(stocks_info)} stock locations:")
                for stock in stocks_info:
                    location = stock.get('location', {})
                    location_name = location.get('name', {})
                    if isinstance(location_name, dict):
                        location_name = location_name.get('en', location_name.get('ar', 'Unknown'))

                    if stock.get('is_infinite'):
                        is_infinite = True
                        _logger.info(f"  📍 {location_name}: INFINITE stock")
                    else:
                        qty = stock.get('available_quantity', 0) or 0
                        total_qty += qty
                        _logger.info(f"  📍 {location_name}: {qty} units")

                # Update variant data with calculated totals
                variant_data['quantity'] = total_qty
                variant_data['is_infinite'] = is_infinite

                _logger.info(f"  📊 Total Quantity: {total_qty}, Infinite: {is_infinite}")
            else:
                _logger.warning(f"Variant {sku} has no stocks data!")
                _logger.debug(f"Processing variant {idx}/{len(variants)} - ID: {variant_id}")

            _logger.debug(f"Variant data keys: {list(variant_data.keys())}")
            self._process_single_variant(variant_data, parent_product)

    def _process_single_variant(self, variant_data, parent_product):
        """Process a single variant"""
        variant_id = str(variant_data.get('id', ''))
        sku = variant_data.get('sku', '')

        _logger.debug(f"Processing single variant - ID: {variant_id}, SKU: {sku}")

        # Log the first variant's structure for debugging
        if self.imported_variants + self.updated_variants + self.failed_variants == 0:
            _logger.info(f"First variant structure - Keys: {list(variant_data.keys())}")
            _logger.debug(f"First variant sample data:")
            for key in ['id', 'sku', 'price', 'quantity', 'is_published', 'is_infinite']:
                if key in variant_data:
                    _logger.debug(f"  {key}: {variant_data.get(key)}")

            # Log stocks information if available
            if 'stocks' in variant_data:
                stocks = variant_data.get('stocks', [])
                _logger.info(f"First variant has {len(stocks)} stock locations:")
                for stock in stocks:
                    location = stock.get('location', {})
                    location_name = location.get('name', {})
                    if isinstance(location_name, dict):
                        location_name = location_name.get('en', location_name.get('ar', 'Unknown'))
                    else:
                        location_name = str(location_name)

                    qty = stock.get('available_quantity', 0)
                    is_inf = stock.get('is_infinite', False)
                    _logger.info(f"  - {location_name}: {'Infinite' if is_inf else f'{qty} units'}")

        try:
            # Apply filters
            if not self._should_import_variant(variant_data):
                _logger.info(f"Variant {sku} filtered out, skipping")
                self._add_progress(_('  Skipped variant %s (filtered)\n') % sku)
                return

            # Check if variant exists
            existing_variant = self.env['zid.variant'].search([
                ('zid_variant_id', '=', variant_id),
                ('zid_connector_id', '=', self.zid_connector_id.id)
            ], limit=1)

            if existing_variant:
                _logger.debug(f"Found existing variant {sku} with ID: {existing_variant.id}")

                if not self.update_existing:
                    _logger.info(f"Skipping existing variant {sku} (update_existing=False)")
                    self._add_progress(_('  Skipped existing variant %s\n') % sku)
                    return
            else:
                _logger.debug(f"Variant {sku} does not exist")

                if not self.create_new:
                    _logger.info(f"Skipping new variant {sku} (create_new=False)")
                    self._add_progress(_('  Skipped new variant %s\n') % sku)
                    return

            # Log stock information before create/update
            if 'stocks' in variant_data:
                total_qty = variant_data.get('quantity', 0)
                is_infinite = variant_data.get('is_infinite', False)
                _logger.info(f"Variant {sku} stock summary - Total: {total_qty}, Infinite: {is_infinite}")

            # Create or update variant
            _logger.info(f"Creating/updating variant {sku}")

            # Ensure stocks data is passed to create_or_update_from_zid
            variant = self.env['zid.variant'].create_or_update_from_zid(
                variant_data,
                parent_product,
                self.zid_connector_id.id
            )

            if existing_variant:
                self.updated_variants += 1
                _logger.info(f"✓ Successfully updated variant {sku}")
                self._add_progress(_('  ✓ Updated variant %s\n') % sku)
            else:
                self.imported_variants += 1
                _logger.info(f"✓ Successfully created variant {sku}")
                self._add_progress(_('  ✓ Created variant %s\n') % sku)

        except Exception as e:
            self.failed_variants += 1
            error_msg = f"Failed to process variant {sku}: {str(e)}"
            self.error_log += f"\n{error_msg}"

            _logger.error(f"✗ {error_msg}", exc_info=True)
            self._add_progress(_('  ✗ %s\n') % error_msg)

    def _should_import_variant(self, variant_data):
        """Check if variant should be imported based on filters"""
        variant_id = variant_data.get('id', '')
        sku = variant_data.get('sku', '')

        _logger.debug(f"Checking filters for variant {sku} (ID: {variant_id})")

        # SKU filter
        if self.filter_by_sku and self.sku_pattern:
            if self.sku_pattern.lower() not in sku.lower():
                _logger.debug(f"Variant {sku} filtered by SKU pattern '{self.sku_pattern}'")
                return False

        # Stock filter
        if self.filter_by_stock and self.stock_filter:
            quantity = float(variant_data.get('quantity', 0) or 0)
            is_infinite = variant_data.get('is_infinite', False)

            _logger.debug(
                f"Stock check for {sku}: quantity={quantity}, infinite={is_infinite}, filter={self.stock_filter}")

            if self.stock_filter == 'in_stock' and not (is_infinite or quantity > 0):
                _logger.debug(f"Variant {sku} filtered out (not in stock)")
                return False
            elif self.stock_filter == 'out_of_stock' and (is_infinite or quantity > 0):
                _logger.debug(f"Variant {sku} filtered out (in stock)")
                return False
            elif self.stock_filter == 'low_stock' and (is_infinite or quantity >= 10 or quantity <= 0):
                _logger.debug(f"Variant {sku} filtered out (not low stock)")
                return False

        # Published filter
        if self.filter_published:
            is_published = variant_data.get('is_published', True)
            _logger.debug(
                f"Published check for {sku}: is_published={is_published}, filter_published={self.filter_published}")

            if not is_published:
                _logger.info(f"Variant {sku} filtered out (not published: is_published={is_published})")
                # Log more details about the variant to understand why it's not published
                _logger.debug(f"Variant details - ID: {variant_id}, SKU: {sku}")
                _logger.debug(f"Variant keys: {list(variant_data.keys())}")

                # Check for alternative published fields
                for key in ['published', 'active', 'enabled', 'visible', 'is_active', 'is_visible']:
                    if key in variant_data:
                        _logger.debug(f"Alternative field '{key}': {variant_data.get(key)}")

                return False

        # Date filter
        if self.filter_by_date:
            updated_at = variant_data.get('updated_at')
            if updated_at:
                updated_date = self._parse_datetime(updated_at)
                if updated_date:
                    if self.date_from and updated_date < self.date_from:
                        _logger.debug(
                            f"Variant {sku} filtered out (before date_from: {updated_date} < {self.date_from})")
                        return False
                    if self.date_to and updated_date > self.date_to:
                        _logger.debug(f"Variant {sku} filtered out (after date_to: {updated_date} > {self.date_to})")
                        return False

        _logger.debug(f"Variant {sku} passed all filters")
        return True

    # ==================== Sync Methods ====================
    def _sync_stock_levels(self):
        """Sync only stock levels for existing variants"""
        _logger.info("Starting sync_stock_levels operation")
        self._add_progress(_('Syncing stock levels...\n'))

        variants = self.env['zid.variant'].search([
            ('zid_connector_id', '=', self.zid_connector_id.id)
        ])

        _logger.info(f"Found {len(variants)} variants to sync stock")

        for idx, variant in enumerate(variants, 1):
            _logger.debug(f"Syncing stock {idx}/{len(variants)} - SKU: {variant.sku}")

            try:
                # Fetch latest data from API
                variant_data = self._fetch_variant_details(variant.zid_variant_id)

                if variant_data:
                    _logger.debug(f"Fetched data for variant {variant.sku}")
                    # Update stock lines
                    variant._update_stock_lines(variant_data)
                    self.updated_variants += 1

                    _logger.info(f"✓ Updated stock for {variant.sku}")
                    self._add_progress(_('  ✓ Updated stock for %s\n') % variant.sku)
                else:
                    _logger.warning(f"Could not fetch data for variant {variant.sku}")

            except Exception as e:
                self.failed_variants += 1
                error_msg = f"Failed to sync stock for {variant.sku}: {str(e)}"
                self.error_log += f"\n{error_msg}"

                _logger.error(f"✗ {error_msg}", exc_info=True)
                self._add_progress(_('  ✗ %s\n') % error_msg)

    def _update_prices(self):
        """Update only prices for existing variants"""
        _logger.info("Starting update_prices operation")
        self._add_progress(_('Updating prices...\n'))

        variants = self.env['zid.variant'].search([
            ('zid_connector_id', '=', self.zid_connector_id.id)
        ])

        _logger.info(f"Found {len(variants)} variants to update prices")

        for idx, variant in enumerate(variants, 1):
            _logger.debug(f"Updating prices {idx}/{len(variants)} - SKU: {variant.sku}")

            try:
                # Fetch latest data from API
                variant_data = self._fetch_variant_details(variant.zid_variant_id)

                if variant_data:
                    old_price = variant.price
                    old_sale_price = variant.sale_price

                    # Update prices
                    variant.write({
                        'price': float(variant_data.get('price', 0) or 0),
                        'sale_price': float(variant_data.get('sale_price', 0) or 0),
                        'cost': float(variant_data.get('cost', 0) or 0),
                        'formatted_price': variant_data.get('formatted_price', ''),
                        'formatted_sale_price': variant_data.get('formatted_sale_price', ''),
                    })

                    self.updated_variants += 1

                    _logger.info(
                        f"✓ Updated prices for {variant.sku}: {old_price} -> {variant.price}, Sale: {old_sale_price} -> {variant.sale_price}")
                    self._add_progress(_('  ✓ Updated prices for %s\n') % variant.sku)
                else:
                    _logger.warning(f"Could not fetch data for variant {variant.sku}")

            except Exception as e:
                self.failed_variants += 1
                error_msg = f"Failed to update prices for {variant.sku}: {str(e)}"
                self.error_log += f"\n{error_msg}"

                _logger.error(f"✗ {error_msg}", exc_info=True)
                self._add_progress(_('  ✗ %s\n') % error_msg)

    # ==================== API Methods ====================
    def _fetch_all_products(self):
        """Fetch all products from Zid API"""
        _logger.info("Fetching all products from Zid API")

        try:
            page = 1
            all_products = []

            while True:
                _logger.debug(f"Fetching page {page}")

                response = self.zid_connector_id.api_request(
                    endpoint='products/',
                    method='GET',
                    params={
                        'page': page,
                        'page_size': 50
                    }
                )

                _logger.debug(f"API Response type: {type(response)}")

                if isinstance(response, dict) and 'results' in response:
                    products = response.get('results', [])
                    all_products.extend(products)

                    _logger.debug(f"Page {page}: Found {len(products)} products")

                    # Log first product structure to understand the data
                    if products and page == 1:
                        first_product = products[0]
                        _logger.info(f"Sample product structure - Keys: {list(first_product.keys())}")
                        _logger.debug(f"Sample product ID: {first_product.get('id')}")
                        _logger.debug(f"Sample product has variants: {'variants' in first_product}")
                        if 'variants' in first_product:
                            _logger.debug(f"Number of variants in sample: {len(first_product.get('variants', []))}")

                    if not response.get('next'):
                        _logger.info(f"No more pages, total products fetched: {len(all_products)}")
                        break

                    page += 1
                else:
                    _logger.warning(f"Unexpected response format on page {page}")
                    _logger.debug(
                        f"Response keys: {list(response.keys()) if isinstance(response, dict) else 'Not a dict'}")
                    break

            return all_products

        except Exception as e:
            _logger.error(f"Failed to fetch products: {str(e)}", exc_info=True)
            raise

    def _fetch_product_details(self, product_id):
        """Fetch single product details from API"""
        _logger.info(f"Fetching product details for ID: {product_id}")

        try:
            response = self.zid_connector_id.api_request(
                endpoint=f'products/{product_id}/',
                method='GET'
            )

            _logger.debug(f"Successfully fetched product {product_id}")
            return response

        except Exception as e:
            _logger.error(f"Failed to fetch product {product_id}: {str(e)}", exc_info=True)
            return None

    def _fetch_variant_details(self, variant_id):
        """Fetch single variant details from API"""
        _logger.info(f"Fetching variant details for ID: {variant_id}")

        try:
            # Note: This endpoint might need adjustment based on actual API
            response = self.zid_connector_id.api_request(
                endpoint=f'products/variants/{variant_id}/',
                method='GET'
            )

            _logger.debug(f"Successfully fetched variant {variant_id}")
            return response

        except Exception as e:
            _logger.error(f"Failed to fetch variant {variant_id}: {str(e)}", exc_info=True)
            return None

    # ==================== Helper Methods ====================
    def _add_progress(self, text):
        """Add text to progress log"""
        if not self.progress_text:
            self.progress_text = ''
        self.progress_text += text
        _logger.debug(f"Progress update: {text.strip()}")

    @api.model
    def _parse_datetime(self, datetime_str):
        """Parse datetime from API format"""
        if not datetime_str:
            _logger.debug("Empty datetime string provided")
            return False

        try:
            if isinstance(datetime_str, str):
                original_str = datetime_str

                if datetime_str.endswith('Z'):
                    datetime_str = datetime_str[:-1]

                if '.' in datetime_str:
                    datetime_str = datetime_str.split('.')[0]

                result = datetime.strptime(datetime_str, '%Y-%m-%dT%H:%M:%S')
                _logger.debug(f"Parsed datetime: {original_str} -> {result}")
                return result

        except Exception as e:
            _logger.warning(f"Could not parse datetime {datetime_str}: {str(e)}")
            return False

    # ==================== Action Methods ====================
    def action_view_imported_variants(self):
        """View imported variants"""
        self.ensure_one()

        _logger.info(f"Opening imported variants view for connector {self.zid_connector_id.id}")

        return {
            'type': 'ir.actions.act_window',
            'name': _('Imported Variants'),
            'res_model': 'zid.variant',
            'view_mode': 'list,form',
            'domain': [
                ('zid_connector_id', '=', self.zid_connector_id.id),
                ('last_sync_date', '>=', self.create_date)
            ],
            'context': {
                'default_zid_connector_id': self.zid_connector_id.id
            }
        }