"""Offline canonicalization, not a fetcher or DNS/redirect authorization service."""
import ipaddress
import re
from urllib.parse import parse_qsl, unquote, urlencode, urlsplit, urlunsplit

import tldextract

_suffixes = tldextract.TLDExtract(cache_dir=None, suffix_list_urls=(), include_psl_private_domains=True)
_tracking = {"gclid", "fbclid", "msclkid"}


def normalize_url(raw: str, *, demo: bool = False) -> tuple[str, str]:
    try:
        if (not raw or len(raw) > 4000 or any(ord(c) <= 32 or ord(c) == 127 for c in raw)
            or any(ord(c) < 32 or ord(c) == 127 for c in unquote(raw)) or "\\" in raw):
            raise ValueError()
        url = urlsplit(raw)
        host = (url.hostname or "").rstrip(".").encode("idna").decode("ascii").lower()
        if url.scheme not in {"http", "https"} or url.username is not None or url.password is not None:
            raise ValueError()
        if not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?", host) or ".." in host:
            raise ValueError()
        labels = host.split(".")
        if len(labels) < 2 or any(len(label) > 63 or label.startswith("-") or label.endswith("-") for label in labels):
            raise ValueError()
        try:
            ipaddress.ip_address(host)
        except ValueError:
            pass
        else:
            raise ValueError()
        if host.endswith((".localhost", ".local", ".internal", ".test", ".example")) or labels[-1].isdigit():
            raise ValueError()
        if host.endswith(".invalid") and not demo:
            raise ValueError()
        port = url.port
        if port not in {None, 80 if url.scheme == "http" else 443}:
            raise ValueError()
        suffix = _suffixes(host)
        domain = suffix.top_domain_under_public_suffix
        if not domain:
            if not (demo and host.endswith(".invalid")):
                raise ValueError()
            domain = ".".join(labels[-2:])
        query = [(k, v) for k, v in parse_qsl(url.query, keep_blank_values=True) if not k.lower().startswith("utm_") and k.lower() not in _tracking]
        sensitive = {"api_key", "apikey", "key", "token", "access_token", "authorization", "session", "signature", "password", "client_secret", "x-amz-signature", "x-amz-credential"}
        if any(unquote(unquote(k)).lower().replace("-", "_") in {name.replace("-", "_") for name in sensitive} for k, _ in query):
            raise ValueError()
        # Preserve scheme, meaningful query order and case-sensitive path identity.
        canonical = urlunsplit((url.scheme, host, url.path or "/", urlencode(query), ""))
        return canonical, domain
    except (ValueError, UnicodeError):
        raise ValueError("unsafe_source_url") from None
