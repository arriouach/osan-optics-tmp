from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging
import json

import logging
_logger = logging.getLogger(__name__)


class ZidProductLine(models.Model):
    _name = 'zid.product.line'
    _description = 'Zid Product Store Line'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, id'

    # Sequence for ordering
    sequence = fields.Integer(
        string='Sequence',
        default=10,
        help='Used to order the product lines'
    )

    # Relations
    product_template_id = fields.Many2one(
        'product.template',
        string='Product Template',
        required=True,
        ondelete='cascade'
    )

    zid_connector_id = fields.Many2one(
        'zid.connector',
        string='Store',
        required=True,
        domain=[('authorization_status', '=', 'connected')],
        help='Select the Zid store for this product'
    )

    zid_location_id = fields.Many2one(
        'zid.location',
        string='Location',
        required=True,
        domain="[('zid_connector_id', '=', zid_connector_id)]",
        help='Select the location within the store'
    )

    zid_product_product_id = fields.Many2one('zid.product', string='Zid Product', ondelete='cascade')

    # Product Information
    zid_product_id = fields.Char(
        string='Zid Product ID',
        help='Product ID in Zid system'
    )

    zid_sku = fields.Char(
        string='Zid SKU',
        help='SKU in Zid system'
    )

    is_published = fields.Boolean(
        string='Published in Zid',
        default=False,
        help='Whether this product is published in the Zid store'
    )

    # Pricing
    zid_price = fields.Float(
        string='Price in Zid',
        digits='Product Price',
        help='Product price in Zid store'
    )

    zid_compare_price = fields.Float(
        string='Compare at Price',
        digits='Product Price',
        help='Compare at price in Zid store'
    )

    # Stock
    zid_quantity = fields.Integer(
        string='Quantity in Zid',
        help='Available quantity in Zid location'
    )

    track_inventory = fields.Boolean(
        string='Track Inventory',
        default=True,
        help='Whether to track inventory for this product in Zid'
    )

    # Sync Information
    last_sync_date = fields.Datetime(
        string='Last Sync Date',
        readonly=True
    )

    sync_status = fields.Selection([
        ('not_synced', 'Not Synced'),
        ('synced', 'Synced'),
        ('error', 'Error'),
        ('pending', 'Pending')
    ], string='Sync Status', default='not_synced')

    sync_error_message = fields.Text(
        string='Sync Error',
        readonly=True
    )

    force_sync = fields.Boolean(
        string='Force Next Sync',
        default=False,
        help='Force sync on next cron run even if quantity unchanged'
    )

    # Store Information (from connector)
    store_name = fields.Char(
        related='zid_connector_id.store_name',
        string='Store Name',
        readonly=True,
        store=True
    )

    location_name = fields.Char(
        string='Location Name',
        readonly=True,
        store=True
    )

    # Active
    active = fields.Boolean(
        string='Active',
        default=True
    )

    # Storage for created variants data
    zid_variants_data = fields.Text(
        string='Zid Variants Data',
        help='JSON storage for created variants information'
    )

    def action_get_zid_variants(self):
        """Fetch variants from Zid API and create zid.variant and zid.variant.mapping records"""
        self.ensure_one()
        
        _logger.info("=" * 80)
        _logger.info(f"[GET_ZID_VARIANTS] Starting to fetch variants from Zid")
        _logger.info(f"[GET_ZID_VARIANTS] Product Template: {self.product_template_id.name}")
        _logger.info(f"[GET_ZID_VARIANTS] Store: {self.zid_connector_id.store_name}")
        _logger.info(f"[GET_ZID_VARIANTS] Zid Product ID: {self.zid_product_id}")
        
        # Check prerequisites
        if not self.zid_connector_id:
            raise ValidationError(_('No Zid connector configured for this line'))
            
        if not self.zid_connector_id.is_connected:
            raise ValidationError(_(f'Store {self.zid_connector_id.store_name} is not connected'))
            
        if not self.zid_product_id:
            raise ValidationError(_('This product has no Zid Product ID. Please create it in Zid first.'))
        
        try:
            # Step 1: Fetch product details from Zid API
            _logger.info(f"[GET_ZID_VARIANTS] Fetching product details from Zid API...")
            product_data = self.zid_connector_id.api_request(
                endpoint=f'products/{self.zid_product_id}/',
                method='GET'
            )
            
            if not product_data:
                raise ValidationError(_('No response from Zid API'))
            
            _logger.info(f"[GET_ZID_VARIANTS] Product fetched successfully")
            
            # Extract product name properly
            product_name = product_data.get('name', {})
            if isinstance(product_name, dict):
                product_name_en = product_name.get('en', '')
                product_name_ar = product_name.get('ar', '')
            else:
                product_name_en = str(product_name)
                product_name_ar = str(product_name)
            
            _logger.info(f"[GET_ZID_VARIANTS] Product name: {product_name_en or product_name_ar or 'Unknown'}")
            
            # Step 2: Create or update parent zid.product record
            _logger.info(f"[GET_ZID_VARIANTS] Creating/updating parent zid.product...")
            parent_product = self.env['zid.product'].search([
                ('zid_product_id', '=', self.zid_product_id),
                ('zid_connector_id', '=', self.zid_connector_id.id)
            ], limit=1)
            
            if not parent_product:
                # Create parent product
                parent_product = self.env['zid.product'].create_or_update_from_zid(
                    product_data,
                    self.zid_connector_id.id
                )
                _logger.info(f"[GET_ZID_VARIANTS] Created parent zid.product with ID: {parent_product.id}")
            else:
                # Update existing parent product
                parent_product.write({
                    'name': product_name_en or product_name_ar,
                    'name_ar': product_name_ar or product_name_en,
                    'sku': product_data.get('sku', ''),
                    'price': product_data.get('price', 0),
                    'is_published': product_data.get('is_published', False),
                    'raw_response': json.dumps(product_data)
                })
                _logger.info(f"[GET_ZID_VARIANTS] Updated parent zid.product ID: {parent_product.id}")
            
            # Link to this line if not already linked
            if not self.zid_product_product_id:
                self.zid_product_product_id = parent_product
            
            # Step 3: Process variants
            variants = product_data.get('variants', [])
            
            # If no variants key, check if it's a simple product
            if not variants:
                _logger.info(f"[GET_ZID_VARIANTS] No variants found in response, checking if simple product...")
                
                # For simple products, treat the product itself as a single variant
                if product_data.get('sku') and product_data.get('price') is not None:
                    _logger.info(f"[GET_ZID_VARIANTS] Simple product detected, creating single variant")
                    variants = [{
                        'id': product_data.get('id'),
                        'sku': product_data.get('sku'),
                        'barcode': product_data.get('barcode', ''),
                        'price': product_data.get('price', 0),
                        'sale_price': product_data.get('sale_price', 0),
                        'cost': product_data.get('cost', 0),
                        'quantity': product_data.get('quantity', 0),
                        'is_published': product_data.get('is_published', True),
                        'stocks': product_data.get('stocks', []),
                        'attributes': []  # Simple products have no attributes
                    }]
            
            _logger.info(f"[GET_ZID_VARIANTS] Found {len(variants)} variant(s) to process")
            
            created_variants = []
            created_mappings = []
            
            # Step 4: Create zid.variant records for each variant
            for idx, variant_data in enumerate(variants, 1):
                variant_id = str(variant_data.get('id', ''))
                sku = variant_data.get('sku', '')
                
                _logger.info(f"[GET_ZID_VARIANTS] Processing variant {idx}/{len(variants)} - ID: {variant_id}, SKU: {sku}")
                
                # Check if variant already exists
                existing_variant = self.env['zid.variant'].search([
                    ('zid_variant_id', '=', variant_id),
                    ('zid_connector_id', '=', self.zid_connector_id.id)
                ], limit=1)
                
                if existing_variant:
                    _logger.info(f"[GET_ZID_VARIANTS] Variant already exists, updating...")
                    # Update existing variant
                    existing_variant.write({
                        'sku': sku,
                        'barcode': variant_data.get('barcode', ''),
                        'price': variant_data.get('price', 0),
                        'sale_price': variant_data.get('sale_price', 0),
                        'cost': variant_data.get('cost', 0),
                        'quantity': variant_data.get('quantity', 0),
                        'is_published': variant_data.get('is_published', True),
                        'raw_data': json.dumps(variant_data)
                    })
                    zid_variant = existing_variant
                else:
                    _logger.info(f"[GET_ZID_VARIANTS] Creating new variant...")
                    # Create new variant
                    zid_variant = self.env['zid.variant'].create_or_update_from_zid(
                        variant_data,
                        parent_product,
                        self.zid_connector_id.id
                    )
                
                created_variants.append(zid_variant)
                _logger.info(f"[GET_ZID_VARIANTS] Variant processed: {zid_variant.display_name}")
                
                # Step 5: Create zid.variant.mapping for this variant
                # Check if mapping already exists
                existing_mapping = self.env['zid.variant.mapping'].search([
                    ('zid_variant_id', '=', zid_variant.id),
                    ('product_tmpl_id', '=', self.product_template_id.id),
                    ('zid_connector_id', '=', self.zid_connector_id.id)
                ], limit=1)
                
                if not existing_mapping:
                    _logger.info(f"[GET_ZID_VARIANTS] Creating variant mapping...")
                    
                    # Create the mapping
                    mapping_vals = {
                        'zid_variant_id': zid_variant.id,
                        'zid_connector_id': self.zid_connector_id.id,
                        'product_tmpl_id': self.product_template_id.id,
                        'zid_tmpl_id': parent_product.id,  # Link to parent zid.product
                        'odoo_variant_id': False,  # Will be mapped manually later
                    }
                    
                    mapping = self.env['zid.variant.mapping'].create(mapping_vals)
                    created_mappings.append(mapping)
                    _logger.info(f"[GET_ZID_VARIANTS] Created mapping ID: {mapping.id}")
                else:
                    _logger.info(f"[GET_ZID_VARIANTS] Mapping already exists for this variant")
                    created_mappings.append(existing_mapping)
            
            # Step 6: Update sync status
            self.write({
                'last_sync_date': fields.Datetime.now(),
                'sync_status': 'synced',
                'sync_error_message': False
            })
            
            _logger.info(f"[GET_ZID_VARIANTS] Process completed successfully!")
            _logger.info(f"[GET_ZID_VARIANTS] Created/Updated {len(created_variants)} variants")
            _logger.info(f"[GET_ZID_VARIANTS] Created {len([m for m in created_mappings if m])} new mappings")
            _logger.info("=" * 80)
            
            # Return action to show the created mappings
            return {
                'type': 'ir.actions.act_window',
                'name': _('Zid Variant Mappings'),
                'res_model': 'zid.variant.mapping',
                'view_mode': 'tree,form',
                'domain': [('id', 'in', [m.id for m in created_mappings if m])],
                'context': {
                    'default_product_tmpl_id': self.product_template_id.id,
                    'default_zid_connector_id': self.zid_connector_id.id,
                    'default_zid_tmpl_id': parent_product.id
                },
                'target': 'current'
            }
            
        except Exception as e:
            _logger.error(f"[GET_ZID_VARIANTS] Failed to fetch variants: {str(e)}")
            _logger.error("=" * 80)
            
            # Update sync status with error
            self.write({
                'sync_status': 'error',
                'sync_error_message': str(e)
            })
            
            raise ValidationError(_(f'Failed to fetch variants from Zid: {str(e)}'))

    @api.constrains('product_template_id', 'zid_connector_id', 'zid_location_id')
    def _check_unique_store_location(self):
        """Ensure unique combination of product, store, and location"""
        for line in self:
            return True
            duplicate = self.search([
                ('product_template_id', '=', line.product_template_id.id),
                ('zid_connector_id', '=', line.zid_connector_id.id),
                ('zid_location_id', '=', line.zid_location_id.id),
                ('id', '!=', line.id)
            ])
            if duplicate:
                store_name = line.zid_connector_id.store_name if line.zid_connector_id else 'Unknown Store'
                location_name = line.zid_location_id.name_ar if line.zid_location_id else 'Unknown Location'
                raise ValidationError(_(
                    'Product already exists for store "%s" and location "%s"'
                ) % (store_name, location_name))

    @api.onchange('zid_connector_id')
    def _onchange_zid_connector_id(self):
        """Clear location when store changes"""
        if self.zid_connector_id:
            # Clear location if it doesn't belong to the new store
            if self.zid_location_id and self.zid_location_id.zid_connector_id != self.zid_connector_id:
                self.zid_location_id = False
            # Set domain for locations
            return {
                'domain': {
                    'zid_location_id': [('zid_connector_id', '=', self.zid_connector_id.id)]
                }
            }
        else:
            self.zid_location_id = False
            return {
                'domain': {
                    'zid_location_id': [('id', '=', False)]
                }
            }

    def create_in_zid(self):

        """Create this product in Zid for this specific store/location"""
        self.ensure_one()

        _logger.info("=" * 80)
        _logger.info(f"[CREATE_IN_ZID] Starting product creation in Zid")
        _logger.info(
            f"[CREATE_IN_ZID] Product Template: {self.product_template_id.name} (ID: {self.product_template_id.id})")
        _logger.info(f"[CREATE_IN_ZID] Store: {self.zid_connector_id.store_name}")
        _logger.info(
            f"[CREATE_IN_ZID] Location: {self.zid_location_id.name_ar if self.zid_location_id else 'No Location'}")

        # Check if connector is connected
        if not self.zid_connector_id.is_connected:
            _logger.error(f"[CREATE_IN_ZID] Store {self.zid_connector_id.store_name} is not connected")
            raise ValidationError(_(f'Store {self.zid_connector_id.store_name} is not connected'))

        # Check if product already exists in Zid
        if self.zid_product_id:
            _logger.warning(f"[CREATE_IN_ZID] Product already exists in Zid with ID: {self.zid_product_id}")
            raise ValidationError(_(f'This product already exists in Zid (ID: {self.zid_product_id})'))

        try:
            # Step 1: Create base product with ALL stock locations
            _logger.info(f"[CREATE_IN_ZID] Step 1: Creating base product with stock data...")
            base_product_data = self._prepare_base_product_data()
            _logger.info(f"[CREATE_IN_ZID] Base product data: {json.dumps(base_product_data, indent=2)}")

            response = self.zid_connector_id.api_request(
                endpoint='products/',
                method='POST',
                data=base_product_data
            )

            if not response:
                raise ValidationError(_('No response from Zid API when creating base product'))

            # Update with base product info
            self._update_from_zid_response(response)
            _logger.info(f"[CREATE_IN_ZID] Base product created with ID: {self.zid_product_id}")

            # NEW: Create zid.product record
            _logger.info(f"[CREATE_IN_ZID] Creating zid.product record...")
            zid_product = self.env['zid.product'].create_or_update_from_zid(
                response,
                self.zid_connector_id.id
            )

            # Link the zid.product to this line
            self.zid_product_product_id = zid_product.id
            _logger.info(f"[CREATE_IN_ZID] Created zid.product record: {zid_product.id}")

            # Step 2: Create variants if needed
            product = self.product_template_id
            if len(product.product_variant_ids) > 1:
                _logger.info(f"[CREATE_IN_ZID] Step 2: Creating {len(product.product_variant_ids)} variants...")
                variants_response = self._create_variants_in_zid()

                # NEW: Create zid.variant records from variants response
                if variants_response:
                    _logger.info(f"[CREATE_IN_ZID] Creating zid.variant records...")
                    self._create_zid_variant_records(variants_response, zid_product)
            else:
                _logger.info(f"[CREATE_IN_ZID] Step 2: Single variant product - stocks already added during creation")

                # For single variant products, also create a zid.variant record
                if response.get('variants'):
                    _logger.info(f"[CREATE_IN_ZID] Creating zid.variant record for single variant...")
                    for variant_data in response.get('variants', []):
                        self.env['zid.variant'].create_or_update_from_zid(
                            variant_data,
                            zid_product,
                            self.zid_connector_id.id
                        )

            # Step 3: Create variant lines and link them to product.product
            _logger.info(f"[CREATE_IN_ZID] Step 3: Creating variant lines and linking to Odoo products...")
            self._create_and_link_variant_records()

            # Update sync status
            self.write({
                'sync_status': 'synced',
                'last_sync_date': fields.Datetime.now(),
                'sync_error_message': False
            })

            _logger.info(f"[CREATE_IN_ZID] Product creation completed successfully!")
            _logger.info("=" * 80)

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success!'),
                    'message': _(
                        f'Product created successfully in {self.zid_connector_id.store_name}. ID: {self.zid_product_id}'),
                    'type': 'success',
                    'sticky': False,
                }
            }

        except Exception as e:
            _logger.error(f"[CREATE_IN_ZID] Failed to create product in Zid: {str(e)}")
            _logger.error("=" * 80)
            self.write({
                'sync_status': 'error',
                'sync_error_message': str(e)
            })
            raise ValidationError(_(f'Failed to create product in Zid: {str(e)}'))

    def _create_variants_in_zid(self):
        """Create variants in Zid with their individual stock quantities"""
        self.ensure_one()
        product = self.product_template_id
        _logger.info(f"[CREATE_VARIANTS] Starting variants creation for product: {product.name}")

        if not self.zid_product_id:
            raise ValidationError(_('Base product must be created first'))

        try:
            # Collect variant attributes
            attributes_data = self._collect_variant_attributes()
            if not attributes_data:
                _logger.warning(f"[CREATE_VARIANTS] No attributes found for variants")
                return

            _logger.info(f"[CREATE_VARIANTS] Creating attributes: {json.dumps(attributes_data, indent=2)}")

            # Create attributes/options in Zid
            variants_response = self.zid_connector_id.api_request(
                endpoint=f'products/{self.zid_product_id}/options/',
                method='POST',
                data=attributes_data
            )

            if not variants_response:
                raise ValidationError(_('No response when creating variants'))

            _logger.info(f"[CREATE_VARIANTS] Variants created successfully")

            # Store variants data
            if hasattr(variants_response, 'get') and variants_response.get('variants'):
                self.zid_variants_data = json.dumps(variants_response.get('variants', []))

            # Step 2: Add stock for each variant across ALL locations
            self._add_stock_for_all_variants_all_locations(variants_response)

        except Exception as e:
            _logger.error(f"[CREATE_VARIANTS] Error creating variants: {str(e)}")
            raise

    def _add_stock_for_all_variants_all_locations(self, variants_response):
        """Add stock for all variants in all locations"""
        self.ensure_one()
        _logger.info(f"[ADD_VARIANT_STOCKS] Adding stock for all variants in all locations")

        # Get all Zid variants
        zid_variants = []
        if hasattr(variants_response, 'get') and variants_response.get('variants'):
            zid_variants = variants_response['variants']
        else:
            # Fetch product to get variants
            try:
                product_response = self.zid_connector_id.api_request(
                    endpoint=f'products/{self.zid_product_id}',
                    method='GET'
                )
                if product_response and product_response.get('variants'):
                    zid_variants = product_response['variants']
            except Exception as e:
                _logger.error(f"[ADD_VARIANT_STOCKS] Error fetching variants: {str(e)}")
                return

        if not zid_variants:
            _logger.warning(f"[ADD_VARIANT_STOCKS] No variants found")
            return

        _logger.info(f"[ADD_VARIANT_STOCKS] Found {len(zid_variants)} variants")

        # Process each Zid variant
        for zid_variant in zid_variants:
            zid_variant_id = zid_variant.get('id')
            if not zid_variant_id:
                continue

            _logger.info(f"[ADD_VARIANT_STOCKS] Processing variant: {zid_variant.get('name', 'Unknown')}")

            # Find matching Odoo variant
            odoo_variant = self._find_matching_odoo_variant(zid_variant)
            if not odoo_variant:
                _logger.warning(f"[ADD_VARIANT_STOCKS] No matching Odoo variant found for {zid_variant_id}")
                continue

            # Get stock quantities for this variant in ALL locations
            variant_stocks = self._get_variant_stock_all_locations(odoo_variant)

            if not variant_stocks:
                _logger.info(f"[ADD_VARIANT_STOCKS] No stock found for variant {odoo_variant.display_name}")
                continue

            # Add stock for each location
            for stock_data in variant_stocks:
                try:
                    _logger.info(
                        f"[ADD_VARIANT_STOCKS] Adding {stock_data['available_quantity']} units in location {stock_data['location']}")

                    response = self.zid_connector_id.api_request(
                        endpoint=f'products/{zid_variant_id}/stocks/',
                        method='POST',
                        data=stock_data
                    )

                    _logger.info(f"[ADD_VARIANT_STOCKS] Stock added successfully")

                except Exception as e:
                    _logger.error(f"[ADD_VARIANT_STOCKS] Error adding stock: {str(e)}")
                    continue

    def _get_variant_stock_all_locations(self, variant):
        """Get stock data for a specific variant in all Zid-linked locations"""
        self.ensure_one()

        _logger.info(f"[GET_VARIANT_STOCKS] Getting stock for variant: {variant.display_name}")

        # Get all quants for this variant with quantity > 0
        quants = self.env['stock.quant'].search([
            ('product_id', '=', variant.id),
            ('location_id.usage', 'in', ['internal', 'transit']),
            ('quantity', '>', 0)
        ])

        if not quants:
            _logger.info(f"[GET_VARIANT_STOCKS] No stock available for this variant")
            return []

        # Group by Zid location
        location_quantities = {}

        for quant in quants:
            odoo_location = quant.location_id

            # Check if this location is linked to a Zid location
            if odoo_location.zid_location_id and odoo_location.zid_location_id.zid_location_id:
                # Make sure it's for the same connector
                if odoo_location.zid_location_id.zid_connector_id.id == self.zid_connector_id.id:
                    zid_loc_id = odoo_location.zid_location_id.zid_location_id

                    if zid_loc_id not in location_quantities:
                        location_quantities[zid_loc_id] = 0

                    location_quantities[zid_loc_id] += quant.quantity

                    _logger.info(f"[GET_VARIANT_STOCKS] {odoo_location.complete_name}: +{quant.quantity}")

        # Build stocks array
        stocks_data = []
        for zid_loc_id, quantity in location_quantities.items():
            stocks_data.append({
                'available_quantity': int(quantity),
                'is_infinite': False,
                'location': zid_loc_id
            })

        _logger.info(f"[GET_VARIANT_STOCKS] Total: {len(stocks_data)} location(s) with stock")

        return stocks_data




    def _collect_variant_attributes(self):
        """Collect variant attributes and their values"""
        self.ensure_one()
        product = self.product_template_id
        _logger.info(f"[COLLECT_ATTRIBUTES] Collecting attributes for {len(product.product_variant_ids)} variants")

        if len(product.product_variant_ids) <= 1:
            return []

        # Get all attribute lines
        attribute_lines = product.attribute_line_ids
        if not attribute_lines:
            _logger.warning(f"[COLLECT_ATTRIBUTES] No attribute lines found")
            return []

        attributes_data = []

        for line in attribute_lines:
            attribute = line.attribute_id
            values = line.value_ids

            # Use 'color' slug if it's a color attribute, otherwise use the attribute name
            slug = 'color' if 'color' in attribute.name.lower() or 'لون' in attribute.name else attribute.name.lower().replace(
                ' ', '_')

            choices = []
            for value in values:
                choices.append({
                    'ar': value.name,
                    'en': value.name
                })

            attribute_data = {
                'slug': slug,
                'name': {
                    'ar': attribute.name,
                    'en': attribute.name
                },
                'choices': choices
            }

            attributes_data.append(attribute_data)
            _logger.info(f"[COLLECT_ATTRIBUTES] Added attribute: {attribute.name} with {len(choices)} choices")

        _logger.info(f"[COLLECT_ATTRIBUTES] Collected {len(attributes_data)} attributes")
        return attributes_data

    def _add_stock_for_all_variants(self, variants_response):
        """Add stock for all created variants"""
        self.ensure_one()
        _logger.info(f"[ADD_STOCK_VARIANTS] Adding stock for all variants")

        # Get Odoo location linked to Zid location
        odoo_location = self._get_odoo_location()
        if not odoo_location:
            _logger.warning(f"[ADD_STOCK_VARIANTS] No Odoo location found for Zid location")
            return

        # Get variants from response or fetch them
        zid_variants = []
        if hasattr(variants_response, 'get') and variants_response.get('variants'):
            zid_variants = variants_response['variants']
        else:
            # Fetch product to get variants
            try:
                product_response = self.zid_connector_id.api_request(
                    endpoint=f'products/{self.zid_product_id}',
                    method='GET'
                )
                if product_response and product_response.get('variants'):
                    zid_variants = product_response['variants']
            except Exception as e:
                _logger.error(f"[ADD_STOCK_VARIANTS] Error fetching variants: {str(e)}")
                return

        if not zid_variants:
            _logger.warning(f"[ADD_STOCK_VARIANTS] No variants found in response")
            return

        _logger.info(f"[ADD_STOCK_VARIANTS] Found {len(zid_variants)} variants to add stock")

        # Add stock for each variant
        for zid_variant in zid_variants:
            try:
                self._add_stock_for_zid_variant(zid_variant, odoo_location)
            except Exception as e:
                _logger.error(f"[ADD_STOCK_VARIANTS] Error adding stock for variant {zid_variant.get('id')}: {str(e)}")
                continue

    def _add_stock_for_zid_variant(self, zid_variant, odoo_location):
        """Add stock for a specific Zid variant"""
        zid_variant_id = zid_variant.get('id')
        if not zid_variant_id:
            _logger.warning(f"[ADD_STOCK_VARIANT] No variant ID found")
            return

        _logger.info(f"[ADD_STOCK_VARIANT] Adding stock for variant: {zid_variant.get('name', 'Unknown')}")

        # Find matching Odoo variant
        odoo_variant = self._find_matching_odoo_variant(zid_variant)
        if not odoo_variant:
            _logger.warning(f"[ADD_STOCK_VARIANT] No matching Odoo variant found")
            return

        # Get stock quantity
        quantity = self._get_variant_quantity(odoo_variant, odoo_location)
        _logger.info(f"[ADD_STOCK_VARIANT] Quantity for variant {odoo_variant.display_name}: {quantity}")

        # Add stock via API
        try:
            stock_data = {
                'available_quantity': int(quantity),
                'is_infinite': False,
                'location': self.zid_location_id.zid_location_id
            }

            response = self.zid_connector_id.api_request(
                endpoint=f'products/{zid_variant_id}/stocks/',
                method='POST',
                data=stock_data
            )

            _logger.info(f"[ADD_STOCK_VARIANT] Stock added successfully for variant {zid_variant_id}")

        except Exception as e:
            _logger.error(f"[ADD_STOCK_VARIANT] Error adding stock for variant {zid_variant_id}: {str(e)}")
            raise

    def _find_matching_odoo_variant(self, zid_variant):
        """Find matching Odoo variant based on linked Zid attributes"""
        product = self.product_template_id
        zid_attributes = zid_variant.get('attributes', [])

        _logger.info("=" * 60)
        _logger.info(f"[FIND_VARIANT] START - Looking for matching Odoo variant")
        _logger.info(f"[FIND_VARIANT] Product Template: {product.name}")
        _logger.info(f"[FIND_VARIANT] Total Odoo variants: {len(product.product_variant_ids)}")
        _logger.info(f"[FIND_VARIANT] Zid variant full data: {json.dumps(zid_variant, indent=2, ensure_ascii=False)}")
        _logger.info(f"[FIND_VARIANT] Zid attributes count: {len(zid_attributes)}")

        if not zid_attributes:
            _logger.info(f"[FIND_VARIANT] No attributes found, returning first variant")
            first_variant = product.product_variant_ids[0] if product.product_variant_ids else None
            _logger.info(f"[FIND_VARIANT] Returning: {first_variant.display_name if first_variant else 'None'}")
            _logger.info("=" * 60)
            return first_variant

        # Extract Odoo attribute values we're looking for
        target_odoo_values = []

        for idx, zid_attr_data in enumerate(zid_attributes):
            _logger.info(f"[FIND_VARIANT] --- Processing Zid attribute #{idx + 1} ---")
            _logger.info(f"[FIND_VARIANT] Zid attr raw data: {zid_attr_data}")

            # Get the value from Zid
            value = zid_attr_data.get('value', {})
            _logger.info(f"[FIND_VARIANT] Extracted value: {value} (type: {type(value).__name__})")

            value_ar = None
            value_en = None

            if isinstance(value, dict):
                value_ar = value.get('ar', '')
                value_en = value.get('en', '')
                _logger.info(f"[FIND_VARIANT] Value is dict - AR: '{value_ar}', EN: '{value_en}'")
            else:
                value_ar = str(value) if value else ''
                value_en = str(value) if value else ''
                _logger.info(f"[FIND_VARIANT] Value is string - AR/EN: '{value_ar}'")

            # Get the attribute name too
            attr_name = zid_attr_data.get('name', {})
            attr_name_ar = attr_name.get('ar', '') if isinstance(attr_name, dict) else str(attr_name)
            attr_name_en = attr_name.get('en', '') if isinstance(attr_name, dict) else str(attr_name)
            _logger.info(f"[FIND_VARIANT] Attribute name - AR: '{attr_name_ar}', EN: '{attr_name_en}'")

            # Search for this Zid attribute in zid.attribute model
            _logger.info(f"[FIND_VARIANT] Searching in zid.attribute model...")
            _logger.info(
                f"[FIND_VARIANT] Search criteria: connector_id={self.zid_connector_id.id}, value_ar='{value_ar}' OR value_en='{value_en}'")

            zid_attr_record = self.env['zid.attribute'].search([
                ('zid_connector_id', '=', self.zid_connector_id.id),
                '|',
                ('value_ar', '=', value_ar),
                ('value_en', '=', value_en)
            ], limit=1)

            _logger.info(f"[FIND_VARIANT] Found zid.attribute records: {len(zid_attr_record)}")

            if zid_attr_record:
                _logger.info(
                    f"[FIND_VARIANT] Found zid.attribute: ID={zid_attr_record.id}, Display={zid_attr_record.display_name}")
                _logger.info(
                    f"[FIND_VARIANT] - odoo_attribute_id: {zid_attr_record.odoo_attribute_id.name if zid_attr_record.odoo_attribute_id else 'None'}")
                _logger.info(
                    f"[FIND_VARIANT] - odoo_value_id: {zid_attr_record.odoo_value_id.name if zid_attr_record.odoo_value_id else 'None'}")

                if zid_attr_record.odoo_value_id:
                    target_odoo_values.append(zid_attr_record.odoo_value_id.id)
                    _logger.info(
                        f"[FIND_VARIANT] ✓ Added Odoo value ID: {zid_attr_record.odoo_value_id.id} ({zid_attr_record.odoo_value_id.name})")
                else:
                    _logger.warning(f"[FIND_VARIANT] ✗ zid.attribute found but no odoo_value_id linked!")
            else:
                _logger.warning(f"[FIND_VARIANT] ✗ No zid.attribute found for this value!")
                _logger.info(f"[FIND_VARIANT] Attempting fallback name matching...")

                # Fallback: search all attribute values by name
                found_fallback = False
                for variant in product.product_variant_ids:
                    for attr_val in variant.product_template_attribute_value_ids.mapped('product_attribute_value_id'):
                        _logger.info(f"[FIND_VARIANT] Comparing with Odoo value: '{attr_val.name}'")
                        if (attr_val.name.lower() == value_ar.lower() or
                                attr_val.name.lower() == value_en.lower()):
                            target_odoo_values.append(attr_val.id)
                            _logger.info(
                                f"[FIND_VARIANT] ✓ Fallback match! Added Odoo value ID: {attr_val.id} ({attr_val.name})")
                            found_fallback = True
                            break
                    if found_fallback:
                        break

                if not found_fallback:
                    _logger.error(f"[FIND_VARIANT] ✗✗ No fallback match found for value: {value_ar}/{value_en}")

        _logger.info(f"[FIND_VARIANT] Target Odoo value IDs collected: {target_odoo_values}")

        if not target_odoo_values:
            _logger.error(f"[FIND_VARIANT] ERROR - No Odoo values found, returning first variant as fallback")
            first_variant = product.product_variant_ids[0] if product.product_variant_ids else None
            _logger.info(f"[FIND_VARIANT] Returning: {first_variant.display_name if first_variant else 'None'}")
            _logger.info("=" * 60)
            return first_variant

        # Find the variant that has ALL these attribute values
        _logger.info(f"[FIND_VARIANT] Now matching against Odoo variants...")

        for variant_idx, odoo_variant in enumerate(product.product_variant_ids):
            variant_value_ids = odoo_variant.product_template_attribute_value_ids.mapped(
                'product_attribute_value_id.id')
            variant_value_names = odoo_variant.product_template_attribute_value_ids.mapped(
                'product_attribute_value_id.name')

            _logger.info(f"[FIND_VARIANT] Variant #{variant_idx + 1}: {odoo_variant.display_name}")
            _logger.info(f"[FIND_VARIANT] - Value IDs: {variant_value_ids}")
            _logger.info(f"[FIND_VARIANT] - Value Names: {variant_value_names}")

            # Check if all target values are in this variant
            matches = []
            for target_id in target_odoo_values:
                is_match = target_id in variant_value_ids
                matches.append(is_match)
                _logger.info(f"[FIND_VARIANT] - Checking ID {target_id}: {'✓ MATCH' if is_match else '✗ NO MATCH'}")

            all_match = all(matches)
            _logger.info(f"[FIND_VARIANT] - Overall: {'✓✓ PERFECT MATCH!' if all_match else '✗ Not a match'}")

            if all_match:
                _logger.info(f"[FIND_VARIANT] SUCCESS - Found matching variant: {odoo_variant.display_name}")
                _logger.info("=" * 60)
                return odoo_variant

        # No exact match found
        _logger.error(f"[FIND_VARIANT] ERROR - No exact match found after checking all variants!")
        _logger.error(f"[FIND_VARIANT] Returning first variant as last resort")
        first_variant = product.product_variant_ids[0] if product.product_variant_ids else None
        _logger.info(f"[FIND_VARIANT] Returning: {first_variant.display_name if first_variant else 'None'}")
        _logger.info("=" * 60)
        return first_variant


    def _variant_attributes_match(self, odoo_variant, zid_attributes):
        """Check if Odoo variant attributes match Zid variant attributes"""
        odoo_values = odoo_variant.product_template_attribute_value_ids.mapped('product_attribute_value_id.name')
        zid_values = [attr.get('value', '') for attr in zid_attributes if attr.get('value')]

        # Simple matching - check if any Zid values are in Odoo values
        for zid_value in zid_values:
            if zid_value in odoo_values:
                return True
        return False




    def _get_odoo_location(self):
        """Get Odoo location linked to Zid location"""
        if not self.zid_location_id or not self.zid_location_id.zid_location_id:
            return None

        return self.env['stock.location'].search([
            ('zid_location_id.zid_location_id', '=', self.zid_location_id.zid_location_id)
        ], limit=1)

    def _get_variant_quantity(self, variant, location):
        """Get quantity for specific variant in specific location"""
        if not variant or not location:
            return 0

        quants = self.env['stock.quant'].search([
            ('product_id', '=', variant.id),
            ('location_id', '=', location.id)
        ])
        return sum(quants.mapped('quantity'))

    def _get_total_quantity_for_location(self, location):
        """Get total quantity for all variants in location"""
        if not location:
            return 0

        product = self.product_template_id
        quants = self.env['stock.quant'].search([
            ('product_id', 'in', product.product_variant_ids.ids),
            ('location_id', '=', location.id)
        ])
        return sum(quants.mapped('quantity'))

    def _update_from_zid_response(self, response):
        """Update line from Zid API response after creation"""
        self.ensure_one()
        _logger.info(f"[UPDATE_RESPONSE] Updating product line from Zid response")

        if not response:
            _logger.warning(f"[UPDATE_RESPONSE] No response data to update")
            return

        update_vals = {}

        # Update product ID
        if response.get('id'):
            update_vals['zid_product_id'] = str(response['id'])
            _logger.info(f"[UPDATE_RESPONSE] Zid Product ID: {update_vals['zid_product_id']}")

        # Update SKU
        if response.get('sku'):
            update_vals['zid_sku'] = response['sku']
            _logger.info(f"[UPDATE_RESPONSE] SKU: {update_vals['zid_sku']}")

        # Update quantity
        if 'quantity' in response:
            update_vals['zid_quantity'] = response['quantity']
            _logger.info(f"[UPDATE_RESPONSE] Quantity: {update_vals['zid_quantity']}")

        # Update price
        if 'price' in response:
            update_vals['zid_price'] = response['price']
            _logger.info(f"[UPDATE_RESPONSE] Price: {update_vals['zid_price']}")

        # Update published status
        if 'is_published' in response:
            update_vals['is_published'] = response['is_published']
            _logger.info(f"[UPDATE_RESPONSE] Published: {update_vals['is_published']}")

        # Write updates
        if update_vals:
            self.write(update_vals)
            _logger.info(f"[UPDATE_RESPONSE] Product line updated with {len(update_vals)} field(s)")
        else:
            _logger.info(f"[UPDATE_RESPONSE] No fields to update")

    def _prepare_base_product_data(self):
        """Prepare base product data with ALL stock locations"""
        self.ensure_one()
        product = self.product_template_id
        _logger.info(f"[PREPARE_BASE] Preparing base product data for: {product.name}")

        # Basic product data
        data = {
            'name': {
                'ar': product.name or '',
                'en': product.name or ''
            },
            'sku': self.zid_sku or product.default_code or f'BASE-{product.id}',
            'price': float(self.zid_price or product.list_price or 0),
            'is_published': self.is_published,
            'is_draft': False,
            'is_taxable': True,
            'requires_shipping': product.type == 'product',
        }

        # Get ALL stock locations with quantities
        stocks_data = self._get_all_stock_locations()

        if stocks_data:
            data['stocks'] = stocks_data
            _logger.info(f"[PREPARE_BASE] Added {len(stocks_data)} stock location(s)")
        else:
            # Fallback: add only the current location with 0 quantity if no stock found
            _logger.warning(f"[PREPARE_BASE] No stock found in any linked location")
            data['stocks'] = [{
                'available_quantity': 0,
                'is_infinite': False,
                'location': self.zid_location_id.zid_location_id
            }]

        # Add optional fields
        if product.description_sale:
            data['description'] = {
                'ar': product.description_sale,
                'en': product.description_sale
            }

        if product.barcode:
            data['barcode'] = product.barcode

        if product.standard_price:
            data['cost'] = float(product.standard_price)

        if product.weight:
            data['weight'] = {
                'value': float(product.weight),
                'unit': 'kg'
            }

        _logger.info(f"[PREPARE_BASE] Base product data prepared successfully")
        return data

    def _get_all_stock_locations(self):
        """Get stock data for ALL locations that have this product"""
        self.ensure_one()

        _logger.info(f"[GET_ALL_STOCKS] Getting stock for all locations")

        # Get all products (variants)
        products = self.product_template_id.product_variant_ids

        if not products:
            _logger.warning(f"[GET_ALL_STOCKS] No products found")
            return []

        # Get all quants with quantity > 0
        quants = self.env['stock.quant'].search([
            ('product_id', 'in', products.ids),
            ('location_id.usage', 'in', ['internal', 'transit']),
            ('quantity', '>', 0)
        ])

        if not quants:
            _logger.info(f"[GET_ALL_STOCKS] No stock available")
            return []

        # Group by Zid location
        location_quantities = {}

        for quant in quants:
            odoo_location = quant.location_id

            # Check if this Odoo location has a linked Zid location
            if odoo_location.zid_location_id and odoo_location.zid_location_id.zid_location_id:
                # Make sure the Zid location belongs to the same connector
                if odoo_location.zid_location_id.zid_connector_id.id == self.zid_connector_id.id:
                    zid_loc_id = odoo_location.zid_location_id.zid_location_id

                    if zid_loc_id not in location_quantities:
                        location_quantities[zid_loc_id] = {
                            'quantity': 0,
                            'name': odoo_location.zid_location_id.name_ar or 'Unknown'
                        }

                    location_quantities[zid_loc_id]['quantity'] += quant.quantity

                    _logger.info(
                        f"[GET_ALL_STOCKS] Location '{odoo_location.complete_name}' -> Zid '{location_quantities[zid_loc_id]['name']}': +{quant.quantity}")
                else:
                    _logger.debug(
                        f"[GET_ALL_STOCKS] Skipping location {odoo_location.complete_name} - belongs to different connector")
            else:
                _logger.debug(f"[GET_ALL_STOCKS] Skipping location {odoo_location.complete_name} - not linked to Zid")

        # Build stocks array
        stocks_data = []
        for zid_loc_id, data in location_quantities.items():
            stocks_data.append({
                'available_quantity': int(data['quantity']),
                'is_infinite': False,
                'location': zid_loc_id
            })
            _logger.info(f"[GET_ALL_STOCKS] Adding stock: {data['name']} = {int(data['quantity'])} units")

        _logger.info(f"[GET_ALL_STOCKS] Total: {len(stocks_data)} location(s) with stock")

        return stocks_data







    # Rest of the existing methods remain the same...
    def update_in_zid(self):
        """Update product in Zid with current data"""
        self.ensure_one()
        if not self.zid_product_id:
            raise ValidationError(_('Product does not exist in Zid yet. Create it first.'))

        if not self.zid_connector_id.is_connected:
            raise ValidationError(_(f'Store {self.zid_connector_id.store_name} is not connected'))

        try:
            # Prepare product data
            product_data = self._prepare_base_product_data()

            # Make API request to update product
            response = self.zid_connector_id.api_request(
                endpoint=f'products/{self.zid_product_id}',
                method='PUT',
                data=product_data
            )

            # Update line with response data
            if response:
                self._update_from_zid_response(response)

            # Update sync status
            self.write({
                'sync_status': 'synced',
                'last_sync_date': fields.Datetime.now(),
                'sync_error_message': False
            })

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success!'),
                    'message': _(f'Product updated successfully in {self.zid_connector_id.store_name}'),
                    'type': 'success',
                    'sticky': False,
                }
            }

        except Exception as e:
            _logger.error(f"Failed to update product in Zid: {str(e)}")
            self.write({
                'sync_status': 'error',
                'sync_error_message': str(e)
            })
            raise ValidationError(_(f'Failed to update product in Zid: {str(e)}'))

    def add_variants_to_existing_product(self):
        """Add new variants from Odoo to existing product in Zid"""
        self.ensure_one()
        
        _logger.info("=" * 80)
        _logger.info(f"[ADD_VARIANTS_TO_ZID] Starting to add Odoo variants to Zid")
        _logger.info(f"[ADD_VARIANTS_TO_ZID] Product Template: {self.product_template_id.name}")
        _logger.info(f"[ADD_VARIANTS_TO_ZID] Store: {self.zid_connector_id.store_name}")
        _logger.info(f"[ADD_VARIANTS_TO_ZID] Zid Product ID: {self.zid_product_id}")
        
        # Check if connector is connected
        if not self.zid_connector_id.is_connected:
            raise ValidationError(_(f'Store {self.zid_connector_id.store_name} is not connected'))
        
        # Check if product exists in Zid
        if not self.zid_product_id:
            raise ValidationError(_('Product must be created in Zid first. Please use "Create in Zid" button.'))
        
        product = self.product_template_id
        
        # Check if product has multiple variants in Odoo
        variant_count = len(product.product_variant_ids)
        _logger.info(f"[ADD_VARIANTS_TO_ZID] Odoo product has {variant_count} variant(s)")
        
        if variant_count <= 1:
            raise ValidationError(_('Product has only one variant in Odoo. No variants to add.'))
        
        try:
            # Step 1: Check current state in Zid
            _logger.info(f"[ADD_VARIANTS_TO_ZID] Fetching current product state from Zid...")
            current_product = self.zid_connector_id.api_request(
                endpoint=f'products/{self.zid_product_id}',
                method='GET'
            )
            
            if not current_product:
                raise ValidationError(_('Could not fetch product from Zid'))
            
            # Check existing variants in Zid
            existing_variants = current_product.get('variants', [])
            _logger.info(f"[ADD_VARIANTS_TO_ZID] Product currently has {len(existing_variants)} variant(s) in Zid")
            
            if existing_variants and len(existing_variants) > 1:
                # Product already has multiple variants, show warning
                _logger.warning(f"[ADD_VARIANTS_TO_ZID] Product already has {len(existing_variants)} variants in Zid")
                raise ValidationError(_(f'Product already has {len(existing_variants)} variants in Zid. Use "Update in Zid" to sync changes.'))
            
            # Step 2: Collect variant attributes from Odoo
            _logger.info(f"[ADD_VARIANTS_TO_ZID] Collecting variant attributes from Odoo...")
            attributes_data = self._collect_variant_attributes()
            
            if not attributes_data:
                raise ValidationError(_('No attributes found for variants. Make sure your product has variant attributes configured.'))
            
            _logger.info(f"[ADD_VARIANTS_TO_ZID] Found {len(attributes_data)} attribute(s) to create")
            for attr in attributes_data:
                _logger.info(f"[ADD_VARIANTS_TO_ZID] - {attr['name']['en']}: {len(attr['choices'])} values")
            
            # Step 3: Create variants in Zid using options API
            _logger.info(f"[ADD_VARIANTS_TO_ZID] Creating variants in Zid...")
            variants_response = self.zid_connector_id.api_request(
                endpoint=f'products/{self.zid_product_id}/options/',
                method='POST',
                data=attributes_data
            )
            
            if not variants_response:
                raise ValidationError(_('No response when creating variants'))
            
            _logger.info(f"[ADD_VARIANTS_TO_ZID] Variants created successfully!")
            
            # Store variants data
            if hasattr(variants_response, 'get') and variants_response.get('variants'):
                self.zid_variants_data = json.dumps(variants_response.get('variants', []))
                _logger.info(f"[ADD_VARIANTS_TO_ZID] Created {len(variants_response.get('variants', []))} variants")
            
            # Step 4: Add stock for each variant
            _logger.info(f"[ADD_VARIANTS_TO_ZID] Adding stock for created variants...")
            self._add_stock_for_all_variants(variants_response)
            
            # Step 5: Create zid.variant records and link them to Odoo variants
            _logger.info(f"[ADD_VARIANTS_TO_ZID] Creating variant records and linking...")
            self._create_zid_variant_records_from_response(variants_response)
            
            # Update sync status
            self.write({
                'sync_status': 'synced',
                'last_sync_date': fields.Datetime.now(),
                'sync_error_message': False
            })
            
            _logger.info(f"[ADD_VARIANTS_TO_ZID] Process completed successfully!")
            _logger.info("=" * 80)
            
            # Success message
            message = _(f'Successfully added {variant_count - 1} new variant(s) to the product in Zid.\n'
                      f'The product now has {variant_count} total variants.')
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Variants Added Successfully!'),
                    'message': message,
                    'type': 'success',
                    'sticky': True,
                }
            }
            
        except Exception as e:
            _logger.error(f"[ADD_VARIANTS_TO_ZID] Failed: {str(e)}")
            _logger.error("=" * 80)
            self.write({
                'sync_status': 'error',
                'sync_error_message': str(e)
            })
            raise ValidationError(_(f'Failed to add variants to Zid: {str(e)}'))
    
    def _create_zid_variant_records_from_response(self, variants_response):
        """Create zid.variant records from API response and link them to Odoo variants"""
        self.ensure_one()
        
        _logger.info(f"[CREATE_VARIANT_RECORDS] Creating zid.variant records from response")
        
        # Ensure parent zid.product exists
        parent_zid_product = self.env['zid.product'].search([
            ('zid_product_id', '=', self.zid_product_id),
            ('zid_connector_id', '=', self.zid_connector_id.id)
        ], limit=1)
        
        if not parent_zid_product:
            # Create parent zid.product if not exists
            _logger.info(f"[CREATE_VARIANT_RECORDS] Creating parent zid.product record")
            parent_zid_product = self.env['zid.product'].create({
                'zid_connector_id': self.zid_connector_id.id,
                'zid_product_id': self.zid_product_id,
                'name': self.product_template_id.name,
                'name_ar': self.product_template_id.name,
                'sku': self.zid_sku or self.product_template_id.default_code or '',
                'price': self.zid_price or self.product_template_id.list_price or 0,
                'is_published': self.is_published,
                'product_class': 'variable',
                'raw_response': json.dumps(variants_response) if variants_response else '{}'
            })
            _logger.info(f"[CREATE_VARIANT_RECORDS] Created parent zid.product: {parent_zid_product.id}")
        
        # Get variants from response or fetch them
        zid_variants = []
        if hasattr(variants_response, 'get') and variants_response.get('variants'):
            zid_variants = variants_response['variants']
        else:
            # Fetch product to get variants
            try:
                product_response = self.zid_connector_id.api_request(
                    endpoint=f'products/{self.zid_product_id}',
                    method='GET'
                )
                if product_response and product_response.get('variants'):
                    zid_variants = product_response['variants']
            except Exception as e:
                _logger.error(f"[CREATE_VARIANT_RECORDS] Error fetching variants: {str(e)}")
                return
        
        if not zid_variants:
            _logger.warning(f"[CREATE_VARIANT_RECORDS] No variants found in response")
            return
        
        _logger.info(f"[CREATE_VARIANT_RECORDS] Processing {len(zid_variants)} variants")
        
        # Create zid.variant records for each variant
        for zid_variant_data in zid_variants:
            variant_id = zid_variant_data.get('id')
            if not variant_id:
                continue
            
            # Check if this variant already exists
            existing_variant = self.env['zid.variant'].search([
                ('zid_variant_id', '=', str(variant_id)),
                ('zid_connector_id', '=', self.zid_connector_id.id)
            ], limit=1)
            
            if existing_variant:
                _logger.info(f"[CREATE_VARIANT_RECORDS] Variant {variant_id} already exists, updating...")
                existing_variant.write({
                    'sku': zid_variant_data.get('sku', ''),
                    'price': zid_variant_data.get('price', 0),
                    'quantity': zid_variant_data.get('quantity', 0),
                    'raw_data': json.dumps(zid_variant_data)
                })
            else:
                # Create new zid.variant
                zid_variant = self.env['zid.variant'].create({
                    'zid_connector_id': self.zid_connector_id.id,
                    'zid_variant_id': str(variant_id),
                    'parent_product_id': parent_zid_product.id,
                    'sku': zid_variant_data.get('sku', ''),
                    'barcode': zid_variant_data.get('barcode', ''),
                    'price': zid_variant_data.get('price', 0),
                    'sale_price': zid_variant_data.get('sale_price', 0),
                    'cost': zid_variant_data.get('cost', 0),
                    'quantity': zid_variant_data.get('quantity', 0),
                    'is_default': zid_variant_data.get('is_default', False),
                    'raw_data': json.dumps(zid_variant_data)
                })
                _logger.info(f"[CREATE_VARIANT_RECORDS] Created zid.variant: {zid_variant.zid_variant_id}")
            
            # Try to match and link with Odoo variants
            odoo_variant = self._find_matching_odoo_variant(zid_variant_data)
            if odoo_variant:
                # Create or update zid.variant.line
                variant_line = self.env['zid.variant.line'].search([
                    ('product_id', '=', odoo_variant.id),
                    ('zid_connector_id', '=', self.zid_connector_id.id),
                    ('zid_location_id', '=', self.zid_location_id.id)
                ], limit=1)
                
                if variant_line:
                    # Link the zid.variant to the line
                    if existing_variant:
                        variant_line.zid_variant_id = existing_variant
                    else:
                        variant_line.zid_variant_id = zid_variant
                    _logger.info(f"[CREATE_VARIANT_RECORDS] Linked zid.variant to existing variant line")
                else:
                    # Create new variant line
                    new_line = self.env['zid.variant.line'].create({
                        'product_id': odoo_variant.id,
                        'zid_connector_id': self.zid_connector_id.id,
                        'zid_location_id': self.zid_location_id.id,
                        'zid_variant_id': existing_variant.id if existing_variant else zid_variant.id,
                        'zid_sku': zid_variant_data.get('sku', odoo_variant.default_code),
                        'zid_price': zid_variant_data.get('price', 0),
                        'sync_status': 'synced',
                        'last_sync_date': fields.Datetime.now()
                    })
                    _logger.info(f"[CREATE_VARIANT_RECORDS] Created new variant line for {odoo_variant.display_name}")

    def _create_and_link_variant_records(self):
        """Create zid.variant records and link them to product.product via zid.variant.line"""
        self.ensure_one()

        _logger.info("[CREATE_LINK_VARIANTS] Starting to create and link variant records")

        if not self.zid_product_id:
            _logger.warning("[CREATE_LINK_VARIANTS] No Zid product ID found, skipping")
            return

        # First ensure parent zid.product exists
        parent_zid_product = self.env['zid.product'].search([
            ('zid_product_id', '=', self.zid_product_id),
            ('zid_connector_id', '=', self.zid_connector_id.id)
        ], limit=1)

        if not parent_zid_product:
            # Create parent zid.product
            _logger.info("[CREATE_LINK_VARIANTS] Creating parent zid.product record")

            # Check available product_class values dynamically
            product_class_field = self.env['zid.product']._fields.get('product_class')
            available_values = []
            if product_class_field and hasattr(product_class_field, 'selection'):
                if callable(product_class_field.selection):
                    available_values = [val[0] for val in product_class_field.selection(self.env['zid.product'])]
                else:
                    available_values = [val[0] for val in product_class_field.selection]

            _logger.info(f"[CREATE_LINK_VARIANTS] Available product_class values: {available_values}")

            # Choose appropriate product_class
            if len(self.product_template_id.product_variant_ids) > 1:
                # Try 'variable' first, then alternatives
                if 'variable' in available_values:
                    product_class = 'variable'
                elif 'variant' in available_values:
                    product_class = 'variant'
                elif 'configurable' in available_values:
                    product_class = 'configurable'
                else:
                    # Fallback to first available or 'simple'
                    product_class = available_values[0] if available_values else 'simple'
                _logger.info(f"[CREATE_LINK_VARIANTS] Product has multiple variants, using class: {product_class}")
            else:
                product_class = 'simple'
                _logger.info(f"[CREATE_LINK_VARIANTS] Single variant product, using class: {product_class}")

            parent_zid_product = self.env['zid.product'].create({
                'zid_connector_id': self.zid_connector_id.id,
                'zid_product_id': self.zid_product_id,
                'name': self.product_template_id.name,
                'name_ar': self.product_template_id.name,
                'sku': self.zid_sku or self.product_template_id.default_code or '',
                'price': self.zid_price or self.product_template_id.list_price or 0,
                'is_published': self.is_published,
                'product_class': product_class
            })
            _logger.info(
                f"[CREATE_LINK_VARIANTS] Created parent zid.product: {parent_zid_product.id} with class: {product_class}")

        # Fetch the created product from Zid to get all variants
        try:
            product_response = self.zid_connector_id.api_request(
                endpoint=f'products/{self.zid_product_id}',
                method='GET'
            )

            if not product_response:
                _logger.error("[CREATE_LINK_VARIANTS] No response from Zid")
                return

            zid_variants = product_response.get('variants', [])
            _logger.info(f"[CREATE_LINK_VARIANTS] Found {len(zid_variants)} variants in Zid response")

            # Process each Zid variant
            for zid_variant_data in zid_variants:
                variant_id = zid_variant_data.get('id')
                if not variant_id:
                    continue

                _logger.info(f"[CREATE_LINK_VARIANTS] Processing Zid variant {variant_id}")

                # Check if zid.variant already exists
                zid_variant = self.env['zid.variant'].search([
                    ('zid_variant_id', '=', str(variant_id)),
                    ('zid_connector_id', '=', self.zid_connector_id.id)
                ], limit=1)

                if not zid_variant:
                    # Create new zid.variant
                    zid_variant = self.env['zid.variant'].create({
                        'zid_connector_id': self.zid_connector_id.id,
                        'zid_variant_id': str(variant_id),
                        'parent_product_id': parent_zid_product.id,
                        'sku': zid_variant_data.get('sku', ''),
                        'barcode': zid_variant_data.get('barcode', ''),
                        'price': zid_variant_data.get('price', 0),
                        'sale_price': zid_variant_data.get('sale_price', 0),
                        'cost': zid_variant_data.get('cost', 0),
                        'quantity': zid_variant_data.get('quantity', 0),
                        'is_default': zid_variant_data.get('is_default', False),
                        'raw_data': json.dumps(zid_variant_data)
                    })
                    _logger.info(f"[CREATE_LINK_VARIANTS] Created zid.variant: {zid_variant.id}")

                # Find matching Odoo variant (product.product)
                odoo_variant = self._find_matching_odoo_variant(zid_variant_data)

                if odoo_variant:
                    _logger.info(f"[CREATE_LINK_VARIANTS] Found matching Odoo variant: {odoo_variant.display_name}")

                    # Check if zid.variant.line already exists
                    existing_line = self.env['zid.variant.line'].search([
                        ('product_id', '=', odoo_variant.id),
                        ('zid_connector_id', '=', self.zid_connector_id.id),
                        ('zid_location_id', '=', self.zid_location_id.id)
                    ], limit=1)

                    if existing_line:
                        # Update existing line
                        existing_line.write({
                            'zid_variant_id': zid_variant.id,
                            'zid_sku': zid_variant_data.get('sku', odoo_variant.default_code),
                            'zid_price': zid_variant_data.get('price', 0),
                            'sync_status': 'synced',
                            'last_sync_date': fields.Datetime.now()
                        })
                        _logger.info(f"[CREATE_LINK_VARIANTS] Updated existing variant line")
                    else:
                        # Create new zid.variant.line
                        new_line = self.env['zid.variant.line'].create({
                            'product_id': odoo_variant.id,
                            'zid_connector_id': self.zid_connector_id.id,
                            'zid_location_id': self.zid_location_id.id,
                            'zid_variant_id': zid_variant.id,
                            'zid_sku': zid_variant_data.get('sku', odoo_variant.default_code),
                            'zid_price': zid_variant_data.get('price', 0),
                            'zid_quantity': zid_variant_data.get('quantity', 0),
                            'sync_status': 'synced',
                            'last_sync_date': fields.Datetime.now()
                        })
                        _logger.info(f"[CREATE_LINK_VARIANTS] Created new variant line for {odoo_variant.display_name}")
                else:
                    _logger.warning(
                        f"[CREATE_LINK_VARIANTS] No matching Odoo variant found for Zid variant {variant_id}")

            _logger.info("[CREATE_LINK_VARIANTS] Completed creating and linking variant records")

        except Exception as e:
            _logger.error(f"[CREATE_LINK_VARIANTS] Error: {str(e)}")
            # Don't raise - this is not critical for the main flow
    

    def sync_to_zid(self):
        """Sync this product line to Zid (create or update)"""
        self.ensure_one()
        if not self.zid_connector_id.is_connected:
            store_name = self.zid_connector_id.store_name if self.zid_connector_id else 'Unknown Store'
            raise ValidationError(_('Store "%s" is not connected') % store_name)

        # If product doesn't exist in Zid, create it
        if not self.zid_product_id:
            return self.create_in_zid()
        else:
            # Otherwise update it
            return self.update_in_zid()

    def _create_zid_variant_records(self, variants_response, parent_zid_product):
        """Create zid.variant records from API response"""
        self.ensure_one()

        _logger.info(f"[CREATE_ZID_VARIANTS] Creating zid.variant records from response")

        # Get variants from response
        zid_variants = []
        if hasattr(variants_response, 'get') and variants_response.get('variants'):
            zid_variants = variants_response['variants']
        else:
            # Fetch product to get variants if not in response
            try:
                product_response = self.zid_connector_id.api_request(
                    endpoint=f'products/{self.zid_product_id}',
                    method='GET'
                )
                if product_response and product_response.get('variants'):
                    zid_variants = product_response['variants']
            except Exception as e:
                _logger.error(f"[CREATE_ZID_VARIANTS] Error fetching variants: {str(e)}")
                return

        if not zid_variants:
            _logger.warning(f"[CREATE_ZID_VARIANTS] No variants found in response")
            return

        _logger.info(f"[CREATE_ZID_VARIANTS] Processing {len(zid_variants)} variants")

        # Create zid.variant records for each variant
        created_variants = []
        for zid_variant_data in zid_variants:
            variant_id = zid_variant_data.get('id')
            if not variant_id:
                continue

            try:
                # Create or update the zid.variant record
                zid_variant = self.env['zid.variant'].create_or_update_from_zid(
                    zid_variant_data,
                    parent_zid_product,
                    self.zid_connector_id.id
                )

                if zid_variant:
                    created_variants.append(zid_variant)
                    _logger.info(f"[CREATE_ZID_VARIANTS] Created/Updated zid.variant: {zid_variant.zid_variant_id}")

                    # Try to match and link with Odoo variants
                    odoo_variant = self._find_matching_odoo_variant(zid_variant_data)
                    if odoo_variant:
                        # Link the zid.variant to the Odoo product
                        zid_variant.odoo_product_id = odoo_variant
                        _logger.info(
                            f"[CREATE_ZID_VARIANTS] Linked zid.variant to Odoo product: {odoo_variant.display_name}")

                        # Create zid.variant.line for each stock location
                        for stock_line in zid_variant.stock_line_ids:
                            variant_line_vals = {
                                'product_id': odoo_variant.id,
                                'zid_connector_id': self.zid_connector_id.id,
                                'zid_location_id': stock_line.location_id.id,
                                'zid_variant_id': zid_variant.id,
                                'zid_sku': zid_variant.sku,
                                'is_published': zid_variant.is_published,
                                'zid_price': zid_variant.price,
                                'zid_compare_price': zid_variant.sale_price,
                                'zid_quantity': int(stock_line.available_quantity),
                                'track_inventory': not stock_line.is_infinite,
                                'last_sync_date': fields.Datetime.now(),
                                'sync_status': 'synced',
                                'location_name': stock_line.location_id.display_name,
                                'active': True,
                            }

                            self.env['zid.variant.line'].create(variant_line_vals)
                            _logger.info(
                                f"[CREATE_ZID_VARIANTS] Created variant line for {odoo_variant.display_name} at {stock_line.location_id.display_name}")
                    else:
                        _logger.warning(
                            f"[CREATE_ZID_VARIANTS] No matching Odoo variant found for Zid variant {variant_id}")

            except Exception as e:
                _logger.error(f"[CREATE_ZID_VARIANTS] Error creating variant {variant_id}: {str(e)}")
                continue

        _logger.info(f"[CREATE_ZID_VARIANTS] Created {len(created_variants)} zid.variant records")
        return created_variants


    def action_sync_stock(self):
        """Sync stock from Odoo to Zid for this line"""
        self.ensure_one()
        if not self.zid_product_id:
            raise ValidationError(_('This product line has no Zid product ID yet'))

        # Find the Odoo location linked to this Zid location
        odoo_location = self._get_odoo_location()
        if not odoo_location:
            raise ValidationError(
                _(f'No Odoo location found linked to Zid location {self.zid_location_id.display_name}'))

        # Calculate total quantity from stock.quant
        total_qty = self._get_total_quantity_for_location(odoo_location)

        # Update stock in Zid
        self.update_stock_in_zid(total_qty)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _(f'Stock synced successfully. Quantity: {int(total_qty)}'),
                'type': 'success',
                'sticky': False,
            }
        }

    def update_stock_in_zid(self, quantity):
        """Direct method to update stock in Zid for this specific line"""
        self.ensure_one()
        if not self.zid_product_id:
            raise ValidationError(_('No Zid product ID for this line'))

        if not self.zid_connector_id.is_connected:
            raise ValidationError(_(f'Store {self.zid_connector_id.store_name} is not connected'))

        try:
            _logger.info(f"[UPDATE_STOCK] Starting stock update for product {self.zid_product_id} in location {self.zid_location_id.zid_location_id}")
            
            # Method 1: Fetch current product data to get stock ID for this location
            product_response = self.zid_connector_id.api_request(
                endpoint=f'products/{self.zid_product_id}',
                method='GET'
            )
            
            # Find the stock ID for our specific location
            existing_stocks = product_response.get('stocks', [])
            stock_id_for_location = None
            
            for stock in existing_stocks:
                # Check both location ID directly and location object ID
                stock_location = stock.get('location')
                if isinstance(stock_location, dict):
                    location_id = stock_location.get('id')
                else:
                    location_id = stock_location
                    
                if location_id == self.zid_location_id.zid_location_id:
                    stock_id_for_location = stock.get('id')
                    _logger.info(f"[UPDATE_STOCK] Found existing stock ID {stock_id_for_location} for location")
                    break
            
            if stock_id_for_location:
                # Method 1A: Update existing stock using PUT or PATCH on specific stock ID
                _logger.info(f"[UPDATE_STOCK] Updating existing stock {stock_id_for_location}")
                
                stock_update_data = {
                    'available_quantity': int(quantity),
                    'is_infinite': False
                }
                
                # Try to update the specific stock
                try:
                    response = self.zid_connector_id.api_request(
                        endpoint=f'products/{self.zid_product_id}/stocks/{stock_id_for_location}',
                        method='PUT',  # Use PUT to update existing stock
                        data=stock_update_data
                    )
                    _logger.info(f"[UPDATE_STOCK] Stock updated successfully using PUT")
                except Exception as put_error:
                    _logger.warning(f"[UPDATE_STOCK] PUT failed, trying PATCH: {str(put_error)}")
                    # If PUT fails, try PATCH
                    response = self.zid_connector_id.api_request(
                        endpoint=f'products/{self.zid_product_id}/stocks/{stock_id_for_location}',
                        method='PATCH',
                        data=stock_update_data
                    )
                    _logger.info(f"[UPDATE_STOCK] Stock updated successfully using PATCH")
            else:
                # Method 1B: No existing stock for this location, create new one
                _logger.info(f"[UPDATE_STOCK] No existing stock for location, creating new one")
                
                stock_create_data = {
                    'available_quantity': int(quantity),
                    'is_infinite': False,
                    'location': self.zid_location_id.zid_location_id
                }
                
                response = self.zid_connector_id.api_request(
                    endpoint=f'products/{self.zid_product_id}/stocks/',
                    method='POST',
                    data=stock_create_data
                )
                _logger.info(f"[UPDATE_STOCK] New stock created successfully")
            
            # Update the line
            self.write({
                'zid_quantity': int(quantity),
                'last_sync_date': fields.Datetime.now(),
                'sync_status': 'synced',
                'sync_error_message': False
            })
            
            return response
            
        except Exception as e:
            _logger.error(f"[UPDATE_STOCK] Primary method failed: {str(e)}")
            
            # Fallback Method: Update all stocks at once (preserving other locations)
            try:
                _logger.info(f"[UPDATE_STOCK] Using fallback method - updating all stocks")
                
                # Fetch current product data with all stocks
                product_response = self.zid_connector_id.api_request(
                    endpoint=f'products/{self.zid_product_id}',
                    method='GET'
                )
                
                # Get existing stocks
                existing_stocks = product_response.get('stocks', [])
                _logger.info(f"[UPDATE_STOCK] Current stocks: {existing_stocks}")
                
                # Update or add stock for our location
                updated_stocks = []
                location_found = False
                
                for stock in existing_stocks:
                    # Check both location ID directly and location object ID
                    stock_location = stock.get('location')
                    if isinstance(stock_location, dict):
                        location_id = stock_location.get('id')
                    else:
                        location_id = stock_location
                    
                    if location_id == self.zid_location_id.zid_location_id:
                        # Update this location's stock
                        stock['available_quantity'] = int(quantity)
                        stock['is_infinite'] = False
                        location_found = True
                        _logger.info(f"[UPDATE_STOCK] Updated location {self.zid_location_id.zid_location_id} quantity to {quantity}")
                    
                    # Clean up the stock object - keep only essential fields
                    clean_stock = {
                        'available_quantity': stock.get('available_quantity', 0),
                        'is_infinite': stock.get('is_infinite', False),
                        'location': location_id  # Use only the ID, not the full object
                    }
                    # Include stock ID if it exists
                    if stock.get('id'):
                        clean_stock['id'] = stock['id']
                    
                    updated_stocks.append(clean_stock)
                
                # If location not found in existing stocks, add it
                if not location_found:
                    _logger.warning(f"[UPDATE_STOCK] Location {self.zid_location_id.zid_location_id} not found in existing stocks - this should not happen!")
                    # Don't add a new stock in PATCH if it doesn't exist - this causes errors
                    # Instead, raise an error to indicate the issue
                    raise ValidationError(_(f'Location {self.zid_location_id.zid_location_id} does not have stock for this product. Please sync products first.'))
                
                _logger.info(f"[UPDATE_STOCK] Sending updated stocks: {updated_stocks}")
                
                # Update product with all stocks
                update_data = {
                    'stocks': updated_stocks
                }
                
                response = self.zid_connector_id.api_request(
                    endpoint=f'products/{self.zid_product_id}/',
                    method='PATCH',
                    data=update_data
                )
                
                _logger.info(f"[UPDATE_STOCK] Fallback method successful")
                
                # Update the line
                self.write({
                    'zid_quantity': int(quantity),
                    'last_sync_date': fields.Datetime.now(),
                    'sync_status': 'synced',
                    'sync_error_message': False
                })
                
                return response
                
            except Exception as e2:
                _logger.error(f"[UPDATE_STOCK] Fallback method also failed: {str(e2)}")
                self.write({
                    'sync_status': 'error',
                    'sync_error_message': f"Primary error: {str(e)}. Fallback error: {str(e2)}"
                })
                raise ValidationError(_(f'Failed to update stock in Zid: {str(e)}'))

    @api.model
    def create(self, vals):
        """Override create to set default SKU"""
        line = super().create(vals)
        # Set default SKU if not provided
        if not line.zid_sku and line.product_template_id.default_code:
            line.zid_sku = line.product_template_id.default_code
        return line

    def name_get(self):
        """Display name for the line"""
        result = []
        for line in self:
            store_name = line.zid_connector_id.store_name if line.zid_connector_id else 'No Store'
            location_name = line.zid_location_id.name_ar if line.zid_location_id else 'No Location'
            name = f"{store_name} - {location_name}"
            result.append((line.id, name))
        return result