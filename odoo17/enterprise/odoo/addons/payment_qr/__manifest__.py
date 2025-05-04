{
    'name': 'QR Payment Method',
    'version': '1.0',
    'category': 'Accounting/Payment',
    'summary': 'Add QR code payment method to invoices',
    'author': 'Nik Wanchaloem',
    'website': 'https://github.com/nikwanchaloem',
    'description': """
        This module adds support for QR code payments:
        * Upload multiple QR codes for payments
        * Display QR codes on invoices
        * Show QR code on payment page
        * Track QR code scans
        * Validate QR code formats
    """,
    'depends': ['account', 'payment', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'views/qr_payment_views.xml',
        'views/account_move_views.xml',
        'views/qr_code_scan_views.xml',
        'views/templates.xml',
        'data/payment_provider_data.xml',
        'report/invoice_report_templates.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
