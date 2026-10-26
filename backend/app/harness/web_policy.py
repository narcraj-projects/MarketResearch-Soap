"""Public destination, DNS/peer pinning and conservative robots policy."""
from dataclasses import dataclass
import ipaddress
import re
from urllib.parse import quote, unquote, urlsplit

from .policy import PolicyDenied
from .urls import normalize_url

USER_AGENT = "LatherLensBot"


def safe_url(raw: str) -> str:
    try:
        canonical, _ = normalize_url(raw, demo=True)
        decoded = unquote(unquote(urlsplit(canonical).path)).lower()
        if any(piece in {".", ".."} for piece in decoded.split("/")) or decoded.count("/") != urlsplit(canonical).path.count("/"):
            raise ValueError()
        if any(piece in decoded.split("/") for piece in ("login", "signin", "sign-in", "account", "admin", "wp-admin", "checkout", "cart")):
            raise ValueError()
        if re.search(r"(?:[?&])(?:api_key|token|authorization|session|signature|password)=", canonical, re.I):
            raise ValueError()
        if "\\" in decoded or any(ord(c) < 32 for c in decoded):
            raise ValueError()
        return canonical
    except ValueError:
        raise PolicyDenied("unsafe_url") from None


def public_ip(value: str) -> str:
    try:
        ip = ipaddress.ip_address(value)
        if not ip.is_global or ip.is_multicast or ip.is_unspecified or ip.is_reserved:
            raise ValueError()
        if isinstance(ip, ipaddress.IPv6Address) and (ip.ipv4_mapped is not None or ip.sixtofour is not None or ip.teredo is not None):
            raise ValueError()
        # The globally routed well-known NAT64 prefix can translate private IPv4.
        if ip in ipaddress.ip_network("64:ff9b::/96"):
            raise ValueError()
        return str(ip)
    except ValueError:
        raise PolicyDenied("nonpublic_address") from None


@dataclass(frozen=True)
class Destination:
    url: str
    hostname: str
    port: int
    ip: str


def destination(raw: str, addresses: tuple[str, ...]) -> Destination:
    url = safe_url(raw)
    if not addresses or len(addresses) > 32:
        raise PolicyDenied("dns_unavailable")
    # Reject the ENTIRE answer if any A/AAAA record is nonpublic, not just the first.
    ips = tuple(public_ip(address) for address in addresses)
    parsed = urlsplit(url)
    return Destination(url, parsed.hostname or "", 443 if parsed.scheme == "https" else 80, ips[0])


def verify_peer(target: Destination, peer: str | None) -> None:
    if peer is None or public_ip(peer) != target.ip:
        raise PolicyDenied("peer_mismatch")


def rep_path(value: str) -> str:
    def escape(match):
        char = chr(int(match[1], 16))
        return char if char.isascii() and (char.isalnum() or char in "-._~") else "%" + match[1].upper()
    return re.sub(r"%([0-9a-fA-F]{2})", escape, quote(value, safe="/%?=&:$*+;,@!~-._"))


class Robots:
    """RFC-style longest match, merged agent groups, Allow wins an equal match.

    Unsupported robots response statuses/redirects are handled as deny by the gateway.
    Crawl-delay is a conservative extension, not an RFC 9309 directive.
    """
    def __init__(self, text: str):
        groups: list[tuple[list[str], list[tuple[str, str]], float]] = []
        agents: list[str] = []
        rules: list[tuple[str, str]] = []
        delay = 0.0
        directives = False
        for line in [*text.splitlines(), "User-agent: __end__"]:
            key, separator, value = line.split("#", 1)[0].strip().partition(":")
            if not separator:
                continue
            key, value = key.strip().lower(), value.strip()
            if key == "user-agent":
                if directives:
                    groups.append((agents, rules, delay))
                    agents, rules, delay, directives = [], [], 0.0, False
                agents.append(value.lower())
            elif agents and key in {"allow", "disallow", "crawl-delay"}:
                directives = True
                if key == "crawl-delay":
                    try:
                        parsed = float(value)
                        if not 0 <= parsed <= 60:
                            raise ValueError()
                        delay = max(delay, parsed)
                    except ValueError:
                        raise PolicyDenied("robots_invalid_delay") from None
                elif value:
                    rules.append((key, rep_path(value)))
        scores = [(max((len(agent) for agent in a if agent != "*" and agent in USER_AGENT.lower()), default=0), a, r, d) for a, r, d in groups]
        best = max((s for s, _, _, _ in scores), default=0)
        chosen = [(r, d) for s, a, r, d in scores if (s == best and best > 0) or (best == 0 and "*" in a)]
        self.rules = [rule for rules, _ in chosen for rule in rules]
        self.delay = max((d for _, d in chosen), default=0.0)

    def allows(self, url: str) -> bool:
        parsed = urlsplit(url)
        path = rep_path((parsed.path or "/") + ("?" + parsed.query if parsed.query else ""))
        matches = []
        for kind, pattern in self.rules:
            anchored = pattern.endswith("$")
            pattern = pattern[:-1] if anchored else pattern
            expression = "^" + re.escape(pattern).replace(r"\*", ".*") + ("$" if anchored else "")
            if re.search(expression, path):
                matches.append((len(pattern.replace("*", "")), kind == "allow"))
        return not matches or max(matches)[1]
