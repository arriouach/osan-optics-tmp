# -*- coding: utf-8 -*-
import requests
import base64
import json
from odoo import models, fields, api
from odoo.exceptions import UserError


class PosOrder(models.Model):
    _inherit = 'pos.order'

    @api.model
    def _order_fields(self, ui_order):
        """Override to trigger BusinessChat send after order creation"""
        res = super(PosOrder, self)._order_fields(ui_order)
        return res

    def _create_invoice(self, move_vals):
        """Override to automatically send invoice to BusinessChat after invoice creation"""
        move = super(PosOrder, self)._create_invoice(move_vals)
        
        # Check if move is actually a move object (not False/True) and partner exists
        if move and isinstance(move, type(self.env['account.move'])) and self.partner_id and self.account_move:
            try:
                # Commit the transaction to ensure attachment is accessible
                self.env.cr.commit()
                # Small delay to ensure attachment is fully accessible
                import time
                time.sleep(2)
                self.action_send_invoice_to_businesschat(auto_trigger=True)
            except Exception as e:
                # Log error but don't block invoice creation
                self.message_post(body=f"⚠️ Auto-send to BusinessChat failed: {str(e)}")
        
        return move

    def action_send_invoice_to_businesschat(self, auto_trigger=False):
        """Send invoice PDF to BusinessChat webhook"""
        self.ensure_one()
        
        trigger_source = "🤖 AUTO-TRIGGER" if auto_trigger else "👆 MANUAL BUTTON"
        
        if not self.account_move:
            raise UserError("No invoice found for this POS order.")
        
        invoice = self.account_move
        
        # Ensure invoice is a valid record, not a boolean
        if not invoice or not hasattr(invoice, 'name'):
            raise UserError("Invalid invoice record.")
        
        # 1. Generate PDF using the correct method
        report_xml_id = 'account.report_invoice'
        pdf_content, content_type = self.env['ir.actions.report'].sudo()._render_qweb_pdf(
            report_xml_id, [invoice.id]
        )
        
        # 2. Create Attachment (datas field expects base64-encoded content)
        invoice_name = invoice.name if invoice.name else 'Invoice'
        attachment = self.env['ir.attachment'].create({
            'name': f"Invoice_{invoice_name.replace('/', '_')}.pdf",
            'type': 'binary',
            'datas': base64.b64encode(pdf_content),
            'res_model': 'pos.order',
            'res_id': self.id,
            'mimetype': 'application/pdf',
            'public': True,
        })
        
        # Ensure attachment is committed to database
        if auto_trigger:
            self.env.cr.commit()
        
        # 3. Prepare Webhook payload
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        file_url = f"{base_url}/web/content/{attachment.id}?download=true"
        
        payload = {
            "CustomerName": self.partner_id.name,
            "CustomerNumber": self.partner_id.mobile or self.partner_id.phone or '',
            "FileURL": file_url,
            "InvoiceNumber": self.account_move.name
        }
        
        # Log the payload for debugging
        import json
        debug_message = f"""🔍 Debug Info - BusinessChat Webhook
{trigger_source}

Attachment ID: {attachment.id}
File URL: {file_url}
PDF Size: {len(pdf_content)} bytes
Base64 Size: {len(base64.b64encode(pdf_content))} bytes

Webhook Payload:
{json.dumps(payload, indent=2)}
"""
        self.message_post(body=debug_message)
        
        # 4. Send Webhook
        try:
            url = "https://kotlin-web-api.businesschat.io/webhook/7782/automations/20866"
            response = requests.post(url, json=payload, timeout=15)
            response.raise_for_status()
            
            # Log successful response
            success_message = f"""{trigger_source} ✅ Success - Invoice Sent to BusinessChat

Status Code: {response.status_code}
Response: {response.text[:500]}
"""
            self.message_post(body=success_message)
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Success',
                    'message': 'Invoice sent to BusinessChat',
                    'type': 'success',
                    'sticky': False,
                }
            }
        except Exception as e:
            error_msg = f"""❌ Webhook Failed

Error: {str(e)}
File URL: {file_url}

Payload:
{json.dumps(payload, indent=2)}
"""
            self.message_post(body=error_msg)
            raise UserError(f"Webhook Failed: {str(e)}")
