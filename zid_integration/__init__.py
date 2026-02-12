from . import models
from . import controllers
from . import wizards


def post_init_hook(env):
    """Post-installation hook to open Zid Connectors page"""
    # This will be called after module installation
    # Return an action to open the Zid Connectors view
    action = env.ref('zid_integration.action_zid_connector')
    return {
        'type': 'ir.actions.client',
        'tag': 'display_notification',
        'params': {
            'title': 'Zid Integration Installed!',
            'message': 'Go to Zid Integration > Configuration > Zid Connectors to set up your first connection.',
            'type': 'success',
            'sticky': False,
            'next': {
                'type': 'ir.actions.act_window',
                'res_model': 'zid.connector',
                'view_mode': 'kanban,form',
                'views': [[False, 'kanban'], [False, 'form']],
                'target': 'current',
            }
        }
    }