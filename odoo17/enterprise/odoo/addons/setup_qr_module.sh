#!/bin/bash

# Set the module name
MODULE_NAME="payment_qr"

# Remove existing module directory if it exists
rm -rf $MODULE_NAME

# Create main module directory
mkdir -p $MODULE_NAME/{models,controllers,views,security,data,report,static/{src/{js,css,xml},description}}

# Create __init__.py files
echo "from . import models
from . import controllers" > $MODULE_NAME/__init__.py

echo "from . import qr_payment" > $MODULE_NAME/models/__init__.py
echo "from . import main" > $MODULE_NAME/controllers/__init__.py

# Create manifest file
cat > $MODULE_NAME/__manifest__.py << 'EOF'
{
    'name': 'QR Payment Method',
    'version': '1.0',
    'category': 'Accounting/Payment',
    'summary': 'Add QR code payment method to invoices',
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
EOF

# Create models file
cat > $MODULE_NAME/models/qr_payment.py << 'EOF'
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import base64
import imghdr
import qrcode
from io import BytesIO
import logging

_logger = logging.getLogger(__name__)

class QRCode(models.Model):
    _name = 'qr.code'
    _description = 'QR Code'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(required=True, tracking=True)
    qr_code = fields.Binary(string='QR Code', attachment=True, required=True, tracking=True)
    qr_code_filename = fields.Char()
    provider_id = fields.Many2one('payment.provider', string='Payment Provider', required=True)
    active = fields.Boolean(default=True, tracking=True)
    scan_count = fields.Integer(string='Scan Count', compute='_compute_scan_count', store=True)
    description = fields.Text()
    last_scan = fields.Datetime(string='Last Scanned', compute='_compute_last_scan')
    scan_ids = fields.One2many('qr.code.scan', 'qr_code_id', string='Scans')
    
    @api.constrains('qr_code')
    def _check_qr_code_format(self):
        for record in self:
            if record.qr_code:
                try:
                    image_data = base64.b64decode(record.qr_code)
                    image_type = imghdr.what(None, image_data)
                    if image_type not in ['png', 'jpeg', 'jpg']:
                        raise ValidationError(_('QR Code must be a PNG or JPEG image'))
                except Exception as e:
                    raise ValidationError(_('Invalid image format: %s') % str(e))

    @api.depends('scan_ids')
    def _compute_scan_count(self):
        for record in self:
            record.scan_count = len(record.scan_ids)

    @api.depends('scan_ids')
    def _compute_last_scan(self):
        for record in self:
            last_scan = self.env['qr.code.scan'].search([
                ('qr_code_id', '=', record.id)
            ], order='scan_date desc', limit=1)
            record.last_scan = last_scan.scan_date if last_scan else False
EOF

# Continue models file with additional classes
cat >> $MODULE_NAME/models/qr_payment.py << 'EOF'

class QRCodeScan(models.Model):
    _name = 'qr.code.scan'
    _description = 'QR Code Scan'
    _order = 'scan_date desc'

    qr_code_id = fields.Many2one('qr.code', string='QR Code', required=True)
    scan_date = fields.Datetime(default=fields.Datetime.now, required=True)
    ip_address = fields.Char()
    user_agent = fields.Char()
    invoice_id = fields.Many2one('account.move', string='Related Invoice')

class QRPaymentProvider(models.Model):
    _inherit = 'payment.provider'

    qr_code_ids = fields.One2many('qr.code', 'provider_id', string='QR Codes')
    provider_code = fields.Selection(
        selection_add=[('qr_payment', 'QR Payment')],
        ondelete={'qr_payment': 'set default'}
    )
    default_qr_code_id = fields.Many2one('qr.code', string='Default QR Code')

    def _get_default_payment_method_id(self):
        self.ensure_one()
        if self.code != 'qr_payment':
            return super()._get_default_payment_method_id()
        return self.env.ref('payment.payment_method_manual').id

class AccountMove(models.Model):
    _inherit = 'account.move'

    qr_code_id = fields.Many2one('qr.code', string='Payment QR Code', readonly=True)
    qr_scan_count = fields.Integer(related='qr_code_id.scan_count', string='QR Scan Count')
    qr_last_scan = fields.Datetime(related='qr_code_id.last_scan', string='Last QR Scan')

    def action_post(self):
        res = super(AccountMove, self).action_post()
        for move in self:
            if move.move_type == 'out_invoice':
                qr_provider = self.env['payment.provider'].search([
                    ('code', '=', 'qr_payment'),
                    ('state', '=', 'enabled')
                ], limit=1)
                if qr_provider and qr_provider.default_qr_code_id:
                    move.qr_code_id = qr_provider.default_qr_code_id.id
        return res

    def action_view_qr_scans(self):
        self.ensure_one()
        return {
            'name': _('QR Code Scans'),
            'view_mode': 'tree,form',
            'res_model': 'qr.code.scan',
            'domain': [('qr_code_id', '=', self.qr_code_id.id)],
            'type': 'ir.actions.act_window',
            'context': {'default_qr_code_id': self.qr_code_id.id},
        }
EOF

# Create controller file
cat > $MODULE_NAME/controllers/main.py << 'EOF'
from odoo import http
from odoo.http import request

class QRCodeController(http.Controller):
    @http.route(['/qr/scan/<int:qr_code_id>'], type='http', auth='public', website=True)
    def qr_code_scan(self, qr_code_id, **kwargs):
        qr_code = request.env['qr.code'].sudo().browse(qr_code_id)
        if qr_code.exists():
            # Record the scan
            request.env['qr.code.scan'].sudo().create({
                'qr_code_id': qr_code.id,
                'ip_address': request.httprequest.remote_addr,
                'user_agent': request.httprequest.user_agent.string,
            })
            # Redirect to payment portal or show payment instructions
            return request.render('payment_qr.qr_code_scan_success', {
                'qr_code': qr_code,
            })
        return request.not_found()
EOF

# Create security file
cat > $MODULE_NAME/security/ir.model.access.csv << 'EOF'
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_qr_code_user,qr.code.user,model_qr_code,account.group_account_user,1,1,1,0
access_qr_code_manager,qr.code.manager,model_qr_code,account.group_account_manager,1,1,1,1
access_qr_code_scan_user,qr.code.scan.user,model_qr_code_scan,account.group_account_user,1,1,1,0
access_qr_code_scan_manager,qr.code.scan.manager,model_qr_code_scan,account.group_account_manager,1,1,1,1
EOF

# Create QR payment views file
cat > $MODULE_NAME/views/qr_payment_views.xml << 'EOF'
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <!-- QR Code Form View -->
    <record id="view_qr_code_form" model="ir.ui.view">
        <field name="name">qr.code.form</field>
        <field name="model">qr.code</field>
        <field name="arch" type="xml">
            <form>
                <sheet>
                    <div class="oe_button_box" name="button_box">
                        <button name="toggle_active" type="object" class="oe_stat_button" icon="fa-archive">
                            <field name="active" widget="boolean_button"/>
                        </button>
                    </div>
                    <div class="oe_title">
                        <h1>
                            <field name="name" placeholder="e.g. Company Bank QR"/>
                        </h1>
                    </div>
                    <group>
                        <group>
                            <field name="provider_id"/>
                            <field name="scan_count"/>
                            <field name="last_scan"/>
                        </group>
                        <group>
                            <field name="qr_code" widget="image"/>
                            <field name="qr_code_filename" invisible="1"/>
                        </group>
                    </group>
                    <notebook>
                        <page string="Description" name="description">
                            <field name="description"/>
                        </page>
                        <page string="Scans" name="scans">
                            <field name="scan_ids">
                                <tree>
                                    <field name="scan_date"/>
                                    <field name="ip_address"/>
                                    <field name="user_agent"/>
                                    <field name="invoice_id"/>
                                </tree>
                            </field>
                        </page>
                    </notebook>
                </sheet>
                <div class="oe_chatter">
                    <field name="message_follower_ids" widget="mail_followers"/>
                    <field name="activity_ids" widget="mail_activity"/>
                    <field name="message_ids" widget="mail_thread"/>
                </div>
            </form>
        </field>
    </record>

    <!-- QR Code Tree View -->
    <record id="view_qr_code_tree" model="ir.ui.view">
        <field name="name">qr.code.tree</field>
        <field name="model">qr.code</field>
        <field name="arch" type="xml">
            <tree>
                <field name="name"/>
                <field name="provider_id"/>
                <field name="scan_count"/>
                <field name="last_scan"/>
                <field name="active"/>
            </tree>
        </field>
    </record>

    <!-- QR Code Search View -->
    <record id="view_qr_code_search" model="ir.ui.view">
        <field name="name">qr.code.search</field>
        <field name="model">qr.code</field>
        <field name="arch" type="xml">
            <search>
                <field name="name"/>
                <field name="provider_id"/>
                <filter string="Archived" name="inactive" domain="[('active', '=', False)]"/>
            </search>
        </field>
    </record>

    <!-- QR Code Action -->
    <record id="action_qr_code_list" model="ir.actions.act_window">
        <field name="name">QR Codes</field>
        <field name="res_model">qr.code</field>
        <field name="view_mode">tree,form</field>
        <field name="search_view_id" ref="view_qr_code_search"/>
        <field name="help" type="html">
            <p class="o_view_nocontent_smiling_face">
                Create your first QR Code
            </p>
        </field>
    </record>

    <!-- QR Code Scan Tree View -->
    <record id="view_qr_code_scan_tree" model="ir.ui.view">
        <field name="name">qr.code.scan.tree</field>
        <field name="model">qr.code.scan</field>
        <field name="arch" type="xml">
            <tree>
                <field name="scan_date"/>
                <field name="qr_code_id"/>
                <field name="ip_address"/>
                <field name="invoice_id"/>
            </tree>
        </field>
    </record>

    <!-- QR Code Scan Action -->
    <record id="action_qr_code_scan_list" model="ir.actions.act_window">
        <field name="name">QR Scans</field>
        <field name="res_model">qr.code.scan</field>
        <field name="view_mode">tree</field>
        <field name="help" type="html">
            <p class="o_view_nocontent_smiling_face">
                No QR code scans yet
            </p>
        </field>
    </record>

    <!-- Payment Provider Form View Extension -->
    <record id="qr_payment_provider_form" model="ir.ui.view">
        <field name="name">qr.payment.provider.form</field>
        <field name="model">payment.provider</field>
        <field name="inherit_id" ref="payment.payment_provider_form"/>
        <field name="arch" type="xml">
            <xpath expr="//notebook" position="inside">
                <page string="QR Codes" attrs="{'invisible': [('code', '!=', 'qr_payment')]}">
                    <group>
                        <field name="default_qr_code_id" domain="[('provider_id', '=', active_id)]"/>
                    </group>
                    <field name="qr_code_ids" context="{'default_provider_id': active_id}">
                        <tree>
                            <field name="name"/>
                            <field name="scan_count"/>
                            <field name="last_scan"/>
                            <field name="active"/>
                        </tree>
                    </field>
                </page>
            </xpath>
        </field>
    </record>

    <!-- Menu Items -->
    <menuitem id="menu_qr_code_root" 
              name="QR Codes"
              parent="account.menu_finance_configuration"
              sequence="5"/>

    <menuitem id="menu_qr_code_list"
              name="QR Codes"
              action="action_qr_code_list"
              parent="menu_qr_code_root"
              sequence="1"/>

    <menuitem id="menu_qr_code_scans"
              name="QR Scans"
              action="action_qr_code_scan_list"
              parent="menu_qr_code_root"
              sequence="2"/>
</odoo>
EOF

# Create account move views file
cat > $MODULE_NAME/views/account_move_views.xml << 'EOF'
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="view_move_form_inherit_qr" model="ir.ui.view">
        <field name="name">account.move.form.inherit.qr</field>
        <field name="model">account.move</field>
        <field name="inherit_id" ref="account.view_move_form"/>
        <field name="arch" type="xml">
            <xpath expr="//div[@name='button_box']" position="inside">
                <button class="oe_stat_button" type="object" name="action_view_qr_scans" 
                        icon="fa-qrcode" attrs="{'invisible': [('qr_code_id', '=', False)]}">
                    <field name="qr_scan_count" widget="statinfo" string="QR Scans"/>
                </button>
            </xpath>
            <xpath expr="//group[@name='payment_info']" position="inside">
                <field name="qr_code_id" readonly="1"/>
                <field name="qr_last_scan" readonly="1"/>
            </xpath>
        </field>
    </record>
</odoo>
EOF

# Create QR code scan views file
cat > $MODULE_NAME/views/qr_code_scan_views.xml << 'EOF'
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <!-- QR Code Scan Form View -->
    <record id="view_qr_code_scan_form" model="ir.ui.view">
        <field name="name">qr.code.scan.form</field>
        <field name="model">qr.code.scan</field>
        <field name="arch" type="xml">
            <form>
                <sheet>
                    <group>
                        <group>
                            <field name="qr_code_id"/>
                            <field name="scan_date"/>
                            <field name="invoice_id"/>
                        </group>
                        <group>
                            <field name="ip_address"/>
                            <field name="user_agent"/>
                        </group>
                    </group>
                </sheet>
            </form>
        </field>
    </record>

    <!-- QR Code Scan Search View -->
    <record id="view_qr_code_scan_search" model="ir.ui.view">
        <field name="name">qr.code.scan.search</field>
        <field name="model">qr.code.scan</field>
        <field name="arch" type="xml">
            <search>
                <field name="qr_code_id"/>
                <field name="invoice_id"/>
                <field name="scan_date"/>
                <group expand="0" string="Group By">
                    <filter string="QR Code" name="group_by_qr_code" context="{'group_by': 'qr_code_id'}"/>
                    <filter string="Invoice" name="group_by_invoice" context="{'group_by': 'invoice_id'}"/>
                    <filter string="Scan Date" name="group_by_date" context="{'group_by': 'scan_date:day'}"/>
                </group>
            </search>
        </field>
    </record>
</odoo>
EOF

# Create data file
cat > $MODULE_NAME/data/payment_provider_data.xml << 'EOF'
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <data noupdate="1">
        <record id="payment_provider_qr" model="payment.provider">
            <field name="name">QR Payment</field>
            <field name="code">qr_payment</field>
            <field name="state">enabled</field>
            <field name="company_id" ref="base.main_company"/>
        </record>
    </data>
</odoo>
EOF

# Create report template
cat > $MODULE_NAME/report/invoice_report_templates.xml << 'EOF'
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <template id="report_invoice_document_inherit_qr" inherit_id="account.report_invoice_document">
        <xpath expr="//div[@name='payment_term']" position="after">
            <div t-if="o.qr_code_id" class="row">
                <div class="col-6">
                    <strong>Payment QR Code:</strong>
                    <div class="mt-2">
                        <img t-att-src="'data:image/png;base64,%s' % o.qr_code_id.qr_code" style="max-width: 200px;"/>
                    </div>
                    <p class="text-muted mt-2">Scan to pay</p>
                </div>
            </div>
        </xpath>
    </template>
</odoo>
EOF

# Create QR scan success template
cat > $MODULE_NAME/views/templates.xml << 'EOF'
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <template id="qr_code_scan_success" name="QR Code Scan Success">
        <t t-call="web.layout">
            <div class="container mt-4">
                <div class="alert alert-success">
                    <h4>QR Code Scanned Successfully!</h4>
                    <p>Thank you for scanning the QR code for <t t-esc="qr_code.name"/>.</p>
                    <p>Please follow the payment instructions below:</p>
                    <div t-field="qr_code.description"/>
                </div>
            </div>
        </t>
    </template>
</odoo>
EOF

# Create empty __init__.py files for directories
touch $MODULE_NAME/report/__init__.py
touch $MODULE_NAME/static/__init__.py

# Set proper permissions
chmod -R 755 $MODULE_NAME

echo "Module $MODULE_NAME has been created successfully!"
echo "Please move the module folder to your Odoo addons directory"