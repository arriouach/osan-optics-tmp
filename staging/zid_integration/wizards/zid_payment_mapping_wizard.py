# -*- coding: utf-8 -*-

from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class ZidPaymentMappingWizard(models.TransientModel):
    _name = 'zid.payment.mapping.wizard'
    _description = 'Zid Payment Method Mapping Wizard'

    connector_id = fields.Many2one('zid.connector', string='Zid Connector', required=True)
    
    # Statistics
    total_mappings = fields.Integer(string='Total Mappings', compute='_compute_statistics')
    configured_mappings = fields.Integer(string='Configured Mappings', compute='_compute_statistics')
    
    # Common payment methods as individual fields for simplicity
    cod_journal_id = fields.Many2one('account.journal', string='Cash on Delivery Journal', domain=[('type', '=', 'cash')])
    credit_card_journal_id = fields.Many2one('account.journal', string='Credit Card Journal', domain=[('type', '=', 'bank')])
    debit_card_journal_id = fields.Many2one('account.journal', string='Debit Card Journal', domain=[('type', '=', 'bank')])
    apple_pay_journal_id = fields.Many2one('account.journal', string='Apple Pay Journal', domain=[('type', '=', 'bank')])
    stc_pay_journal_id = fields.Many2one('account.journal', string='STC Pay Journal', domain=[('type', '=', 'bank')])
    mada_journal_id = fields.Many2one('account.journal', string='Mada Journal', domain=[('type', '=', 'bank')])
    visa_journal_id = fields.Many2one('account.journal', string='Visa Journal', domain=[('type', '=', 'bank')])
    mastercard_journal_id = fields.Many2one('account.journal', string='Mastercard Journal', domain=[('type', '=', 'bank')])
    bank_transfer_journal_id = fields.Many2one('account.journal', string='Bank Transfer Journal', domain=[('type', '=', 'bank')])
    wallet_journal_id = fields.Many2one('account.journal', string='Digital Wallet Journal', domain=[('type', '=', 'bank')])
    
    @api.depends('connector_id')
    def _compute_statistics(self):
        for record in self:
            if record.connector_id:
                existing_mappings = self.env['zid.payment.mapping'].search([
                    ('zid_connector_id', '=', record.connector_id.id)
                ])
                record.total_mappings = 10  # Number of common payment methods
                record.configured_mappings = len(existing_mappings)
            else:
                record.total_mappings = 0
                record.configured_mappings = 0

    @api.onchange('connector_id')
    def _onchange_connector_id(self):
        if self.connector_id:
            self._load_existing_mappings()

    def _load_existing_mappings(self):
        """Load existing mappings into the wizard fields"""
        existing_mappings = self.env['zid.payment.mapping'].search([
            ('zid_connector_id', '=', self.connector_id.id)
        ])
        
        for mapping in existing_mappings:
            if mapping.payment_method_code == 'cod':
                self.cod_journal_id = mapping.payment_journal_id
            elif mapping.payment_method_code == 'credit_card':
                self.credit_card_journal_id = mapping.payment_journal_id
            elif mapping.payment_method_code == 'debit_card':
                self.debit_card_journal_id = mapping.payment_journal_id
            elif mapping.payment_method_code == 'apple_pay':
                self.apple_pay_journal_id = mapping.payment_journal_id
            elif mapping.payment_method_code == 'stc_pay':
                self.stc_pay_journal_id = mapping.payment_journal_id
            elif mapping.payment_method_code == 'mada':
                self.mada_journal_id = mapping.payment_journal_id
            elif mapping.payment_method_code == 'visa':
                self.visa_journal_id = mapping.payment_journal_id
            elif mapping.payment_method_code == 'mastercard':
                self.mastercard_journal_id = mapping.payment_journal_id
            elif mapping.payment_method_code == 'bank_transfer':
                self.bank_transfer_journal_id = mapping.payment_journal_id
            elif mapping.payment_method_code == 'wallet':
                self.wallet_journal_id = mapping.payment_journal_id

    def action_apply_mappings(self):
        """Apply the payment method mappings"""
        if not self.connector_id:
            return
        
        created_count = 0
        updated_count = 0
        
        # Define payment methods and their corresponding wizard fields
        payment_methods = [
            ('cod', 'Cash on Delivery', self.cod_journal_id),
            ('credit_card', 'Credit Card', self.credit_card_journal_id),
            ('debit_card', 'Debit Card', self.debit_card_journal_id),
            ('apple_pay', 'Apple Pay', self.apple_pay_journal_id),
            ('stc_pay', 'STC Pay', self.stc_pay_journal_id),
            ('mada', 'Mada', self.mada_journal_id),
            ('visa', 'Visa', self.visa_journal_id),
            ('mastercard', 'Mastercard', self.mastercard_journal_id),
            ('bank_transfer', 'Bank Transfer', self.bank_transfer_journal_id),
            ('wallet', 'Digital Wallet', self.wallet_journal_id),
        ]
        
        for code, name, journal in payment_methods:
            if not journal:
                continue
            
            # Check if mapping already exists
            existing_mapping = self.env['zid.payment.mapping'].search([
                ('zid_connector_id', '=', self.connector_id.id),
                ('payment_method_code', '=', code)
            ], limit=1)
            
            mapping_vals = {
                'zid_connector_id': self.connector_id.id,
                'payment_method_code': code,
                'payment_method_name': name,
                'payment_journal_id': journal.id,
                'auto_register_payment': True,
            }
            
            if existing_mapping:
                existing_mapping.write(mapping_vals)
                updated_count += 1
            else:
                self.env['zid.payment.mapping'].create(mapping_vals)
                created_count += 1
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Payment Mappings Applied',
                'message': f'Created {created_count} new mappings, updated {updated_count} existing mappings.',
                'type': 'success',
                'sticky': False,
            }
        }