#!/usr/bin/env python3
"""Export Genesys Cloud canned responses from libraries belonging to one country."""

import argparse
import base64
import csv
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


REGION_DOMAIN = (
    os.environ.get("GENESYS_REGION")
    or os.environ.get("GENESYS_REGION_DOMAIN")
    or "mypurecloud.de"
).strip()
API_BASE = f"https://api.{REGION_DOMAIN}"
TOKEN_URL = f"https://login.{REGION_DOMAIN}/oauth/token"
PAGE_SIZE = 100
TIMEOUT_SECONDS = 60
EXPORT_DIR = Path(__file__).resolve().parent / "exports"

# ISO 3166-1 alpha-2 codes; extra spellings are separated by "|".
COUNTRY_DATA = """
AD Andorra
AE United Arab Emirates|UAE
AF Afghanistan
AG Antigua and Barbuda
AI Anguilla
AL Albania
AM Armenia
AO Angola
AQ Antarctica
AR Argentina
AS American Samoa
AT Austria
AU Australia
AW Aruba
AX Åland Islands|Aland Islands
AZ Azerbaijan
BA Bosnia and Herzegovina
BB Barbados
BD Bangladesh
BE Belgium
BF Burkina Faso
BG Bulgaria
BH Bahrain
BI Burundi
BJ Benin
BL Saint Barthélemy|Saint Barthelemy
BM Bermuda
BN Brunei
BO Bolivia
BQ Caribbean Netherlands
BR Brazil
BS Bahamas
BT Bhutan
BV Bouvet Island
BW Botswana
BY Belarus
BZ Belize
CA Canada
CC Cocos Islands
CD Democratic Republic of the Congo|DR Congo
CF Central African Republic
CG Republic of the Congo
CH Switzerland
CI Côte d'Ivoire|Cote d'Ivoire|Ivory Coast
CK Cook Islands
CL Chile
CM Cameroon
CN China
CO Colombia
CR Costa Rica
CU Cuba
CV Cabo Verde|Cape Verde
CW Curaçao|Curacao
CX Christmas Island
CY Cyprus
CZ Czechia|Czech Republic
DE Germany
DJ Djibouti
DK Denmark
DM Dominica
DO Dominican Republic
DZ Algeria
EC Ecuador
EE Estonia
EG Egypt
EH Western Sahara
ER Eritrea
ES Spain
ET Ethiopia
FI Finland
FJ Fiji
FK Falkland Islands
FM Micronesia
FO Faroe Islands
FR France
GA Gabon
GB United Kingdom|Great Britain|UK
GD Grenada
GE Georgia
GF French Guiana
GG Guernsey
GH Ghana
GI Gibraltar
GL Greenland
GM Gambia
GN Guinea
GP Guadeloupe
GQ Equatorial Guinea
GR Greece
GS South Georgia and the South Sandwich Islands
GT Guatemala
GU Guam
GW Guinea-Bissau
GY Guyana
HK Hong Kong
HM Heard Island and McDonald Islands
HN Honduras
HR Croatia
HT Haiti
HU Hungary
ID Indonesia
IE Ireland
IL Israel
IM Isle of Man
IN India
IO British Indian Ocean Territory
IQ Iraq
IR Iran
IS Iceland
IT Italy
JE Jersey
JM Jamaica
JO Jordan
JP Japan
KE Kenya
KG Kyrgyzstan
KH Cambodia
KI Kiribati
KM Comoros
KN Saint Kitts and Nevis
KP North Korea
KR South Korea
KW Kuwait
KY Cayman Islands
KZ Kazakhstan
LA Laos
LB Lebanon
LC Saint Lucia
LI Liechtenstein
LK Sri Lanka
LR Liberia
LS Lesotho
LT Lithuania
LU Luxembourg
LV Latvia
LY Libya
MA Morocco
MC Monaco
MD Moldova
ME Montenegro
MF Saint Martin
MG Madagascar
MH Marshall Islands
MK North Macedonia
ML Mali
MM Myanmar
MN Mongolia
MO Macao|Macau
MP Northern Mariana Islands
MQ Martinique
MR Mauritania
MS Montserrat
MT Malta
MU Mauritius
MV Maldives
MW Malawi
MX Mexico
MY Malaysia
MZ Mozambique
NA Namibia
NC New Caledonia
NE Niger
NF Norfolk Island
NG Nigeria
NI Nicaragua
NL Netherlands|Holland
NO Norway
NP Nepal
NR Nauru
NU Niue
NZ New Zealand
OM Oman
PA Panama
PE Peru
PF French Polynesia
PG Papua New Guinea
PH Philippines
PK Pakistan
PL Poland
PM Saint Pierre and Miquelon
PN Pitcairn Islands
PR Puerto Rico
PS Palestine
PT Portugal
PW Palau
PY Paraguay
QA Qatar
RE Réunion|Reunion
RO Romania
RS Serbia
RU Russia
RW Rwanda
SA Saudi Arabia
SB Solomon Islands
SC Seychelles
SD Sudan
SE Sweden
SG Singapore
SH Saint Helena
SI Slovenia
SJ Svalbard and Jan Mayen
SK Slovakia
SL Sierra Leone
SM San Marino
SN Senegal
SO Somalia
SR Suriname
SS South Sudan
ST São Tomé and Príncipe|Sao Tome and Principe
SV El Salvador
SX Sint Maarten
SY Syria
SZ Eswatini|Swaziland
TC Turks and Caicos Islands
TD Chad
TF French Southern Territories
TG Togo
TH Thailand
TJ Tajikistan
TK Tokelau
TL Timor-Leste|East Timor
TM Turkmenistan
TN Tunisia
TO Tonga
TR Türkiye|Turkiye|Turkey
TT Trinidad and Tobago
TV Tuvalu
TW Taiwan
TZ Tanzania
UA Ukraine
UG Uganda
UM United States Minor Outlying Islands
US United States|USA
UY Uruguay
UZ Uzbekistan
VA Vatican City
VC Saint Vincent and the Grenadines
VE Venezuela
VG British Virgin Islands
VI U.S. Virgin Islands|US Virgin Islands
VN Vietnam|Viet Nam
VU Vanuatu
WF Wallis and Futuna
WS Samoa
YE Yemen
YT Mayotte
ZA South Africa
ZM Zambia
ZW Zimbabwe
"""

COUNTRY_NAMES = {
    code: names.split("|")
    for code, names in (line.split(" ", 1) for line in COUNTRY_DATA.strip().splitlines())
}


def word_pattern(text):
    return re.compile(rf"\b{re.escape(text)}\b", re.IGNORECASE)


def build_library_matcher(country_code):
    names = COUNTRY_NAMES[country_code]
    code_pattern = re.compile(rf"^\s*{country_code}(?![A-Za-z])")
    name_patterns = [word_pattern(name) for name in names]
    # Prevents e.g. "Guinea" from matching "Papua New Guinea" or "Sudan" matching "South Sudan".
    containing_names = [
        word_pattern(other_name)
        for other_code, other_names in COUNTRY_NAMES.items()
        if other_code != country_code
        for other_name in other_names
        if any(pattern.search(other_name) for pattern in name_patterns)
    ]

    def matches(library_name):
        if code_pattern.match(library_name):
            return True
        remaining = library_name
        for pattern in containing_names:
            remaining = pattern.sub(" ", remaining)
        return any(pattern.search(remaining) for pattern in name_patterns)

    return matches


def request_json(url, *, headers=None, data=None):
    request = Request(url, headers=headers or {}, data=data)
    try:
        with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        raise RuntimeError(f"Genesys Cloud returned HTTP {error.code}") from error
    except URLError as error:
        raise RuntimeError(f"Could not connect to Genesys Cloud: {error.reason}") from error


def get_access_token(client_id, client_secret):
    credentials = base64.b64encode(f"{client_id}:{client_secret}".encode("utf-8")).decode("ascii")
    return request_json(
        TOKEN_URL,
        headers={
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data=urlencode({"grant_type": "client_credentials"}).encode("ascii"),
    )["access_token"]


def get_all_pages(path, token, params=None):
    page_number = 1
    while True:
        query = urlencode({**(params or {}), "pageNumber": page_number, "pageSize": PAGE_SIZE})
        result = request_json(
            f"{API_BASE}{path}?{query}",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        )
        entities = result.get("entities") or []
        yield from entities

        page_count = result.get("pageCount")
        if page_count is not None:
            if page_number >= page_count:
                break
        elif len(entities) < PAGE_SIZE:
            break
        page_number += 1


def collect_responses(token, libraries):
    responses_by_id = {}
    for library in libraries:
        for response in get_all_pages(
            "/api/v2/responsemanagement/responses", token, {"libraryId": library["id"]}
        ):
            response_id = response.get("id") or json.dumps(response, sort_keys=True)
            record = responses_by_id.setdefault(response_id, {"response": response, "libraries": set()})
            record["libraries"].add(library.get("name", ""))
    return responses_by_id


def write_csv(country_code, responses_by_id):
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_path = EXPORT_DIR / f"canned_responses_{country_code}_{timestamp}.csv"
    columns = ["id", "name", "response_type", "libraries", "texts", "raw_json"]

    with output_path.open("w", newline="", encoding="utf-8-sig") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=columns)
        writer.writeheader()
        for record in responses_by_id.values():
            response = record["response"]
            writer.writerow(
                {
                    "id": response.get("id", ""),
                    "name": response.get("name", ""),
                    "response_type": response.get("responseType", ""),
                    "libraries": json.dumps(sorted(record["libraries"]), ensure_ascii=False),
                    "texts": json.dumps(response.get("texts", []), ensure_ascii=False),
                    "raw_json": json.dumps(response, ensure_ascii=False, sort_keys=True),
                }
            )

    return output_path


def main():
    parser = argparse.ArgumentParser(
        description="Export canned responses from libraries for one country (e.g. SE, AT, AU)."
    )
    parser.add_argument("country_code", help="Two-letter ISO country code, e.g. SE")
    country_code = parser.parse_args().country_code.strip().upper()
    if country_code not in COUNTRY_NAMES:
        print(f"Unknown country code: {country_code}", file=sys.stderr)
        return 2

    client_id = os.environ.get("CLIENT_ID") or os.environ.get("GENESYS_CLIENT_ID")
    client_secret = os.environ.get("CLIENT_SECRET") or os.environ.get("GENESYS_CLIENT_SECRET")
    if not client_id or not client_secret:
        print(
            "Set CLIENT_ID and CLIENT_SECRET before running this script.",
            file=sys.stderr,
        )
        return 2

    matches = build_library_matcher(country_code)
    try:
        token = get_access_token(client_id, client_secret)
        libraries = [
            library
            for library in get_all_pages("/api/v2/responsemanagement/libraries", token)
            if library.get("id") and matches(library.get("name", ""))
        ]
        if not libraries:
            names = ", ".join(COUNTRY_NAMES[country_code])
            print(f"No libraries found starting with {country_code} or naming {names}.")
            return 1

        print("Matched libraries:")
        for library in libraries:
            print(f"  - {library.get('name', '')}")

        responses = collect_responses(token, libraries)
        output_path = write_csv(country_code, responses)
    except (KeyError, RuntimeError, json.JSONDecodeError) as error:
        print(f"Export failed: {error}", file=sys.stderr)
        return 1

    print(f"Exported {len(responses)} unique responses to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
