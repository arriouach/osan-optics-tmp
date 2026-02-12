# -*- coding: utf-8 -*-

from odoo import models, fields, api
from datetime import timedelta
import logging

_logger = logging.getLogger(__name__)


class ZidDiagnostic(models.TransientModel):
    _name = 'zid.diagnostic'
    _description = 'Zid Integration Diagnostic Tool'

    connector_id = fields.Many2one('zid.connector', string='Zid Connector', required=True)
    
    def diagnose_product_mappings(self):
        """Diagnose product mapping issues"""
        connector = self.connector_id
        
        # Check Zid Products
        zid_products = self.env['zid.product'].search([('zid_connector_id', '=', connector.id)])
        mapped_products = zid_products.filtered('odoo_product_id')
        unmapped_products = zid_products.filtered(lambda p: not p.odoo_product_id)
        
        # Check Zid Variants
        zid_variants = self.env['zid.variant'].search([('zid_connector_id', '=', connector.id)])
        mapped_variants = zid_variants.filtered('odoo_product_id')
        unmapped_variants = zid_variants.filtered(lambda v: not v.odoo_product_id)
        
        # Check Odoo Products (simplified - no company filter)
        odoo_products = self.env['product.product'].search([])
        products_with_sku = odoo_products.filtered('default_code')
        products_with_barcode = odoo_products.filtered('barcode')
        
        report = f"""
=== ZID PRODUCT MAPPING DIAGNOSTIC ===
Connector: {connector.name}
Product Match Priority: {connector.product_match_priority}
Product Match Method: {connector.product_match_by}

ZID PRODUCTS:
- Total Zid Products: {len(zid_products)}
- Mapped to Odoo: {len(mapped_products)}
- Unmapped: {len(unmapped_products)}

ZID VARIANTS:
- Total Zid Variants: {len(zid_variants)}
- Mapped to Odoo: {len(mapped_variants)}
- Unmapped: {len(unmapped_variants)}

ODOO PRODUCTS:
- Total Odoo Products: {len(odoo_products)}
- Products with SKU: {len(products_with_sku)}
- Products with Barcode: {len(products_with_barcode)}

MATCHING STRATEGY ANALYSIS:
"""
        
        if connector.product_match_priority == 'mapping_first':
            report += "✓ Using Zid mappings first, then SKU/Barcode fallback (Recommended)\n"
        elif connector.product_match_priority == 'direct_only':
            report += "⚠ Using SKU/Barcode only - Zid mappings will be ignored\n"
        elif connector.product_match_priority == 'mapping_only':
            report += "⚠ Using Zid mappings only - No SKU/Barcode fallback\n"
        
        if connector.product_match_priority in ['mapping_first', 'mapping_only'] and len(unmapped_products) > 0:
            report += f"⚠ WARNING: {len(unmapped_products)} Zid products are not mapped to Odoo products\n"
        
        if connector.product_match_priority in ['mapping_first', 'direct_only']:
            if connector.product_match_by == 'sku' and len(products_with_sku) == 0:
                report += "⚠ WARNING: Match method is SKU but no Odoo products have SKU set\n"
            elif connector.product_match_by == 'barcode' and len(products_with_barcode) == 0:
                report += "⚠ WARNING: Match method is Barcode but no Odoo products have Barcode set\n"

        report += "\nUNMAPPED ZID PRODUCTS:\n"
        
        for product in unmapped_products[:10]:  # Show first 10
            report += f"- ID: {product.zid_product_id}, Name: {product.name}, SKU: {product.sku}\n"
        
        if len(unmapped_products) > 10:
            report += f"... and {len(unmapped_products) - 10} more\n"
        
        report += "\nUNMAPPED ZID VARIANTS:\n"
        for variant in unmapped_variants[:10]:  # Show first 10
            report += f"- ID: {variant.zid_variant_id}, Name: {variant.name}, SKU: {variant.sku}\n"
        
        if len(unmapped_variants) > 10:
            report += f"... and {len(unmapped_variants) - 10} more\n"
        
        _logger.info(report)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Diagnostic Complete',
                'message': f'Found {len(unmapped_products)} unmapped products and {len(unmapped_variants)} unmapped variants. Check logs for details.',
                'type': 'info',
                'sticky': True,
            }
        }
    
    def diagnose_recent_orders(self):
        """Diagnose recent order processing issues"""
        connector = self.connector_id
        
        # Get recent Zid orders
        recent_orders = self.env['zid.sale.order'].search([
            ('zid_connector_id', '=', connector.id),
            ('create_date', '>=', fields.Datetime.now() - timedelta(days=7))
        ], order='create_date desc', limit=10)
        
        report = f"""
=== RECENT ORDER DIAGNOSTIC ===
Connector: {connector.name}
Automation Settings:
- Auto-Confirm Orders: {connector.auto_confirm_orders}
- Auto-Create Invoice: {connector.auto_create_invoice}
- Auto-Confirm Invoice: {connector.auto_confirm_invoice}
- Auto-Validate Delivery: {connector.auto_validate_delivery}

Sales Team Configuration:
- Default Salesperson: {connector.default_user_id.name if connector.default_user_id else 'Not Set'}
- Default Sales Team: {connector.default_team_id.name if connector.default_team_id else 'Not Set'}

RECENT ORDERS (Last 7 days):
"""
        
        for order in recent_orders:
            sale_order = order.sale_order_id
            line_count = len(sale_order.order_line) if sale_order else 0
            salesperson = sale_order.user_id.name if sale_order and sale_order.user_id else 'Not Set'
            sales_team = sale_order.team_id.name if sale_order and sale_order.team_id else 'Not Set'
            
            report += f"""
Order: {order.zid_order_id} ({order.order_code})
- Zid Order ID: {order.zid_order_id}
- Status: {order.order_status}
- Sale Order: {'Yes' if sale_order else 'No'}
- Order Lines: {line_count}
- Salesperson: {salesperson}
- Sales Team: {sales_team}
- Total: {order.total_amount}
"""
        
        _logger.info(report)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Order Diagnostic Complete',
                'message': f'Analyzed {len(recent_orders)} recent orders. Check logs for details.',
                'type': 'info',
                'sticky': True,
            }
        }
    
    def diagnose_automation_settings(self):
        """Diagnose automation configuration and potential issues"""
        connector = self.connector_id
        
        report = f"""
=== AUTOMATION SETTINGS DIAGNOSTIC ===
Connector: {connector.name}

CURRENT AUTOMATION SETTINGS:
- Auto-Confirm Orders: {'✓ Enabled' if connector.auto_confirm_orders else '✗ Disabled'}
- Auto-Create Invoice: {'✓ Enabled' if connector.auto_create_invoice else '✗ Disabled'}
- Auto-Confirm Invoice: {'✓ Enabled' if connector.auto_confirm_invoice else '✗ Disabled'}
- Auto-Validate Delivery: {'✓ Enabled' if connector.auto_validate_delivery else '✗ Disabled'}

AUTOMATION FLOW ANALYSIS:
"""
        
        if connector.auto_confirm_orders:
            report += "1. ✓ Orders will be automatically confirmed\n"
            
            if connector.auto_create_invoice:
                report += "2. ✓ Invoices will be automatically created\n"
                
                if connector.auto_confirm_invoice:
                    report += "3. ✓ Invoices will be automatically confirmed\n"
                else:
                    report += "3. ⚠ Invoices will be created but NOT confirmed (manual step required)\n"
            else:
                report += "2. ⚠ Invoices will NOT be created automatically\n"
                
            if connector.auto_validate_delivery:
                report += "4. ✓ Deliveries will be automatically validated (if stock available)\n"
            else:
                report += "4. ⚠ Deliveries will NOT be validated automatically\n"
        else:
            report += "1. ⚠ Orders will remain in draft state (manual confirmation required)\n"
            report += "   → Invoice and delivery automation will not trigger\n"
        
        # Check for potential issues
        report += "\nPOTENTIAL ISSUES:\n"
        
        _logger.info(report)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Automation Diagnostic Complete',
                'message': 'Automation settings analyzed. Check logs for details.',
                'type': 'info',
                'sticky': True,
            }
        }
    
    def test_pos_order_fetch(self):
        """Test fetching POS order details to debug missing products issue"""
        connector = self.connector_id
        
        # Find a recent POS order
        pos_order = self.env['zid.sale.order'].search([
            ('zid_connector_id', '=', connector.id),
            ('source', '=', 'ZidPOS')
        ], limit=1, order='create_date desc')
        
        if not pos_order:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'No POS Orders Found',
                    'message': 'No POS orders found to test with.',
                    'type': 'warning',
                }
            }
        
        report = f"""
=== POS ORDER FETCH TEST ===
Testing Order: {pos_order.zid_order_id} ({pos_order.order_code})
Zid Order ID: {pos_order.zid_order_id}
Source: {pos_order.source}

ORIGINAL ORDER DATA:
"""
        
        try:
            import json
            original_data = json.loads(pos_order.raw_data) if pos_order.raw_data else {}
            report += f"Has 'products' key: {'Yes' if 'products' in original_data else 'No'}\n"
            
            if 'products' in original_data:
                report += f"Products count: {len(original_data['products'])}\n"
            else:
                report += "No products in original data - will try to fetch full details\n"
                
                # Test fetching full order details
                endpoint = f"managers/store/orders/{pos_order.zid_order_id}/view"
                response = connector.api_request(endpoint=endpoint, method='GET')
                
                if response and 'order' in response:
                    full_order_data = response['order']
                    report += f"\nFULL ORDER DATA FETCH: SUCCESS\n"
                    report += f"Has 'products' key: {'Yes' if 'products' in full_order_data else 'No'}\n"
                    
                    if 'products' in full_order_data:
                        products = full_order_data['products']
                        report += f"Products count: {len(products)}\n"
                        
                        # Show first product details and test matching
                        if products:
                            first_product = products[0]
                            product_id = first_product.get('id', 'N/A')
                            sku = first_product.get('sku', 'N/A')
                            barcode = first_product.get('barcode', 'N/A')
                            name = first_product.get('name', 'N/A')
                            
                            report += f"\nFIRST PRODUCT SAMPLE:\n"
                            report += f"- ID: {product_id}\n"
                            report += f"- Name: {name}\n"
                            report += f"- SKU: {sku}\n"
                            report += f"- Barcode: {barcode}\n"
                            report += f"- Quantity: {first_product.get('quantity', 'N/A')}\n"
                            
                            # Test product matching
                            report += f"\nPRODUCT MATCHING TEST:\n"
                            report += f"Connector Match Priority: {connector.product_match_priority}\n"
                            report += f"Connector Match Method: {connector.product_match_by}\n"
                            
                            # Check Zid mappings
                            if product_id != 'N/A':
                                variant_mapping = self.env['zid.variant'].search([
                                    ('zid_variant_id', '=', str(product_id)),
                                    ('zid_connector_id', '=', connector.id)
                                ], limit=1)
                                
                                product_mapping = self.env['zid.product'].search([
                                    ('zid_product_id', '=', str(product_id)),
                                    ('zid_connector_id', '=', connector.id)
                                ], limit=1)
                                
                                report += f"- Zid Variant Mapping: {'Found' if variant_mapping else 'Not Found'}\n"
                                if variant_mapping:
                                    report += f"  → Mapped to: {variant_mapping.odoo_product_id.display_name if variant_mapping.odoo_product_id else 'No Odoo Product'}\n"
                                
                                report += f"- Zid Product Mapping: {'Found' if product_mapping else 'Not Found'}\n"
                                if product_mapping:
                                    report += f"  → Mapped to: {product_mapping.odoo_product_id.display_name if product_mapping.odoo_product_id else 'No Odoo Product'}\n"
                            
                            # Check direct SKU/Barcode matches
                            if sku != 'N/A':
                                sku_products = self.env['product.product'].search([
                                    ('default_code', '=', sku)
                                ])
                                report += f"- Odoo Products with SKU '{sku}': {len(sku_products)}\n"
                                if sku_products:
                                    report += f"  → Found: {', '.join(sku_products.mapped('display_name'))}\n"
                            
                            if barcode != 'N/A':
                                barcode_products = self.env['product.product'].search([
                                    ('barcode', '=', barcode)
                                ])
                                report += f"- Odoo Products with Barcode '{barcode}': {len(barcode_products)}\n"
                                if barcode_products:
                                    report += f"  → Found: {', '.join(barcode_products.mapped('display_name'))}\n"
                            
                            # Provide recommendations
                            report += f"\nRECOMMENDATIONS:\n"
                            if not variant_mapping and not product_mapping:
                                if sku != 'N/A' and not sku_products:
                                    report += f"❌ Create an Odoo product with SKU '{sku}'\n"
                                if barcode != 'N/A' and not barcode_products:
                                    report += f"❌ Create an Odoo product with Barcode '{barcode}'\n"
                                if not sku_products and not barcode_products:
                                    report += f"❌ Either create Zid product mappings or create Odoo products with matching SKU/Barcode\n"
                            else:
                                if variant_mapping and not variant_mapping.odoo_product_id:
                                    report += f"❌ Zid variant mapping exists but no Odoo product assigned\n"
                                if product_mapping and not product_mapping.odoo_product_id:
                                    report += f"❌ Zid product mapping exists but no Odoo product assigned\n"
                    else:
                        report += "❌ ISSUE: Full order data also doesn't contain products!\n"
                        report += "This suggests POS orders don't include product details in Zid API.\n"
                        
                        # Check what keys are available
                        available_keys = list(full_order_data.keys())
                        report += f"Available keys: {', '.join(available_keys)}\n"
                else:
                    report += f"\n❌ FAILED TO FETCH FULL ORDER DATA\n"
                    report += f"API Response: {response}\n"
                    
        except Exception as e:
            report += f"\n❌ ERROR DURING TEST: {str(e)}\n"
        
        _logger.info(report)
        
        # Also create a more detailed popup with results
        return {
            'type': 'ir.actions.act_window',
            'name': 'POS Order Diagnostic Results',
            'res_model': 'zid.diagnostic.result',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_title': 'POS Order Fetch Test Results',
                'default_content': report,
            }
        }
        
        if connector.auto_confirm_invoice and not connector.auto_create_invoice:
            report += "⚠ WARNING: Auto-confirm invoice is enabled but auto-create invoice is disabled\n"
        
        if connector.auto_validate_delivery and not connector.auto_confirm_orders:
            report += "⚠ WARNING: Auto-validate delivery is enabled but auto-confirm orders is disabled\n"
        
        # Check company settings that might affect automation
        company = connector.company_id
        if connector.auto_create_invoice:
            if not company.account_fiscal_country_id:
                report += "⚠ WARNING: Company fiscal country not set - may affect invoice creation\n"
        
        _logger.info(report)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Automation Diagnostic Complete',
                'message': 'Automation settings analyzed. Check logs for detailed report.',
                'type': 'info',
                'sticky': True,
            }
        }
    
    def diagnose_payment_mappings(self):
        """Diagnose payment mapping configuration"""
        connector = self.connector_id
        
        # Get payment mappings
        payment_mappings = self.env['zid.payment.mapping'].search([
            ('zid_connector_id', '=', connector.id)
        ])
        
        # Get recent orders with payment info
        recent_orders = self.env['zid.sale.order'].search([
            ('zid_connector_id', '=', connector.id),
            ('create_date', '>=', fields.Datetime.now() - timedelta(days=30))
        ], limit=50)
        
        # Analyze payment methods used
        payment_methods_used = set(recent_orders.mapped('payment_method_code'))
        payment_methods_used.discard(False)  # Remove empty values
        
        mapped_methods = set(payment_mappings.mapped('payment_method_code'))
        unmapped_methods = payment_methods_used - mapped_methods
        
        report = f"""
=== PAYMENT MAPPING DIAGNOSTIC ===
Connector: {connector.name}

PAYMENT AUTOMATION SETTINGS:
- Auto-Register Payment: {'✓ Enabled' if connector.auto_register_payment else '✗ Disabled'}
- Auto-Reconcile Payment: {'✓ Enabled' if connector.auto_reconcile_payment else '✗ Disabled'}
- Default Payment Journal: {connector.default_payment_journal_id.name if connector.default_payment_journal_id else 'Not Set'}

PAYMENT MAPPINGS:
- Total Mappings Configured: {len(payment_mappings)}
- Payment Methods Used (Last 30 days): {len(payment_methods_used)}
- Unmapped Methods: {len(unmapped_methods)}

CONFIGURED MAPPINGS:
"""
        
        for mapping in payment_mappings:
            report += f"- {mapping.payment_method_code} → {mapping.payment_journal_id.name}\n"
        
        if unmapped_methods:
            report += f"\nUNMAPPED PAYMENT METHODS (Found in recent orders):\n"
            for method in unmapped_methods:
                count = len(recent_orders.filtered(lambda o: o.payment_method_code == method))
                report += f"- {method} (used in {count} orders)\n"
        
        # Check for potential issues
        report += "\nPOTENTIAL ISSUES:\n"
        
        if connector.auto_register_payment and not connector.default_payment_journal_id and len(payment_mappings) == 0:
            report += "⚠ WARNING: Auto-register payment is enabled but no default journal or mappings configured\n"
        
        if connector.auto_reconcile_payment and not connector.auto_register_payment:
            report += "⚠ WARNING: Auto-reconcile payment is enabled but auto-register payment is disabled\n"
        
        if len(unmapped_methods) > 0:
            report += f"⚠ WARNING: {len(unmapped_methods)} payment methods used in orders but not mapped\n"
        
        _logger.info(report)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Payment Diagnostic Complete',
                'message': f'Found {len(unmapped_methods)} unmapped payment methods. Check logs for details.',
                'type': 'info',
                'sticky': True,
            }
        }


class ZidDiagnosticResult(models.TransientModel):
    _name = 'zid.diagnostic.result'
    _description = 'Zid Diagnostic Results Display'

    title = fields.Char(string='Title', readonly=True)
    content = fields.Text(string='Results', readonly=True)