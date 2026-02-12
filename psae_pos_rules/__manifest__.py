{
    "name": "PoS Shop Rules",
    "summary": """Record Rules on PoS""",
    "category": "Point of Sale",
    "version": "18.0.0.0.0",
    "author": "Odoo PS",
    "website": "https://www.odoo.com",
    "license": "OEEL-1",
    "depends": [
        'point_of_sale', 'pos_hr'
    ],
    "data": [
        "security/ir_rule.xml",
        "views/res_user_views.xml",
    ],
    "task_id": [4818079],
}
