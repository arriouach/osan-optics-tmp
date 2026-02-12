from odoo import models, fields, api, _
from datetime import datetime, date, timedelta
from odoo.exceptions import ValidationError, UserError
from dateutil import relativedelta
import logging
import json
import traceback

_logger = logging.getLogger(__name__)


class ZidVariantMapping(models.Model):
    _name = 'zid.variant.mapping'
    _description = 'Zid Variant Mapping'
    _log_access = True
    _inherit = ['mail.thread', 'mail.activity.mixin']

    zid_connector_id = fields.Many2one(
        'zid.connector',
        string='Store',
        required=True,
        domain=[('authorization_status', '=', 'connected')],
        help='Select the Zid store for this product'
    )
    product_tmpl_id = fields.Many2one('product.template', string = 'Odoo Template', ondelete='cascade')
    zid_tmpl_id = fields.Many2one('zid.product', string = 'Zid Template', ondelete='cascade')

    odoo_variant_id = fields.Many2one('product.product', string = 'Odoo Product', ondelete='cascade')
    zid_variant_id = fields.Many2one('zid.variant', string = 'Zid Product', ondelete='cascade')

    def action_sync_stock(self):
        """Sync stock from Odoo to Zid for selected mapping(s)"""
        _logger.info("=" * 80)
        _logger.info("[SYNC_STOCK_MAPPING] Starting stock sync for mapping records")
        _logger.info(f"[SYNC_STOCK_MAPPING] Number of records to sync: {len(self)}")

        success_count = 0
        failed_count = 0
        error_messages = []

        for mapping in self:
            _logger.info("-" * 60)
            _logger.info(f"[SYNC_STOCK_MAPPING] Processing mapping ID: {mapping.id}")

            try:
                # Step 1: Check prerequisites
                _logger.info(f"[SYNC_STOCK_MAPPING] Step 1: Checking prerequisites for mapping ID: {mapping.id}")

                if not mapping.odoo_variant_id:
                    _logger.error(f"[SYNC_STOCK_MAPPING] No Odoo variant linked to mapping ID: {mapping.id}")
                    raise ValidationError(
                        _('No Odoo variant linked to this mapping. Please set the Odoo Product first.'))

                if not mapping.zid_variant_id:
                    _logger.error(f"[SYNC_STOCK_MAPPING] No Zid variant linked to mapping ID: {mapping.id}")
                    raise ValidationError(_('No Zid variant linked to this mapping.'))

                if not mapping.zid_connector_id:
                    _logger.error(f"[SYNC_STOCK_MAPPING] No Zid connector configured for mapping ID: {mapping.id}")
                    raise ValidationError(_('No Zid connector configured for this mapping.'))

                if not mapping.zid_connector_id.is_connected:
                    _logger.error(
                        f"[SYNC_STOCK_MAPPING] Store {mapping.zid_connector_id.store_name} is not connected for mapping ID: {mapping.id}")
                    raise ValidationError(_(f'Store {mapping.zid_connector_id.store_name} is not connected'))

                _logger.info(f"[SYNC_STOCK_MAPPING] Prerequisites check passed for mapping ID: {mapping.id}")

                odoo_variant = mapping.odoo_variant_id
                zid_variant = mapping.zid_variant_id
                connector = mapping.zid_connector_id

                _logger.info(f"[SYNC_STOCK_MAPPING] Odoo Variant: {odoo_variant.display_name} (ID: {odoo_variant.id})")
                _logger.info(
                    f"[SYNC_STOCK_MAPPING] Zid Variant: {zid_variant.display_name} (ID: {zid_variant.zid_variant_id})")
                _logger.info(f"[SYNC_STOCK_MAPPING] Store: {connector.store_name}")

                # Step 2: Get all stock locations for this Odoo variant
                _logger.info(f"[SYNC_STOCK_MAPPING] Step 2: Getting stock quantities for all locations...")

                # Get all quants for this product
                _logger.info(f"[SYNC_STOCK_MAPPING] Searching for stock quants for product ID: {odoo_variant.id}")
                quants = self.env['stock.quant'].search([
                    ('product_id', '=', odoo_variant.id),
                    ('location_id.usage', 'in', ['internal', 'transit'])
                ])

                _logger.info(f"[SYNC_STOCK_MAPPING] Found {len(quants)} stock quant(s)")

                # Log each quant found
                for idx, quant in enumerate(quants):
                    _logger.info(
                        f"[SYNC_STOCK_MAPPING] Quant {idx + 1}: Location='{quant.location_id.complete_name}', Quantity={quant.quantity}, Reserved={quant.reserved_quantity}")

                # Step 3: Group quantities by Zid location
                _logger.info(f"[SYNC_STOCK_MAPPING] Step 3: Grouping quantities by Zid location...")
                location_stocks = {}

                for quant in quants:
                    odoo_location = quant.location_id
                    _logger.info(f"[SYNC_STOCK_MAPPING] Processing quant for location: {odoo_location.complete_name}")

                    # Check if this Odoo location has a linked Zid location
                    if odoo_location.zid_location_id:
                        _logger.info(
                            f"[SYNC_STOCK_MAPPING] Found linked Zid location: {odoo_location.zid_location_id.name_ar}")

                        if odoo_location.zid_location_id.zid_location_id:
                            _logger.info(
                                f"[SYNC_STOCK_MAPPING] Zid location ID: {odoo_location.zid_location_id.zid_location_id}")

                            # Make sure it's for the same connector
                            if odoo_location.zid_location_id.zid_connector_id.id == connector.id:
                                _logger.info(
                                    f"[SYNC_STOCK_MAPPING] Connector match confirmed for location: {odoo_location.complete_name}")

                                zid_location_id = odoo_location.zid_location_id.zid_location_id

                                if zid_location_id not in location_stocks:
                                    location_stocks[zid_location_id] = {
                                        'quantity': 0,
                                        'location_name': odoo_location.zid_location_id.name_ar or odoo_location.name,
                                        'odoo_location': odoo_location
                                    }
                                    _logger.info(
                                        f"[SYNC_STOCK_MAPPING] Initialized location stock for Zid location ID: {zid_location_id}")

                                location_stocks[zid_location_id]['quantity'] += quant.quantity

                                _logger.info(f"[SYNC_STOCK_MAPPING] Location '{odoo_location.complete_name}' "
                                             f"-> Zid location '{location_stocks[zid_location_id]['location_name']}': "
                                             f"+{quant.quantity} (Total: {location_stocks[zid_location_id]['quantity']})")
                            else:
                                _logger.debug(
                                    f"[SYNC_STOCK_MAPPING] Skipping location {odoo_location.complete_name} - different connector (Expected: {connector.id}, Found: {odoo_location.zid_location_id.zid_connector_id.id})")
                        else:
                            _logger.debug(
                                f"[SYNC_STOCK_MAPPING] Skipping location {odoo_location.complete_name} - no Zid location ID set")
                    else:
                        _logger.debug(
                            f"[SYNC_STOCK_MAPPING] Skipping location {odoo_location.complete_name} - no Zid location linked")

                _logger.info(f"[SYNC_STOCK_MAPPING] Location stocks summary: {len(location_stocks)} locations found")
                for zid_loc_id, stock_info in location_stocks.items():
                    _logger.info(
                        f"[SYNC_STOCK_MAPPING] - Zid Location {zid_loc_id} ({stock_info['location_name']}): {stock_info['quantity']} units")

                if not location_stocks:
                    _logger.warning(f"[SYNC_STOCK_MAPPING] No stock locations found with Zid mapping for this product")
                    # Continue without raising error - product might have 0 stock

                # Step 4: Prepare stock data for Zid API
                _logger.info(f"[SYNC_STOCK_MAPPING] Step 4: Preparing stock data for Zid API...")
                stocks_data = []

                for zid_loc_id, stock_info in location_stocks.items():
                    stock_entry = {
                        'location': zid_loc_id,
                        'available_quantity': int(stock_info['quantity']),
                        'is_infinite': False
                    }
                    stocks_data.append(stock_entry)
                    _logger.info(
                        f"[SYNC_STOCK_MAPPING] Preparing to sync: Location {zid_loc_id} ({stock_info['location_name']}) = {int(stock_info['quantity'])} units")

                # If no stocks found, add at least one location with 0 quantity
                if not stocks_data:
                    _logger.info(
                        f"[SYNC_STOCK_MAPPING] No location stocks found, searching for default Zid location...")

                    # Try to get the first Zid location for this connector
                    zid_location = self.env['zid.location'].search([
                        ('zid_connector_id', '=', connector.id)
                    ], limit=1)

                    if zid_location:
                        stock_entry = {
                            'location': zid_location.zid_location_id,
                            'available_quantity': 0,
                            'is_infinite': False
                        }
                        stocks_data.append(stock_entry)
                        _logger.info(
                            f"[SYNC_STOCK_MAPPING] No stock found, setting {zid_location.name_ar} (ID: {zid_location.zid_location_id}) to 0")
                    else:
                        _logger.warning(f"[SYNC_STOCK_MAPPING] No Zid locations found for connector {connector.id}")

                _logger.info(f"[SYNC_STOCK_MAPPING] Final stocks_data: {len(stocks_data)} entries prepared")

                # Step 5: Get parent product ID (needed for API call)
                _logger.info(f"[SYNC_STOCK_MAPPING] Step 5: Getting parent product information...")

                parent_product = zid_variant.parent_product_id
                if not parent_product:
                    _logger.error(f"[SYNC_STOCK_MAPPING] Zid variant {zid_variant.id} has no parent product linked")
                    raise ValidationError(_('Zid variant has no parent product linked'))

                zid_product_id = parent_product.zid_product_id
                _logger.info(f"[SYNC_STOCK_MAPPING] Parent Zid Product ID: {zid_product_id}")
                _logger.info(f"[SYNC_STOCK_MAPPING] Parent Product Name: {parent_product.display_name}")

                # Step 6: Update stock in Zid using variant approach
                _logger.info(f"[SYNC_STOCK_MAPPING] Step 6: Updating stock in Zid...")
                _logger.info(f"[SYNC_STOCK_MAPPING] Sending stock update to Zid API for product ID: {zid_product_id}")

                # Prepare update data using variant structure
                update_data = {
                    'variants': [
                        {
                            'id': zid_variant.zid_variant_id,
                            'stocks': stocks_data
                        }
                    ]
                }

                _logger.info(f"[SYNC_STOCK_MAPPING] Update data: {json.dumps(update_data, indent=2)}")

                # Make API request using PATCH with variant structure
                _logger.info(f"[SYNC_STOCK_MAPPING] Making API request to endpoint: products/{zid_product_id}/")
                _logger.info(f"[SYNC_STOCK_MAPPING] Request method: PATCH")

                response = connector.api_request(
                    endpoint=f'products/{zid_product_id}/',
                    method='PATCH',
                    data=update_data
                )

                _logger.info(f"[SYNC_STOCK_MAPPING] API Response received: {response}")
                _logger.info(f"[SYNC_STOCK_MAPPING] Successfully synced stock for mapping ID: {mapping.id}")
                success_count += 1

                # Step 7: Update variant record with new quantities
                _logger.info(f"[SYNC_STOCK_MAPPING] Step 7: Updating variant record with new quantities...")

                total_quantity = sum([stock['available_quantity'] for stock in stocks_data])
                _logger.info(f"[SYNC_STOCK_MAPPING] Calculated total quantity: {total_quantity}")

                zid_variant.write({
                    'quantity': total_quantity,
                    'last_sync_date': fields.Datetime.now()
                })
                _logger.info(
                    f"[SYNC_STOCK_MAPPING] Updated zid_variant {zid_variant.id} with quantity: {total_quantity}")

                # Step 8: Create/update stock lines in zid.variant.stock.line
                _logger.info(f"[SYNC_STOCK_MAPPING] Step 8: Creating/updating stock lines...")

                for stock_data in stocks_data:
                    _logger.info(f"[SYNC_STOCK_MAPPING] Processing stock line for location {stock_data['location']}")

                    stock_line = self.env['zid.variant.stock.line'].search([
                        ('variant_id', '=', zid_variant.id),
                        ('location_id.zid_location_id', '=', stock_data['location'])
                    ], limit=1)

                    if stock_line:
                        _logger.info(f"[SYNC_STOCK_MAPPING] Found existing stock line ID: {stock_line.id}")
                        stock_line.write({
                            'available_quantity': stock_data['available_quantity'],
                            'last_update': fields.Datetime.now()
                        })
                        _logger.info(
                            f"[SYNC_STOCK_MAPPING] Updated stock line for location {stock_line.location_id.name_ar} with quantity: {stock_data['available_quantity']}")
                    else:
                        _logger.info(f"[SYNC_STOCK_MAPPING] No existing stock line found, creating new one...")

                        # Find the zid.location record
                        zid_location_rec = self.env['zid.location'].search([
                            ('zid_location_id', '=', stock_data['location']),
                            ('zid_connector_id', '=', connector.id)
                        ], limit=1)

                        if zid_location_rec:
                            _logger.info(f"[SYNC_STOCK_MAPPING] Found zid.location record ID: {zid_location_rec.id}")

                            new_stock_line = self.env['zid.variant.stock.line'].create({
                                'variant_id': zid_variant.id,
                                'location_id': zid_location_rec.id,
                                'available_quantity': stock_data['available_quantity'],
                                'is_infinite': stock_data.get('is_infinite', False),
                                'last_update': fields.Datetime.now()
                            })
                            _logger.info(
                                f"[SYNC_STOCK_MAPPING] Created stock line ID: {new_stock_line.id} for location {zid_location_rec.name_ar} with quantity: {stock_data['available_quantity']}")
                        else:
                            _logger.warning(
                                f"[SYNC_STOCK_MAPPING] Could not find zid.location record for location ID: {stock_data['location']} and connector ID: {connector.id}")

                _logger.info(f"[SYNC_STOCK_MAPPING] Completed processing mapping ID: {mapping.id} successfully")

            except Exception as e:
                failed_count += 1
                error_msg = f"Mapping ID {mapping.id}: {str(e)}"
                error_messages.append(error_msg)
                _logger.error(f"[SYNC_STOCK_MAPPING] Failed to sync stock for mapping ID: {mapping.id}")
                _logger.error(f"[SYNC_STOCK_MAPPING] Error message: {str(e)}")
                _logger.error(f"[SYNC_STOCK_MAPPING] Traceback:\n{traceback.format_exc()}")
                continue

        _logger.info("=" * 80)
        _logger.info(f"[SYNC_STOCK_MAPPING] Sync process completed")
        _logger.info(f"[SYNC_STOCK_MAPPING] Total mappings processed: {len(self)}")
        _logger.info(f"[SYNC_STOCK_MAPPING] Successful syncs: {success_count}")
        _logger.info(f"[SYNC_STOCK_MAPPING] Failed syncs: {failed_count}")

        # Show result message
        if failed_count > 0:
            _logger.error(f"[SYNC_STOCK_MAPPING] Sync completed with errors")
            error_detail = '\n'.join(error_messages)
            _logger.error(f"[SYNC_STOCK_MAPPING] Error details:\n{error_detail}")

            raise UserError(_(f'Stock sync completed with errors:\n'
                              f'Success: {success_count}\n'
                              f'Failed: {failed_count}\n\n'
                              f'Errors:\n{error_detail}'))
        else:
            _logger.info(f"[SYNC_STOCK_MAPPING] All syncs completed successfully!")

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success!'),
                    'message': _(f'Stock synced successfully for {success_count} mapping(s)'),
                    'type': 'success',
                    'sticky': False,
                }
            }


    def create_in_zid(self):
        """Create the Odoo variant in Zid (for new products not yet in Zid)"""
        _logger.info("=" * 80)
        _logger.info("[CREATE_IN_ZID_MAPPING] Starting to create variants in Zid")
        _logger.info(f"[CREATE_IN_ZID_MAPPING] Number of mappings to process: {len(self)}")
        
        success_count = 0
        failed_count = 0
        error_messages = []
        
        for mapping in self:
            _logger.info("-" * 60)
            _logger.info(f"[CREATE_IN_ZID_MAPPING] Processing mapping ID: {mapping.id}")
            
            try:
                # Check prerequisites
                if not mapping.odoo_variant_id:
                    raise ValidationError(_('No Odoo variant linked to this mapping. Please set the Odoo Product first.'))
                
                if not mapping.product_tmpl_id:
                    raise ValidationError(_('No Odoo product template linked to this mapping.'))
                
                if not mapping.zid_connector_id:
                    raise ValidationError(_('No Zid connector configured for this mapping.'))
                
                if not mapping.zid_connector_id.is_connected:
                    raise ValidationError(_(f'Store {mapping.zid_connector_id.store_name} is not connected'))
                
                # For now, this is a placeholder - actual implementation would need to:
                # 1. Check if parent product exists in Zid
                # 2. If not, create the parent product first
                # 3. Then add this variant to it
                # 4. Update the mapping with the created Zid variant
                
                _logger.warning(f"[CREATE_IN_ZID_MAPPING] Create in Zid not fully implemented yet for mapping ID: {mapping.id}")
                raise UserError(_('Create in Zid functionality is not yet fully implemented. Please create the product in Zid first, then use "Get Variants" to fetch and map them.'))
                
            except Exception as e:
                failed_count += 1
                error_msg = f"Mapping ID {mapping.id}: {str(e)}"
                error_messages.append(error_msg)
                _logger.error(f"[CREATE_IN_ZID_MAPPING] Failed: {str(e)}")
                continue
        
        _logger.info("=" * 80)
        
        if failed_count > 0:
            error_detail = '\n'.join(error_messages)
            raise UserError(_(f'Create in Zid completed with errors:\n'
                            f'Success: {success_count}\n'
                            f'Failed: {failed_count}\n\n'
                            f'Errors:\n{error_detail}'))
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success!'),
                    'message': _(f'Created {success_count} variant(s) in Zid successfully'),
                    'type': 'success',
                    'sticky': False,
                }
            }


