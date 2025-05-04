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
