from odoo import models, fields, api, _

class ZidPaymentMapping(models.Model):
    _name = 'zid.payment.mapping'
    _description = 'Zid Payment Method Mapping'
    _rec_name = 'payment_method_code'

    zid_connector_id = fields.Many2one(
        'zid.connector',
        string='Zid Connector',
        required=True,
        ondelete='cascade'
    )

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        related='zid_connector_id.company_id',
        store=True,
        readonly=True
    )


    # Zid Side
    payment_method_code = fields.Char(
        string='Zid Payment Code',
        required=True,
        help="The code received from Zid (e.g., 'cod', 'credit_card', 'apple_pay')"
    )
    
    payment_method_name = fields.Char(
        string='Zid Payment Name',
        help="Human readable name for reference"
    )

    # Odoo Side
    payment_journal_id = fields.Many2one(
        'account.journal',
        string='Payment Journal',
        domain=[('type', 'in', ('bank', 'cash'))],
        required=True,
        help="The journal to record payments in"
    )

    payment_term_id = fields.Many2one(
        'account.payment.term',
        string='Payment Term',
        help="Payment term to set on the Sale Order"
    )

    # Workflow Configuration
    auto_create_invoice = fields.Boolean(
        string='Auto Create Invoice',
        default=True,
        help="Automatically create invoice when order is confirmed"
    )

    auto_validate_invoice = fields.Boolean(
        string='Auto Validate Invoice',
        default=True,
        help="Automatically validate the invoice"
    )

    auto_register_payment = fields.Boolean(
        string='Auto Register Payment',
        default=True,
        help="Automatically register payment if the order is paid in Zid"
    )

    _sql_constraints = [
        ('unique_mapping', 'unique(zid_connector_id, payment_method_code)', 
         'Mapping for this payment method already exists for this connector!')
    ]
