#!/usr/bin/env python3
"""Export Genesys Cloud response-management responses to CSV."""

import base64
import csv
import json
import os
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


def get_page(path, token, page_number):
    query = urlencode({"pageNumber": page_number, "pageSize": PAGE_SIZE})
    return request_json(
        f"{API_BASE}{path}?{query}",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
    )


def get_all_pages(path, token):
    page_number = 1
    while True:
        result = get_page(path, token, page_number)
        entities = result.get("entities") or []
        yield from entities

        page_count = result.get("pageCount")
        if page_count is not None:
            if page_number >= page_count:
                break
        elif len(entities) < PAGE_SIZE:
            break
        page_number += 1


def collect_responses(token):
    responses_by_id = {}
    libraries = get_all_pages("/api/v2/responsemanagement/libraries", token)

    for library in libraries:
        library_id = library.get("id")
        if not library_id:
            continue

        page_number = 1
        while True:
            query = urlencode(
                {"libraryId": library_id, "pageNumber": page_number, "pageSize": PAGE_SIZE}
            )
            result = request_json(
                f"{API_BASE}/api/v2/responsemanagement/responses?{query}",
                headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            )
            entities = result.get("entities") or []
            library_name = library.get("name", "")

            for response in entities:
                response_id = response.get("id") or json.dumps(response, sort_keys=True)
                record = responses_by_id.setdefault(
                    response_id,
                    {"response": response, "libraries": set()},
                )
                if library_name:
                    record["libraries"].add(library_name)

            page_count = result.get("pageCount")
            if page_count is not None:
                if page_number >= page_count:
                    break
            elif len(entities) < PAGE_SIZE:
                break
            page_number += 1

    return responses_by_id


def write_csv(responses_by_id):
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_path = EXPORT_DIR / f"canned_responses_{timestamp}.csv"
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
    client_id = os.environ.get("CLIENT_ID") or os.environ.get("GENESYS_CLIENT_ID")
    client_secret = os.environ.get("CLIENT_SECRET") or os.environ.get("GENESYS_CLIENT_SECRET")
    if not client_id or not client_secret:
        print(
            "Set CLIENT_ID and CLIENT_SECRET before running this script.",
            file=sys.stderr,
        )
        return 2

    try:
        token = get_access_token(client_id, client_secret)
        responses = collect_responses(token)
        output_path = write_csv(responses)
    except (KeyError, RuntimeError, json.JSONDecodeError) as error:
        print(f"Export failed: {error}", file=sys.stderr)
        return 1

    print(f"Exported {len(responses)} unique responses to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
