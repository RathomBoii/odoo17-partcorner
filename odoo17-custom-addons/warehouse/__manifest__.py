{
    'name': 'Warehouse',
    'author': 'James Jessada',
    'version': '1.0',
    'category': 'Operations',
    'depends': ['sale_management', 'account', 'base', 'portal', 'process_tracker'],
    'data': [
        'security/ir.model.access.csv',
        'views/actions.xml',
        'views/menus.xml',
        'views/task_views.xml',
    ],
    'installable': True,
    'application': True,
}

