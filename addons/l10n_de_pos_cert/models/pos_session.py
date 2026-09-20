# -*- coding: utf-8 -*-

from typing import Dict

from odoo import models, fields, _, release
from odoo.tools.float_utils import float_repr
from odoo.exceptions import UserError
import uuid

COUNTRY_CODE_MAP = {
    "BD": "BGD", "BE": "BEL", "BF": "BFA", "BG": "BGR", "BA": "BIH", "BB": "BRB", "WF": "WLF", "BL": "BLM", "BM": "BMU",
    "BN": "BRN", "BO": "BOL", "BH": "BHR", "BI": "BDI", "BJ": "BEN", "BT": "BTN", "JM": "JAM", "BV": "BVT", "BW": "BWA",
    "WS": "WSM", "BQ": "BES", "BR": "BRA", "BS": "BHS", "JE": "JEY", "BY": "BLR", "BZ": "BLZ", "RU": "RUS", "RW": "RWA",
    "RS": "SRB", "TL": "TLS", "RE": "REU", "TM": "TKM", "TJ": "TJK", "RO": "ROU", "TK": "TKL", "GW": "GNB", "GU": "GUM",
    "GT": "GTM", "GS": "SGS", "GR": "GRC", "GQ": "GNQ", "GP": "GLP", "JP": "JPN", "GY": "GUY", "GG": "GGY", "GF": "GUF",
    "GE": "GEO", "GD": "GRD", "GB": "GBR", "GA": "GAB", "SV": "SLV", "GN": "GIN", "GM": "GMB", "GL": "GRL", "GI": "GIB",
    "GH": "GHA", "OM": "OMN", "TN": "TUN", "JO": "JOR", "HR": "HRV", "HT": "HTI", "HU": "HUN", "HK": "HKG", "HN": "HND",
    "HM": "HMD", "VE": "VEN", "PR": "PRI", "PS": "PSE", "PW": "PLW", "PT": "PRT", "SJ": "SJM", "PY": "PRY", "IQ": "IRQ",
    "PA": "PAN", "PF": "PYF", "PG": "PNG", "PE": "PER", "PK": "PAK", "PH": "PHL", "PN": "PCN", "PL": "POL", "PM": "SPM",
    "ZM": "ZMB", "EH": "ESH", "EE": "EST", "EG": "EGY", "ZA": "ZAF", "EC": "ECU", "IT": "ITA", "VN": "VNM", "SB": "SLB",
    "ET": "ETH", "SO": "SOM", "ZW": "ZWE", "SA": "SAU", "ES": "ESP", "ER": "ERI", "ME": "MNE", "MD": "MDA", "MG": "MDG",
    "MF": "MAF", "MA": "MAR", "MC": "MCO", "UZ": "UZB", "MM": "MMR", "ML": "MLI", "MO": "MAC", "MN": "MNG", "MH": "MHL",
    "MK": "MKD", "MU": "MUS", "MT": "MLT", "MW": "MWI", "MV": "MDV", "MQ": "MTQ", "MP": "MNP", "MS": "MSR", "MR": "MRT",
    "IM": "IMN", "UG": "UGA", "TZ": "TZA", "MY": "MYS", "MX": "MEX", "IL": "ISR", "FR": "FRA", "IO": "IOT", "SH": "SHN",
    "FI": "FIN", "FJ": "FJI", "FK": "FLK", "FM": "FSM", "FO": "FRO", "NI": "NIC", "NL": "NLD", "NO": "NOR", "NA": "NAM",
    "VU": "VUT", "NC": "NCL", "NE": "NER", "NF": "NFK", "NG": "NGA", "NZ": "NZL", "NP": "NPL", "NR": "NRU", "NU": "NIU",
    "CK": "COK", "XK": "XKX", "CI": "CIV", "CH": "CHE", "CO": "COL", "CN": "CHN", "CM": "CMR", "CL": "CHL", "CC": "CCK",
    "CA": "CAN", "CG": "COG", "CF": "CAF", "CD": "COD", "CZ": "CZE", "CY": "CYP", "CX": "CXR", "CR": "CRI", "CW": "CUW",
    "CV": "CPV", "CU": "CUB", "SZ": "SWZ", "SY": "SYR", "SX": "SXM", "KG": "KGZ", "KE": "KEN", "SS": "SSD", "SR": "SUR",
    "KI": "KIR", "KH": "KHM", "KN": "KNA", "KM": "COM", "ST": "STP", "SK": "SVK", "KR": "KOR", "SI": "SVN", "KP": "PRK",
    "KW": "KWT", "SN": "SEN", "SM": "SMR", "SL": "SLE", "SC": "SYC", "KZ": "KAZ", "KY": "CYM", "SG": "SGP", "SE": "SWE",
    "SD": "SDN", "DO": "DOM", "DM": "DMA", "DJ": "DJI", "DK": "DNK", "VG": "VGB", "DE": "DEU", "YE": "YEM", "DZ": "DZA",
    "US": "USA", "UY": "URY", "YT": "MYT", "UM": "UMI", "LB": "LBN", "LC": "LCA", "LA": "LAO", "TV": "TUV", "TW": "TWN",
    "TT": "TTO", "TR": "TUR", "LK": "LKA", "LI": "LIE", "LV": "LVA", "TO": "TON", "LT": "LTU", "LU": "LUX", "LR": "LBR",
    "LS": "LSO", "TH": "THA", "TF": "ATF", "TG": "TGO", "TD": "TCD", "TC": "TCA", "LY": "LBY", "VA": "VAT", "VC": "VCT",
    "AE": "ARE", "AD": "AND", "AG": "ATG", "AF": "AFG", "AI": "AIA", "VI": "VIR", "IS": "ISL", "IR": "IRN", "AM": "ARM",
    "AL": "ALB", "AO": "AGO", "AQ": "ATA", "AS": "ASM", "AR": "ARG", "AU": "AUS", "AT": "AUT", "AW": "ABW", "IN": "IND",
    "AX": "ALA", "AZ": "AZE", "IE": "IRL", "ID": "IDN", "UA": "UKR", "QA": "QAT", "MZ": "MOZ"
}


class PosSession(models.Model):
    _inherit = 'pos.session'
    l10n_de_fiskaly_cash_point_closing_uuid = fields.Char(string="Fiskaly Cash Point Closing Uuid", readonly=True,
        help="The uuid of the 'cash point closing' created at Fiskaly when closing the session.")

    def _validate_session(self, balancing_account=False, amount_to_balance=0, bank_payment_method_diffs=None):
        res = super()._validate_session(balancing_account, amount_to_balance, bank_payment_method_diffs)

        # If the result is a dict, this means that there was a problem and the _validate_session was not completed.
        # In this case, a wizard should show up which is represented by the returned dictionary.
        # Return the dictionary to prevent running the remaining code.
        if isinstance(res, dict):
            return res
        orders = self.order_ids.filtered(lambda o: o.state == 'done')
        # We don't want to block the user that need to validate his session order in order to create his TSS
        if self.config_id.is_company_country_germany and self.config_id.l10n_de_fiskaly_tss_id and orders:
            orders = orders.sorted('write_date')  # there are possible cases where the end date won't be set
            json = self._l10n_de_create_cash_point_closing_json(orders)
            self._l10n_de_send_fiskaly_cash_point_closing(json)

        return res

    def _l10n_de_create_cash_point_closing_json(self, orders):
        self.env.cr.execute("""
            SELECT pm.is_cash_count, sum(p.amount) AS amount
            FROM pos_payment p
                LEFT JOIN pos_payment_method pm ON p.payment_method_id=pm.id
                JOIN account_journal journal ON pm.journal_id=journal.id
            WHERE p.session_id=%s AND journal.type IN ('cash', 'bank')
            GROUP BY pm.is_cash_count
        """, [self.id])
        total_payment_result = self.env.cr.dictfetchall()

        total_cash = 0
        total_bank = 0
        for payment in total_payment_result:
            if payment['is_cash_count']:
                total_cash = payment['amount']
            else:
                total_bank = payment['amount']

        return self._get_dsfinvk_cash_point_closing_data(**{
            'orders': orders,
            'total_cash': total_cash,
            'total_bank': total_bank,
        })

    def _get_vat_details(self, export_vat_id, incl_vat, excl_vat):
        precision = self.currency_id.decimal_places
        return {
                "vat_definition_export_id": export_vat_id,
                "incl_vat": float_repr(incl_vat, precision),
                "excl_vat": float_repr(excl_vat, precision),
                "vat": float_repr(incl_vat - excl_vat, precision),
            }

    def get_cash_statement_cases(self, transactions):
        # Since multiple business cases can occur, we group transactions by their type to clearly differentiate and categorize each
        precision = self.currency_id.decimal_places
        summary = {}
        for txn in transactions:
            lines = txn.get("data", {}).get("lines", [])
            for line in lines:
                business_case = line.get("business_case", {})
                case_type = business_case.get("type")
                amounts = business_case.get("amounts_per_vat_id", [])

                if case_type not in summary:
                    summary[case_type] = []

                for amt in amounts:
                    vat_id = amt.get("vat_definition_export_id", 5)
                    # There can be multiple VAT rates under the same case type (e.g., standard sales with both 19% and 7% rates),
                    # so we need to summarize the data per case type and per VAT rate.
                    existing_statement_entry = next(
                        (entry for entry in summary[case_type] if entry.get("vat_definition_export_id") == vat_id),
                        None
                    )
                    if existing_statement_entry:
                        # Add to existing totals
                        existing_statement_entry["incl_vat"] = float_repr(float(existing_statement_entry["incl_vat"]) + float(amt.get("incl_vat", 0)), precision)
                        existing_statement_entry["excl_vat"] = float_repr(float(existing_statement_entry["excl_vat"]) + float(amt.get("excl_vat", 0)), precision)
                    else:
                        # Create new statement entry for this vat
                        summary[case_type].append({
                            "vat_definition_export_id": vat_id,
                            "incl_vat": amt.get("incl_vat", "0"),
                            "excl_vat": amt.get("excl_vat", "0"),
                            "vat": amt.get("vat", "0"),
                        })

        # Build final statements directly
        # This refers to transactions that fall entirely outside the scope of VAT law (UStG) → Nicht steuerbar (Not Taxable) so vat id 5.
        statements = [
            {"type": "Anfangsbestand", "name": "Opening Cash", "amounts_per_vat_id": [self._get_vat_details(5, self.cash_register_balance_start, self.cash_register_balance_start)]},
            {"type": "DifferenzSollIst", "name": "Cash Discrepancy", "amounts_per_vat_id": [self._get_vat_details(5, self.cash_register_difference, self.cash_register_difference)]},
        ]

        move_statements = [entry for entry in self.get_cash_in_out_list() if entry.get('cashier_name')]  # remove difference line
        for cash_move in move_statements:
            # Need to update here if we update format in _prepareTryCashInOutPayload(), _prepare_account_bank_statement_line_vals()
            # current structure of name is: {session_name}-{move_type}-{statement_type}-{move_reason}
            # so if - is in name or reason direct spiltting won't work
            move_parts = cash_move['name'].removeprefix(self.name).split('-')
            move_type, statement_type, move_reason = move_parts[1], move_parts[2], "-".join(move_parts[3:])
            statements.append({"type": statement_type.capitalize(), "name": f"Cash {move_type} - {move_reason}"[:40], "amounts_per_vat_id": [self._get_vat_details(5, cash_move['amount'], cash_move['amount'])]})
        return statements

    def _get_dsfinvk_cash_point_closing_data(
        self,
        orders,
        total_cash,
        total_bank,
    ) -> Dict:

        company = self.company_id
        config = self.config_id
        session = self

        # To update the value of `l10n_de_vat_definition_export_identifier` for existing customers when they upgrade
        # this will ensure that all taxes have their export IDs set once their first session is closed
        company._check_vat_definition_export_id()

        precision = self.currency_id.decimal_places
        transactions = []
        for i, o in enumerate(orders, start=1):
            if o.partner_id:
                buyer = {
                    "name": f"{o.partner_id.name[:50]}",
                    "buyer_export_id": f"{o.partner_id.id}",
                    "type": "Kunde" if company.id != o.partner_id.company_id.id else "Mitarbeiter",
                    "address": {
                        "street": o.partner_id.street[:60] or 'N/A',  # minimum 1 character required
                        "postal_code": o.partner_id.zip[:10] or 'N/A',  # minimum 1 character required
                        "country_code": COUNTRY_CODE_MAP.get(o.partner_id.country_id.code) or "DEU",
                    },
                }
            else:
                buyer = {"name": "Customer", "buyer_export_id": "null", "type": "Kunde"}

            lines_data, payment_types = o._prepare_lines_and_payments()
            transaction = {
                "head": {
                    "tx_id": f"{o.l10n_de_fiskaly_transaction_uuid}",
                    "transaction_export_id": str(i),
                    "closing_client_id": f"{config.l10n_de_fiskaly_client_id}",
                    "type": "Beleg",
                    "storno": False,
                    "number": o.id,
                    "timestamp_start": o.l10n_de_fiskaly_time_start and int(o.l10n_de_fiskaly_time_start.timestamp()) or 0,
                    "timestamp_end": o.l10n_de_fiskaly_time_end and int(o.l10n_de_fiskaly_time_end.timestamp()) or 0,
                    "user": {
                        "user_export_id": f"{(o.user_id or o.create_uid).id}",
                        "name": f"{(o.user_id or o.create_uid).name[:50]}",
                    },
                    "buyer": buyer,
                },
                "data": {
                    "full_amount_incl_vat": float_repr(o.amount_total, precision),
                    "payment_types": payment_types,
                    "amounts_per_vat_id": o._l10n_de_amounts_per_vat(),
                    "lines": lines_data,
                },
                # `l10n_de_fiskaly_signature_public_key` is set only when the transaction finishes successfully (no 5xx errors or network issues).
                "security": {"tss_tx_id": f"{o.l10n_de_fiskaly_transaction_uuid}"} if o.l10n_de_fiskaly_signature_public_key else {"error_message": "Error while reaching TSS may be due to network issues or TSS unavailability."},
            }
            transactions.append(transaction)

        return {
            "client_id": config.l10n_de_fiskaly_client_id,
            "cash_point_closing_export_id": session.id,
            "head": {
                "export_creation_date": int(session.write_date.timestamp()),
                "first_transaction_export_id": f"{orders[0].id}",
                "last_transaction_export_id": f"{orders[-1].id}",
            },
            "cash_statement": {
                "business_cases": self.get_cash_statement_cases(transactions),
                "payment": {
                    "full_amount": float_repr(total_cash + total_bank, precision),
                    "cash_amount": float_repr(total_cash, precision),
                    "cash_amounts_by_currency": [
                        {"currency_code": "EUR", "amount": float_repr(total_cash, precision)}
                    ],
                    "payment_types":
                        ([{"type": "Bar", "currency_code": "EUR", "amount": float_repr(total_cash, precision)}]
                            if total_cash or not total_bank else []) +
                        ([{"type": "Unbar", "currency_code": "EUR", "amount": float_repr(total_bank, precision)}]
                            if total_bank else [])
                }
            },
            "transactions": transactions,
        }

    def _l10n_de_send_fiskaly_cash_point_closing(self, json):
        cash_point_closing_uuid = str(uuid.uuid4())
        cash_register_resp = self.company_id._l10n_de_fiskaly_dsfinvk_rpc('GET', '/cash_registers/%s' % self.config_id.l10n_de_fiskaly_client_id)
        if cash_register_resp.status_code == 404:  # register the cash register
            self._l10n_de_create_fiskaly_cash_register()
        cash_point_closing_resp = self.company_id._l10n_de_fiskaly_dsfinvk_rpc('PUT', '/cash_point_closings/%s' % cash_point_closing_uuid, json)
        if cash_point_closing_resp.status_code != 200:
            raise UserError(_('Cash point closing error with Fiskaly: \n %s', cash_point_closing_resp.json()))
        self.write({'l10n_de_fiskaly_cash_point_closing_uuid': cash_point_closing_uuid})

    def _l10n_de_create_fiskaly_cash_register(self):
        json = {
            'cash_register_type': {
                'type': 'MASTER',
                'tss_id': self.config_id._l10n_de_get_tss_id()
            },
            'brand': 'Odoo',
            'model': 'Odoo',
            'base_currency_code': 'EUR',
            'software': {
                'version': release.version
            }
        }

        self.company_id._l10n_de_fiskaly_dsfinvk_rpc('PUT', '/cash_registers/%s' % self.config_id.l10n_de_fiskaly_client_id, json)
