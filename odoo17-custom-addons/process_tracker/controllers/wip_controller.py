from odoo import http
from odoo.http import request

class WIPStatusController(http.Controller):

    @http.route(['/wip/transition/<int:wip_id>/<string:status>'], type='http', auth='public', website=True)
    def wip_transition(self, wip_id, status, token=None, **kwargs):
        wip = request.env['process.wip'].sudo().browse(wip_id)
        if not wip or wip.token != token:
            return request.render("website.404")  # secure fallback

        if status not in dict(wip._fields['status'].selection).keys():
            return request.render("website.404")

        old_status = wip.status
        wip.write({'status': status})
        return f"""
        <h2>Status updated!</h2>
        <p>From <strong>{old_status}</strong> to <strong>{status}</strong></p>
        """
