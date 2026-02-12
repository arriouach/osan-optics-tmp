{
    'name': 'Zid Integration',
    'version': '18.0.1.0.0',
    'summary': 'Integration with Zid E-commerce Platform',
    'description': """
        Zid Integration Module
        ======================

        This module provides integration with Zid e-commerce platform.

        Features:
        ---------
        * OAuth 2.0 authentication with Zid
        * Secure token management
        * Easy connection setup
        * Store information synchronization
        * API connection testing

        Developed by Cloudmen
    """,
    'author': 'Cloudmen',
    'website': 'https://www.cloudmen.ae',
    'category': 'Sales/Point of Sale',
    'depends': ['base', 'web','mail','stock','product','sale','purchase'],
    'data': [
        'security/groups.xml',
        'security/ir.model.access.csv',
        'security/zid_security.xml',
        
        # Actions that are referenced by menus (must load very early)
        'views/zid_dashboard_actions.xml',
        
        'data/server_actions.xml',
        'data/ir_cron_data.xml',
        'data/cron_jobs.xml',
        
        # All views first (except product_template which references wizard actions)
        'views/zid_queue_ept_views.xml',
        'views/zid_locations.xml',
        'views/stock_locations.xml',
        'views/zid_stock_sync_views.xml',
        'views/zid_stock_update_log_views.xml',
        'views/zid_product_views.xml',
        'views/zid_product_line_views.xml',
        'views/zid_product_category_views.xml',
        'views/zid_abandoned_cart_views.xml',
        'views/zid_payout_views.xml',
        'views/webhook_views.xml',
        'views/zid_sale_order_views.xml',
        'views/zid_reverse_order_views.xml',
        'views/zid_reverse_reason_views.xml',
        'views/zid_variant_views.xml',
        'views/zid_variant_stock_line_views.xml',
        'views/zid_attribute_views.xml',
        'views/zid_payment_mapping_views.xml',
        'views/zid_dashboard_view.xml',
        'views/oauth_templates.xml',
        'views/sale_order_views.xml',

        # Menu structure (must be loaded after dashboard actions are defined)
        'views/menu_views.xml',
        
        # Views that reference menu items (load after menu_views.xml)
        'views/zid_diagnostic_views.xml',

        # All wizards second
        'wizards/zid_products_connector_views.xml',
        'wizards/zid_order_fetch_wizard.xml',
        'wizards/zid_product_update_wizard.xml',
        'wizards/zid_stock_sync_wizard_views.xml',
        'wizards/zid_location_mapping_wizard_views.xml',
        'wizards/zid_stock_debug_wizard_views.xml',
        'wizards/zid_sale_order_connector.xml',
        'wizards/zid_order_status_updater.xml',
        'wizards/zid_order_note_wizard.xml',
        'wizards/zid_reverse_reason_sync.xml',
        'wizards/zid_reverse_waybill_create.xml',
        'wizards/zid_product_relink_wizard.xml',
        'wizards/zid_variant_connector.xml',
        'wizards/zid_attribute_connector_views.xml',
        'wizards/zid_product_sync_wizard.xml',
        'wizards/zid_stock_update_wizard.xml',
        'wizards/zid_customer_sync_wizard.xml',
        'wizards/zid_abandoned_cart_fetch_wizard.xml',
        'wizards/zid_bulk_sync_wizard.xml',
        'wizards/zid_health_report_wizard.xml',
        'wizards/zid_product_matching_wizard_views.xml',
        'wizards/zid_automation_wizard_views.xml',
        'wizards/zid_payment_mapping_wizard_views.xml',
        'wizards/zid_sales_team_wizard_views.xml',
        
        # Product template view after wizards (references wizard actions)
        'views/product_template.xml',
        
        # Connector views last (after all actions are defined)
        'views/zid_connector_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'zid_integration/static/src/css/zid_dashboard.css',
        ],
    },
    'installable': True,
    'auto_install': False,
    'application': True,
    'license': 'LGPL-3',
    'sequence': 100,
    'post_init_hook': 'post_init_hook',
}
