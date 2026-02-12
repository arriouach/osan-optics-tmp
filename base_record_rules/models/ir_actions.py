from odoo import models


class IrActionsActWindow(models.Model):
    _inherit = "ir.actions.act_window"

    def read(self, fields=None, load="_classic_read"):
        self = self.with_context(
            limit_visibility=not self.env.user.has_group("base.group_system")
        )
        return super(IrActionsActWindow, self).read(fields, load)
