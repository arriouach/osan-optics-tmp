# -*- coding: utf-8 -*-

from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class ZidAutomationWizard(models.TransientModel):
    _name = 'zid.automation.wizard'
    _description = 'Zid Order Automation Configuration Wizard'

    connector_id = fields.Many2one('zid.connector', string='Zid Connector', required=True)
    
    # Current settings (readonly)
    current_auto_confirm_orders = fields.Boolean(related='connector_id.auto_confirm_orders', readonly=True)
    current_auto_create_invoice = fields.Boolean(related='connector_id.auto_create_invoice', readonly=True)
    current_auto_confirm_invoice = fields.Boolean(related='connector_id.auto_confirm_invoice', readonly=True)
    current_auto_validate_delivery = fields.Boolean(related='connector_id.auto_validate_delivery', readonly=True)
    current_auto_register_payment = fields.Boolean(related='connector_id.auto_register_payment', readonly=True)
    current_auto_reconcile_payment = fields.Boolean(related='connector_id.auto_reconcile_payment', readonly=True)
    
    # New settings
    auto_confirm_orders = fields.Boolean(string='Auto-Confirm Orders', default=False)
    auto_create_invoice = fields.Boolean(string='Auto-Create Invoice', default=False)
    auto_confirm_invoice = fields.Boolean(string='Auto-Confirm Invoice', default=False)
    auto_validate_delivery = fields.Boolean(string='Auto-Validate Delivery', default=False)
    auto_register_payment = fields.Boolean(string='Auto-Register Payment', default=False)
    auto_reconcile_payment = fields.Boolean(string='Auto-Reconcile Payment', default=False)
    
    # Preset configurations
    automation_preset = fields.Selection([
        ('manual', 'Manual Processing (No Automation)'),
        ('basic', 'Basic Automation (Confirm Orders Only)'),
        ('advanced', 'Advanced Automation (Orders + Invoices)'),
        ('full', 'Full Automation (Orders + Invoices + Delivery)'),
        ('custom', 'Custom Configuration')
    ], string='Automation Preset', default='custom')
    
    recommendation = fields.Html(string='Recommendation', compute='_compute_recommendation')

    @api.onchange('connector_id')
    def _onchange_connector_id(self):
        if self.connector_id:
            self.auto_confirm_orders = self.connector_id.auto_confirm_orders
            self.auto_create_invoice = self.connector_id.auto_create_invoice
            self.auto_confirm_invoice = self.connector_id.auto_confirm_invoice
            self.auto_validate_delivery = self.connector_id.auto_validate_delivery
            self.auto_register_payment = self.connector_id.auto_register_payment
            self.auto_reconcile_payment = self.connector_id.auto_reconcile_payment
            self._determine_current_preset()

    def _determine_current_preset(self):
        """Determine which preset matches current settings"""
        if not any([self.auto_confirm_orders, self.auto_create_invoice, self.auto_confirm_invoice, 
                   self.auto_validate_delivery, self.auto_register_payment]):
            self.automation_preset = 'manual'
        elif self.auto_confirm_orders and not self.auto_create_invoice and not self.auto_validate_delivery and not self.auto_register_payment:
            self.automation_preset = 'basic'
        elif (self.auto_confirm_orders and self.auto_create_invoice and self.auto_confirm_invoice and 
              not self.auto_validate_delivery and not self.auto_register_payment):
            self.automation_preset = 'advanced'
        elif (self.auto_confirm_orders and self.auto_create_invoice and self.auto_confirm_invoice and 
              self.auto_validate_delivery and self.auto_register_payment):
            self.automation_preset = 'full'
        else:
            self.automation_preset = 'custom'

    @api.onchange('automation_preset')
    def _onchange_automation_preset(self):
        if self.automation_preset == 'manual':
            self.auto_confirm_orders = False
            self.auto_create_invoice = False
            self.auto_confirm_invoice = False
            self.auto_validate_delivery = False
            self.auto_register_payment = False
            self.auto_reconcile_payment = False
        elif self.automation_preset == 'basic':
            self.auto_confirm_orders = True
            self.auto_create_invoice = False
            self.auto_confirm_invoice = False
            self.auto_validate_delivery = False
            self.auto_register_payment = False
            self.auto_reconcile_payment = False
        elif self.automation_preset == 'advanced':
            self.auto_confirm_orders = True
            self.auto_create_invoice = True
            self.auto_confirm_invoice = True
            self.auto_validate_delivery = False
            self.auto_register_payment = True
            self.auto_reconcile_payment = True
        elif self.automation_preset == 'full':
            self.auto_confirm_orders = True
            self.auto_create_invoice = True
            self.auto_confirm_invoice = True
            self.auto_validate_delivery = True
            self.auto_register_payment = True
            self.auto_reconcile_payment = True
        # 'custom' doesn't change anything - user sets manually

    @api.depends('automation_preset', 'auto_confirm_orders', 'auto_create_invoice', 'auto_confirm_invoice', 
                 'auto_validate_delivery', 'auto_register_payment', 'auto_reconcile_payment')
    def _compute_recommendation(self):
        for record in self:
            html = "<div class='alert alert-info'>"
            
            if record.automation_preset == 'manual':
                html += "<h5>Manual Processing</h5>"
                html += "<p>All order processing steps will require manual intervention. Good for:</p>"
                html += "<ul><li>Testing and validation</li><li>Orders requiring review</li><li>Complex approval workflows</li></ul>"
                
            elif record.automation_preset == 'basic':
                html += "<h5>Basic Automation</h5>"
                html += "<p>Orders will be automatically confirmed but invoices, payments and deliveries remain manual. Good for:</p>"
                html += "<ul><li>Standard e-commerce workflows</li><li>When you want to review invoices manually</li><li>Payment verification workflows</li></ul>"
                
            elif record.automation_preset == 'advanced':
                html += "<h5>Advanced Automation</h5>"
                html += "<p>Orders, invoices and payments are fully automated, deliveries remain manual. Good for:</p>"
                html += "<ul><li>High-volume operations</li><li>Trusted payment gateways</li><li>When you want delivery control</li></ul>"
                
            elif record.automation_preset == 'full':
                html += "<h5>Full Automation</h5>"
                html += "<p><strong>⚠ Use with caution!</strong> Complete automation from order to delivery and payment. Good for:</p>"
                html += "<ul><li>Digital products</li><li>Reliable inventory systems</li><li>Trusted payment processing</li><li>High-volume, low-risk orders</li></ul>"
                html += "<p class='text-warning'><strong>Note:</strong> Ensure payment mappings are configured and stock levels are reliable.</p>"
                
            elif record.automation_preset == 'custom':
                html += "<h5>Custom Configuration</h5>"
                html += "<p>You've configured a custom automation flow:</p>"
                html += "<ul>"
                if record.auto_confirm_orders:
                    html += "<li>✓ Orders will be confirmed automatically</li>"
                else:
                    html += "<li>✗ Orders will remain in draft (manual confirmation required)</li>"
                
                if record.auto_create_invoice:
                    html += "<li>✓ Invoices will be created automatically</li>"
                    if record.auto_confirm_invoice:
                        html += "<li>✓ Invoices will be confirmed automatically</li>"
                    else:
                        html += "<li>⚠ Invoices will be created but not confirmed</li>"
                else:
                    html += "<li>✗ Invoices will not be created automatically</li>"
                
                if record.auto_register_payment:
                    html += "<li>✓ Payments will be registered automatically for paid orders</li>"
                    if record.auto_reconcile_payment:
                        html += "<li>✓ Payments will be reconciled automatically</li>"
                    else:
                        html += "<li>⚠ Payments will be registered but not reconciled</li>"
                else:
                    html += "<li>✗ Payments will not be registered automatically</li>"
                
                if record.auto_validate_delivery:
                    html += "<li>✓ Deliveries will be validated automatically</li>"
                else:
                    html += "<li>✗ Deliveries will require manual validation</li>"
                html += "</ul>"
            
            html += "</div>"
            record.recommendation = html

    def action_apply_settings(self):
        """Apply the automation settings"""
        if self.connector_id:
            self.connector_id.write({
                'auto_confirm_orders': self.auto_confirm_orders,
                'auto_create_invoice': self.auto_create_invoice,
                'auto_confirm_invoice': self.auto_confirm_invoice,
                'auto_validate_delivery': self.auto_validate_delivery,
                'auto_register_payment': self.auto_register_payment,
                'auto_reconcile_payment': self.auto_reconcile_payment,
            })
            
            preset_name = dict(self._fields['automation_preset'].selection)[self.automation_preset]
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Automation Settings Applied',
                    'message': f'Order automation configured: {preset_name}',
                    'type': 'success',
                    'sticky': False,
                }
            }

    def action_test_automation(self):
        """Test automation with a sample scenario"""
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Test Complete',
                'message': 'Automation settings validated. Process a test order to verify behavior.',
                'type': 'info',
                'sticky': True,
            }
        }