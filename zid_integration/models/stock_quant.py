from odoo import models, fields, api, _
from datetime import datetime, date, timedelta
from odoo.exceptions import ValidationError, UserError
from dateutil import relativedelta
import logging
import json
import traceback

_logger = logging.getLogger(__name__)


class StockQuant(models.Model):
    _inherit = 'stock.quant'

    def write(self, vals):
        _logger.info("=" * 80)
        _logger.info("[STOCK_QUANT.WRITE] Starting stock quant write operation")
        _logger.info(f"[STOCK_QUANT.WRITE] Values to update: {vals}")
        _logger.info(f"[STOCK_QUANT.WRITE] Number of quants: {len(self)}")

        # Store old values before update
        old_quantities = {}
        for quant in self:
            old_quantities[quant.id] = {
                'product_id': quant.product_id,
                'location_id': quant.location_id,
                'quantity': quant.quantity,
            }
            _logger.info(
                f"[STOCK_QUANT.WRITE] Quant ID {quant.id}: Product={quant.product_id.name}, Location={quant.location_id.name}, Old Qty={quant.quantity}")

        # Execute original write
        result = super(StockQuant, self).write(vals)
        _logger.info(f"[STOCK_QUANT.WRITE] Write operation completed successfully")

        # Sync to Zid after successful update
        if 'quantity' in vals:
            _logger.info(f"[STOCK_QUANT.WRITE] Quantity changed, checking for Zid sync...")
            for quant in self:
                old_data = old_quantities.get(quant.id)
                if old_data and old_data['quantity'] != quant.quantity:
                    _logger.info(
                        f"[STOCK_QUANT.WRITE] Quantity changed for Quant {quant.id}: {old_data['quantity']} -> {quant.quantity}")
                    _logger.info(
                        f"[STOCK_QUANT.WRITE] Triggering Zid sync for product {quant.product_id.name} in {quant.location_id.name}")
                    self._sync_to_zid_if_needed(
                        quant.product_id,
                        quant.location_id,
                        quant.quantity
                    )
                else:
                    _logger.info(f"[STOCK_QUANT.WRITE] No quantity change for Quant {quant.id}, skipping sync")
        else:
            _logger.info(f"[STOCK_QUANT.WRITE] No quantity in vals, skipping Zid sync")

        _logger.info("[STOCK_QUANT.WRITE] Write operation finished")
        _logger.info("=" * 80)
        return result

    def _sync_to_zid_if_needed(self, product, location, new_quantity):
        """Check if sync is needed and trigger it"""
        _logger.info("-" * 60)
        _logger.info("[SYNC_IF_NEEDED] Starting sync check")
        _logger.info(f"[SYNC_IF_NEEDED] Product: {product.name} (ID: {product.id})")
        _logger.info(f"[SYNC_IF_NEEDED] Location: {location.name} (ID: {location.id})")
        _logger.info(f"[SYNC_IF_NEEDED] New Quantity: {new_quantity}")
        
        # Calculate total quantity for this product in this location (including new quantity)
        # This is important for CREATE operations where we might have multiple quants
        total_quants = self.search([
            ('product_id', '=', product.id),
            ('location_id', '=', location.id)
        ])
        total_quantity = sum(total_quants.mapped('quantity'))
        _logger.info(f"[SYNC_IF_NEEDED] Total quantity in location (all quants): {total_quantity}")
        
        # Use total quantity instead of new_quantity for sync
        sync_quantity = total_quantity

        # Check if location has zid_location_id
        if not location.zid_location_id:
            _logger.warning(f"[SYNC_IF_NEEDED] ❌ Location {location.name} has no Zid location linked")
            return

        _logger.info(
            f"[SYNC_IF_NEEDED] Location has Zid location: {location.zid_location_id.name_ar if location.zid_location_id else 'N/A'}")
        _logger.info(
            f"[SYNC_IF_NEEDED] Zid location ID: {location.zid_location_id.zid_location_id if location.zid_location_id else 'N/A'}")

        # Get the Zid location record
        _logger.info(
            f"[SYNC_IF_NEEDED] Searching for Zid location record with ID: {location.zid_location_id.zid_location_id}")
        zid_location = self.env['zid.location'].search([
            ('zid_location_id', '=', location.zid_location_id.zid_location_id)
        ], limit=1)

        if not zid_location:
            _logger.error(
                f"[SYNC_IF_NEEDED] ❌ Zid location record not found for {location.zid_location_id.zid_location_id}")
            return

        _logger.info(f"[SYNC_IF_NEEDED] ✅ Found Zid location record: {zid_location.name_ar} (ID: {zid_location.id})")

        # Get the connector from the Zid location
        connector = zid_location.zid_connector_id

        if not connector:
            _logger.error(f"[SYNC_IF_NEEDED] ❌ No connector found for Zid location {zid_location.name_ar}")
            return

        if not connector.is_connected:
            _logger.error(f"[SYNC_IF_NEEDED] ❌ Connector '{connector.store_name}' is not connected")
            return

        _logger.info(
            f"[SYNC_IF_NEEDED] ✅ Connector found: {connector.store_name} (Connected: {connector.is_connected})")

        # Check product template for variants count
        product_template = product.product_tmpl_id
        variant_count = len(product_template.product_variant_ids)
        
        _logger.info(f"[SYNC_IF_NEEDED] Product template: {product_template.name}")
        _logger.info(f"[SYNC_IF_NEEDED] Number of variants: {variant_count}")
        
        # APPROACH 1: Simple products (single variant)
        if variant_count == 1:
            _logger.info("[SYNC_IF_NEEDED] 📦 Simple product detected (single variant)")
            
            # NEW APPROACH: Look for ANY product line with same connector to get zid_product_id
            # We don't need the line for the specific location, just any line in the same store
            any_product_line = self.env['zid.product.line'].search([
                ('product_template_id', '=', product_template.id),
                ('zid_connector_id', '=', connector.id),  # Same store/connector
                ('zid_product_id', '!=', False)  # Has a Zid product ID
            ], limit=1)
            
            if not any_product_line:
                _logger.warning(
                    f"[SYNC_IF_NEEDED] ❌ No product lines found for simple product {product_template.name} in store {connector.store_name}")
                _logger.warning(f"[SYNC_IF_NEEDED] Product doesn't exist in Zid store yet. Cannot sync.")
                return
            
            # Get the Zid product ID from any line in the same store
            zid_product_id = any_product_line.zid_product_id
            _logger.info(f"[SYNC_IF_NEEDED] ✅ Found product in store with Zid Product ID: {zid_product_id}")
            _logger.info(f"[SYNC_IF_NEEDED] Using location: {zid_location.name_ar} ({zid_location.zid_location_id})")
            _logger.info(f"[SYNC_IF_NEEDED] 🚀 Triggering simple product sync to Zid with quantity: {sync_quantity}")
            
            # Now sync the stock directly using the connector, zid_product_id, and location
            try:
                self._sync_simple_product_stock_to_zid(
                    product=product,
                    zid_product_id=zid_product_id,
                    zid_location=zid_location,
                    connector=connector,
                    quantity=sync_quantity
                )
                _logger.info(f"[SYNC_IF_NEEDED] ✅ Successfully synced simple product stock")
            except Exception as e:
                _logger.error(f"[SYNC_IF_NEEDED] ❌ Failed to sync simple product: {str(e)}")
                raise
        
        # APPROACH 2: Products with variants (using zid.variant.mapping)
        else:
            _logger.info(f"[SYNC_IF_NEEDED] 🎨 Product with {variant_count} variants detected")
            _logger.info(f"[SYNC_IF_NEEDED] Looking for variant mappings for product.product ID: {product.id}")

            # Search for variant mappings linked to this product and connector
            variant_mappings = self.env['zid.variant.mapping'].search([
                ('odoo_variant_id', '=', product.id),
                ('zid_connector_id', '=', connector.id)
            ])

            if not variant_mappings:
                _logger.warning(
                    f"[SYNC_IF_NEEDED] ❌ No variant mappings found for product {product.name} in store {connector.store_name}")
                _logger.warning(f"[SYNC_IF_NEEDED] Product variant doesn't exist in Zid store yet. Cannot sync.")
                return

            _logger.info(f"[SYNC_IF_NEEDED] ✅ Found {len(variant_mappings)} variant mapping(s) for this product")
            
            # Use the first mapping found
            variant_mapping = variant_mappings[0]
            
            if not variant_mapping.zid_variant_id:
                _logger.warning(f"[SYNC_IF_NEEDED] Variant mapping has no Zid variant linked, skipping")
                return
                
            if not variant_mapping.zid_tmpl_id:
                _logger.warning(f"[SYNC_IF_NEEDED] Variant mapping has no Zid template linked, skipping")
                return

            zid_variant = variant_mapping.zid_variant_id
            zid_product = variant_mapping.zid_tmpl_id

            _logger.info(f"[SYNC_IF_NEEDED] Processing variant: {zid_variant.display_name}")
            _logger.info(f"[SYNC_IF_NEEDED] Zid Variant ID: {zid_variant.zid_variant_id}")
            _logger.info(f"[SYNC_IF_NEEDED] Parent Product ID: {zid_product.zid_product_id}")

            # Trigger sync using the mapping's action_sync_stock method
            _logger.info(f"[SYNC_IF_NEEDED] 🚀 Triggering variant sync using mapping.action_sync_stock()")
            
            try:
                # Call the action_sync_stock method from zid.variant.mapping
                variant_mapping.action_sync_stock()
                _logger.info(f"[SYNC_IF_NEEDED] ✅ Successfully triggered sync via mapping")
            except Exception as e:
                _logger.error(f"[SYNC_IF_NEEDED] ❌ Failed to sync via mapping: {str(e)}")
                # Fallback to direct sync method if mapping sync fails
                _logger.info(f"[SYNC_IF_NEEDED] Falling back to direct sync method...")
                self._sync_variant_stock_to_zid(
                    product=product,
                    zid_variant=zid_variant,
                    zid_location=zid_location,
                    connector=connector,
                    quantity=sync_quantity,
                    variant_line=None  # No variant line in this approach
                )

        _logger.info("-" * 60)

    def _sync_variant_stock_to_zid(self, product, zid_variant, zid_location, connector, quantity, variant_line):
        """Sync stock to Zid using variant approach (as per Zid API documentation)"""
        _logger.info("*" * 70)
        _logger.info("[SYNC_VARIANT_TO_ZID] Starting variant-based sync to Zid")
        _logger.info(f"[SYNC_VARIANT_TO_ZID] Odoo Product: {product.name}")
        _logger.info(f"[SYNC_VARIANT_TO_ZID] Zid Variant: {zid_variant.display_name}")
        _logger.info(f"[SYNC_VARIANT_TO_ZID] Zid Variant ID: {zid_variant.zid_variant_id}")
        _logger.info(f"[SYNC_VARIANT_TO_ZID] Parent Product ID: {zid_variant.parent_product_id.zid_product_id}")
        _logger.info(f"[SYNC_VARIANT_TO_ZID] Location: {zid_location.name_ar}")
        _logger.info(f"[SYNC_VARIANT_TO_ZID] Quantity to sync: {quantity}")

        # Create log entry
        log_model = self.env['zid.stock.update.log']
        _logger.info("[SYNC_VARIANT_TO_ZID] Creating log entry...")

        # Get the Odoo location
        odoo_location = self.env['stock.location'].search([
            ('zid_location_id.zid_location_id', '=', zid_location.zid_location_id)
        ], limit=1)

        log = log_model.create({
            'zid_connector_id': connector.id,
            'product_id': product.id,
            'product_template_id': product.product_tmpl_id.id,
            'zid_product_id': zid_variant.parent_product_id.id,
            'odoo_location_id': odoo_location.id if odoo_location else False,
            'zid_location_id': zid_location.id,
            'quantity_before_odoo': variant_line.zid_quantity if variant_line else 0,
            'quantity_after_odoo': quantity,
            'quantity_before_zid': variant_line.zid_quantity if variant_line else 0,
            'operation_type': 'inventory',
            'trigger_source': 'stock_quant',
            'sync_direction': 'odoo_to_zid',
            'status': 'processing',
            'api_endpoint': f'products/{zid_variant.parent_product_id.zid_product_id}/',
            'api_method': 'PATCH',
            'notes': f'Variant sync: {zid_variant.zid_variant_id}'
        })
        _logger.info(f"[SYNC_VARIANT_TO_ZID] Log entry created with ID: {log.id}")

        try:
            # Calculate total quantity for this location
            if odoo_location:
                _logger.info(f"[SYNC_VARIANT_TO_ZID] Found Odoo location: {odoo_location.name}")
                # Get all quants for this product in this location
                quants = self.search([
                    ('product_id', '=', product.id),
                    ('location_id', '=', odoo_location.id)
                ])
                total_qty = sum(quants.mapped('quantity'))
                _logger.info(f"[SYNC_VARIANT_TO_ZID] Total quantity calculated from Odoo: {total_qty}")
            else:
                _logger.warning(f"[SYNC_VARIANT_TO_ZID] No Odoo location found, using passed quantity: {quantity}")
                total_qty = quantity

            # Get ALL variant lines for the same Zid variant in different locations
            _logger.info(f"[SYNC_VARIANT_TO_ZID] Looking for all locations of the same variant")
            all_variant_lines = self.env['zid.variant.line'].search([
                ('zid_variant_id', '=', zid_variant.id),
                ('zid_connector_id', '=', connector.id)
            ])
            _logger.info(f"[SYNC_VARIANT_TO_ZID] Found {len(all_variant_lines)} location(s) for this variant")

            # Build stocks array with all locations for this variant
            stocks_data = []
            _logger.info("[SYNC_VARIANT_TO_ZID] Building stocks data array...")

            for line in all_variant_lines:
                if line.zid_location_id.id == zid_location.id:
                    # This is the location we're updating
                    line_qty = int(total_qty)
                    _logger.info(
                        f"[SYNC_VARIANT_TO_ZID]   🎯 Current location - {line.zid_location_id.name_ar}: {line_qty}")
                else:
                    # Other locations - get their current quantity from Odoo
                    other_odoo_location = self.env['stock.location'].search([
                        ('zid_location_id.zid_location_id', '=', line.zid_location_id.zid_location_id)
                    ], limit=1)

                    if other_odoo_location:
                        other_quants = self.search([
                            ('product_id', '=', product.id),
                            ('location_id', '=', other_odoo_location.id)
                        ])
                        line_qty = int(sum(other_quants.mapped('quantity')))
                        _logger.info(
                            f"[SYNC_VARIANT_TO_ZID]   Other location - {line.zid_location_id.name_ar}: calculated qty = {line_qty}")
                    else:
                        # Use last synced quantity as fallback
                        line_qty = line.zid_quantity or 0
                        _logger.info(
                            f"[SYNC_VARIANT_TO_ZID]   Other location - {line.zid_location_id.name_ar}: using last synced qty = {line_qty}")

                stocks_data.append({
                    'location': line.zid_location_id.zid_location_id,
                    'available_quantity': line_qty,
                    'is_infinite': False
                })

            _logger.info(f"[SYNC_VARIANT_TO_ZID] Total locations in update: {len(stocks_data)}")

            # If we only have one location, try to preserve others from Zid
            if len(stocks_data) == 1:
                try:
                    _logger.info(
                        f"[SYNC_VARIANT_TO_ZID] Single location update, fetching variant data from Zid to preserve other locations")

                    # First get the product to find all variants
                    current_product = connector.api_request(
                        endpoint=f'products/{zid_variant.parent_product_id.zid_product_id}',
                        method='GET'
                    )

                    if current_product and 'variants' in current_product:
                        # Find our variant in the response
                        for variant in current_product.get('variants', []):
                            if variant.get('id') == zid_variant.zid_variant_id:
                                existing_stocks = variant.get('stocks', [])
                                _logger.info(
                                    f"[SYNC_VARIANT_TO_ZID] Found {len(existing_stocks)} existing stocks for variant in Zid")

                                if existing_stocks:
                                    # Build a dict of our updates
                                    updates_dict = {stock['location']: stock for stock in stocks_data}

                                    # Preserve other locations
                                    for stock in existing_stocks:
                                        location_id = stock.get('location')
                                        if location_id not in updates_dict:
                                            stocks_data.append({
                                                'location': location_id,
                                                'available_quantity': stock.get('available_quantity', 0),
                                                'is_infinite': stock.get('is_infinite', False)
                                            })
                                            _logger.info(
                                                f"[SYNC_VARIANT_TO_ZID] Preserved location {location_id} from Zid")
                                break
                except Exception as e:
                    _logger.warning(f"[SYNC_VARIANT_TO_ZID] Could not fetch from Zid: {str(e)}")

            # Prepare update data using variant structure
            update_data = {
                'variants': [
                    {
                        'id': zid_variant.zid_variant_id,
                        'stocks': stocks_data
                    }
                ]
            }

            # Update log with request data
            log.write({
                'request_data': json.dumps(update_data, indent=2)
            })

            _logger.info(f"[SYNC_VARIANT_TO_ZID] Sending update to Zid...")
            _logger.info(f"[SYNC_VARIANT_TO_ZID] Endpoint: products/{zid_variant.parent_product_id.zid_product_id}/")
            _logger.info(f"[SYNC_VARIANT_TO_ZID] Method: PATCH")
            _logger.info(f"[SYNC_VARIANT_TO_ZID] Data: {json.dumps(update_data, indent=2)}")

            # Make API request using PATCH with variant structure
            response = connector.api_request(
                endpoint=f'products/{zid_variant.parent_product_id.zid_product_id}/',
                method='PATCH',
                data=update_data
            )

            _logger.info(f"[SYNC_VARIANT_TO_ZID] ✅ API Response received successfully")

            # Update log with success
            log.mark_success(
                response_data=response,
                response_code=200,
                notes=f"Successfully updated variant {zid_variant.zid_variant_id} stock for {len(stocks_data)} location(s)"
            )

            # Update variant line quantities
            if variant_line:
                variant_line.write({
                    'zid_quantity': int(total_qty),
                    'last_sync_date': fields.Datetime.now(),
                    'sync_status': 'synced',
                    'sync_error_message': False
                })

            # Update other variant lines if they exist
            for line in all_variant_lines:
                if line.id != (variant_line.id if variant_line else 0):
                    # Find the quantity for this line from stocks_data
                    for stock in stocks_data:
                        if stock['location'] == line.zid_location_id.zid_location_id:
                            line.write({
                                'zid_quantity': stock['available_quantity'],
                                'last_sync_date': fields.Datetime.now(),
                            })
                            break

            # Update variant stock lines in zid.variant.stock.line
            for stock_data in stocks_data:
                stock_line = self.env['zid.variant.stock.line'].search([
                    ('variant_id', '=', zid_variant.id),
                    ('location_id.zid_location_id', '=', stock_data['location'])
                ], limit=1)

                if stock_line:
                    stock_line.write({
                        'available_quantity': stock_data['available_quantity'],
                        'last_update': fields.Datetime.now()
                    })
                    _logger.info(
                        f"[SYNC_VARIANT_TO_ZID] Updated stock line for location {stock_line.location_id.name_ar}")

            # Update product template status
            product.product_tmpl_id.write({
                'last_stock_sync': fields.Datetime.now(),
                'stock_sync_status': 'success'
            })

            _logger.info(f"[SYNC_VARIANT_TO_ZID] ✅ Sync completed successfully!")
            _logger.info("*" * 70)

            return response

        except Exception as e:
            _logger.error(f"[SYNC_VARIANT_TO_ZID] ❌ ERROR: {str(e)}")
            _logger.error(f"[SYNC_VARIANT_TO_ZID] Traceback:\n{traceback.format_exc()}")

            # Update log with error
            log.mark_failed(
                error_message=str(e),
                error_details=traceback.format_exc(),
                response_code=getattr(e, 'response_code', None)
            )

            # Update variant line status if exists
            if variant_line:
                variant_line.write({
                    'sync_status': 'error',
                    'sync_error_message': str(e)
                })

            # Update product template status
            product.product_tmpl_id.write({
                'stock_sync_status': 'failed',
                'zid_error_message': str(e)
            })

            _logger.error("*" * 70)
            raise

    def _sync_simple_product_stock_to_zid(self, product, zid_product_id, zid_location, connector, quantity):
        """Sync stock to Zid for simple products (single variant)"""
        _logger.info("*" * 70)
        _logger.info("[SYNC_SIMPLE_TO_ZID] Starting simple product sync to Zid")
        _logger.info(f"[SYNC_SIMPLE_TO_ZID] Odoo Product: {product.name}")
        _logger.info(f"[SYNC_SIMPLE_TO_ZID] Zid Product ID: {zid_product_id}")
        _logger.info(f"[SYNC_SIMPLE_TO_ZID] Location: {zid_location.name_ar}")
        _logger.info(f"[SYNC_SIMPLE_TO_ZID] Zid Location ID: {zid_location.zid_location_id}")
        _logger.info(f"[SYNC_SIMPLE_TO_ZID] Quantity to sync: {quantity}")

        # Create log entry
        log_model = self.env['zid.stock.update.log']
        _logger.info("[SYNC_SIMPLE_TO_ZID] Creating log entry...")

        # Get the Odoo location
        odoo_location = self.env['stock.location'].search([
            ('zid_location_id.zid_location_id', '=', zid_location.zid_location_id)
        ], limit=1)

        # Get zid.product record if exists
        zid_product = self.env['zid.product'].search([
            ('zid_product_id', '=', zid_product_id),
            ('zid_connector_id', '=', connector.id)
        ], limit=1)

        log = log_model.create({
            'zid_connector_id': connector.id,
            'product_id': product.id,
            'product_template_id': product.product_tmpl_id.id,
            'zid_product_id': zid_product.id if zid_product else False,
            'odoo_location_id': odoo_location.id if odoo_location else False,
            'zid_location_id': zid_location.id,
            'quantity_before_odoo': 0,  # We don't track this for simple products yet
            'quantity_after_odoo': quantity,
            'quantity_before_zid': 0,
            'operation_type': 'inventory',
            'trigger_source': 'stock_quant',
            'sync_direction': 'odoo_to_zid',
            'status': 'processing',
            'api_endpoint': f'products/{zid_product_id}/',
            'api_method': 'PATCH',
            'notes': f'Simple product sync'
        })
        _logger.info(f"[SYNC_SIMPLE_TO_ZID] Log entry created with ID: {log.id}")

        try:
            # Calculate total quantity for this location
            if odoo_location:
                _logger.info(f"[SYNC_SIMPLE_TO_ZID] Found Odoo location: {odoo_location.name}")
                # Get all quants for this product in this location
                quants = self.search([
                    ('product_id', '=', product.id),
                    ('location_id', '=', odoo_location.id)
                ])
                total_qty = sum(quants.mapped('quantity'))
                _logger.info(f"[SYNC_SIMPLE_TO_ZID] Total quantity calculated from Odoo: {total_qty}")
            else:
                _logger.warning(f"[SYNC_SIMPLE_TO_ZID] No Odoo location found, using passed quantity: {quantity}")
                total_qty = quantity

            # Get ALL product lines for the same product in different locations but same connector
            _logger.info(f"[SYNC_SIMPLE_TO_ZID] Looking for all locations of the same product in the same store")
            all_product_lines = self.env['zid.product.line'].search([
                ('product_template_id', '=', product.product_tmpl_id.id),
                ('zid_connector_id', '=', connector.id)
            ])
            _logger.info(f"[SYNC_SIMPLE_TO_ZID] Found {len(all_product_lines)} location(s) for this product")

            # Build stocks array with all locations for this product
            stocks_data = []
            _logger.info("[SYNC_SIMPLE_TO_ZID] Building stocks data array...")

            # First, add the current location we're updating
            stocks_data.append({
                'location': zid_location.zid_location_id,
                'available_quantity': int(total_qty),
                'is_infinite': False
            })
            _logger.info(f"[SYNC_SIMPLE_TO_ZID]   🎯 Current location - {zid_location.name_ar}: {int(total_qty)}")

            # Then add other locations from product lines
            for line in all_product_lines:
                # Skip if it's the same location we just added
                if line.zid_location_id.id == zid_location.id:
                    continue
                
                # Get quantity for this location
                other_odoo_location = self.env['stock.location'].search([
                    ('zid_location_id.zid_location_id', '=', line.zid_location_id.zid_location_id)
                ], limit=1)

                if other_odoo_location:
                    other_quants = self.search([
                        ('product_id', '=', product.id),
                        ('location_id', '=', other_odoo_location.id)
                    ])
                    line_qty = int(sum(other_quants.mapped('quantity')))
                    _logger.info(
                        f"[SYNC_SIMPLE_TO_ZID]   Other location - {line.zid_location_id.name_ar}: calculated qty = {line_qty}")
                else:
                    # Use last synced quantity as fallback
                    line_qty = line.zid_quantity or 0
                    _logger.info(
                        f"[SYNC_SIMPLE_TO_ZID]   Other location - {line.zid_location_id.name_ar}: using last synced qty = {line_qty}")

                stocks_data.append({
                    'location': line.zid_location_id.zid_location_id,
                    'available_quantity': line_qty,
                    'is_infinite': False
                })

            _logger.info(f"[SYNC_SIMPLE_TO_ZID] Total locations in update: {len(stocks_data)}")

            # Prepare update data for simple product
            update_data = {
                'stocks': stocks_data
            }

            # Update log with request data
            log.write({
                'request_data': json.dumps(update_data, indent=2)
            })

            _logger.info(f"[SYNC_SIMPLE_TO_ZID] Sending update to Zid...")
            _logger.info(f"[SYNC_SIMPLE_TO_ZID] Endpoint: products/{zid_product_id}/")
            _logger.info(f"[SYNC_SIMPLE_TO_ZID] Method: PATCH")
            _logger.info(f"[SYNC_SIMPLE_TO_ZID] Data: {json.dumps(update_data, indent=2)}")

            # Make API request using PATCH
            response = connector.api_request(
                endpoint=f'products/{zid_product_id}/',
                method='PATCH',
                data=update_data
            )

            _logger.info(f"[SYNC_SIMPLE_TO_ZID] ✅ API Response received successfully")

            # Update log with success
            log.mark_success(
                response_data=response,
                response_code=200,
                notes=f"Successfully updated simple product stock for {len(stocks_data)} location(s)"
            )

            # Update product lines quantities for tracking
            for line in all_product_lines:
                # Find the quantity for this line from stocks_data
                for stock in stocks_data:
                    if stock['location'] == line.zid_location_id.zid_location_id:
                        line.write({
                            'zid_quantity': stock['available_quantity'],
                            'last_sync_date': fields.Datetime.now(),
                            'sync_status': 'synced',
                            'sync_error_message': False
                        })
                        break

            # Update product template status
            product.product_tmpl_id.write({
                'last_stock_sync': fields.Datetime.now(),
                'stock_sync_status': 'success'
            })

            _logger.info(f"[SYNC_SIMPLE_TO_ZID] ✅ Sync completed successfully!")
            _logger.info("*" * 70)

            return response

        except Exception as e:
            _logger.error(f"[SYNC_SIMPLE_TO_ZID] ❌ ERROR: {str(e)}")
            _logger.error(f"[SYNC_SIMPLE_TO_ZID] Traceback:\n{traceback.format_exc()}")

            # Update log with error
            log.mark_failed(
                error_message=str(e),
                error_details=traceback.format_exc(),
                response_code=getattr(e, 'response_code', None)
            )

            # Update product template status
            product.product_tmpl_id.write({
                'stock_sync_status': 'failed',
                'zid_error_message': str(e)
            })

            _logger.error("*" * 70)
            raise

    @api.model
    def _cron_auto_sync_stock_to_zid(self):
        """Cron job to sync stock changes to Zid using variant approach"""
        _logger.info("=" * 80)
        _logger.info("[CRON_SYNC] 🕔 STARTING AUTOMATIC STOCK SYNC TO ZID (VARIANT APPROACH)")
        _logger.info(f"[CRON_SYNC] Time: {fields.Datetime.now()}")

        # Get all products that have variant lines
        products = self.env['product.product'].search([
            ('zid_variant_line_ids', '!=', False)
        ])

        _logger.info(f"[CRON_SYNC] Found {len(products)} products with Zid variant lines")

        sync_count = 0
        error_count = 0

        for idx, product in enumerate(products, 1):
            _logger.info(f"[CRON_SYNC] Processing product {idx}/{len(products)}: {product.name} (ID: {product.id})")

            try:
                # Get all variant lines for this product
                variant_lines = product.zid_variant_line_ids

                _logger.info(f"[CRON_SYNC] Found {len(variant_lines)} variant line(s)")

                # Group variant lines by variant
                variants_dict = {}
                for line in variant_lines:
                    if line.zid_variant_id:
                        if line.zid_variant_id.id not in variants_dict:
                            variants_dict[line.zid_variant_id.id] = []
                        variants_dict[line.zid_variant_id.id].append(line)

                # Process each variant
                for zid_variant_id, lines in variants_dict.items():
                    zid_variant = self.env['zid.variant'].browse(zid_variant_id)
                    _logger.info(f"[CRON_SYNC]   Processing variant: {zid_variant.display_name}")

                    # Check if sync is needed for any location
                    needs_sync = False
                    for line in lines:
                        # Get Odoo location
                        odoo_location = self.env['stock.location'].search([
                            ('zid_location_id.zid_location_id', '=', line.zid_location_id.zid_location_id)
                        ], limit=1)

                        if not odoo_location:
                            continue

                        # Calculate current quantity
                        quants = self.search([
                            ('product_id', '=', product.id),
                            ('location_id', '=', odoo_location.id)
                        ])

                        total_qty = sum(quants.mapped('quantity'))
                        current_zid_qty = line.zid_quantity if line.zid_quantity is not None else -1

                        if int(total_qty) != current_zid_qty or line.force_sync:
                            needs_sync = True
                            _logger.info(
                                f"[CRON_SYNC]     Location {line.zid_location_id.name_ar}: {current_zid_qty} -> {total_qty} (needs sync)")
                            break

                    if needs_sync:
                        _logger.info(f"[CRON_SYNC]   🔄 SYNC NEEDED for variant {zid_variant.zid_variant_id}")

                        # Use the first line's connector and location for sync
                        first_line = lines[0]
                        connector = first_line.zid_connector_id

                        # Sync the variant
                        self._sync_variant_stock_to_zid(
                            product=product,
                            zid_variant=zid_variant,
                            zid_location=first_line.zid_location_id,
                            connector=connector,
                            quantity=0,  # Will be recalculated in the method
                            variant_line=first_line
                        )

                        sync_count += 1
                        _logger.info(f"[CRON_SYNC]   ✅ Sync completed for variant")
                    else:
                        _logger.info(f"[CRON_SYNC]   🆗 No sync needed for variant")

            except Exception as e:
                error_count += 1
                _logger.error(f"[CRON_SYNC] ❌ ERROR for product {product.name}: {str(e)}")
                _logger.error(f"[CRON_SYNC] Traceback:\n{traceback.format_exc()}")
                continue

        _logger.info(f"[CRON_SYNC] 🏁 CRON SYNC COMPLETED")
        _logger.info(f"[CRON_SYNC] Summary:")
        _logger.info(f"[CRON_SYNC]   - Products processed: {len(products)}")
        _logger.info(f"[CRON_SYNC]   - Successful syncs: {sync_count}")
        _logger.info(f"[CRON_SYNC]   - Errors: {error_count}")
        _logger.info(f"[CRON_SYNC] End time: {fields.Datetime.now()}")
        _logger.info("=" * 80)

    @api.model
    def create(self, vals):
        """Override create to sync new stock to Zid"""
        _logger.info("=" * 80)
        _logger.info("[STOCK_QUANT.CREATE] Creating new stock quant")
        _logger.info(f"[STOCK_QUANT.CREATE] Values: {vals}")

        quant = super(StockQuant, self).create(vals)

        _logger.info(f"[STOCK_QUANT.CREATE] Quant created successfully")
        _logger.info(f"[STOCK_QUANT.CREATE] Product: {quant.product_id.name}")
        _logger.info(f"[STOCK_QUANT.CREATE] Location: {quant.location_id.name}")
        _logger.info(f"[STOCK_QUANT.CREATE] Quantity: {quant.quantity}")

        # Check if product is simple or has variants
        product_template = quant.product_id.product_tmpl_id
        variant_count = len(product_template.product_variant_ids)
        _logger.info(f"[STOCK_QUANT.CREATE] Product template: {product_template.name}")
        _logger.info(f"[STOCK_QUANT.CREATE] Number of variants: {variant_count}")

        # Always sync to Zid, even if quantity is 0
        _logger.info(f"[STOCK_QUANT.CREATE] Triggering Zid sync...")
        try:
            self._sync_to_zid_if_needed(
                quant.product_id,
                quant.location_id,
                quant.quantity
            )
            _logger.info(f"[STOCK_QUANT.CREATE] ✅ Zid sync completed successfully")
        except Exception as e:
            _logger.error(f"[STOCK_QUANT.CREATE] ❌ Failed to sync to Zid: {str(e)}")
            # Don't raise to avoid breaking the stock creation
            # The sync can be retried later

        _logger.info("[STOCK_QUANT.CREATE] Create operation finished")
        _logger.info("=" * 80)
        return quant

    @api.model
    def _update_available_quantity(self, product_id, location_id, quantity=False,
                                   reserved_quantity=False, lot_id=None, package_id=None,
                                   owner_id=None, in_date=None):
        """Override to track quantity updates through this method"""
        _logger.info("=" * 80)
        _logger.info("[UPDATE_AVAILABLE_QTY] Updating available quantity")
        _logger.info(f"[UPDATE_AVAILABLE_QTY] Product: {product_id.name if product_id else 'N/A'}")
        _logger.info(f"[UPDATE_AVAILABLE_QTY] Location: {location_id.name if location_id else 'N/A'}")
        _logger.info(f"[UPDATE_AVAILABLE_QTY] Quantity delta: {quantity}")
        _logger.info(f"[UPDATE_AVAILABLE_QTY] Reserved quantity: {reserved_quantity}")

        # Get current quantity before update
        quants = self._gather(product_id, location_id, lot_id=lot_id,
                              package_id=package_id, owner_id=owner_id, strict=True)

        old_quantity = sum(quants.mapped('quantity')) if quants else 0
        _logger.info(f"[UPDATE_AVAILABLE_QTY] Current quantity before update: {old_quantity}")

        # Execute original update
        result = super(StockQuant, self)._update_available_quantity(
            product_id, location_id, quantity, reserved_quantity,
            lot_id, package_id, owner_id, in_date
        )
        _logger.info(f"[UPDATE_AVAILABLE_QTY] Update executed successfully")

        # Get new quantity after update
        if quantity:
            new_quantity = old_quantity + quantity
            _logger.info(f"[UPDATE_AVAILABLE_QTY] New quantity after update: {new_quantity}")
            _logger.info(f"[UPDATE_AVAILABLE_QTY] Triggering Zid sync...")

            # Sync to Zid
            try:
                self._sync_to_zid_if_needed(
                    product_id,
                    location_id,
                    new_quantity
                )
                _logger.info(f"[UPDATE_AVAILABLE_QTY] ✅ Zid sync triggered successfully")
            except Exception as e:
                _logger.error(f"[UPDATE_AVAILABLE_QTY] ❌ Failed to sync: {str(e)}")
                # Don't raise the error to avoid breaking stock operations
        else:
            _logger.info(f"[UPDATE_AVAILABLE_QTY] No quantity change, skipping Zid sync")

        _logger.info("[UPDATE_AVAILABLE_QTY] Operation finished")
        _logger.info("=" * 80)
        return result