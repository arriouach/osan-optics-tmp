from odoo import api, models, _
from odoo.osv import expression
from odoo.exceptions import ValidationError
from odoo.tools.safe_eval import safe_eval, time


class LimitVisibilityMixin(models.AbstractModel):
    _name = 'limit.visibility.mixin'
    _description = 'Limit Visibility Hack'
    _limit_domain = ""

    @api.model
    def _eval_context(self):
        """
            Returns a dictionary to use as evaluation context for
            limit.visibility.mixin _limit_domain.
        """
        return {
            'user': self.env.user.with_context({}),
            'time': time,
            'company_ids': self.env.companies.ids,
            'company_id': self.env.company.id,
        }

    def _get_limit_domain(self):
        eval_context = self._eval_context()
        try:
            domain = safe_eval(self._limit_domain, eval_context)
            expression.expression(domain, self.env[self._name].sudo())
        except Exception as e:
            raise ValidationError(_('Invalid domain: %s', e))
        return domain

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        if not self.env.user.has_group("base.group_system") and self._limit_domain:
            _domain = self._get_limit_domain()
            args = expression.AND([_domain, args or []])
        return super().name_search(name, args, operator, limit)

    @api.model
    def _search(self, domain, offset=0, limit=None, order=None):
        if self.env.context.get("limit_visibility") and self._limit_domain:
            _domain = self._get_limit_domain()
            domain = expression.AND([_domain, domain])
        return super()._search(domain, offset, limit, order)

    def fetch(self, field_names):
        return super(LimitVisibilityMixin, self.with_context(limit_visibility=False)).fetch(field_names)

    @api.model
    def read_group(self, domain, fields, groupby, offset=0, limit=None, orderby=False, lazy=True):
        if self.env.context.get("limit_visibility") and self._limit_domain:
            _domain = self._get_limit_domain()
            domain = expression.AND([_domain, domain])
        return super().read_group(domain, fields, groupby, offset, limit, orderby, lazy)

    @api.model
    def _read_group(self, domain, groupby=(), aggregates=(), having=(), offset=0, limit=None, order=None):
        if self.env.context.get("limit_visibility") and self._limit_domain:
            _domain = self._get_limit_domain()
            domain = expression.AND([_domain, domain])
        return super()._read_group(domain, groupby, aggregates, having, offset, limit, order)
