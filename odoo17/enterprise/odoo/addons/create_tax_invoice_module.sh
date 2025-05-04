#!/bin/bash

# Create main module directory
mkdir -p tax_invoice_th/{models,views,data,security}

# Create __init__.py files
echo "from . import models" > tax_invoice_th/__init__.py
echo "from . import account_move" > tax_invoice_th/models/__init__.py
echo "from . import account_payment" >> tax_invoice_th/models/__init__.py

# Create manifest file
cat > tax_invoice_th/__manifest__.py << 'EOL'
{
    'name': 'Thai Tax Invoice',
    'version': '17.0.1.0.0',
    'category': 'Accounting/Localizations',
    'summary': 'Generate Tax Invoice after payment for Thailand',
    'depends': ['account'],
    'data': [
        'security/ir.model.access.csv',
        'views/account_move_views.xml',
        'data/sequences.xml',
    ],
    'license': 'LGPL-3',
    'installable': True,
    'auto_install': False,
}
EOL

# Create account_move.py
cat > tax_invoice_th/models/account_move.py << 'EOL'
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class AccountMove(models.Model):
    _inherit = 'account.move'

    tax_invoice_number = fields.Char(string='Tax Invoice Number', copy=False, readonly=True)
    tax_invoice_date = fields.Date(string='Tax Invoice Date', copy=False)
    payment_id = fields.Many2one('account.payment', string='Related Payment', copy=False)
    original_invoice_id = fields.Many2one('account.move', string='Original Invoice')

    def action_generate_tax_invoice(self):
        if not self.payment_id:
            raise UserError(_('Cannot generate tax invoice without payment'))
        
        if self.tax_invoice_number:
            raise UserError(_('Tax invoice already generated'))

        sequence = self.env['ir.sequence'].next_by_code('thai.tax.invoice')
        
        new_lines = []
        for line in self.invoice_line_ids:
            new_lines.append((0, 0, {
                'product_id': line.product_id.id,
                'name': line.name,
                'quantity': line.quantity,
                'price_unit': line.price_unit,
                'tax_ids': [(6, 0, line.tax_ids.ids)],
            }))

        tax_invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner_id.id,
            'invoice_date': fields.Date.today(),
            'tax_invoice_number': sequence,
            'tax_invoice_date': fields.Date.today(),
            'invoice_line_ids': new_lines,
            'original_invoice_id': self.id,
            'payment_id': self.payment_id.id,
        })

        return tax_invoice
EOL

# Create account_payment.py
cat > tax_invoice_th/models/account_payment.py << 'EOL'
from odoo import models, fields, api

class AccountPayment(models.Model):
    _inherit = 'account.payment'

    def action_post(self):
        res = super(AccountPayment, self).action_post()
        self._create_tax_invoice()
        return res

    def _create_tax_invoice(self):
        for payment in self:
            if payment.payment_type == 'inbound' and payment.reconciled_invoice_ids:
                for invoice in payment.reconciled_invoice_ids:
                    if invoice.state == 'posted' and not invoice.tax_invoice_number:
                        invoice.payment_id = payment.id
                        tax_invoice = invoice.action_generate_tax_invoice()
                        tax_invoice.action_post()
EOL

# Create view file
cat > tax_invoice_th/views/account_move_views.xml << 'EOL'
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="view_move_form_inherit_tax_invoice" model="ir.ui.view">
        <field name="name">account.move.form.inherit.tax.invoice</field>
        <field name="model">account.move</field>
        <field name="inherit_id" ref="account.view_move_form"/>
        <field name="arch" type="xml">
            <xpath expr="//field[@name='payment_reference']" position="after">
                <field name="tax_invoice_number" attrs="{'invisible': [('move_type', 'not in', ['out_invoice', 'out_refund'])]}"/>
                <field name="tax_invoice_date" attrs="{'invisible': [('move_type', 'not in', ['out_invoice', 'out_refund'])]}"/>
            </xpath>
            <xpath expr="//header" position="inside">
                <button string="Generate Tax Invoice" 
                        name="action_generate_tax_invoice" 
                        type="object" 
                        attrs="{'invisible': ['|', ('state', '!=', 'posted'), ('tax_invoice_number', '!=', False)]}"
                        class="oe_highlight"/>
            </xpath>
        </field>
    </record>
</odoo>
EOL

# Create sequence data file
cat > tax_invoice_th/data/sequences.xml << 'EOL'
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <data noupdate="1">
        <record id="seq_thai_tax_invoice" model="ir.sequence">
            <field name="name">Thai Tax Invoice</field>
            <field name="code">thai.tax.invoice</field>
            <field name="prefix">TAX/%(year)s/</field>
            <field name="padding">5</field>
            <field name="company_id" eval="False"/>
        </record>
    </data>
</odoo>
EOL

# Create security file
cat > tax_invoice_th/security/ir.model.access.csv << 'EOL'
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_account_move_tax,account.move.tax,model_account_move,account.group_account_invoice,1,1,1,1
EOL

# Set execute permissions
chmod +x tax_invoice_th/__init__.py

echo "Module tax_invoice_th has been created successfully!"
EOL