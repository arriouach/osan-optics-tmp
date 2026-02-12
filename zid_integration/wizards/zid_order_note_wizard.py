from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class ZidOrderNoteWizard(models.TransientModel):
    _name = 'zid.order.note.wizard'
    _description = 'Add Note to Zid Order'

    zid_order_id = fields.Many2one(
        'zid.sale.order',
        string='Zid Order',
        required=True,
        readonly=True
    )

    comment = fields.Text(
        string='Comment',
        required=True,
        help='Maximum 100 characters'
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self.env.context.get('active_id'):
            res['zid_order_id'] = self.env.context['active_id']
        return res

    @api.constrains('comment')
    def _check_comment_length(self):
        for record in self:
            if record.comment and len(record.comment) > 100:
                raise UserError(_('Comment must be 100 characters or less. Current length: %d') % len(record.comment))

    def action_add_note(self):
        """Add note to order in Zid"""
        self.ensure_one()

        if not self.zid_order_id.zid_connector_id.is_connected:
            raise UserError(_('Zid connector is not connected'))

        if not self.comment:
            raise UserError(_('Please enter a comment'))

        try:
            connector = self.zid_order_id.zid_connector_id
            endpoint = f"managers/store/orders/{self.zid_order_id.zid_order_id}/add-order-comment"

            # Make API request
            response = connector.api_request(
                endpoint=endpoint,
                method='POST',
                data={'comment': self.comment}
            )

            # Log in Odoo
            self.zid_order_id.message_post(
                body=_('Added note to Zid order: %s') % self.comment
            )

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': _('Note added successfully'),
                    'type': 'success',
                    'sticky': False,
                }
            }

        except Exception as e:
            _logger.error(f"Failed to add order note: {str(e)}")
            raise UserError(_('Failed to add note: %s') % str(e))