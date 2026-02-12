# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import json
import logging
from datetime import datetime

_logger = logging.getLogger(__name__)


class ZidStockUpdateLog(models.Model):
    _name = 'zid.stock.update.log'
    _description = 'Zid Stock Update Log'
    _order = 'create_date desc'
    _rec_name = 'display_name'
    
    # =============== Basic Information ===============
    display_name = fields.Char(
        string='Reference',
        compute='_compute_display_name',
        store=True
    )
    
    reference = fields.Char(
        string='Reference Number',
        required=True,
        default=lambda self: self._get_default_reference(),
        readonly=True,
        copy=False
    )
    
    # =============== Connector & Product Info ===============
    zid_connector_id = fields.Many2one(
        'zid.connector',
        string='Zid Connector',
        required=False,
        ondelete='cascade'
    )
    
    product_id = fields.Many2one(
        'product.product',
        string='Odoo Product',
        required=False,
        ondelete='cascade'
    )
    
    product_template_id = fields.Many2one(
        'product.template',
        string='Product Template',
        related='product_id.product_tmpl_id',
        store=True,
        readonly=True
    )
    
    zid_product_id = fields.Many2one(
        'zid.product',
        string='Zid Product',
        ondelete='set null'
    )
    
    zid_product_line_id = fields.Many2one(
        'zid.product.line',
        string='Zid Product Line',
        ondelete='set null'
    )
    
    # =============== Location Info ===============
    odoo_location_id = fields.Many2one(
        'stock.location',
        string='Odoo Location',
        required=False
    )
    
    zid_location_id = fields.Many2one(
        'zid.location',
        string='Zid Location'
    )
    
    # =============== Quantity Changes ===============
    quantity_before_odoo = fields.Float(
        string='Odoo Qty Before',
        digits='Product Unit of Measure',
        required=False,
        default=0.0
    )
    
    quantity_after_odoo = fields.Float(
        string='Odoo Qty After',
        digits='Product Unit of Measure',
        required=False,
        default=0.0
    )
    
    quantity_change_odoo = fields.Float(
        string='Odoo Change',
        digits='Product Unit of Measure',
        compute='_compute_quantity_changes',
        store=True
    )
    
    quantity_before_zid = fields.Float(
        string='Zid Qty Before',
        digits='Product Unit of Measure'
    )
    
    quantity_after_zid = fields.Float(
        string='Zid Qty After',
        digits='Product Unit of Measure'
    )
    
    quantity_change_zid = fields.Float(
        string='Zid Change',
        digits='Product Unit of Measure',
        compute='_compute_quantity_changes',
        store=True
    )
    
    # =============== Operation Details ===============
    operation_type = fields.Selection([
        ('manual', 'Manual Adjustment'),
        ('receipt', 'Receipt'),
        ('delivery', 'Delivery'),
        ('internal', 'Internal Transfer'),
        ('manufacturing', 'Manufacturing'),
        ('inventory', 'Inventory Adjustment'),
        ('scrap', 'Scrap'),
        ('sale', 'Sale Order'),
        ('purchase', 'Purchase Order'),
        ('return', 'Return'),
        ('other', 'Other')
    ], string='Operation Type', required=True, default='manual')
    
    trigger_source = fields.Selection([
        ('stock_move', 'Stock Move'),
        ('stock_quant', 'Stock Quant'),
        ('inventory_adjustment', 'Inventory Adjustment'),
        ('sale_order', 'Sale Order'),
        ('purchase_order', 'Purchase Order'),
        ('manual_sync', 'Manual Sync'),
        ('automated_sync', 'Automated Sync'),
        ('webhook', 'Webhook'),
        ('cron', 'Scheduled Job'),
        ('other', 'Other')
    ], string='Trigger Source', required=True, default='manual_sync')
    
    # =============== Related Documents ===============
    stock_move_id = fields.Many2one(
        'stock.move',
        string='Stock Move',
        ondelete='set null'
    )
    
    stock_picking_id = fields.Many2one(
        'stock.picking',
        string='Stock Picking',
        ondelete='set null'
    )
    
    sale_order_id = fields.Many2one(
        'sale.order',
        string='Sale Order',
        ondelete='set null'
    )
    
    purchase_order_id = fields.Many2one(
        'purchase.order',
        string='Purchase Order',
        ondelete='set null'
    )
    
    # =============== API Communication ===============
    api_endpoint = fields.Char(
        string='API Endpoint',
        help='The Zid API endpoint that was called'
    )
    
    api_method = fields.Selection([
        ('GET', 'GET'),
        ('POST', 'POST'),
        ('PUT', 'PUT'),
        ('PATCH', 'PATCH'),
        ('DELETE', 'DELETE')
    ], string='API Method', default='PUT')
    
    request_data = fields.Text(
        string='Request Data',
        help='JSON data sent to Zid API'
    )
    
    response_data = fields.Text(
        string='Response Data',
        help='JSON response from Zid API'
    )
    
    response_code = fields.Integer(
        string='Response Code',
        help='HTTP response code from Zid API'
    )
    
    # =============== Status & Timing ===============
    status = fields.Selection([
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('success', 'Success'),
        ('partial', 'Partial Success'),
        ('failed', 'Failed'),
        ('error', 'Error'),
        ('timeout', 'Timeout'),
        ('cancelled', 'Cancelled')
    ], string='Status', required=True, default='pending', index=True)
    
    sync_direction = fields.Selection([
        ('odoo_to_zid', 'Odoo → Zid'),
        ('zid_to_odoo', 'Zid → Odoo'),
        ('bidirectional', 'Bidirectional')
    ], string='Sync Direction', required=True, default='odoo_to_zid')
    
    start_time = fields.Datetime(
        string='Start Time',
        default=fields.Datetime.now,
        required=True
    )
    
    end_time = fields.Datetime(
        string='End Time'
    )
    
    duration = fields.Float(
        string='Duration (seconds)',
        compute='_compute_duration',
        store=True
    )
    
    # =============== Error Handling ===============
    error_message = fields.Text(
        string='Error Message'
    )
    
    error_details = fields.Text(
        string='Error Details',
        help='Detailed error traceback or additional information'
    )
    
    retry_count = fields.Integer(
        string='Retry Count',
        default=0
    )
    
    max_retries = fields.Integer(
        string='Max Retries',
        default=3
    )
    
    can_retry = fields.Boolean(
        string='Can Retry',
        compute='_compute_can_retry'
    )
    
    # =============== Additional Info ===============
    notes = fields.Text(
        string='Notes'
    )
    
    user_id = fields.Many2one(
        'res.users',
        string='User',
        default=lambda self: self.env.user,
        required=True
    )
    
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True
    )
    
    # SKU and Barcode for quick reference
    product_sku = fields.Char(
        string='SKU',
        related='product_id.default_code',
        store=True,
        readonly=True
    )
    
    product_barcode = fields.Char(
        string='Barcode',
        related='product_id.barcode',
        store=True,
        readonly=True
    )
    
    # =============== Computed Fields ===============
    @api.depends('reference', 'product_id', 'status')
    def _compute_display_name(self):
        for log in self:
            status_emoji = {
                'success': '✅',
                'failed': '❌',
                'error': '⚠️',
                'pending': '⏳',
                'processing': '🔄',
                'partial': '⚡',
                'timeout': '⏱️',
                'cancelled': '🚫'
            }.get(log.status, '')
            
            log.display_name = f"{status_emoji} {log.reference} - {log.product_id.display_name if log.product_id else 'Unknown'}"
    
    @api.depends('quantity_before_odoo', 'quantity_after_odoo', 'quantity_before_zid', 'quantity_after_zid')
    def _compute_quantity_changes(self):
        for log in self:
            log.quantity_change_odoo = log.quantity_after_odoo - log.quantity_before_odoo
            log.quantity_change_zid = log.quantity_after_zid - log.quantity_before_zid
    
    @api.depends('start_time', 'end_time')
    def _compute_duration(self):
        for log in self:
            if log.start_time and log.end_time:
                delta = log.end_time - log.start_time
                log.duration = delta.total_seconds()
            else:
                log.duration = 0
    
    @api.depends('status', 'retry_count', 'max_retries')
    def _compute_can_retry(self):
        for log in self:
            log.can_retry = (
                log.status in ['failed', 'error', 'timeout'] and
                log.retry_count < log.max_retries
            )
    
    # =============== Methods ===============
    @api.model
    def _get_default_reference(self):
        """Generate a unique reference number"""
        sequence = self.env['ir.sequence'].sudo().search([
            ('code', '=', 'zid.stock.update.log')
        ], limit=1)
        
        if not sequence:
            # Create sequence if it doesn't exist
            sequence = self.env['ir.sequence'].sudo().create({
                'name': 'Zid Stock Update Log',
                'code': 'zid.stock.update.log',
                'prefix': 'ZID/STOCK/',
                'padding': 5,
                'company_id': False,
            })
        
        return sequence.next_by_id()
    
    @api.model
    def create_log(self, vals):
        """Helper method to create a log entry"""
        # Ensure we have a reference
        if 'reference' not in vals:
            vals['reference'] = self._get_default_reference()
        
        # Set start time if not provided
        if 'start_time' not in vals:
            vals['start_time'] = fields.Datetime.now()
        
        return self.create(vals)
    
    def mark_success(self, response_data=None, response_code=200, notes=None):
        """Mark the log as successful"""
        self.ensure_one()
        vals = {
            'status': 'success',
            'end_time': fields.Datetime.now(),
            'response_code': response_code,
        }
        
        if response_data:
            if isinstance(response_data, dict):
                vals['response_data'] = json.dumps(response_data, indent=2)
            else:
                vals['response_data'] = str(response_data)
        
        if notes:
            vals['notes'] = notes
        
        self.write(vals)
        _logger.info(f"Stock update log {self.reference} marked as success")
    
    def mark_failed(self, error_message, error_details=None, response_code=None):
        """Mark the log as failed"""
        self.ensure_one()
        vals = {
            'status': 'failed',
            'end_time': fields.Datetime.now(),
            'error_message': error_message,
        }
        
        if error_details:
            vals['error_details'] = error_details
        
        if response_code:
            vals['response_code'] = response_code
        
        self.write(vals)
        _logger.error(f"Stock update log {self.reference} marked as failed: {error_message}")
    
    def action_retry(self):
        """Retry the failed operation"""
        self.ensure_one()
        
        if not self.can_retry:
            raise UserError(_('This operation cannot be retried.'))
        
        # Increment retry count
        self.retry_count += 1
        self.status = 'pending'
        
        # Trigger the sync operation again based on operation type
        try:
            if self.zid_product_line_id and hasattr(self.zid_product_line_id, 'action_sync_stock'):
                # Sync through product line
                self.zid_product_line_id.action_sync_stock()
                self.mark_success(
                    response_data={'retried': True},
                    response_code=200,
                    notes='Retry successful'
                )
            elif self.product_template_id and hasattr(self.product_template_id, 'action_update_stock_to_zid'):
                # Sync through product template
                self.product_template_id.action_update_stock_to_zid()
                self.mark_success(
                    response_data={'retried': True},
                    response_code=200,
                    notes='Retry successful'
                )
            else:
                raise UserError(_('No sync method available for this log entry'))
        except Exception as e:
            self.mark_failed(str(e))
    
    def action_view_request_data(self):
        """View request data in a formatted way"""
        self.ensure_one()
        
        if not self.request_data:
            raise UserError(_('No request data available'))
        
        try:
            data = json.loads(self.request_data)
            formatted_data = json.dumps(data, indent=2, ensure_ascii=False)
        except:
            formatted_data = self.request_data
        
        return {
            'name': _('Request Data'),
            'type': 'ir.actions.act_window',
            'res_model': 'zid.stock.update.log',
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': self.env.ref('zid_integration.view_zid_stock_update_log_data_form').id,
            'target': 'new',
            'context': {
                'default_data_type': 'request',
                'default_data_content': formatted_data
            }
        }
    
    def action_view_response_data(self):
        """View response data in a formatted way"""
        self.ensure_one()
        
        if not self.response_data:
            raise UserError(_('No response data available'))
        
        try:
            data = json.loads(self.response_data)
            formatted_data = json.dumps(data, indent=2, ensure_ascii=False)
        except:
            formatted_data = self.response_data
        
        return {
            'name': _('Response Data'),
            'type': 'ir.actions.act_window',
            'res_model': 'zid.stock.update.log',
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': self.env.ref('zid_integration.view_zid_stock_update_log_data_form').id,
            'target': 'new',
            'context': {
                'default_data_type': 'response',
                'default_data_content': formatted_data
            }
        }
    
    # =============== Cron & Cleanup ===============
    @api.model
    def cleanup_old_logs(self, days=30):
        """Clean up old logs"""
        cutoff_date = fields.Datetime.now() - timedelta(days=days)
        old_logs = self.search([
            ('create_date', '<', cutoff_date),
            ('status', 'in', ['success', 'cancelled'])
        ])
        
        count = len(old_logs)
        old_logs.unlink()
        
        _logger.info(f"Cleaned up {count} old stock update logs")
        return count
