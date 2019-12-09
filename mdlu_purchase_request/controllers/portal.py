# -*- coding: utf-8 -*-

import base64
from collections import OrderedDict
import datetime

from odoo import http
from odoo.exceptions import AccessError, MissingError
from odoo.http import request
from odoo.tools import image_resize_image
from odoo.tools.translate import _
from odoo.addons.portal.controllers.portal import pager as portal_pager, CustomerPortal, get_records_pager
from odoo.addons.web.controllers.main import Binary



class CustomerPortal(CustomerPortal):

    def _prepare_portal_layout_values(self):
        values = super(CustomerPortal, self)._prepare_portal_layout_values()
        values['purchase_request_count'] = request.env['purchase.request'].search_count([('state','not in', ['draft'])])
        return values

    @http.route(['/my/purchase_requests', '/my/purchase_requests/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_purchase_requests(self, page=1, date_begin=None, date_end=None, sortby=None, filterby=None, **kw):
        values = self._prepare_portal_layout_values()
        partner = request.env.user.partner_id
        PurchaseRequest = request.env['purchase.request']

        domain = []

        archive_groups = self._get_archive_groups('purchase.order', domain)
        if date_begin and date_end:
            domain += [('create_date', '>', date_begin), ('create_date', '<=', date_end)]

        searchbar_sortings = {
            'date': {'label': _('Newest'), 'order': 'create_date desc, id desc'},
            'name': {'label': _('Name'), 'order': 'name asc, id asc'},
            'amount_total': {'label': _('Total'), 'order': 'amount_total desc, id desc'},
        }
        # default sort by value
        if not sortby:
            sortby = 'date'
        order = searchbar_sortings[sortby]['order']

        searchbar_filters = {
            'all': {'label': _('All'), 'domain': [('state', 'not in', ['draft'])]},
            'to_approve': {'label': _('Waiting for Approval'), 'domain': [('state', '=', 'to_approve')]},
            'approved': {'label': _('Approved'), 'domain': [('state', '=', 'approved')]},
            'partial_approved': {'label': _('Partially Approved'), 'domain': [('state', '=', 'partial_approved')]},
            'cancel': {'label': _('Cancelled'), 'domain': [('state', '=', 'cancelled')]},
            'rejected': {'label': _('Rejected'), 'domain': [('state', '=', 'rejected')]},
            'done': {'label': _('Ordered'), 'domain': [('state', '=', 'ordered')]},
        }
        # default filter by value
        if not filterby:
            filterby = 'all'
        domain += searchbar_filters[filterby]['domain']

        # count for pager
        purchase_request_count = PurchaseRequest.search_count(domain)
        # make pager
        pager = portal_pager(
            url="/my/purchase_requests",
            url_args={'date_begin': date_begin, 'date_end': date_end},
            total=purchase_request_count,
            page=page,
            step=self._items_per_page
        )
        # search the purchase orders to display, according to the pager data
        orders = PurchaseRequest.search(
            domain,
            order=order,
            limit=self._items_per_page,
            offset=pager['offset']
        )
        request.session['my_purchases_request_history'] = orders.ids[:100]

        values.update({
            'purchase_requests': orders,
            'page_name': 'Purchase Requests',
            'pager': pager,
            'archive_groups': archive_groups,
            'searchbar_sortings': searchbar_sortings,
            'sortby': sortby,
            'searchbar_filters': OrderedDict(sorted(searchbar_filters.items())),
            'filterby': filterby,
            'default_url': '/my/purchase_requests',
        })
        return request.render("mdlu_purchase_request.portal_my_purchase_requests", values)

    @http.route(['/my/purchase_requests/<int:purchase_request_id>'], type='http', auth="public", website=True)
    def portal_my_purchase_request(self, purchase_request_id=None, access_token=None, message=False, download=False, **kw):
        try:
            pr_sudo = self._document_check_access('purchase.request', purchase_request_id, access_token=access_token)
        except (AccessError, MissingError):
            return request.redirect('/my')

        now = datetime.date.today()

        if pr_sudo and request.session.get('view_pr_%s' % pr_sudo.id) != now and request.env.user.share and access_token:
            request.session['view_quote_%s' % pr_sudo.id] = now
            body = _('Purchase request viewed by customer')
            _message_post_helper(res_model='purchase.request', res_id=pr_sudo.id, message=body, token=pr_sudo.access_token, message_type='notification', subtype="mail.mt_note", partner_ids=pr_sudo.user_id.sudo().partner_id.ids)
        values = {
            'purchase_request': pr_sudo,
            'message': message,
            'token': access_token,
            'return_url': '/my/purchase_requests',
            'bootstrap_formatting': True,
            'partner_id': pr_sudo.user_id.partner_id.id,
        }
        if pr_sudo.company_id:
            values['res_company'] = pr_sudo.company_id

        history = request.session.get('my_purchases_request_history', [])
        values.update(get_records_pager(history, pr_sudo))

        return request.render("mdlu_purchase_request.portal_my_purchase_request", values)

    @http.route(['/my/purchase_requests/<int:purchase_request>/cancel'], type='http', methods=["POST"], auth="public", website=True)
    def cancel_item(self, account_id, line_id, **kw):
        account = request.env['purchase.request'].browse(account_id)
        account_line = request.env['purchase.request.line'].search([('id','=', line_id.id)])


        account.message_post(body=_('%s has been cancelled from this Purchase Request') % (kw.get('product_name')))
        account_line.message_post(body=_('This line has been cancelled'))
        account_line.button_cancel()
        return request.redirect('/my/purchase_requests/<int:account_id>')
