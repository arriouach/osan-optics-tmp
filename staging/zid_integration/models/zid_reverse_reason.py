from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class ZidReverseReason(models.Model):
    _name = 'zid.reverse.reason'
    _description = 'Zid Reverse Order Reasons'
    _rec_name = 'name'
    _order = 'name'

    zid_connector_id = fields.Many2one(
        'zid.connector',
        string='Zid Connector',
        required=True,
        ondelete='cascade'
    )

    zid_reason_id = fields.Char(
        string='Zid Reason ID',
        required=True,
        readonly=True
    )

    name = fields.Char(
        string='Reason',
        required=True
    )

    active = fields.Boolean(
        string='Active',
        default=True
    )

    usage_count = fields.Integer(
        string='Usage Count',
        readonly=True,
        default=0,
        help='Number of times this reason has been used'
    )

    _sql_constraints = [
        ('unique_zid_reason', 'UNIQUE(zid_connector_id, zid_reason_id)',
         'This reason already exists for this connector!')
    ]

    @api.model
    def create_or_update_from_zid(self, reason_data, connector_id):
        """Create or update reason from Zid data"""
        existing = self.search([
            ('zid_reason_id', '=', reason_data.get('id')),
            ('zid_connector_id', '=', connector_id)
        ], limit=1)

        vals = {
            'zid_connector_id': connector_id,
            'zid_reason_id': reason_data.get('id'),
            'name': reason_data.get('name', '').strip('"')
        }

        if existing:
            existing.write(vals)
            return existing
        else:
            return self.create(vals)