{
    'name': 'Warehouse',
    'author': 'James Jessada',
    'version': '1.0',
    'category': 'Operations',
    'depends': [
        'sale_management', 
        'account', 
        'base', 
        'portal', 
        'process_tracker', 
        'mail'
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/actions.xml',
        'views/menus.xml',
        'views/task_views.xml',
        'views/pickup_request_views.xml',
    ],
    # 'assets': {
    #     'web.assets_backend': [
    #         'warehouse/static/src/js/warehouse_task_control_panel.js'
    #         'warehouse/static/src/xml/warehouse_task_control_panel.xml'
    #     ]
    # },
    'installable': True,
    'application': True,
}

