from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import datetime, timedelta
import json
import logging

_logger = logging.getLogger(__name__)


class ZidHealthReportWizard(models.TransientModel):
    _name = 'zid.health.report.wizard'
    _description = 'Zid Integration Health Report'

    connector_id = fields.Many2one(
        'zid.connector',
        string='Zid Connector',
        required=True,
        readonly=True
    )

    report_data = fields.Text(
        string='Report Data',
        readonly=True
    )

    # Connection Health
    connection_status = fields.Char(
        string='Connection Status',
        compute='_compute_health_metrics'
    )

    last_sync_date = fields.Datetime(
        string='Last Sync',
        compute='_compute_health_metrics'
    )

    health_score = fields.Integer(
        string='Health Score (%)',
        compute='_compute_health_metrics'
    )

    # Statistics
    total_products = fields.Integer(
        string='Total Products',
        compute='_compute_health_metrics'
    )

    total_orders = fields.Integer(
        string='Total Orders',
        compute='_compute_health_metrics'
    )

    total_customers = fields.Integer(
        string='Total Customers',
        compute='_compute_health_metrics'
    )

    # Recent Activity
    today_orders = fields.Integer(
        string="Today's Orders",
        compute='_compute_health_metrics'
    )

    week_orders = fields.Integer(
        string="This Week's Orders",
        compute='_compute_health_metrics'
    )

    month_revenue = fields.Float(
        string="This Month's Revenue",
        compute='_compute_health_metrics'
    )

    # Issues
    pending_orders = fields.Integer(
        string='Pending Orders',
        compute='_compute_health_metrics'
    )

    low_stock_products = fields.Integer(
        string='Low Stock Products',
        compute='_compute_health_metrics'
    )

    sync_errors = fields.Integer(
        string='Sync Errors (Last 7 Days)',
        compute='_compute_health_metrics'
    )

    failed_webhooks = fields.Integer(
        string='Failed Webhooks',
        compute='_compute_health_metrics'
    )

    # Recommendations
    recommendations = fields.Text(
        string='Recommendations',
        compute='_compute_recommendations'
    )

    # Detailed Logs
    error_log_ids = fields.Many2many(
        'zid.stock.update.log',
        string='Recent Errors',
        compute='_compute_error_logs'
    )

    @api.depends('connector_id')
    def _compute_health_metrics(self):
        """Compute all health metrics"""
        for wizard in self:
            connector = wizard.connector_id

            # Connection
            wizard.connection_status = connector.authorization_status
            wizard.last_sync_date = connector.last_sync_date
            wizard.health_score = connector.sync_health_score

            # Statistics
            wizard.total_products = connector.product_count
            wizard.total_orders = connector.order_count
            wizard.total_customers = connector.customer_count

            # Recent Activity
            wizard.today_orders = connector.today_orders
            wizard.week_orders = connector.week_orders
            wizard.month_revenue = connector.month_revenue

            # Issues
            wizard.pending_orders = connector.pending_orders
            wizard.low_stock_products = connector.low_stock_products
            wizard.sync_errors = connector.sync_errors

            # Failed webhooks
            wizard.failed_webhooks = self.env['zid.webhook'].search_count([
                ('zid_connector_id', '=', connector.id),
                ('is_active', '=', False)
            ])

    @api.depends('connector_id', 'sync_errors', 'low_stock_products', 'pending_orders', 'health_score')
    def _compute_recommendations(self):
        """Generate recommendations based on health metrics"""
        for wizard in self:
            recommendations = []

            # Connection issues
            if wizard.connection_status != 'connected':
                recommendations.append('🔴 CRITICAL: Reconnect to Zid immediately')

            # Sync errors
            if wizard.sync_errors > 10:
                recommendations.append(f'⚠️  HIGH: {wizard.sync_errors} sync errors detected - Review error logs')
            elif wizard.sync_errors > 0:
                recommendations.append(f'⚠️  MEDIUM: {wizard.sync_errors} sync errors - Monitor closely')

            # Low stock
            if wizard.low_stock_products > 20:
                recommendations.append(f'⚠️  HIGH: {wizard.low_stock_products} products low on stock')
            elif wizard.low_stock_products > 0:
                recommendations.append(f'ℹ️  INFO: {wizard.low_stock_products} products low on stock')

            # Pending orders
            if wizard.pending_orders > 50:
                recommendations.append(f'⚠️  HIGH: {wizard.pending_orders} pending orders need attention')
            elif wizard.pending_orders > 10:
                recommendations.append(f'ℹ️  INFO: {wizard.pending_orders} pending orders')

            # Health score
            if wizard.health_score < 70:
                recommendations.append('🔴 CRITICAL: Health score below 70% - Immediate action required')
            elif wizard.health_score < 90:
                recommendations.append('⚠️  MEDIUM: Health score below 90% - Review sync processes')

            # Failed webhooks
            if wizard.failed_webhooks > 0:
                recommendations.append(f'ℹ️  INFO: {wizard.failed_webhooks} inactive webhooks - Consider reactivating')

            # Last sync
            if wizard.last_sync_date:
                hours_since_sync = (datetime.now() - wizard.last_sync_date).total_seconds() / 3600
                if hours_since_sync > 24:
                    recommendations.append('⚠️  MEDIUM: No sync in last 24 hours - Run manual sync')

            # No issues
            if not recommendations:
                recommendations.append('✅ EXCELLENT: All systems operating normally')

            wizard.recommendations = '\n'.join(recommendations)

    @api.depends('connector_id')
    def _compute_error_logs(self):
        """Get recent error logs"""
        for wizard in self:
            seven_days_ago = datetime.now() - timedelta(days=7)
            wizard.error_log_ids = self.env['zid.stock.update.log'].search([
                ('zid_connector_id', '=', wizard.connector_id.id),
                ('status', '=', 'failed'),
                ('create_date', '>=', seven_days_ago)
            ], limit=20, order='create_date desc')

    def action_fix_connection(self):
        """Open connector to fix connection"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Fix Connection'),
            'res_model': 'zid.connector',
            'res_id': self.connector_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_errors(self):
        """View error logs"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Sync Errors'),
            'res_model': 'zid.stock.update.log',
            'view_mode': 'list,form',
            'domain': [
                ('zid_connector_id', '=', self.connector_id.id),
                ('status', '=', 'failed')
            ],
        }

    def action_view_low_stock(self):
        """View low stock products"""
        self.ensure_one()
        
        # Get products with low stock
        products = self.env['product.template'].search([
            ('zid_connector_id', '=', self.connector_id.id),
            ('qty_available', '<', 10),
            ('qty_available', '>', 0)
        ])

        return {
            'type': 'ir.actions.act_window',
            'name': _('Low Stock Products'),
            'res_model': 'product.template',
            'view_mode': 'list,form',
            'domain': [('id', 'in', products.ids)],
        }

    def action_view_pending_orders(self):
        """View pending orders"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Pending Orders'),
            'res_model': 'zid.sale.order',
            'view_mode': 'list,form',
            'domain': [
                ('zid_connector_id', '=', self.connector_id.id),
                ('order_status', 'in', ['new', 'preparing'])
            ],
        }

    def action_run_sync(self):
        """Run bulk sync"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Bulk Sync'),
            'res_model': 'zid.bulk.sync.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_connector_id': self.connector_id.id,
            }
        }

    def action_export_report(self):
        """Export health report as JSON"""
        self.ensure_one()

        report = {
            'connector': self.connector_id.name,
            'store_id': self.connector_id.store_id,
            'generated_at': datetime.now().isoformat(),
            'connection': {
                'status': self.connection_status,
                'last_sync': self.last_sync_date.isoformat() if self.last_sync_date else None,
                'health_score': self.health_score,
            },
            'statistics': {
                'products': self.total_products,
                'orders': self.total_orders,
                'customers': self.total_customers,
                'today_orders': self.today_orders,
                'week_orders': self.week_orders,
                'month_revenue': self.month_revenue,
            },
            'issues': {
                'pending_orders': self.pending_orders,
                'low_stock_products': self.low_stock_products,
                'sync_errors': self.sync_errors,
                'failed_webhooks': self.failed_webhooks,
            },
            'recommendations': self.recommendations.split('\n') if self.recommendations else [],
        }

        # Create attachment
        attachment = self.env['ir.attachment'].create({
            'name': f'zid_health_report_{self.connector_id.store_id}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json',
            'type': 'binary',
            'datas': json.dumps(report, indent=2).encode('utf-8'),
            'mimetype': 'application/json',
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'new',
        }
