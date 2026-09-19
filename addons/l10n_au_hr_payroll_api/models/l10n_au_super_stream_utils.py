# Part of Odoo. See LICENSE file for full copyright and licensing details.

import time
from odoo.tools import float_round
from odoo.addons.l10n_au_hr_payroll_account.models.l10n_au_stp import split_name
from odoo.addons.l10n_au_hr_payroll_account.models.l10n_au_super_stream import (
    L10n_AuSuperStreamLine,
    L10n_auSuperStream,
)


def contactDetails(contact):
    contact.ensure_one()
    first_name, last_name = split_name(contact.name)
    return {
        "name": {
            "title": contact.title.shortcut or "",
            "firstName": first_name,
            "lastName": last_name,
        },
        "phoneNumber": {
            "type": "MOBILE_PHONE",
            "value": contact.mobile,
        } if contact.mobile else {
            "type": "LAND_LINE",
            "value": contact.phone,
        },
        "email": {
            "value": contact.email,
        },
    }


def bankAccount(bank_account):
    return {
        "accountName": bank_account.acc_holder_name,
        "bsb": bank_account.aba_bsb,
        "accountNumber": bank_account.acc_number,
    }


def employerDetails(super_record):
    super_record.ensure_one()
    first_name, last_name = split_name(super_record.l10n_au_super_stream_lines.sender_id.name)
    return {
        "organisationName": super_record.company_id.name,
        "australianBusinessNumber": str(
            super_record.company_id.vat and super_record.company_id.vat.replace(" ", "")
        ),
        "paymentDetails": {
            "paymentType": "DIRECTDEBIT",
            "directDebit": {
                "bankAccount": bankAccount(super_record.journal_id.bank_account_id),
                "directDebitPaymentAmount": {
                    "value": super_record.amount_total,
                    "currency": super_record.currency_id.name,
                },
            },
        },
        "refundAccount": bankAccount(super_record.journal_id.bank_account_id),
        "contactDetails": {
            "name": {
                "firstName": first_name,
                "lastName": last_name,
            },
            "phoneNumber": {
                "type": "MOBILE_PHONE",
                "value": super_record.l10n_au_super_stream_lines.sender_id.private_phone,
            } if super_record.l10n_au_super_stream_lines.sender_id.private_phone else {
                "type": "LAND_LINE",
                "value": super_record.l10n_au_super_stream_lines.sender_id.work_phone,
            },
            "email": {
                "value": super_record.l10n_au_super_stream_lines.sender_id.work_email,
            },
        },
    }


def transactionFund(fund):
    if fund.fund_type == "APRA":
        return {"usi": fund.usi}
    else:
        return {
            "organisationDetails": {
                "organisationName": fund.display_name,
                "australianBusinessNumber": fund.abn,
            },
            "esa": {"alias": fund.esa},
            "account": bankAccount(fund.bank_account_id),
        }


def memberContribution(super_line: L10n_AuSuperStreamLine):
    GENDERS = {"male": "MALE", "female": "FEMALE", "other": "NOT_STATED"}
    employee = super_line.employee_id
    first_name, last_name = split_name(employee.name)
    contribution = {
        "name": {
            "firstName": first_name,
            "lastName": last_name,
        },
        "gender": GENDERS[employee.sex],
        "dob": {
            "year": employee.birthday.year,
            "month": employee.birthday.strftime("%B").upper(),
            "day": employee.birthday.day,
        },
        "email": {
            "value": employee.private_email,
        },
        "phoneNumber": {
            "type": "MOBILE_PHONE",
            "value": employee.private_phone,
        },
        "taxFileNumber": employee.l10n_au_tfn,
        "memberNumber": super_line.super_account_id.member_nbr,
        "employmentPayrollNumber": employee.l10n_au_payroll_id,
        "employmentStartDate": int(time.mktime(super_line.employment_start_date.timetuple()) * 1000),
        "payPeriodStartDate": int(time.mktime(super_line.start_date.timetuple()) * 1000),
        "payPeriodEndDate": int(time.mktime(super_line.end_date.timetuple()) * 1000),
        "totalMemberContributionAmount": {
            "value": super_line.amount_total,
            "currency": super_line.currency_id.name,
        },
    }

    if employee.private_country_id.code == "AU":
        contribution["address"] = {
            "australianAddress": {
                "line1": employee.private_street,
                **(
                    {"line2": employee.private_street2}
                    if employee.private_street2
                    else {}
                ),
                "suburb": employee.private_city,
                "postCode": employee.private_zip,
                "stateOrTerritory": employee.private_state_id.code,
                "countryCode": employee.private_country_id.code,
            }
        }
    else:
        contribution["address"] = {
            "internationalAddress": {
                "line1": employee.private_street,
                **(
                    {"line2": employee.private_street2}
                    if employee.private_street2
                    else {}
                ),
                "suburb": employee.private_city,
                "postCode": employee.private_zip,
                "stateOrTerritory": employee.private_state_id.code,
                "country": employee.private_country_id.name,
            }
        }
    if super_line.superannuation_guarantee_amount:
        contribution["superGuaranteeAmount"] = {
            "value": super_line.superannuation_guarantee_amount,
            "currency": super_line.currency_id.name,
        }
    if super_line.award_or_productivity_amount:
        contribution["awardOrProductivityAmount"] = {
            "value": super_line.award_or_productivity_amount,
            "currency": super_line.currency_id.name,
        }
    if super_line.personal_contributions_amount:
        contribution["personalContributionsAmount"] = {
            "value": super_line.personal_contributions_amount,
            "currency": super_line.currency_id.name,
        }
    if super_line.salary_sacrificed_amount:
        contribution["salarySacrificedAmount"] = {
            "value": abs(super_line.salary_sacrificed_amount),
            "currency": super_line.currency_id.name,
        }
    if super_line.voluntary_amount:
        contribution["voluntaryAmount"] = {
            "value": super_line.voluntary_amount,
            "currency": super_line.currency_id.name,
        }
    if super_line.spouse_contributions_amount:
        contribution["spouseContributionsAmount"] = {
            "value": super_line.spouse_contributions_amount,
            "currency": super_line.currency_id.name,
        }
    if super_line.child_contributions_amount:
        contribution["childContributionsAmount"] = {
            "value": super_line.child_contributions_amount,
            "currency": super_line.currency_id.name,
        }
    if super_line.other_third_party_contributions_amount:
        contribution["otherThirdPartyContributionsAmount"] = {
            "value": super_line.other_third_party_contributions_amount,
            "currency": super_line.currency_id.name,
        }
    if employee.departure_date:
        contribution["employmentEndDate"] = time.mktime(employee.departure_date.timetuple())
        contribution["employmentEndReason"] = employee.departure_reason_id.name or ""
    return contribution


def contributionDetails(super_stream: L10n_auSuperStream, members=True):
    contributions = {
        "employer": {"employerDetails": employerDetails(super_stream), "funds": []}
    }
    for fund, lines in super_stream.l10n_au_super_stream_lines.grouped("payee_id").items():
        contribution = {}
        if members:
            contribution["members"] = [memberContribution(line) for line in lines]
            contribution["amountForFund"] = {
                "value": float_round(sum(lines.mapped("amount_total")), precision_rounding=lines[0].currency_id.rounding),
                "currency": lines[0].currency_id.name,
            }

        if fund.fund_type == "APRA":
            contribution["fund"] = transactionFund(fund)
        else:
            contribution["smsf"] = transactionFund(fund)
        contributions["employer"]["funds"].append(contribution)
    return contributions
