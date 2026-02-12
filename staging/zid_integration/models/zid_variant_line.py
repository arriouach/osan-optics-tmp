from odoo import models, fields, api, _
from datetime import datetime, date, timedelta
from odoo.exceptions import ValidationError
from dateutil import relativedelta
import logging
import json

_logger = logging.getLogger(__name__)


class VariantLine(models.Model):
    _name = 'zid.variant.line'

    # Sequence for ordering
    sequence = fields.Integer(
        string='Sequence',
        default=10,
        help='Used to order the product lines'
    )

    # Relations
    product_id = fields.Many2one(
        'product.product',
        string='Product Variant',
        required=True,
        ondelete='cascade'
    )

    product_tmpl_id = fields.Many2one(
        'product.template',
        string='Product Template',
        related='product_id.product_tmpl_id',
        store=True,
        readonly=True
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

    zid_variant_id = fields.Many2one('zid.variant', string='Zid Variant', ondelete='cascade')

    # Product Information
    zid_product_id = fields.Char(
        string='Zid Product ID',
        help='Product ID in Zid system',
        related="zid_variant_id.zid_variant_id"
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

    def action_sync_stock(self):
        """Sync stock from Odoo to Zid for this variant line"""
        self.ensure_one()

        _logger.info("=" * 80)
        _logger.info(f"[SYNC_STOCK] Starting stock sync for variant line")
        _logger.info(f"[SYNC_STOCK] Product: {self.product_id.display_name}")
        _logger.info(f"[SYNC_STOCK] Store: {self.store_name}")
        _logger.info(f"[SYNC_STOCK] Location: {self.location_name}")

        if not self.zid_variant_id:
            _logger.error(f"[SYNC_STOCK] No Zid variant linked to this line")
            raise ValidationError(_('This variant line has no Zid variant linked'))

        # Find the Odoo location linked to this Zid location
        odoo_location = self.env['stock.location'].search([
            ('zid_location_id.zid_location_id', '=', self.zid_location_id.zid_location_id)
        ], limit=1)

        if not odoo_location:
            _logger.error(f"[SYNC_STOCK] No Odoo location found for Zid location {self.zid_location_id.display_name}")
            raise ValidationError(
                _(f'No Odoo location found linked to Zid location {self.zid_location_id.display_name}'))

        # Calculate quantity from stock.quant
        quants = self.env['stock.quant'].search([
            ('product_id', '=', self.product_id.id),
            ('location_id', '=', odoo_location.id)
        ])

        total_qty = sum(quants.mapped('quantity'))
        _logger.info(f"[SYNC_STOCK] Current stock in Odoo: {total_qty}")

        # Use the sync method from stock.quant
        self.env['stock.quant']._sync_variant_stock_to_zid(
            product=self.product_id,
            zid_variant=self.zid_variant_id,
            zid_location=self.zid_location_id,
            connector=self.zid_connector_id,
            quantity=total_qty,
            variant_line=self
        )

        _logger.info(f"[SYNC_STOCK] Stock sync completed successfully")
        _logger.info("=" * 80)

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

    def create_in_zid(self):
        """Create this product variant in Zid for this specific store/location"""
        self.ensure_one()

        _logger.info("=" * 80)
        _logger.info(f"[CREATE_VARIANT_IN_ZID] Starting variant creation in Zid")
        _logger.info(
            f"[CREATE_VARIANT_IN_ZID] Product Variant: {self.product_id.display_name} (ID: {self.product_id.id})")
        _logger.info(f"[CREATE_VARIANT_IN_ZID] Parent Template: {self.product_id.product_tmpl_id.name}")
        _logger.info(f"[CREATE_VARIANT_IN_ZID] Store: {self.zid_connector_id.store_name}")
        _logger.info(
            f"[CREATE_VARIANT_IN_ZID] Location: {self.zid_location_id.name_ar if self.zid_location_id else 'No Location'}")

        # Check if connector is connected
        if not self.zid_connector_id.is_connected:
            _logger.error(f"[CREATE_VARIANT_IN_ZID] Store {self.zid_connector_id.store_name} is not connected")
            raise ValidationError(_(f'Store {self.zid_connector_id.store_name} is not connected'))

        # Check if variant already exists in Zid
        if self.zid_product_id:
            _logger.warning(f"[CREATE_VARIANT_IN_ZID] Variant already exists in Zid with ID: {self.zid_product_id}")
            raise ValidationError(_(f'This variant already exists in Zid (ID: {self.zid_product_id})'))

        try:
            # Prepare product/variant data
            _logger.info(f"[CREATE_VARIANT_IN_ZID] Preparing variant data...")
            product_data = self._prepare_variant_data_for_creation()

            _logger.info(f"[CREATE_VARIANT_IN_ZID] Variant data prepared successfully")
            _logger.info(f"[CREATE_VARIANT_IN_ZID] Data to send: {json.dumps(product_data, indent=2)}")

            # Check if parent product exists in Zid
            parent_template = self.product_id.product_tmpl_id
            parent_zid_product = None

            # Look for existing Zid product linked to this template
            zid_product_line = self.env['zid.product.line'].search([
                ('product_template_id', '=', parent_template.id),
                ('zid_connector_id', '=', self.zid_connector_id.id),
                ('zid_product_id', '!=', False)
            ], limit=1)

            if zid_product_line and zid_product_line.zid_product_id:
                parent_zid_product_id = zid_product_line.zid_product_id
                _logger.info(f"[CREATE_VARIANT_IN_ZID] Found existing parent product in Zid: {parent_zid_product_id}")

                # Update the existing product with new variant
                _logger.info(f"[CREATE_VARIANT_IN_ZID] Updating parent product with new variant...")

                # Prepare variant update data
                variant_update_data = {
                    'variants': [product_data.get('variant_data', product_data)]
                }

                # Make API request to update product with new variant
                _logger.info(f"[CREATE_VARIANT_IN_ZID] Sending PATCH request to update parent product...")
                response = self.zid_connector_id.api_request(
                    endpoint=f'products/{parent_zid_product_id}/',
                    method='PATCH',
                    data=variant_update_data
                )

            else:
                # Create new product with variant
                _logger.info(f"[CREATE_VARIANT_IN_ZID] No parent product found, creating new product with variant...")

                # Make API request to create product
                _logger.info(f"[CREATE_VARIANT_IN_ZID] Sending POST request to create product...")
                response = self.zid_connector_id.api_request(
                    endpoint='products/',
                    method='POST',
                    data=product_data
                )

            _logger.info(f"[CREATE_VARIANT_IN_ZID] Response received successfully")
            _logger.info(
                f"[CREATE_VARIANT_IN_ZID] Response: {json.dumps(response, indent=2) if response else 'No response'}")

            # Update line with response data
            if response:
                _logger.info(f"[CREATE_VARIANT_IN_ZID] Updating variant line with response data...")
                self._update_from_zid_response(response)
                _logger.info(f"[CREATE_VARIANT_IN_ZID] Variant line updated")

            # Update sync status
            self.write({
                'sync_status': 'synced',
                'last_sync_date': fields.Datetime.now(),
                'sync_error_message': False
            })

            _logger.info(f"[CREATE_VARIANT_IN_ZID] Variant created successfully!")
            _logger.info("=" * 80)

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success!'),
                    'message': _(f'Variant created successfully in {self.zid_connector_id.store_name}'),
                    'type': 'success',
                    'sticky': False,
                }
            }

        except Exception as e:
            _logger.error(f"[CREATE_VARIANT_IN_ZID] Failed to create variant in Zid: {str(e)}")
            _logger.error("=" * 80)
            self.write({
                'sync_status': 'error',
                'sync_error_message': str(e)
            })
            raise ValidationError(_(f'Failed to create variant in Zid: {str(e)}'))

    def _prepare_variant_data_for_creation(self):
        """Prepare variant data for Zid API creation"""
        self.ensure_one()

        product = self.product_id
        template = product.product_tmpl_id

        _logger.info(f"[PREPARE_VARIANT_DATA] Starting data preparation for variant: {product.display_name}")
        _logger.info(f"[PREPARE_VARIANT_DATA] Parent template: {template.name}")

        # Get variant attributes
        attribute_values = []
        for attribute_line in product.product_template_attribute_value_ids:
            attr_value = {
                'attribute_id': attribute_line.attribute_id.id,
                'attribute_name': attribute_line.attribute_id.name,
                'value_id': attribute_line.product_attribute_value_id.id,
                'value_name': attribute_line.product_attribute_value_id.name
            }
            attribute_values.append(attr_value)
            _logger.info(
                f"[PREPARE_VARIANT_DATA] Attribute: {attr_value['attribute_name']} = {attr_value['value_name']}")

        # Prepare variant specific data
        variant_data = {
            'sku': self.zid_sku or product.default_code or f'ODOO-VAR-{product.id}',
            'price': self.zid_price or product.lst_price or template.list_price or 0,
            'compare_at_price': self.zid_compare_price or 0,
            'cost': product.standard_price or template.standard_price or 0,
            'barcode': product.barcode or '',
            'weight': {
                'value': product.weight or template.weight or 0,
                'unit': 'kg'
            }
        }

        _logger.info(f"[PREPARE_VARIANT_DATA] Variant SKU: {variant_data['sku']}")
        _logger.info(f"[PREPARE_VARIANT_DATA] Variant Price: {variant_data['price']}")

        # Add variant options/attributes
        if attribute_values:
            options = []
            for attr in attribute_values:
                options.append({
                    'name': attr['attribute_name'],
                    'value': attr['value_name']
                })
            variant_data['options'] = options
            _logger.info(f"[PREPARE_VARIANT_DATA] Added {len(options)} option(s) to variant")

        # Get stock for this variant at the specified location
        if self.zid_location_id and self.zid_location_id.zid_location_id:
            _logger.info(f"[PREPARE_VARIANT_DATA] Preparing stock data for location: {self.zid_location_id.name_ar}")

            # Get current stock quantity from Odoo for this variant
            odoo_location = self.env['stock.location'].search([
                ('zid_location_id.zid_location_id', '=', self.zid_location_id.zid_location_id)
            ], limit=1)

            quantity = 0
            if odoo_location:
                quants = self.env['stock.quant'].search([
                    ('product_id', '=', product.id),
                    ('location_id', '=', odoo_location.id)
                ])
                quantity = sum(quants.mapped('quantity'))
                _logger.info(f"[PREPARE_VARIANT_DATA] Current stock at {odoo_location.name}: {quantity}")
            else:
                _logger.warning(f"[PREPARE_VARIANT_DATA] No Odoo location found for Zid location")

            variant_data['stocks'] = [{
                'available_quantity': int(quantity),
                'is_infinite': False,
                'location': self.zid_location_id.zid_location_id
            }]
            _logger.info(f"[PREPARE_VARIANT_DATA] Added stock data: quantity={int(quantity)}")

        # Check if we need to create parent product or just add variant
        zid_product_line = self.env['zid.product.line'].search([
            ('product_template_id', '=', template.id),
            ('zid_connector_id', '=', self.zid_connector_id.id),
            ('zid_product_id', '!=', False)
        ], limit=1)

        if zid_product_line and zid_product_line.zid_product_id:
            # Parent exists, return variant data only
            _logger.info(f"[PREPARE_VARIANT_DATA] Parent product exists, returning variant data only")
            return {
                'variant_data': variant_data
            }
        else:
            # Need to create parent product with this variant
            _logger.info(f"[PREPARE_VARIANT_DATA] Parent product doesn't exist, preparing full product data")

            # Prepare parent product data
            product_data = {
                'name': {
                    'ar': template.name or '',
                    'en': template.name or ''
                },
                'sku': template.default_code or f'ODOO-{template.id}',
                'price': template.list_price or 0,
                'is_published': self.is_published,
                'is_draft': False,
                'is_taxable': True,
                'requires_shipping': template.type == 'product',
            }

            # Add description if available
            if template.description_sale:
                product_data['description'] = {
                    'ar': template.description_sale,
                    'en': template.description_sale
                }
                _logger.info(f"[PREPARE_VARIANT_DATA] Added parent product description")

            # Add parent barcode if available
            if template.barcode:
                product_data['barcode'] = template.barcode
                _logger.info(f"[PREPARE_VARIANT_DATA] Added parent barcode: {template.barcode}")

            # Add parent cost if available
            if template.standard_price:
                product_data['cost'] = template.standard_price
                _logger.info(f"[PREPARE_VARIANT_DATA] Added parent cost: {template.standard_price}")

            # Add parent weight if available
            if template.weight:
                product_data['weight'] = {
                    'value': template.weight,
                    'unit': 'kg'
                }
                _logger.info(f"[PREPARE_VARIANT_DATA] Added parent weight: {template.weight} kg")

            # Add variant as array
            product_data['variants'] = [variant_data]
            _logger.info(f"[PREPARE_VARIANT_DATA] Added variant to parent product data")

            return product_data

    def _update_from_zid_response(self, response):
        """Update variant line from Zid API response"""
        self.ensure_one()

        _logger.info(f"[UPDATE_VARIANT_RESPONSE] Updating variant line from Zid response")

        if not response:
            _logger.warning(f"[UPDATE_VARIANT_RESPONSE] No response data to update")
            return

        # If response contains variants, find our variant
        if 'variants' in response and response['variants']:
            _logger.info(f"[UPDATE_VARIANT_RESPONSE] Response contains {len(response['variants'])} variant(s)")

            # Try to find our variant by SKU or by last created
            our_variant = None
            for variant in response['variants']:
                if variant.get('sku') == (self.zid_sku or self.product_id.default_code):
                    our_variant = variant
                    _logger.info(f"[UPDATE_VARIANT_RESPONSE] Found our variant by SKU match")
                    break

            if not our_variant and len(response['variants']) == 1:
                our_variant = response['variants'][0]
                _logger.info(f"[UPDATE_VARIANT_RESPONSE] Using single variant from response")
            elif not our_variant:
                # Use last variant (likely the newly created one)
                our_variant = response['variants'][-1]
                _logger.info(f"[UPDATE_VARIANT_RESPONSE] Using last variant from response")

            # Create or link zid.variant record
            if our_variant and our_variant.get('id'):
                zid_variant = self.env['zid.variant'].search([
                    ('zid_variant_id', '=', str(our_variant['id'])),
                    ('zid_connector_id', '=', self.zid_connector_id.id)
                ], limit=1)

                if not zid_variant:
                    # Create new zid.variant record
                    _logger.info(f"[UPDATE_VARIANT_RESPONSE] Creating new zid.variant record")

                    # Find parent zid.product
                    parent_zid_product = self.env['zid.product'].search([
                        ('zid_product_id', '=', str(response.get('id'))),
                        ('zid_connector_id', '=', self.zid_connector_id.id)
                    ], limit=1)

                    if not parent_zid_product:
                        # Create parent zid.product if not exists
                        _logger.info(f"[UPDATE_VARIANT_RESPONSE] Creating parent zid.product record")
                        parent_zid_product = self.env['zid.product'].create({
                            'zid_connector_id': self.zid_connector_id.id,
                            'zid_product_id': str(response.get('id')),
                            'name': response.get('name', {}).get('en', 'Unknown Product'),
                            'name_ar': response.get('name', {}).get('ar', ''),
                            'sku': response.get('sku', ''),
                            'price': response.get('price', 0),
                            'is_published': response.get('is_published', False),
                            'product_class': 'simple',
                            'raw_response': json.dumps(response)
                        })

                    zid_variant = self.env['zid.variant'].create({
                        'zid_connector_id': self.zid_connector_id.id,
                        'zid_variant_id': str(our_variant['id']),
                        'parent_product_id': parent_zid_product.id,
                        'sku': our_variant.get('sku', ''),
                        'barcode': our_variant.get('barcode', ''),
                        'price': our_variant.get('price', 0),
                        'sale_price': our_variant.get('sale_price', 0),
                        'cost': our_variant.get('cost', 0),
                        'quantity': our_variant.get('quantity', 0),
                        'is_default': our_variant.get('is_default', False),
                        'raw_data': json.dumps(our_variant)
                    })
                    _logger.info(f"[UPDATE_VARIANT_RESPONSE] Created zid.variant with ID: {zid_variant.zid_variant_id}")

                # Link variant to this line
                self.zid_variant_id = zid_variant
                _logger.info(f"[UPDATE_VARIANT_RESPONSE] Linked zid.variant to variant line")

                # Update other fields
                update_vals = {}

                if our_variant.get('sku'):
                    update_vals['zid_sku'] = our_variant['sku']

                if 'quantity' in our_variant:
                    update_vals['zid_quantity'] = our_variant['quantity']

                if 'price' in our_variant:
                    update_vals['zid_price'] = our_variant['price']

                if update_vals:
                    self.write(update_vals)
                    _logger.info(f"[UPDATE_VARIANT_RESPONSE] Updated variant line with {len(update_vals)} field(s)")

        _logger.info(f"[UPDATE_VARIANT_RESPONSE] Update completed")