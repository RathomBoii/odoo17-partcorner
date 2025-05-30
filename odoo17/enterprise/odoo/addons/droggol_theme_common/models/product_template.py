# -*- coding: utf-8 -*-
# Copyright (c) 2019-Present Droggol Infotech Private Limited. (<https://www.droggol.com/>)

from odoo import api, fields, models, Command
from odoo.addons.website.models import ir_http


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    dr_label_id = fields.Many2one('dr.product.label', string='Label')

    dr_product_tab_ids = fields.Many2many('dr.website.content', 'product_template_tab_rel', 'product_template_id', 'tab_id', string='Tabs')
    dr_product_offer_ids = fields.Many2many('dr.website.content', 'product_template_offer_rel', 'product_template_id', 'offer_id', string='Offers')

    dr_brand_value_id = fields.Many2one('product.attribute.value', compute='_compute_dr_brand_value_id', inverse='_inverse_dr_brand_value_id', search='_search_dr_brand_value_id', string='Brand')
    dr_brand_attribute_ids = fields.Many2many('product.attribute', compute='_compute_dr_brand_attribute_ids')

    dr_free_qty = fields.Float('Free To Use Quantity', compute='_compute_dr_free_qty', search='_search_dr_free_qty', compute_sudo=False, digits='Product Unit of Measure')
    dr_show_out_of_stock = fields.Char(compute='_compute_dr_show_out_of_stock', compute_sudo=True)

    dr_ptav_ids = fields.One2many('product.template.attribute.value', 'product_tmpl_id')
    dr_is_rfq = fields.Boolean('field_name')

    def _search_dr_brand_value_id(self, operator, value):
        if operator in ['in', 'not in']:
            return [('attribute_line_ids.value_ids', operator, value)]
        elif operator in ['ilike', 'not ilike', '=', '!=']:
            brand_attribute_id = self._get_brand_attribute()
            values = self.env['product.attribute.value'].search([('name', operator, value), ('attribute_id', 'in', brand_attribute_id.ids)])
            return [('attribute_line_ids.value_ids', 'in', values.ids)]
        # Does not support other cases
        return []

    def _compute_dr_brand_value_id(self):
        for product in self:
            brand_lines = product.attribute_line_ids.filtered(lambda x: x.attribute_id.dr_is_brand)
            product.dr_brand_value_id = self.env['product.attribute.value']
            if brand_lines:
                product.dr_brand_value_id = brand_lines[0].value_ids[0]

    def _inverse_dr_brand_value_id(self):
        brand_value_id = self.dr_brand_value_id
        for product in self:
            brand_lines = product.attribute_line_ids.filtered(lambda x: x.attribute_id.dr_is_brand)
            brand_line = brand_lines and brand_lines[0]
            if brand_line and brand_value_id:
                brand_line.value_ids = brand_value_id
            elif brand_line and not brand_value_id:
                brand_line.unlink()
            elif brand_value_id:
                product.attribute_line_ids = [Command.create({
                    'attribute_id': brand_value_id.attribute_id.id,
                    'value_ids': [Command.set(brand_value_id.ids)],
                })]

    def _compute_dr_brand_attribute_ids(self):
        attributes = self._get_brand_attribute()
        for product in self:
            product.dr_brand_attribute_ids = attributes

    def _get_brand_attribute(self):
        return self.env['product.attribute'].search([('dr_is_brand', '=', True)])

    @api.depends('product_variant_ids.free_qty')
    def _compute_dr_free_qty(self):
        res = self._compute_dr_free_qty_quantities_dict()
        for template in self:
            template.dr_free_qty = res[template.id]['free_qty']

    def _compute_dr_free_qty_quantities_dict(self):
        website = self.env['website'].get_current_website()
        variants_available = {
            p['id']: p for p in self.sudo().with_context(warehouse=website._get_warehouse_available()).product_variant_ids.read(['free_qty'])
        }
        prod_available = {}
        for template in self:
            free_qty = 0
            for p in template.product_variant_ids:
                free_qty += variants_available[p.id]['free_qty']
            prod_available[template.id] = {
                'free_qty': free_qty,
            }
        return prod_available

    def _search_dr_free_qty(self, operator, value):
        website = self.env['website'].get_current_website()
        domain = [('free_qty', operator, value)]
        product_variant_query = self.env['product.product'].sudo().with_context(warehouse=website._get_warehouse_available())._search(domain)
        return [('product_variant_ids', 'in', product_variant_query)]

    def _compute_dr_show_out_of_stock(self):
        website = ir_http.get_request_website()
        for product in self:
            product.dr_show_out_of_stock = ''
            if website and website._get_dr_theme_config('json_shop_product_item').get('show_stock_label') and not product.allow_out_of_stock_order and product.detailed_type == 'product':
                free_qty = product.dr_free_qty
                if product.show_availability and free_qty <= product.available_threshold:
                    product.dr_show_out_of_stock = int(free_qty)
                if free_qty <= 0:
                    product.dr_show_out_of_stock = 'OUT_OF_STOCK'

    @api.model
    def _search_get_detail(self, website, order, options):
        res = super()._search_get_detail(website, order, options)
        # Hide out of stock
        if options.get('hide_out_of_stock'):
            res['base_domain'].append(['|', '|', ('detailed_type', '!=', 'product'), ('allow_out_of_stock_order', '=', True), '&', ('dr_free_qty', '>', 0), ('allow_out_of_stock_order', '=', False)])
        # Rating
        ratings = options.get('rating')
        if ratings:
            result = self.env['rating.rating'].sudo().read_group([('res_model', '=', 'product.template')], ['rating:avg'], groupby=['res_id'], lazy=False)
            rating_product_ids = []
            for rating in ratings:
                rating_product_ids.extend([item['res_id'] for item in result if item['rating'] >= int(rating)])
            if rating_product_ids:
                res['base_domain'].append([('id', 'in', rating_product_ids)])
            else:
                res['base_domain'].append([('id', 'in', [])])
        return res

    def _get_image_size_based_grid(self, columns, view_mode):
        if view_mode == 'list':
            return 'image_1024'
        if columns <= 2:
            return 'image_1024'
        return 'image_512'

    def _get_product_preview_swatches(self, limit=3):
        swatches = []
        for ptav in self.dr_ptav_ids:
            if ptav.ptav_active and ptav.ptav_product_variant_ids:
                vals = {'id': ptav.id, 'name': ptav.name, 'preview_image': '/web/image/product.product/%s' % ptav.ptav_product_variant_ids.ids[0]}
                if ptav.dr_thumb_image:
                    vals.update({'type': 'image', 'value': '/web/image/product.template.attribute.value/%s/dr_thumb_image' % ptav.id})
                    swatches.append(vals)
                elif ptav.image:
                    vals.update({'type': 'image', 'value': '/web/image/product.template.attribute.value/%s/image' % ptav.id})
                    swatches.append(vals)
                elif ptav.html_color:
                    vals.update({'type': 'color', 'value': ptav.html_color})
                    swatches.append(vals)
        return {'swatches': swatches[:limit], 'more': len(swatches) - limit}

    def _get_product_pricelist_offer(self):
        website_id = self.env['website'].get_current_website()
        if not website_id._dr_has_b2b_access():
            return False
        pricelist_id = website_id.pricelist_id
        price_rule = pricelist_id._compute_price_rule(self, 1)
        price_rule_id = price_rule.get(self.id)[1]
        if price_rule_id:
            rule = self.env['product.pricelist.item'].browse(price_rule_id)
            if rule and rule.date_end:
                return {'rule': rule, 'date_end': rule.date_end.strftime('%Y-%m-%d %H:%M:%S')}
        return False

    def _get_combination_info(self, combination=False, product_id=False, add_qty=1.0, parent_combination=False, only_template=False):
        combination_info = super()._get_combination_info(combination=combination, product_id=product_id, add_qty=add_qty, parent_combination=parent_combination, only_template=only_template)
        website = self.env['website'].get_current_website()
        website_has_theme_prime = website._dr_website_has_theme_prime()
        if website and website_has_theme_prime:
            combination_info['has_b2b_access'] = website._dr_has_b2b_access()
            if combination_info['product_id']:
                product_variant_id = self.env['product.product'].browse(combination_info['product_id'])

                # Bulk Price
                if website._get_dr_theme_config('bool_show_bulk_price') and combination_info.get('has_b2b_access') and combination_info.get('is_combination_possible'):
                    ProductTemplate = self.env['product.template']
                    IrQwebFieldFloat = self.env['ir.qweb.field.float']
                    IrQwebFieldMonetary = self.env['ir.qweb.field.monetary']

                    bulk_price = []
                    all_rule_ids = website.pricelist_id._get_applicable_rules(product_variant_id, fields.Datetime.now()).filtered(lambda x: x.min_quantity)
                    applicable_rule_ids = self.env['product.pricelist.item']
                    for rule in all_rule_ids:
                        if not applicable_rule_ids.filtered(lambda x: x.min_quantity == rule.min_quantity):
                            applicable_rule_ids += rule

                    for rule_id in applicable_rule_ids.sorted(lambda x: x.min_quantity):
                        price = rule_id._compute_price(product_variant_id, rule_id.min_quantity, product_variant_id.uom_id, fields.Datetime.now(), website.currency_id)
                        price = ProductTemplate._apply_taxes_to_price(price, website.currency_id, combination_info['product_taxes'], combination_info['taxes'], product_variant_id)
                        pricelist = rule_id.pricelist_id
                        list_price = combination_info.get('list_price')
                        bulk_price.append({
                            'id': rule_id.id,
                            'qty': rule_id.min_quantity,
                            'formatted_qty': IrQwebFieldFloat.value_to_html(rule_id.min_quantity, {'decimal_precision': 'Product Unit of Measure'}), #TO-REMOVE
                            'price': price,
                            'formatted_price': IrQwebFieldMonetary.value_to_html(price, {'display_currency': website.currency_id}),
                            'saving_price': IrQwebFieldMonetary.value_to_html((list_price - price)* rule_id.min_quantity, {'display_currency': website.currency_id}) if pricelist.discount_policy == 'without_discount' else False,
                            'uom_name': product_variant_id.uom_id.name,
                        })
                    combination_info['bulk_price'] = bulk_price

                # Render extra fields on product detail page
                IrUiView = self.env['ir.ui.view']
                combination_info['tp_extra_fields'] = IrUiView._render_template('theme_prime.product_extra_fields', values={'website': website, 'product_variant': product_variant_id, 'product': product_variant_id.product_tmpl_id})
            # Hide price per UoM feature for B2B mode
            if not combination_info.get('has_b2b_access'):
                combination_info['base_unit_price'] = 0
                combination_info['price_extra'] = 0
                combination_info['list_price'] = 0
                combination_info['price'] = 0
        return combination_info


class ProductTemplateAttributeValue(models.Model):
    _inherit = 'product.template.attribute.value'

    def _get_extra_price(self, combination_info):
        if not combination_info.get('has_b2b_access', True):
            return 0.0
        return super()._get_extra_price(combination_info=combination_info)
