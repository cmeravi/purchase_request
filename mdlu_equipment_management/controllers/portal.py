# -*- coding: utf-8 -*-
import datetime
from collections import OrderedDict
from dateutil.relativedelta import relativedelta
from werkzeug.exceptions import NotFound
from odoo import http
from odoo.http import request
from odoo.tools.translate import _
from odoo.tools import groupby as groupbyelem

from odoo.exceptions import UserError, ValidationError, Warning
from odoo.addons.mdlu_equipment_management.models.equipment_loan import _TYPES as LOAN_TYPES
from odoo.addons.payment.controllers.portal import PaymentProcessing
from odoo.addons.portal.controllers.portal import get_records_pager, pager as portal_pager, CustomerPortal


class CustomerPortal(CustomerPortal):

    # Equipment Request Portal Controllers
    def _get_equipment_request_domain(self, partner):
        return [
            ('partner_id','=',partner.id),
        ]

    def _get_loaned_items_domain(self, partner):
        return [
            ('partner_id', '=',partner.id),
            ('state','not in',['returned','cancelled','new'])
        ]

    def _prepare_portal_layout_values(self):
        """ Add subscription details to main account page """
        values = super(CustomerPortal, self)._prepare_portal_layout_values()
        partner = request.env.user.partner_id
        values['equipment_request_count'] = request.env['equipment.request'].search_count(self._get_equipment_request_domain(partner))
        values['loaned_equipment_count'] = request.env['equipment.loan.line'].search_count(self._get_loaned_items_domain(partner))
        return values

    @http.route(['/my/equipment_requests', '/my/equipment_requests/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_equipment_requests(self, page=1, date_begin=None, date_end=None, sortby=None, filterby=None, **kw):
        values = self._prepare_portal_layout_values()
        partner = request.env.user.partner_id
        EquipmentRequest = request.env['equipment.request']

        domain = self._get_equipment_request_domain(partner)

        archive_groups = self._get_archive_groups('equipment.request', domain)

        if date_begin and date_end:
            domain += [('create_date', '>', date_begin), ('create_date', '<=', date_end)]

        searchbar_sortings = {
            'date': {'label': _('Newest'), 'order': 'create_date desc, id desc'},
            'name': {'label': _('Name'), 'order': 'name asc, id asc'}
        }
        searchbar_filters = {
            'all': {'label': _('All'), 'domain': []},
            'new': {'label': _('New'), 'domain': [('state', '=', 'draft')]},
            'needs_approval': {'label': _('Needs Approval'), 'domain': [('state', 'in', ['needs_approval','partial_approve'])]},
            'approved': {'label': _('Approved'), 'domain': [('state', '=', 'pending')]},
            'cancelled': {'label': _('Cancelled'), 'domain': [('state', '=', 'cancelled')]},
            'rejected': {'label': _('Rejected'), 'domain': [('state', '=', 'rejected')]},
        }

        # default sort by value
        if not sortby:
            sortby = 'date'
        order = searchbar_sortings[sortby]['order']
        # default filter by value
        if not filterby:
            filterby = 'all'
        domain += searchbar_filters[filterby]['domain']

        # pager
        account_count = EquipmentRequest.search_count(domain)
        pager = portal_pager(
            url="/my/equipment_requests",
            url_args={'date_begin': date_begin, 'date_end': date_end, 'sortby': sortby, 'filterby': filterby},
            total=account_count,
            page=page,
            step=self._items_per_page
        )

        requests = EquipmentRequest.search(domain, order=order, limit=self._items_per_page, offset=pager['offset'])
        request.session['my_equipment_request_history'] = requests.ids[:100]

        values.update({
            'requests': requests,
            'page_name': 'Equipment Requests',
            'pager': pager,
            'archive_groups': archive_groups,
            'default_url': '/my/equipment_requests',
            'searchbar_sortings': searchbar_sortings,
            'sortby': sortby,
            'searchbar_filters': OrderedDict(sorted(searchbar_filters.items())),
            'filterby': filterby,
        })
        return request.render("mdlu_equipment_management.portal_my_equipment_requests", values)

    @http.route(['/my/equipment_requests/<int:request_id>'], type='http', auth="public", website=True)
    def portal_equipment_requests_page(self, request_id, access_token=None, message=False, download=False, **kw):
        try:
            req_sudo = self._document_check_access('equipment.request', request_id, access_token=access_token)
        except (AccessError, MissingError):
            return request.redirect('/my/equipment_requests')

        # use sudo to allow accessing/viewing orders for public user
        # only if he knows the private token
        now = datetime.date.today()

        # Log only once a day
        if req_sudo and request.session.get('view_quote_%s' % req_sudo.id) != now and request.env.user.share and access_token:
            request.session['view_quote_%s' % req_sudo.id] = now
            body = _('Request viewed by user')
            _message_post_helper(res_model='equipment.request', res_id=req_sudo.id, message=body, token=req_sudo.access_token, message_type='notification', subtype="mail.mt_note", partner_ids=req_sudo.user_id.sudo().partner_id.ids)
        submit_request = req_sudo.state in ['draft']
        products = request.env['product.product'].sudo().search([('equipment_loan_ok','=',True)])
        vendors = request.env['res.partner'].sudo().search([('supplier','=',True)])
        values = {
            'equipment_request': req_sudo,
            'submit_request': submit_request,
            'message': message,
            'token': access_token,
            'return_url': '/my/equipment_requests',
            'bootstrap_formatting': True,
            'partner_id': req_sudo.partner_id.id,
            'products': products,
            'vendors': vendors,
        }
        if req_sudo.company_id:
            values['res_company'] = req_sudo.company_id

        history = request.session.get('my_equipment_request_history', [])
        values.update(get_records_pager(history, req_sudo))

        return request.render('mdlu_equipment_management.portal_my_equipment_request', values)

    @http.route(['/my/equipment_requests/<int:request_id>/submit'], type='http', auth="public", website=True)
    def submit_request(self, request_id, **kw):
        equipmnt_request = request.env['equipment.request'].browse(request_id)

        equipmnt_request.sudo().action_request_approval()
        url = '/my/equipment_requests/' + str(request_id)
        return request.redirect(url)

    @http.route(['/my/equipment_requests/new'], type='http', auth="public", website=True)
    def new_request(self, **kw):
        EquipmentRequest = request.env['equipment.request']
        user_id = request.env.user
        assigned_to = user_id.partner_id.equipment_manager
        if not assigned_to:
            assigned_to = user_id.company_id.default_equipment_manager
        vals = {
            'name': EquipmentRequest.sudo()._get_default_name(),
            'user_id': user_id.id,
            'company_id': user_id.company_id.id,
            'assigned_to': assigned_to.id,
        }
        new_request = EquipmentRequest.sudo().create(vals)
        url = '/my/equipment_requests/' + str(new_request.id)
        return request.redirect(url)

    @http.route(['/my/equipment_requests/<int:request_id>/new_line'], type='http', methods=["POST"], auth="public", website=True)
    def new_request_line(self, request_id, **kw):
        RequestLine = request.env['equipment.request.line']
        vals = kw
        msg = ''
        url = '/my/equipment_requests/' + str(request_id)
        vals['vendor_id'] = int(vals['vendor_id'])
        vals['product_id'] = int(vals['product_id'])
        vals['product_qty'] = int(vals['product_qty'])
        vals['price_unit'] = float(vals['price_unit'])
        vals['request_id'] = request_id
        RequestLine.sudo().create(vals)
        return request.redirect(url)


    @http.route(['/my/equipment_requests/<int:request_id>/request_line=<int:line_id>/cancel'], type='http', auth="public", website=True)
    def cancel_request_line(self, request_id, line_id, **kw):
        RequestLine = request.env['equipment.request.line'].browse(line_id)
        RequestLine.action_cancel()
        url = '/my/equipment_requests/' + str(request_id)
        return request.redirect(url)


    # Loaned Items Controllers
    @http.route(['/my/loaned_equipment', '/my/loaned_equipment/page/<int:page>', '/my/loaned_equipment/request_line=<int:request_line>', '/my/loaned_equipment/request_line=<int:request_line>/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_equipment_loan(self, request_line=None, page=1, date_begin=None, date_end=None, sortby=None, filterby=None, **kw):
        values = self._prepare_portal_layout_values()
        partner = request.env.user.partner_id
        EquipmentLoanLine = request.env['equipment.loan.line']
        request_line_id = request.env['equipment.request.line'].search([('id','=',request_line)])
        request_id = request_line_id.request_id

        domain = self._get_loaned_items_domain(partner)

        archive_groups = self._get_archive_groups('equipment.loan.line', domain)
        if date_begin and date_end:
            domain += [('create_date', '>', date_begin), ('create_date', '<=', date_end)]

        searchbar_sortings = {
            'newest': {'label': _('Newest'), 'order': 'create_date desc'},
            'oldest': {'label': _('Oldest'), 'order': 'create_date asc'},
            'due_date': {'label': _('Due Date'), 'order': 'due_date asc'},
            'state': {'label': _('Status'), 'order': 'state asc, id asc'},
        }
        searchbar_filters = {
            'all': {'label': _('All'), 'domain': []},
            'long_term': {'label': _('Long Term Loans'), 'domain': [('loan_type', '=', 'long')]},
            'short_term': {'label': _('Short Term Loans'), 'domain': [('loan_type', '=', 'short')]},
            'needs_approval': {'label': _('Needs Approval'), 'domain': [('state', '=', 'needs_approval')]},
            'renew': {'label': _('Renew Requested'), 'domain': [('state', '=', 'renew')]},
            'approved': {'label': _('Approved'), 'domain': [('state', '=', 'approved')]},
            'checked_out': {'label': _('Checked Out'), 'domain': [('state', '=', 'checked_out')]},
            'due_soon': {'label': _('Due Soon'), 'domain': [('state', '=', 'due_soon')]},
            'over_due': {'label': _('Over Due'), 'domain': [('state', '=', 'over_due')]},
        }

        # default sort by value
        if not sortby:
            sortby = 'newest'
        order = searchbar_sortings[sortby]['order']
        # default filter by value
        if not filterby:
            filterby = 'all'
        domain += searchbar_filters[filterby]['domain']

        if request_line:
            domain += [('equipment_requst_line','=',request_line)]

        # pager
        loan_count = EquipmentLoanLine.search_count(domain)
        pager = portal_pager(
            url="/my/loaned_equipment",
            url_args={'date_begin': date_begin, 'date_end': date_end, 'sortby': sortby, 'filterby': filterby},
            total=loan_count,
            page=page,
            step=self._items_per_page
        )

        loan_lines = EquipmentLoanLine.search(domain, order=order, limit=self._items_per_page, offset=pager['offset'])
        request.session['my_equipment_loan_history'] = loan_lines.ids[:100]

        values.update({
            'loans': loan_lines,
            'request_id': request_id,
            'page_name': 'Loaned Equipment',
            'pager': pager,
            'archive_groups': archive_groups,
            'default_url': '/my/loaned_equipment',
            'searchbar_sortings': searchbar_sortings,
            'sortby': sortby,
            'searchbar_filters': OrderedDict(sorted(searchbar_filters.items())),
            'filterby': filterby,
        })
        return request.render("mdlu_equipment_management.portal_my_loaned_equipment", values)

    @http.route(['/my/loaned_equipment/<int:line_id>/renew'], type='http', auth="public", website=True)
    def renew_loaned_item(self, line_id, **kw):
        loan_line = request.env['equipment.loan.line'].browse(line_id)
        body = _('%s has requested that %s be renewed.\n') % (request.env.user.partner_id.name, loan_line.item_id.name)
        subject = _('Renew Request for %s') % (loan_line.item_id.name)
        partner_ids = loan_line.loan_id.department_id.equipment_manager_ids.mapped('user_id').mapped('partner_id')
        loan_line.loan_id.sudo().message_post(body=body,subject=subject, message_type='email',**{'partner_ids': partner_ids.mapped('id'),})
        loan_line.write({'state': 'renew',})
        loan_line.loan_id.write({'renew_request': True,})
        return request.redirect('/my/loaned_equipment/')
