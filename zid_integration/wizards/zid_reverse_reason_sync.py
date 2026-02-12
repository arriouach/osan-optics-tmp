from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class ZidReverseReasonSync(models.TransientModel):
    _name = 'zid.reverse.reason.sync'
    _description = 'Sync Reverse Reasons from Zid'

    zid_connector_id = fields.Many2one(
        'zid.connector',
        string='Zid Connector',
        required=True,
        default=lambda self: self._get_default_connector()
    )

    add_new_reason = fields.Boolean(
        string='Add New Reason',
        default=False
    )

    new_reason_name = fields.Char(
        string='New Reason Name',
        help='Enter the name of the new reason to add'
    )

    @api.model
    def _get_default_connector(self):
        """Get default active connector"""
        connector = self.env['zid.connector'].search([
            ('authorization_status', '=', 'connected'),
            ('active', '=', True)
        ], limit=1)
        return connector

    def action_sync_reasons(self):
        """Sync reverse reasons from Zid"""
        self.ensure_one()

        if not self.zid_connector_id.is_connected:
            raise UserError(_('Selected connector is not connected to Zid'))

        try:
            # Make API request
            response = self.zid_connector_id.api_request(
                endpoint='managers/store/reverse-orders/reasons',
                method='GET'
            )

            if not response:
                raise UserError(_('No response from Zid API'))

            # Handle response
            reasons = response.get('order-reverse-reasons', [])

            if not reasons:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Info'),
                        'message': _('No reverse reasons found in Zid'),
                        'type': 'info',
                    }
                }

            # Create or update reasons
            reason_model = self.env['zid.reverse.reason']
            created_count = 0
            updated_count = 0

            for reason_data in reasons:
                existing = reason_model.search([
                    ('zid_reason_id', '=', reason_data.get('id')),
                    ('zid_connector_id', '=', self.zid_connector_id.id)
                ], limit=1)

                if existing:
                    updated_count += 1
                else:
                    created_count += 1

                reason_model.create_or_update_from_zid(
                    reason_data,
                    self.zid_connector_id.id
                )

            message = _('Sync completed!\nCreated: %d reasons\nUpdated: %d reasons') % (
                created_count, updated_count
            )

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': message,
                    'type': 'success',
                }
            }

        except Exception as e:
            _logger.error(f"Failed to sync reverse reasons: {str(e)}")
            raise UserError(_('Failed to sync reasons: %s') % str(e))

    def action_add_reason(self):
        """Add new reverse reason to Zid"""
        self.ensure_one()

        if not self.new_reason_name:
            raise UserError(_('Please enter a reason name'))

        if not self.zid_connector_id.is_connected:
            raise UserError(_('Selected connector is not connected to Zid'))

        try:
            # Make API request via proxy
            response = self.zid_connector_id.api_request(
                endpoint='managers/store/reverse-orders/reasons',
                method='POST',
                data={'name': self.new_reason_name}
            )

            # Parse response and create local record
            if response and 'order-reverse-reason' in response:
                reason_data = response['order-reverse-reason']
                self.env['zid.reverse.reason'].create_or_update_from_zid(
                    reason_data,
                    self.zid_connector_id.id
                )

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': _('Reason added successfully'),
                    'type': 'success',
                }
            }

        except Exception as e:
            _logger.error(f"Failed to add reverse reason: {str(e)}")
            raise UserError(_('Failed to add reason: %s') % str(e))