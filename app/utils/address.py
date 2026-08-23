from __future__ import annotations

import re


def parse_frontend_address(address_text: str, *, default_postcode: str = "") -> dict:
    cleaned = " ".join(address_text.strip().split())
    parts = [part.strip() for part in cleaned.split(",") if part.strip()]
    street = parts[0] if parts else cleaned
    locality = parts[1] if len(parts) > 1 else ""
    state = "NSW"
    postcode = default_postcode

    locality_match = re.match(r"^(?P<suburb>.*?)(?:\s+(?P<state>[A-Z]{2,3}))?(?:\s+(?P<postcode>\d{4}))?$", locality)
    if locality_match:
        suburb = (locality_match.group("suburb") or "").strip()
        state = locality_match.group("state") or state
        postcode = locality_match.group("postcode") or postcode
    else:
        suburb = locality

    return {
        "street": street,
        "suburb": suburb,
        "state": state,
        "postcode": postcode,
        "full_address": cleaned,
    }
