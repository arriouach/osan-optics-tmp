from odoo import http, _
from odoo.http import request
import logging

_logger = logging.getLogger(__name__)


class ZidOAuthController(http.Controller):

    @http.route(['/zid/callback', '/api/zid/oauth/callback'], type='http', auth='public', methods=['GET'], csrf=False)
    def zid_oauth_callback(self, code=None, state=None, error=None, **kwargs):
        """Handle OAuth callback from Zid (or Proxy)"""

        _logger.info("=" * 80)
        _logger.info("🔔 ZID OAUTH CALLBACK RECEIVED")
        _logger.info(f"📍 Route: /zid/callback")
        _logger.info(f"🔑 Code present: {code is not None}")
        _logger.info(f"🏷️  State: {state}")
        _logger.info(f"❌ Error: {error}")
        _logger.info(f"📦 All params: {kwargs}")
        _logger.info(f"🔐 Access token present: {bool(kwargs.get('access_token'))}")
        _logger.info(f"🔐 Authorization token present: {bool(kwargs.get('authorization_token'))}")
        _logger.info("=" * 80)

        if error:
            _logger.error(f"OAuth error: {error}")
            return request.render('zid_integration.oauth_error', {
                'error': error,
                'error_description': kwargs.get('error_description', 'Unknown error occurred')
            })

        try:
            # Find the connector
            connector = None
            if state:
                try:
                    connector_id = int(state)
                    connector = request.env['zid.connector'].sudo().browse(connector_id)
                    if not connector.exists():
                        connector = None
                except:
                    pass

            if not connector:
                # Fallback search
                connector = request.env['zid.connector'].sudo().search([
                    ('authorization_status', '=', 'not_connected')
                ], limit=1, order='create_date desc')

            if not connector:
                return request.render('zid_integration.oauth_error', {
                    'error': 'no_connector',
                    'error_description': 'No connector found to handle this callback.'
                })

            # In proxy architecture, OAuth is handled entirely by the proxy server
            # The callback should not receive tokens directly
            _logger.warning("OAuth callback received in proxy mode - this should not happen")
            _logger.warning("OAuth should be handled entirely by the proxy server")
            
            return request.render('zid_integration.oauth_error', {
                'error': 'proxy_mode',
                'error_description': 'OAuth is handled by proxy server. Please use the Connect to Zid button in the connector form.'
            })

        except Exception as e:
            _logger.error(f"❌ OAuth callback processing error: {str(e)}")
            import traceback
            _logger.error(traceback.format_exc())
            return request.render('zid_integration.oauth_error', {
                'error': 'processing_error',
                'error_description': f'Failed to process OAuth callback: {str(e)}'
            })

    @http.route('/zid/connect/<int:connector_id>', type='http', auth='user', methods=['GET'])
    def zid_connect_with_state(self, connector_id, **kwargs):
        """Start OAuth process with connector ID in state parameter"""

        try:
            connector = request.env['zid.connector'].browse(connector_id)
            if not connector.exists():
                return request.not_found()

            # Generate OAuth URL with state parameter
            auth_url = connector.get_authorization_url()

            # Add state parameter with connector ID
            separator = '&' if '?' in auth_url else '?'
            auth_url_with_state = f"{auth_url}{separator}state={connector_id}"

            # Use werkzeug redirect for external URLs
            from werkzeug.utils import redirect
            return redirect(auth_url_with_state)

        except Exception as e:
            _logger.error(f"Error starting OAuth process: {str(e)}")
            return request.render('zid_integration.oauth_error', {
                'error': 'connection_error',
                'error_description': str(e)
            })

    @http.route('/zid/test/<int:connector_id>', type='http', auth='user', methods=['GET'])
    def test_zid_connection(self, connector_id, **kwargs):
        """Test Zid API connection"""

        try:
            connector = request.env['zid.connector'].browse(connector_id)
            if not connector.exists():
                return request.not_found()

            # Test the connection
            result = connector.api_request('managers/account/profile')

            return request.make_response(
                f"<h2>Connection Test Successful!</h2>"
                f"<p>Store: {result.get('store', {}).get('name', 'Unknown')}</p>"
                f"<p>Connected at: {connector.connection_date}</p>"
                f"<script>setTimeout(function(){{window.close();}}, 3000);</script>",
                headers={'Content-Type': 'text/html'}
            )

        except Exception as e:
            _logger.error(f"Connection test error: {str(e)}")
            return request.make_response(
                f"<h2>Connection Test Failed!</h2>"
                f"<p>Error: {str(e)}</p>"
                f"<script>setTimeout(function(){{window.close();}}, 5000);</script>",
                headers={'Content-Type': 'text/html'}
            )