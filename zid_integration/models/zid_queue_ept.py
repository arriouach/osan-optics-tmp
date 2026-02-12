from odoo import models, fields, api, _

class ZidQueueEpt(models.Model):
    _name = 'zid.queue.ept'
    _description = 'Zid Data Queue'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char(string='Name', required=True, copy=False, readonly=True, default=lambda self: _('New'))
    zid_connector_id = fields.Many2one('zid.connector', string='Zid Connector', required=True, readonly=True)
    company_id = fields.Many2one('res.company', string='Company', related='zid_connector_id.company_id', store=True)
    
    model_type = fields.Selection([
        ('order', 'Order'),
        ('product', 'Product'),
        ('customer', 'Customer')
    ], string='Type', required=True, default='order')
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('partial', 'Partially Done'),
        ('done', 'Done'),
        ('failed', 'Failed')
    ], string='Status', default='draft', tracking=True, compute='_compute_state', store=True)
    
    line_ids = fields.One2many('zid.queue.line.ept', 'queue_id', string='Queue Lines')
    
    total_count = fields.Integer(string='Total', compute='_compute_counts')
    draft_count = fields.Integer(string='Draft', compute='_compute_counts')
    done_count = fields.Integer(string='Done', compute='_compute_counts')
    failed_count = fields.Integer(string='Failed', compute='_compute_counts')
    
    @api.depends('line_ids.state')
    def _compute_state(self):
        for queue in self:
            if not queue.line_ids:
                queue.state = 'draft'
                continue
                
            states = queue.line_ids.mapped('state')
            if all(s == 'done' for s in states):
                queue.state = 'done'
            elif all(s == 'failed' for s in states):
                queue.state = 'failed'
            elif any(s == 'done' for s in states):
                queue.state = 'partial'
            else:
                queue.state = 'draft'

    @api.depends('line_ids.state')
    def _compute_counts(self):
        for queue in self:
            queue.total_count = len(queue.line_ids)
            queue.draft_count = len(queue.line_ids.filtered(lambda l: l.state == 'draft'))
            queue.done_count = len(queue.line_ids.filtered(lambda l: l.state == 'done'))
            queue.failed_count = len(queue.line_ids.filtered(lambda l: l.state == 'failed'))

    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('zid.queue.ept') or _('New')
        return super(ZidQueueEpt, self).create(vals)

    def action_process(self):
        """Process pending lines in this queue"""
        self.ensure_one()
        pending_lines = self.line_ids.filtered(lambda l: l.state in ['draft', 'failed'])
        pending_lines.process_queue_line()

    def action_cleanup_empty_queues(self):
        """Manual action to cleanup empty queues"""
        empty_queues = self.search([('line_ids', '=', False)])
        
        if empty_queues:
            count = len(empty_queues)
            empty_queues.unlink()
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Cleanup Complete'),
                    'message': _('Removed %d empty queues') % count,
                    'type': 'success',
                }
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('No Cleanup Needed'),
                    'message': _('No empty queues found'),
                    'type': 'info',
                }
            }

    @api.model
    def cron_process_queues(self):
        """Cron job to process pending queues"""
        queues = self.search([
            ('state', 'in', ['draft', 'partial']),
            ('line_ids.state', 'in', ['draft', 'failed'])
        ], limit=10)  # Process 10 queues at a time
        
        for queue in queues:
            try:
                queue.action_process()
                # Commit after each queue to save progress
                self.env.cr.commit()
            except Exception as e:
                _logger.error(f"Failed to process queue {queue.name}: {str(e)}")

    @api.model
    def cron_cleanup_empty_queues(self):
        """Cleanup old empty queues (older than 1 day)"""
        from datetime import datetime, timedelta
        
        cutoff_date = datetime.now() - timedelta(days=1)
        
        empty_queues = self.search([
            ('create_date', '<', cutoff_date),
            ('line_ids', '=', False)  # No queue lines
        ])
        
        if empty_queues:
            _logger.info(f"Cleaning up {len(empty_queues)} empty queues older than 1 day")
            empty_queues.unlink()
        
        # Also cleanup old completed queues (older than 7 days)
        old_completed_queues = self.search([
            ('create_date', '<', datetime.now() - timedelta(days=7)),
            ('state', '=', 'done')
        ])
        
        if old_completed_queues:
            _logger.info(f"Cleaning up {len(old_completed_queues)} completed queues older than 7 days")
            old_completed_queues.unlink()
