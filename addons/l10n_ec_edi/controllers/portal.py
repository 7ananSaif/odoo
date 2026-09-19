# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import _, http
from odoo.exceptions import AccessError, MissingError
from odoo.fields import Domain
from odoo.http import request

from odoo.addons.account.controllers.portal import PortalAccount
from odoo.addons.portal.controllers.portal import pager as portal_pager


class PortalWithholding(PortalAccount):

    def _is_ecuador_company(self):
        return request.env.company.country_code == 'EC'

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        AccountInvoice = request.env['account.move']
        if self._is_ecuador_company() and 'withholding_count' in counters:
            values['withholding_count'] = AccountInvoice.search_count([
                    ('state', 'not in', ('cancel', 'draft')),
                    ('move_type', '=', 'entry'),
                    ('l10n_ec_withhold_type', '=', 'in_withhold')
                ],
            ) if AccountInvoice.has_access('read') else 0
        return values

    # ------------------------------------------------------------
    # My Withholdings
    # ------------------------------------------------------------
    def _invoice_get_page_view_values(self, invoice, access_token, **kwargs):
        """ Override of account to customize the page_name for breadcrumbs """
        values = super()._invoice_get_page_view_values(invoice, access_token, **kwargs)
        if invoice and invoice._l10n_ec_is_withholding():
            values['page_name'] = 'withholding'
        return values

    def _get_invoices_domain(self, m_type=None):
        """Override to allow for new domain type that allows entry moves """
        res = super()._get_invoices_domain(m_type)

        if not self._is_ecuador_company():
            return res
        return Domain.OR([res, [('state', 'not in', ('cancel', 'draft')), ('move_type', '=', 'entry')]])

    def _get_account_searchbar_sortings(self):
        values = super()._get_account_searchbar_sortings()
        if self._is_ecuador_company():
            values['withholding_date'] = {'label': _('Withholding Date'), 'order': 'l10n_ec_withhold_date desc'}
        return values

    def _get_account_searchbar_filters(self):
        values = super()._get_account_searchbar_filters()
        if self._is_ecuador_company():
            values['all']['domain'] = Domain.AND([values['all']['domain'], [('move_type', '!=', 'entry')]])
            values['withholdings'] = {'label': _('Withholdings'), 'domain': [('l10n_ec_withhold_type', '=', 'in_withhold')]}
        return values

    @http.route()
    def portal_my_invoices(self, page=1, date_begin=None, date_end=None, sortby=None, filterby=None, **kw):
        """ Override to allow for us to create a custom page_name and pass a different view """
        if not self._is_ecuador_company() or not filterby or filterby != 'withholdings':
            return super().portal_my_invoices(page=page, date_begin=date_begin, date_end=date_end, sortby=sortby, filterby=filterby, **kw)

        values = self._prepare_my_invoices_values(page, date_begin, date_end, sortby or 'withholding_date', filterby)
        # pager
        pager = portal_pager(**values['pager'])

        # content according to pager and archive selected
        withholdings = values['invoices'](pager['offset'])
        request.session['my_invoices_history'] = [i['invoice'].id for i in withholdings][:100]

        values.update({
            'page_name': 'withholding',
            'invoices': withholdings,
            'pager': pager,
        })
        return request.render("l10n_ec_edi.portal_my_withholdings", values)

    @http.route()
    def portal_my_invoice_detail(self, invoice_id, access_token=None, report_type=None, download=False, **kw):
        """ Override to allow for a unique report to appear on the portal view. """
        try:
            withholding_sudo = self._document_check_access('account.move', invoice_id, access_token)
        except (AccessError, MissingError):
            return request.redirect('/my')

        if withholding_sudo._l10n_ec_is_withholding() and not download and report_type in ('html', 'pdf', 'text'):
            has_generated_invoice = bool(withholding_sudo.invoice_pdf_report_id)
            request.update_context(proforma_invoice=not has_generated_invoice)
            return self._show_report(model=withholding_sudo, report_type=report_type, report_ref='l10n_ec_edi.l10n_ec_edi_withhold', download=download)

        return super().portal_my_invoice_detail(invoice_id, access_token=access_token, report_type=report_type, download=download, **kw)
