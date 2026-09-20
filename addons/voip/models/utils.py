import re

try:
    import phonenumbers
    from phonenumbers import COUNTRY_CODE_TO_REGION_CODE
except ImportError:
    phonenumbers = None


INTERNATIONAL_PHONE_NUMBER_RE = re.compile(
    r"""
    ^                           # Start of the string
    (?:\++|00)                  # Match one or more '+' or '00' at the beginning
    (?P<phone_number>[1-9]\d*)  # a non-zero digit followed by any digits
    $                           # End of the string
    """,
    re.VERBOSE,
)


def extract_country_code(phone_number):
    if not phonenumbers:
        return {"iso": "", "itu": ""}

    def extract_country_code_from_partial_number(phone_number):
        match = INTERNATIONAL_PHONE_NUMBER_RE.match(phone_number)
        if not match:
            return {"iso": "", "itu": ""}
        sanitized_number = match.group("phone_number")  # the phone number without the + or 00
        for length in range(min(4, len(sanitized_number) + 1), 0, -1):  # 3 is the max length of a country code
            country_code = int(sanitized_number[:length])
            if (
                country_code in COUNTRY_CODE_TO_REGION_CODE
                # Only accept country codes that map to exactly one region
                # (e.g., accept 44->['GB'] for UK, reject 1->['US','CA',...] for North America)
                and len(COUNTRY_CODE_TO_REGION_CODE[country_code]) == 1
            ):
                region_code = phonenumbers.region_code_for_country_code(country_code)
                return {
                    "iso": region_code.lower() if region_code != "ZZ" else "",
                    "itu": str(country_code) if region_code != "ZZ" else "",
                }
        return {"iso": "", "itu": ""}

    if len(phone_number) >= 6 and phonenumbers:
        try:
            parsed_number = phonenumbers.parse(phone_number, None)
            country_code = phonenumbers.region_code_for_number(parsed_number)
            if country_code:
                return {
                    "iso": country_code.lower(),
                    "itu": str(parsed_number.country_code),
                }
        except phonenumbers.NumberParseException:
            pass
    return extract_country_code_from_partial_number(phone_number)
