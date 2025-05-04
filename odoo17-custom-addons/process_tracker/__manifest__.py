{
    'name': 'Process Tracker',
    'author': 'James Jessada',
    'version': '1.0',
    'category': 'Operations',
    'depends': ['sale_management', 'account', 'base', 'portal'],
    'data': [
        'data/backlog_schedule_action.xml',
        'security/ir.model.access.csv',
        'views/wip_views.xml',
        'views/backlog_views.xml',
        'views/actions.xml',
        'views/menus.xml',
        'views/wip_backlog_dashboard_views.xml',
        'views/sale_order_view_inherit.xml',
        'views/sale_order_portal_inherit.xml'
    ],
    'installable': True,
    'application': True,
}
