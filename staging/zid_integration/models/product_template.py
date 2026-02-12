from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import json
import logging

_logger = logging.getLogger(__name__)


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    # ============== Zid Fields ==============
    # Connection field
    zid_connector_id = fields.Many2one(
        'zid.connector',
        string='Zid Connector',
        help='Select the Zid connector to use for this product'
    )

    # Zid product identification
    zid_product_id = fields.Char(
        string='Zid Product ID',
        readonly=True,
        copy=False,
        help='The unique ID of this product in Zid'
    )

    zid_sku = fields.Char(
        string='Zid SKU',
        readonly=True,
        copy=False,
        help='SKU as stored in Zid'
    )

    zid_barcode = fields.Char(
        string='Zid Barcode',
        readonly=True,
        copy=False
    )

    # Zid URLs and links
    zid_slug = fields.Char(
        string='Zid URL Slug',
        readonly=True,
        copy=False,
        help='URL slug for the product in Zid store'
    )

    zid_html_url = fields.Char(
        string='Zid Product URL',
        readonly=True,
        copy=False,
        help='Full URL to view the product in Zid store'
    )

    # Zid pricing information
    zid_price = fields.Float(
        string='Zid Price',
        readonly=True,
        copy=False
    )

    zid_sale_price = fields.Float(
        string='Zid Sale Price',
        readonly=True,
        copy=False
    )

    zid_formatted_price = fields.Char(
        string='Zid Formatted Price',
        readonly=True,
        copy=False
    )

    zid_formatted_sale_price = fields.Char(
        string='Zid Formatted Sale Price',
        readonly=True,
        copy=False
    )

    zid_currency = fields.Char(
        string='Zid Currency',
        readonly=True,
        copy=False
    )

    zid_currency_symbol = fields.Char(
        string='Zid Currency Symbol',
        readonly=True,
        copy=False
    )

    # Zid stock information
    zid_quantity = fields.Integer(
        string='Zid Quantity',
        readonly=True,
        copy=False
    )

    zid_is_infinite = fields.Boolean(
        string='Zid Infinite Stock',
        readonly=True,
        copy=False
    )

    # Zid status flags
    zid_is_published = fields.Boolean(
        string='Published in Zid',
        readonly=True,
        copy=False
    )

    zid_is_draft = fields.Boolean(
        string='Draft in Zid',
        readonly=True,
        copy=False
    )

    zid_requires_shipping = fields.Boolean(
        string='Zid Requires Shipping',
        readonly=True,
        copy=False
    )

    zid_is_taxable = fields.Boolean(
        string='Zid Is Taxable',
        readonly=True,
        copy=False
    )

    # Zid product structure
    zid_product_class = fields.Char(
        string='Zid Product Class',
        readonly=True,
        copy=False
    )

    zid_structure = fields.Char(
        string='Zid Structure',
        readonly=True,
        copy=False
    )

    # Zid options
    zid_has_options = fields.Boolean(
        string='Has Options in Zid',
        readonly=True,
        copy=False
    )

    zid_has_fields = fields.Boolean(
        string='Has Fields in Zid',
        readonly=True,
        copy=False
    )

    # Zid dates
    zid_created_at = fields.Datetime(
        string='Created in Zid At',
        readonly=True,
        copy=False
    )

    zid_updated_at = fields.Datetime(
        string='Updated in Zid At',
        readonly=True,
        copy=False
    )

    # Zid sync information
    zid_last_sync = fields.Datetime(
        string='Last Zid Sync',
        readonly=True,
        copy=False
    )

    zid_sync_status = fields.Selection([
        ('not_synced', 'Not Synced'),
        ('synced', 'Synced'),
        ('error', 'Sync Error'),
        ('pending', 'Pending Sync')
    ], string='Zid Sync Status', default='not_synced', copy=False)

    # Zid response storage
    zid_response = fields.Text(
        string='Zid API Response',
        readonly=True,
        copy=False,
        help='Last API response from Zid'
    )

    zid_error_message = fields.Text(
        string='Zid Error Message',
        readonly=True,
        copy=False
    )

    # Computed field to check if product exists in Zid
    zid_exists = fields.Boolean(
        string='Exists in Zid',
        compute='_compute_zid_exists',
        store=True
    )

    # ########################## auto syncing #######################
    auto_sync_stock = fields.Boolean(string='Auto Sync Stock to Zid', default=False)
    zid_location_mappings = fields.One2many('zid.location.mapping', 'product_id')


    zid_product_line_ids = fields.One2many('zid.product.line', 'product_template_id')
    zid_variant_mapping_ids = fields.One2many('zid.variant.mapping', 'product_tmpl_id')
    zid_image_ids = fields.One2many('zid.product.image', 'product_tmpl_id', string='Zid Gallery Images')



    last_stock_sync = fields.Datetime(string='Last Stock Sync')
    stock_sync_status = fields.Selection([
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('pending', 'Pending')
    ])

    


    @api.depends('zid_product_id')
    def _compute_zid_exists(self):
        for product in self:
            product.zid_exists = bool(product.zid_product_id)

    def create_in_zid(self):
        """Create this product in Zid"""
        self.ensure_one()

        # Check if connector is selected
        if not self.zid_connector_id:
            raise UserError(_('Please select a Zid connector first.'))

        # Check if connector is connected
        if not self.zid_connector_id.is_connected:
            raise UserError(_('The selected Zid connector is not connected. Please connect it first.'))

        # Check if product already exists in Zid
        if self.zid_product_id:
            raise UserError(_('This product already exists in Zid (ID: %s)') % self.zid_product_id)

        # Prepare product data for Zid
        product_data = self._prepare_zid_product_data()

        try:
            # Make API request to create product via proxy
            response = self.zid_connector_id.api_request(
                endpoint='products/',
                method='POST',
                data=product_data
            )

            # Save response
            self.zid_response = json.dumps(response, indent=2)

            # Update fields with response data
            self._update_from_zid_response(response)

            # Update sync status
            self.write({
                'zid_sync_status': 'synced',
                'zid_last_sync': fields.Datetime.now(),
                'zid_error_message': False
            })

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success!'),
                    'message': _('Product created successfully in Zid. ID: %s') % self.zid_product_id,
                    'type': 'success',
                    'sticky': False,
                }
            }

        except Exception as e:
            _logger.error(f"Failed to create product in Zid: {str(e)}")
            self.write({
                'zid_sync_status': 'error',
                'zid_error_message': str(e)
            })
            raise UserError(_('Failed to create product in Zid: %s') % str(e))

    def get_zid_locations(self):
        """Get available locations from Zid"""
        self.ensure_one()

        if not self.zid_connector_id or not self.zid_connector_id.is_connected:
            return []

        try:
            response = self.zid_connector_id.api_request(
                endpoint='inventories/locations',
                method='GET'
            )
            return response.get('locations', []) if response else []
        except Exception as e:
            _logger.error(f"Failed to get Zid locations: {str(e)}")
            return []

    def _prepare_zid_product_data(self):
        """Prepare product data for Zid API"""
        self.ensure_one()

        # Basic product data
        data = {
            'name': {
                'ar': self.name or '',
                'en': self.name or ''
            },
            'sku': self.default_code or f'ODOO-{self.id}',
            'price': self.list_price or 0,
            'is_published': True,
            'is_draft': False,
            'is_taxable': True,
            'requires_shipping': self.type == 'product',
        }

        # Add description if available
        if self.description_sale:
            data['description'] = {
                'ar': self.description_sale,
                'en': self.description_sale
            }

        # Add barcode if available
        if self.barcode:
            data['barcode'] = self.barcode

        # Add cost if available
        if self.standard_price:
            data['cost'] = self.standard_price

        # Add weight if available
        if self.weight:
            data['weight'] = {
                'value': self.weight,
                'unit': 'kg'
            }

        # Try to get locations from Zid
        locations = self.get_zid_locations()

        # Add stock information only if we have valid locations
        if locations:
            location_id = locations[0].get('id') if locations else None

            if location_id:
                if self.type == 'product':
                    qty_available = self.qty_available if hasattr(self, 'qty_available') else 0
                    data['stocks'] = [{
                        'available_quantity': int(qty_available),
                        'is_infinite': False,
                        'location': location_id
                    }]
                else:
                    data['stocks'] = [{
                        'available_quantity': 0,
                        'is_infinite': True,
                        'location': location_id
                    }]
        # If no locations found, skip stocks - product will be created without stock

        return data

    def get_default_zid_location(self):
        """Get default Zid location for this product"""
        self.ensure_one()

        if not self.zid_connector_id:
            return False

        # Try default location first
        if self.zid_connector_id.default_location_id:
            return self.zid_connector_id.default_location_id

        # Get first enabled location
        location = self.env['zid.location'].search([
            ('zid_connector_id', '=', self.zid_connector_id.id),
            ('is_enabled', '=', True)
        ], limit=1)

        return location

    def _update_from_zid_response(self, response):
        """Update product fields from Zid API response"""
        self.ensure_one()

        if not response:
            return

        update_vals = {
            'zid_product_id': response.get('id'),
            'zid_sku': response.get('sku'),
            'zid_barcode': response.get('barcode'),
            'zid_slug': response.get('slug'),
            'zid_html_url': response.get('html_url'),
            'zid_price': response.get('price', 0),
            'zid_sale_price': response.get('sale_price'),
            'zid_formatted_price': response.get('formatted_price'),
            'zid_formatted_sale_price': response.get('formatted_sale_price'),
            'zid_currency': response.get('currency'),
            'zid_currency_symbol': response.get('currency_symbol'),
            'zid_quantity': response.get('quantity', 0),
            'zid_is_infinite': response.get('is_infinite', False),
            'zid_is_published': response.get('is_published', False),
            'zid_is_draft': response.get('is_draft', False),
            'zid_requires_shipping': response.get('requires_shipping', False),
            'zid_is_taxable': response.get('is_taxable', False),
            'zid_product_class': response.get('product_class'),
            'zid_structure': response.get('structure'),
            'zid_has_options': response.get('has_options', False),
            'zid_has_fields': response.get('has_fields', False),
        }

        # Handle dates - parse ISO format properly
        from datetime import datetime

        if response.get('created_at'):
            try:
                # Try to parse ISO format with Z timezone
                date_str = response.get('created_at')
                if date_str.endswith('Z'):
                    date_str = date_str[:-1] + '+00:00'
                # Parse the date string
                if '.' in date_str:
                    # Remove microseconds if present
                    date_str = date_str.split('.')[0] + '+00:00'
                parsed_date = datetime.fromisoformat(date_str.replace('+00:00', ''))
                update_vals['zid_created_at'] = parsed_date
            except Exception as e:
                _logger.warning(f"Could not parse created_at date: {response.get('created_at')} - {str(e)}")

        if response.get('updated_at'):
            try:
                # Try to parse ISO format with Z timezone
                date_str = response.get('updated_at')
                if date_str.endswith('Z'):
                    date_str = date_str[:-1] + '+00:00'
                # Parse the date string
                if '.' in date_str:
                    # Remove microseconds if present
                    date_str = date_str.split('.')[0] + '+00:00'
                parsed_date = datetime.fromisoformat(date_str.replace('+00:00', ''))
                update_vals['zid_updated_at'] = parsed_date
            except Exception as e:
                _logger.warning(f"Could not parse updated_at date: {response.get('updated_at')} - {str(e)}")

        self.write(update_vals)




    def sync_from_zid(self):
        """Sync product data from Zid"""
        self.ensure_one()

        if not self.zid_product_id:
            raise UserError(_('This product does not exist in Zid yet. Please create it first.'))

        if not self.zid_connector_id:
            raise UserError(_('Please select a Zid connector first.'))

        if not self.zid_connector_id.is_connected:
            raise UserError(_('The selected Zid connector is not connected.'))

        try:
            # Get product from Zid
            response = self.zid_connector_id.api_request(
                endpoint=f'products/{self.zid_product_id}',
                method='GET'
            )

            # Save response
            self.zid_response = json.dumps(response, indent=2)

            # Update fields
            self._update_from_zid_response(response)

            # Update sync status
            self.write({
                'zid_sync_status': 'synced',
                'zid_last_sync': fields.Datetime.now(),
                'zid_error_message': False
            })

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success!'),
                    'message': _('Product synced successfully from Zid'),
                    'type': 'success',
                    'sticky': False,
                }
            }

        except Exception as e:
            _logger.error(f"Failed to sync product from Zid: {str(e)}")
            self.write({
                'zid_sync_status': 'error',
                'zid_error_message': str(e)
            })
            raise UserError(_('Failed to sync product from Zid: %s') % str(e))

    def action_open_update_wizard(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("zid_integration.action_zid_product_update_wizard")
        # action['res_id'] = self.id
        return action



    def update_in_zid(self):
        """Update product in Zid with current Odoo data"""
        self.ensure_one()

        if not self.zid_product_id:
            raise UserError(_('This product does not exist in Zid yet. Please create it first.'))

        if not self.zid_connector_id:
            raise UserError(_('Please select a Zid connector first.'))

        if not self.zid_connector_id.is_connected:
            raise UserError(_('The selected Zid connector is not connected.'))

        # Prepare update data
        update_data = self._prepare_zid_product_data()

        try:
            # Update product in Zid
            response = self.zid_connector_id.api_request(
                endpoint=f'products/{self.zid_product_id}',
                method='PUT',
                data=update_data
            )

            # Save response
            self.zid_response = json.dumps(response, indent=2)

            # Update fields
            self._update_from_zid_response(response)

            # Update sync status
            self.write({
                'zid_sync_status': 'synced',
                'zid_last_sync': fields.Datetime.now(),
                'zid_error_message': False
            })

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success!'),
                    'message': _('Product updated successfully in Zid'),
                    'type': 'success',
                    'sticky': False,
                }
            }

        except Exception as e:
            _logger.error(f"Failed to update product in Zid: {str(e)}")
            self.write({
                'zid_sync_status': 'error',
                'zid_error_message': str(e)
            })
            raise UserError(_('Failed to update product in Zid: %s') % str(e))

    def update_stock_in_zid(self, location_id, quantity):
        """Legacy method - Update stock for a specific location in Zid"""
        self.ensure_one()

        if not self.zid_product_id:
            raise UserError(_('This product does not exist in Zid yet.'))

        if not self.zid_connector_id or not self.zid_connector_id.is_connected:
            raise UserError(_('Zid connector is not connected.'))

        try:
            # Prepare stock update data
            update_data = {
                'stocks': [{
                    'available_quantity': int(quantity),
                    'is_infinite': False,
                    'location': location_id
                }]
            }
            
            _logger.info(f"Updating stock for product {self.name} (ID: {self.zid_product_id})")
            _logger.info(f"Location ID: {location_id}, Quantity: {int(quantity)}")
            _logger.info(f"Update data: {update_data}")

            # Call API with PATCH
            response = self.zid_connector_id.api_request(
                endpoint=f'products/{self.zid_product_id}/',
                method='PATCH',
                data=update_data
            )
            
            _logger.info(f"Stock update response received for {self.name}")

            return response

        except Exception as e:
            _logger.error(f"Failed to update stock in Zid: {str(e)}")
            raise UserError(_('Failed to update stock in Zid: %s') % str(e))
    
    def create_in_all_zid_stores(self):
        """Create product in all configured Zid stores"""
        self.ensure_one()
        
        if not self.zid_product_line_ids:
            raise UserError(_('No Zid product lines configured. Please add product lines first.'))
        
        success_count = 0
        error_messages = []
        created_stores = []
        
        for line in self.zid_product_line_ids:
            try:
                # Skip lines that already have Zid product ID
                if line.zid_product_id:
                    error_messages.append(f"{line.store_name}: Product already exists (ID: {line.zid_product_id})")
                    continue
                
                # Create product in Zid
                line.create_in_zid()
                success_count += 1
                created_stores.append(line.store_name)
                
            except Exception as e:
                error_messages.append(f"{line.store_name}: {str(e)}")
        
        # Prepare result message
        message = ""
        if success_count > 0:
            message = f"Successfully created product in {success_count} store(s): {', '.join(created_stores)}"
        
        if error_messages:
            if message:
                message += "\n\n"
            message += "Issues:\n" + "\n".join(error_messages)
        
        if success_count == 0 and not error_messages:
            message = "No stores to create products in."
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Create Products Result'),
                'message': _(message),
                'type': 'success' if success_count > 0 else 'warning',
                'sticky': bool(error_messages),
            }
        }
    
    def sync_all_stock_to_zid(self):
        """Sync stock for all product lines to their respective Zid stores"""
        self.ensure_one()
        
        if not self.zid_product_line_ids:
            raise UserError(_('No Zid product lines configured for this product'))
        
        success_count = 0
        error_messages = []
        
        for line in self.zid_product_line_ids:
            try:
                # Skip lines without Zid product ID
                if not line.zid_product_id:
                    error_messages.append(f"Line for {line.store_name} has no Zid product ID")
                    continue
                
                # Get the Odoo location
                odoo_location = self.env['stock.location'].search([
                    ('zid_location_id.zid_location_id', '=', line.zid_location_id.zid_location_id)
                ], limit=1)
                
                if not odoo_location:
                    error_messages.append(f"No Odoo location found for {line.zid_location_id.display_name}")
                    continue
                
                # Calculate quantity
                quants = self.env['stock.quant'].search([
                    ('product_id.product_tmpl_id', '=', self.id),
                    ('location_id', '=', odoo_location.id)
                ])
                
                total_qty = sum(quants.mapped('quantity'))
                
                # Sync using the product line
                self.env['stock.quant']._sync_stock_to_zid_for_line(line, total_qty)
                
                success_count += 1
                
            except Exception as e:
                error_messages.append(f"Failed for {line.store_name}: {str(e)}")
        
        # Prepare result message
        message = f"Successfully synced {success_count} out of {len(self.zid_product_line_ids)} stores."
        if error_messages:
            message += "\n\nErrors:\n" + "\n".join(error_messages)
        
        if success_count == 0:
            raise UserError(_(message))
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Stock Sync Result'),
                'message': _(message),
                'type': 'success' if success_count == len(self.zid_product_line_ids) else 'warning',
                'sticky': bool(error_messages),
            }
        }
