"""DNS verification for custom domains (TXT at _mybaas.<hostname>)."""

from __future__ import annotations

import dns.resolver
from dns.exception import DNSException


def txt_record_contains_token(hostname: str, expected_token: str) -> bool:
    """
    Return True if a TXT record at `hostname` contains the exact verification token.

    `hostname` is typically `_mybaas.shop.example.com`.
    """
    if not hostname or not expected_token:
        return False
    try:
        answers = dns.resolver.resolve(hostname, "TXT")
    except (DNSException, OSError):
        return False
    for rdata in answers:
        for part in rdata.strings:
            s = part.decode("utf-8") if isinstance(part, bytes) else part
            s = s.strip().strip('"')
            if s == expected_token:
                return True
    return False


def verification_txt_hostname(domain: str) -> str:
    """DNS name for the TXT record the merchant must create."""
    return f"_mybaas.{domain}"
