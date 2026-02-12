# -*- coding: utf-8 -*-

from odoo import models, fields, api
from datetime import timedelta
import logging

_logger = logging.getLogger(__name__)


class ZidSalesTeamWizard(models.TransientModel):
    _name = 'zid.sales.team.wizard'
    _description = 'Zid Sales Team Configuration Wizard'

    connector_id = fields.Many2one('zid.connector', string='Zid Connector', required=True)
    
    # Current settings (readonly)
    current_user_id = fields.Many2one(related='connector_id.default_user_id', readonly=True)
    current_team_id = fields.Many2one(related='connector_id.default_team_id', readonly=True)
    
    # New settings
    default_user_id = fields.Many2one(
        'res.users',
        string='Default Salesperson',
        help='Default salesperson to assign to imported orders'
    )
    default_team_id = fields.Many2one(
        'crm.team',
        string='Default Sales Team',
        help='Default sales team to assign to imported orders'
    )
    
    # Configuration options
    assignment_strategy = fields.Selection([
        ('fixed', 'Fixed Assignment (Always use default)'),
        ('round_robin', 'Round Robin (Rotate between team members)'),
        ('by_amount', 'By Order Amount (High value orders to senior sales)'),
        ('by_region', 'By Customer Region (If customer has state/country)')
    ], string='Assignment Strategy', default='fixed',
       help='How to assign orders to salespeople')
    
    # Statistics
    total_orders_last_month = fields.Integer(string='Orders Last Month', compute='_compute_statistics')
    orders_with_salesperson = fields.Integer(string='Orders with Salesperson', compute='_compute_statistics')
    
    recommendation = fields.Html(string='Recommendation', compute='_compute_recommendation')

    @api.depends('connector_id')
    def _compute_statistics(self):
        for record in self:
            if record.connector_id:
                # Get orders from last month
                last_month_orders = self.env['zid.sale.order'].search([
                    ('zid_connector_id', '=', record.connector_id.id),
                    ('create_date', '>=', fields.Datetime.now() - timedelta(days=30))
                ])
                
                # Count orders with assigned salesperson
                orders_with_sales = last_month_orders.filtered(lambda o: o.sale_order_id and o.sale_order_id.user_id)
                
                record.total_orders_last_month = len(last_month_orders)
                record.orders_with_salesperson = len(orders_with_sales)
            else:
                record.total_orders_last_month = 0
                record.orders_with_salesperson = 0

    @api.onchange('connector_id')
    def _onchange_connector_id(self):
        if self.connector_id:
            self.default_user_id = self.connector_id.default_user_id
            self.default_team_id = self.connector_id.default_team_id

    @api.onchange('default_team_id')
    def _onchange_default_team_id(self):
        """When team changes, suggest team leader as default salesperson"""
        if self.default_team_id and self.default_team_id.user_id:
            self.default_user_id = self.default_team_id.user_id

    @api.depends('assignment_strategy', 'default_user_id', 'default_team_id', 'total_orders_last_month')
    def _compute_recommendation(self):
        for record in self:
            html = "<div class='alert alert-info'>"
            
            if record.assignment_strategy == 'fixed':
                html += "<h5>Fixed Assignment Strategy</h5>"
                html += "<p>All imported orders will be assigned to the same salesperson. Good for:</p>"
                html += "<ul><li>Small teams</li><li>Dedicated e-commerce manager</li><li>Simple workflows</li></ul>"
                
                if not record.default_user_id:
                    html += "<p class='text-warning'><strong>Warning:</strong> No default salesperson selected!</p>"
                
            elif record.assignment_strategy == 'round_robin':
                html += "<h5>Round Robin Strategy</h5>"
                html += "<p>Orders will be distributed evenly among team members. Good for:</p>"
                html += "<ul><li>Balanced workload distribution</li><li>Multiple salespeople</li><li>Fair opportunity sharing</li></ul>"
                html += "<p class='text-info'><strong>Note:</strong> This feature requires custom development.</p>"
                
            elif record.assignment_strategy == 'by_amount':
                html += "<h5>Amount-Based Assignment</h5>"
                html += "<p>High-value orders assigned to senior sales staff. Good for:</p>"
                html += "<ul><li>Tiered sales teams</li><li>VIP customer handling</li><li>Commission-based structures</li></ul>"
                html += "<p class='text-info'><strong>Note:</strong> This feature requires custom development.</p>"
                
            elif record.assignment_strategy == 'by_region':
                html += "<h5>Region-Based Assignment</h5>"
                html += "<p>Orders assigned based on customer location. Good for:</p>"
                html += "<ul><li>Regional sales territories</li><li>Local market expertise</li><li>Language preferences</li></ul>"
                html += "<p class='text-info'><strong>Note:</strong> This feature requires custom development.</p>"
            
            # Show statistics
            if record.total_orders_last_month > 0:
                coverage = (record.orders_with_salesperson / record.total_orders_last_month) * 100
                html += f"<p><strong>Current Coverage:</strong> {coverage:.1f}% of orders have assigned salespeople</p>"
            
            html += "</div>"
            record.recommendation = html

    def action_apply_settings(self):
        """Apply the sales team settings"""
        if self.connector_id:
            self.connector_id.write({
                'default_user_id': self.default_user_id.id if self.default_user_id else False,
                'default_team_id': self.default_team_id.id if self.default_team_id else False,
            })
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Sales Team Settings Applied',
                    'message': f'Default salesperson: {self.default_user_id.name if self.default_user_id else "None"}, Team: {self.default_team_id.name if self.default_team_id else "None"}',
                    'type': 'success',
                    'sticky': False,
                }
            }

    def action_create_sales_team(self):
        """Helper to create a new sales team for Zid orders"""
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'crm.team',
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'new',
            'context': {
                'default_name': f'Zid E-commerce Team - {self.connector_id.app_name}',
                'default_use_opportunities': False,
                'default_use_leads': False,
            }
        }