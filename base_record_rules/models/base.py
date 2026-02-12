from odoo import api, models


class Base(models.AbstractModel):
    _inherit = "base"

    @api.model
    def web_search_read(
        self, domain, specification, offset=0, limit=None, order=None, count_limit=None
    ):
        self = self.with_context(
            limit_visibility=not self.env.user.has_group("base.group_system")
        )
        return super(Base, self).web_search_read(
            domain, specification, offset, limit, order, count_limit
        )

    @api.model
    def web_read_group(
        self, domain, fields, groupby, limit=None, offset=0, orderby=False, lazy=True
    ):
        self = self.with_context(
            limit_visibility=not self.env.user.has_group("base.group_system")
        )
        return super(Base, self).web_read_group(
            domain, fields, groupby, limit, offset, orderby, lazy
        )
