import datetime
import re

import ofxparse


class OfxParser(ofxparse.OfxParser):
    """ This class monkey-patches the ofxparse library in order to fix the following known bug: ',' is a valid
        decimal separator for amounts, as we can encounter in ofx files made by european banks.
    """

    @classmethod
    def decimal_separator_cleanup(cls, tag):
        if hasattr(tag, "contents"):
            tag.string = tag.contents[0].replace(',', '.')

    @classmethod
    def parseStatement(cls, stmt_ofx):
        ledger_bal_tag = stmt_ofx.find('ledgerbal')
        if hasattr(ledger_bal_tag, "contents"):
            balamt_tag = ledger_bal_tag.find('balamt')
            cls.decimal_separator_cleanup(balamt_tag)
        avail_bal_tag = stmt_ofx.find('availbal')
        if hasattr(avail_bal_tag, "contents"):
            balamt_tag = avail_bal_tag.find('balamt')
            cls.decimal_separator_cleanup(balamt_tag)
        return super().parseStatement(stmt_ofx)

    @classmethod
    def parseTransaction(cls, txn_ofx):
        amt_tag = txn_ofx.find('trnamt')
        cls.decimal_separator_cleanup(amt_tag)
        return super().parseTransaction(txn_ofx)

    @classmethod
    def parseInvestmentPosition(cls, ofx):
        tag = ofx.find('units')
        cls.decimal_separator_cleanup(tag)
        tag = ofx.find('unitprice')
        cls.decimal_separator_cleanup(tag)
        return super().parseInvestmentPosition(ofx)

    @classmethod
    def parseInvestmentTransaction(cls, ofx):
        tag = ofx.find('units')
        cls.decimal_separator_cleanup(tag)
        tag = ofx.find('unitprice')
        cls.decimal_separator_cleanup(tag)
        return super().parseInvestmentTransaction(ofx)

    @classmethod
    def parseOfxDateTime(cls, ofxDateTime):
        res = re.search(r"^[0-9]*\.([0-9]{0,5})", ofxDateTime)
        if res:
            msec = datetime.timedelta(seconds=float("0." + res.group(1)))
        else:
            msec = datetime.timedelta(seconds=0)

        # Some banks seem to return some OFX dates as YYYY-MM-DD; so we remove
        # the '-' characters to support them as well
        ofxDateTime = ofxDateTime.replace('-', '')

        try:
            local_date = datetime.datetime.strptime(
                ofxDateTime[:14], '%Y%m%d%H%M%S'
            )
            return local_date + msec
        except Exception:  # noqa: BLE001
            if not ofxDateTime or ofxDateTime[:8] == "00000000":
                return None

            return datetime.datetime.strptime(
                ofxDateTime[:8], '%Y%m%d') + msec
