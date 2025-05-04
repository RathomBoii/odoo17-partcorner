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


class QRCodeScan(models.Model):
    _name = 'qr.code.scan'
    _description = 'QR Code Scan'
    _order = 'scan_date desc'

    qr_code_id = fields.Many2one('qr.code', string='QR Code', required=True)
    scan_date = fields.Datetime(default=fields.Datetime.now, required=True)
    ip_address = fields.Char()
    user_agent = fields.Char()
    invoice_id = fields.Many2one('account.move', string='Related Invoice')


class PaymentProvider(models.Model):
    _inherit = 'payment.provider'

    code = fields.Selection(
        selection_add=[('qr_payment', 'QR Payment')],
        ondelete={'qr_payment': 'set default'}
    )
    qr_code_ids = fields.One2many('qr.code', 'provider_id', string='QR Codes')
    default_qr_code_id = fields.Many2one('qr.code', string='Default QR Code')

    @api.model
    def _get_payment_method_information(self):
        res = super()._get_payment_method_information()
        res['qr_payment'] = {'mode': 'unique', 'domain': [('type', '=', 'bank')]}
        return res

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
