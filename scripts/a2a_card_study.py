#!/usr/bin/env python3
"""State of public A2A agents (Q4 plan F1): who publishes an Agent Card, and
is it valid, signed and verifiable?

Hosts come from three public sources, and every row records which:

  roster  the homepage host of every listing on the live board (/api/v1/agents)
  mcp     the host of every remote URL in the official MCP registry (latest versions)
  a2areg  Agent Card URLs on the A2A Registry agent pages its public sitemap lists
          (a sample: its full listing sits behind an API that needs an account)

Per host it fetches only the discovery documents any public client reads:

  /.well-known/agent-card.json   A2A 0.3 and 1.0
  /.well-known/agent.json        A2A before 0.3
  /.well-known/ai-catalog.json   AI Catalog (cross-protocol, links MCP and A2A cards)

and, for a sample of each host's MCP remote URLs, <url>/server-card (SEP-2127).
For a signed card it also fetches the key set its signature names (`jku`).

Politeness: robots.txt is honoured for every host (an unreachable host is
skipped), requests carry an identifying User-Agent, each host is fetched by one
worker with a pause between requests, responses are capped at 512 KB, and a
timeout is 10 s. It never sends credentials and never calls an agent's API.

Signature checks are best-effort. A2A 1.0 signs the card after removing
default-valued fields per its protobuf schema; without that schema we try the
card as served and two approximations of the stripped form, and report a card
as `verified` only when one of them checks out. A signed card we can't verify
is reported as exactly that, never as forged.

Usage:
    python scripts/a2a_card_study.py --out a2a-card-study.json
    python scripts/a2a_card_study.py --out /tmp/x.json --sources a2areg --limit 20
"""
from __future__ import annotations

import argparse
import base64
import json
import math
import re
import statistics
import sys
import threading
import time
import urllib.robotparser
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal
from urllib.parse import urlsplit, urlunsplit

import requests

USER_AGENT = "HVTracker-research/1.0 (+https://hvtracker.net/methodology/; A2A Agent Card study)"
ROBOTS_TOKEN = "HVTracker-research"
TIMEOUT = 10
MAX_BYTES = 512 * 1024
HOST_PAUSE = 0.4            # seconds between requests to the same host
SERVER_CARDS_PER_HOST = 20  # sample cap: one shared host can carry thousands of remotes
WORKERS = 16

BOARD_API = "https://hvtracker.net/api/v1/agents"
MCP_REGISTRY_API = "https://registry.modelcontextprotocol.io/v0.1/servers"
A2A_REGISTRY_SITEMAP = "https://www.a2a-registry.org/sitemap.xml"

CARD_PATH = "/.well-known/agent-card.json"
LEGACY_CARD_PATH = "/.well-known/agent.json"
CATALOG_PATH = "/.well-known/ai-catalog.json"

# Homepages on shared platforms: the well-known path there belongs to the
# platform, not to the project. Per-project subdomains (x.github.io,
# x.vercel.app) are the project's own host and stay in.
SHARED_HOSTS = {
    "github.com", "www.github.com", "gitlab.com", "bitbucket.org", "codeberg.org",
    "pypi.org", "npmjs.com", "www.npmjs.com", "crates.io", "huggingface.co",
    "x.com", "twitter.com", "discord.gg", "discord.com", "t.me", "reddit.com",
    "www.reddit.com", "youtube.com", "www.youtube.com", "youtu.be", "medium.com",
    "linkedin.com", "www.linkedin.com", "docs.google.com", "drive.google.com",
    "marketplace.visualstudio.com", "chromewebstore.google.com", "chrome.google.com",
    "apps.apple.com", "play.google.com", "notion.so", "www.notion.so",
}

# A2A 1.0 REQUIRED fields (specification/a2a.proto, lf.a2a.v1).
V1_REQUIRED = ("name", "description", "supportedInterfaces", "version", "capabilities",
               "defaultInputModes", "defaultOutputModes", "skills")
INTERFACE_REQUIRED = ("url", "protocolBinding", "protocolVersion")
# Keys that stay in the canonical form even when empty (REQUIRED in the proto).
_KEEP_EMPTY = set(V1_REQUIRED) | set(INTERFACE_REQUIRED) | {"id", "tags", "organization"}


# ---------------------------------------------------------------------------
# Fetching
# ---------------------------------------------------------------------------

class Fetcher:
    """One requests session; robots.txt cached per host; never raises."""

    def __init__(self) -> None:
        self._local = threading.local()  # requests.Session isn't thread-safe: one per worker
        self._robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}
        self._lock = threading.Lock()

    @property
    def session(self) -> requests.Session:
        s = getattr(self._local, "session", None)
        if s is None:
            s = requests.Session()
            s.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})
            self._local.session = s
        return s

    def get(self, url: str, max_bytes: int = MAX_BYTES) -> dict:
        """{"status", "json", "error", "content_type"}; body capped at max_bytes
        (MAX_BYTES for third-party hosts; first-party APIs pass a larger cap)."""
        try:
            with self.session.get(url, timeout=TIMEOUT, stream=True, allow_redirects=True) as r:
                body = b""
                for chunk in r.iter_content(16384):
                    body += chunk
                    if len(body) > max_bytes:
                        return {"status": r.status_code, "json": None, "error": "too large",
                                "content_type": r.headers.get("content-type", "")}
                out = {"status": r.status_code, "json": None, "error": None,
                       "content_type": r.headers.get("content-type", ""), "final_url": r.url}
                if r.status_code == 200:
                    try:
                        out["json"] = json.loads(body.decode("utf-8-sig"))
                    except (ValueError, UnicodeDecodeError):
                        out["error"] = "not json"
                return out
        except requests.RequestException as e:
            return {"status": None, "json": None, "error": type(e).__name__, "content_type": ""}

    def robots(self, scheme_host: str) -> urllib.robotparser.RobotFileParser | None:
        """Parsed robots.txt for https://host; None when the host is unreachable.
        A missing robots.txt (4xx) allows everything, per RFC 9309."""
        with self._lock:
            if scheme_host in self._robots:
                return self._robots[scheme_host]
        parser = urllib.robotparser.RobotFileParser()
        try:
            r = self.session.get(scheme_host + "/robots.txt", timeout=TIMEOUT,
                                 headers={"Accept": "text/plain"})
            if r.status_code >= 500:
                parser.disallow_all = True
            elif r.status_code >= 400:
                parser.allow_all = True
            else:
                parser.parse(r.text[:MAX_BYTES].splitlines())
        except requests.RequestException:
            parser = None
        with self._lock:
            self._robots[scheme_host] = parser
        return parser

    def allowed(self, url: str) -> bool | None:
        """True/False per robots.txt; None when the host can't be reached."""
        parts = urlsplit(url)
        parser = self.robots(f"{parts.scheme}://{parts.netloc}")
        if parser is None:
            return None
        return parser.can_fetch(ROBOTS_TOKEN, url)


# ---------------------------------------------------------------------------
# Host lists
# ---------------------------------------------------------------------------

def norm_host(url: str) -> str | None:
    """Lower-case host of an http(s) URL, or None for anything else."""
    try:
        parts = urlsplit((url or "").strip())
    except ValueError:
        return None
    if parts.scheme not in ("http", "https") or not parts.hostname:
        return None
    host = parts.hostname.lower().rstrip(".")
    if re.fullmatch(r"[\d.]+|\[.*\]|localhost", host):
        return None
    return host


def roster_hosts(rows: list[dict]) -> dict[str, list[str]]:
    """{host: [slug, ...]} from listing homepages, shared platforms excluded."""
    out: dict[str, list[str]] = {}
    for r in rows:
        host = norm_host(r.get("github_homepage") or "")
        if host and host not in SHARED_HOSTS:
            out.setdefault(host, []).append(r.get("slug") or "")
    return out


def mcp_remote_urls(entries: list[dict]) -> dict[str, list[str]]:
    """{host: [remote url, ...]} from registry entries' `remotes`."""
    out: dict[str, list[str]] = {}
    for e in entries:
        for remote in (e.get("server") or {}).get("remotes") or []:
            url = (remote.get("url") or "").strip()
            host = norm_host(url)
            if host and "{" not in url:  # skip templated URLs (per-tenant hosts)
                out.setdefault(host, [])
                if url not in out[host]:
                    out[host].append(url)
    return out


def card_urls_from_html(html: str) -> list[str]:
    """Agent Card URLs mentioned on an A2A Registry agent page."""
    found = re.findall(r'https?://[^\s"\'<>\\]+?/\.well-known/agent(?:-card)?\.json', html)
    return sorted(set(found))


# Our own board and the MCP registry return pages far above the 512 KB cap
# meant for third-party hosts (the board is ~4 MB): 6 Oct's first run read 0
# listings because the cap rejected the page as "too large".
FIRST_PARTY_MAX_BYTES = 32 * 1024 * 1024


def load_board(fetcher: Fetcher) -> list[dict]:
    """Every agent listing on the live board. /api/v1/agents returns them all in
    one response (it ignores limit/offset, and its `total` also counts skills)."""
    res = fetcher.get(BOARD_API, max_bytes=FIRST_PARTY_MAX_BYTES)
    if res.get("json") is None:
        raise RuntimeError(f"board API unreadable: {res.get('status')} {res.get('error')}")
    return res["json"].get("agents") or []


def load_mcp_registry(fetcher: Fetcher) -> list[dict]:
    entries, cursor = [], ""
    while True:
        url = f"{MCP_REGISTRY_API}?version=latest&limit=100" + (f"&cursor={requests.utils.quote(cursor)}" if cursor else "")
        res = fetcher.get(url, max_bytes=FIRST_PARTY_MAX_BYTES)
        if res.get("json") is None:
            raise RuntimeError(f"MCP registry unreadable: {res.get('status')} {res.get('error')}")
        data = res.get("json") or {}
        servers = data.get("servers") or []
        entries += servers
        cursor = (data.get("metadata") or {}).get("nextCursor") or ""
        if not cursor or not servers:
            return entries


def load_a2a_registry_sample(fetcher: Fetcher) -> list[str]:
    """Card URLs from the agent pages the registry's sitemap lists."""
    res = fetcher.session.get(A2A_REGISTRY_SITEMAP, timeout=TIMEOUT)
    pages = re.findall(r"<loc>([^<]*/agent/[^<]*)</loc>", res.text if res.ok else "")
    cards: list[str] = []
    for page in pages:
        if fetcher.allowed(page) is not True:
            continue
        try:
            html = fetcher.session.get(page, timeout=TIMEOUT, headers={"Accept": "text/html"}).text
        except requests.RequestException:
            continue
        cards += card_urls_from_html(html)
        time.sleep(HOST_PAUSE)
    return sorted(set(cards))


# ---------------------------------------------------------------------------
# Card analysis
# ---------------------------------------------------------------------------

def looks_like_card(doc) -> bool:
    return (isinstance(doc, dict) and isinstance(doc.get("name"), str)
            and any(k in doc for k in ("skills", "supportedInterfaces", "capabilities", "url")))


def card_version(card: dict) -> str:
    """'1.x' when it declares supportedInterfaces, else the legacy protocolVersion."""
    interfaces = card.get("supportedInterfaces")
    if isinstance(interfaces, list) and interfaces:
        versions = {str(i.get("protocolVersion")) for i in interfaces
                    if isinstance(i, dict) and i.get("protocolVersion")}
        return ",".join(sorted(versions)) or "1.x (unspecified)"
    if card.get("protocolVersion"):
        return str(card["protocolVersion"])
    return "unknown"


def v1_problems(card: dict) -> list[str]:
    """Missing or mistyped A2A 1.0 REQUIRED fields (empty list = valid)."""
    problems = []
    types = {"name": str, "description": str, "supportedInterfaces": list, "version": str,
             "capabilities": dict, "defaultInputModes": list, "defaultOutputModes": list,
             "skills": list}
    for field, kind in types.items():
        if not isinstance(card.get(field), kind):
            problems.append(field)
    for i in card.get("supportedInterfaces") or []:
        if not isinstance(i, dict) or any(not i.get(k) for k in INTERFACE_REQUIRED):
            problems.append("supportedInterfaces[].url/protocolBinding/protocolVersion")
            break
    return problems


def interface_urls(card: dict) -> list[str]:
    urls = [i.get("url") for i in card.get("supportedInterfaces") or [] if isinstance(i, dict)]
    urls += [i.get("url") for i in card.get("additionalInterfaces") or [] if isinstance(i, dict)]
    if card.get("url"):
        urls.append(card["url"])
    return [u for u in urls if isinstance(u, str) and u]


def auth_types(card: dict) -> list[str]:
    """Declared security scheme types; handles the 0.3 `type` field and the 1.0 oneof keys."""
    schemes = card.get("securitySchemes")
    if not isinstance(schemes, dict):
        return []
    out = set()
    for scheme in schemes.values():
        if not isinstance(scheme, dict):
            continue
        if isinstance(scheme.get("type"), str):
            out.add(scheme["type"])
            continue
        for key in scheme:
            name = key.replace("SecurityScheme", "")
            if name in ("apiKey", "httpAuth", "oauth2", "openIdConnect", "mtls"):
                out.add({"httpAuth": "http", "mtls": "mutualTLS"}.get(name, name))
    return sorted(out)


def auth_required(card: dict) -> bool:
    req = card.get("securityRequirements", card.get("security"))
    return isinstance(req, list) and len(req) > 0


def same_site(a: str, b: str) -> bool:
    """Same host, or one is a subdomain of the other's parent (last two labels).
    An approximation of the registrable domain; it errs towards 'different' for
    hosts under two-label public suffixes such as co.uk."""
    if not a or not b:
        return False
    if a == b:
        return True
    pa, pb = a.split("."), b.split(".")
    return len(pa) >= 2 and len(pb) >= 2 and pa[-2:] == pb[-2:]


# ---------------------------------------------------------------------------
# JCS (RFC 8785) and JWS verification
# ---------------------------------------------------------------------------

def _jcs_number(n) -> str:
    """ECMAScript Number::toString, as RFC 8785 section 3.2.2.3 requires."""
    if isinstance(n, bool):
        return "true" if n else "false"
    if isinstance(n, int):
        return str(n)
    if not math.isfinite(n):
        raise ValueError("JCS forbids NaN and Infinity")
    if n == 0:
        return "0"
    sign = "-" if n < 0 else ""
    # repr gives the shortest digits that round-trip, which is what ES uses.
    t = Decimal(repr(abs(n))).normalize().as_tuple()
    digits = "".join(map(str, t.digits))
    k = len(digits)
    e = t.exponent + k  # ES "n": the decimal point sits after this many digits
    if k <= e <= 21:
        return sign + digits + "0" * (e - k)
    if 0 < e <= 21:
        return sign + digits[:e] + "." + digits[e:]
    if -6 < e <= 0:
        return sign + "0." + "0" * (-e) + digits
    exp = e - 1
    mant = digits[0] + ("." + digits[1:] if k > 1 else "")
    return f"{sign}{mant}e{'+' if exp > 0 else '-'}{abs(exp)}"


def jcs(value) -> str:
    """RFC 8785 canonical JSON. Object keys sort by UTF-16 code units."""
    if value is None:
        return "null"
    if isinstance(value, bool) or isinstance(value, (int, float)):
        return _jcs_number(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list):
        return "[" + ",".join(jcs(v) for v in value) + "]"
    if isinstance(value, dict):
        keys = sorted(value, key=lambda k: k.encode("utf-16-be"))
        return "{" + ",".join(json.dumps(k, ensure_ascii=False) + ":" + jcs(value[k]) for k in keys) + "}"
    raise TypeError(f"not JSON: {type(value).__name__}")


def _strip(value, drop_false: bool):
    """Approximate the 1.0 default-value removal: drop empty/null (and optionally
    false/0) non-required fields, recursively."""
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            v = _strip(v, drop_false)
            empty = v is None or v == "" or v == [] or v == {}
            default = drop_false and (v is False or (isinstance(v, (int, float)) and not isinstance(v, bool) and v == 0))
            if (empty or default) and k not in _KEEP_EMPTY:
                continue
            out[k] = v
        return out
    if isinstance(value, list):
        return [_strip(v, drop_false) for v in value]
    return value


def payload_variants(card: dict) -> list[tuple[str, bytes]]:
    base = {k: v for k, v in card.items() if k != "signatures"}
    variants, seen = [], set()
    for label, doc in (("as-served", base), ("empty-stripped", _strip(base, False)),
                       ("defaults-stripped", _strip(base, True))):
        data = jcs(doc).encode("utf-8")
        if data not in seen:
            seen.add(data)
            variants.append((label, data))
    return variants


def b64url_decode(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def b64url_encode(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode("ascii")


def public_key_from_jwk(jwk: dict):
    from cryptography.hazmat.primitives.asymmetric import ec, ed25519, rsa
    kty = jwk.get("kty")
    if kty == "EC":
        curve = {"P-256": ec.SECP256R1(), "P-384": ec.SECP384R1(), "P-521": ec.SECP521R1()}[jwk["crv"]]
        x = int.from_bytes(b64url_decode(jwk["x"]), "big")
        y = int.from_bytes(b64url_decode(jwk["y"]), "big")
        return ec.EllipticCurvePublicNumbers(x, y, curve).public_key()
    if kty == "RSA":
        n = int.from_bytes(b64url_decode(jwk["n"]), "big")
        e = int.from_bytes(b64url_decode(jwk["e"]), "big")
        return rsa.RSAPublicNumbers(e, n).public_key()
    if kty == "OKP" and jwk.get("crv") == "Ed25519":
        return ed25519.Ed25519PublicKey.from_public_bytes(b64url_decode(jwk["x"]))
    raise ValueError(f"unsupported key type {kty}/{jwk.get('crv')}")


def verify_jws(alg: str, key, signing_input: bytes, sig: bytes) -> bool:
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec, padding
    from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
    hashes_by_bits = {"256": hashes.SHA256(), "384": hashes.SHA384(), "512": hashes.SHA512()}
    try:
        if alg in ("ES256", "ES384", "ES512"):
            half = len(sig) // 2
            der = encode_dss_signature(int.from_bytes(sig[:half], "big"), int.from_bytes(sig[half:], "big"))
            key.verify(der, signing_input, ec.ECDSA(hashes_by_bits[alg[2:]]))
        elif alg in ("RS256", "RS384", "RS512"):
            key.verify(sig, signing_input, padding.PKCS1v15(), hashes_by_bits[alg[2:]])
        elif alg in ("PS256", "PS384", "PS512"):
            h = hashes_by_bits[alg[2:]]
            key.verify(sig, signing_input, padding.PSS(mgf=padding.MGF1(h), salt_length=h.digest_size), h)
        elif alg in ("EdDSA", "Ed25519"):
            key.verify(sig, signing_input)
        else:
            return False
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False


def check_signatures(card: dict, card_host: str, fetcher: Fetcher | None) -> dict:
    """Signature facts for one card. `fetcher=None` skips the jku fetch (tests)."""
    sigs = card.get("signatures")
    out = {"signed": isinstance(sigs, list) and len(sigs) > 0, "algs": [], "key_source": None,
           "jku_same_site": None, "verified": False, "verified_variant": None, "verify_note": None}
    if not out["signed"]:
        return out
    variants = payload_variants(card)
    for sig in sigs:
        if not isinstance(sig, dict) or not sig.get("protected") or not sig.get("signature"):
            out["verify_note"] = "malformed signature entry"
            continue
        try:
            header = json.loads(b64url_decode(sig["protected"]))
        except (ValueError, TypeError):
            out["verify_note"] = "protected header not decodable"
            continue
        header = {**(sig.get("header") or {}), **header}
        alg = header.get("alg") or ""
        out["algs"].append(alg)
        keys = []
        if header.get("jku"):
            jku_host = norm_host(header["jku"])
            same = same_site(jku_host or "", card_host)
            out["key_source"] = "jku, same site" if same else "jku, other site"
            out["jku_same_site"] = same
            if fetcher is not None and header["jku"].startswith("https://") and fetcher.allowed(header["jku"]):
                jwks = fetcher.get(header["jku"]).get("json") or {}
                keys = [k for k in jwks.get("keys") or [] if isinstance(k, dict)
                        and (not header.get("kid") or k.get("kid") == header.get("kid"))]
                if not keys:
                    out["verify_note"] = "no matching key in jku"
        elif isinstance(header.get("jwk"), dict):
            out["key_source"] = "embedded jwk"  # self-asserted: proves integrity, not origin
            keys = [header["jwk"]]
        else:
            out["key_source"] = out["key_source"] or "kid only"
            out["verify_note"] = out["verify_note"] or "no key location given"
        for jwk in keys:
            try:
                key = public_key_from_jwk(jwk)
            except (KeyError, ValueError, TypeError):
                out["verify_note"] = "unsupported or malformed key"
                continue
            raw_sig = b64url_decode(sig["signature"])
            for label, payload in variants:
                signing_input = sig["protected"].encode("ascii") + b"." + b64url_encode(payload).encode("ascii")
                if verify_jws(alg, key, signing_input, raw_sig):
                    out.update(verified=True, verified_variant=label, verify_note=None)
                    return out
            out["verify_note"] = "signature did not verify against any canonical form we tried"
    return out


def analyse_card(card: dict, card_url: str, fetcher: Fetcher | None) -> dict:
    host = norm_host(card_url) or ""
    urls = interface_urls(card)
    provider = card.get("provider") if isinstance(card.get("provider"), dict) else {}
    return {
        "card_url": card_url,
        "name": (card.get("name") or "")[:120],
        "protocol_version": card_version(card),
        "v1_valid": not v1_problems(card),
        "v1_problems": v1_problems(card),
        "interfaces": len(urls),
        "interfaces_https": bool(urls) and all(u.startswith("https://") for u in urls),
        "interfaces_same_site": bool(urls) and all(same_site(norm_host(u) or "", host) for u in urls),
        "auth_types": auth_types(card),
        "auth_required": auth_required(card),
        "provider_declared": bool(provider.get("organization")),
        "skills": len(card.get("skills") or []) if isinstance(card.get("skills"), list) else 0,
        **check_signatures(card, host, fetcher),
    }


def analyse_catalog(doc) -> dict | None:
    """Entries, media types and Trust Manifest use in an AI Catalog document
    (https://github.com/Agent-Card/ai-catalog). None when the JSON isn't a
    catalog: the spec requires an `entries` array (which may be empty).
    Entries name their media type in `type`; early drafts used `mediaType`."""
    entries = doc.get("entries") if isinstance(doc, dict) else None
    if not isinstance(entries, list):
        return None
    entries = [e for e in entries if isinstance(e, dict)]
    types = sorted({str(e.get("type") or e.get("mediaType") or "?") for e in entries})
    manifests = [e["trustManifest"] for e in entries if isinstance(e.get("trustManifest"), dict)]
    attestation_types = sorted({str(a.get("type") or "?") for m in manifests
                                for a in m.get("attestations") or [] if isinstance(a, dict)})
    return {"entries": len(entries), "media_types": types,
            "lists_a2a": any("a2a" in t.lower() or "agent-card" in t.lower() for t in types),
            "lists_mcp": any("mcp" in t.lower() or "server-card" in t.lower() for t in types),
            "trust_manifests": len(manifests),
            "signed_trust_manifests": sum(1 for m in manifests if m.get("signature")),
            "attestation_types": attestation_types}


# ---------------------------------------------------------------------------
# Per-host probe
# ---------------------------------------------------------------------------

def probe_host(fetcher: Fetcher, host: str, sources: list[str], remotes: list[str],
               card_urls: list[str]) -> dict:
    row = {"host": host, "sources": sorted(sources), "reachable": True, "robots_blocked": [],
           "card": None, "legacy_card": None, "catalog": None,
           "server_cards_checked": 0, "server_cards_found": 0}
    base = f"https://{host}"
    if fetcher.allowed(base + CARD_PATH) is None:
        row["reachable"] = False
        return row

    def fetch_if_allowed(url: str):
        if not fetcher.allowed(url):
            row["robots_blocked"].append(urlsplit(url).path)
            return None
        res = fetcher.get(url)
        time.sleep(HOST_PAUSE)
        return res

    targets = sorted({base + CARD_PATH, *[u for u in card_urls if norm_host(u) == host]})
    for url in targets:
        res = fetch_if_allowed(url)
        if res and looks_like_card(res.get("json")):
            row["card"] = analyse_card(res["json"], res.get("final_url") or url, fetcher)
            break
    if row["card"] is None:
        res = fetch_if_allowed(base + LEGACY_CARD_PATH)
        if res and looks_like_card(res.get("json")):
            row["legacy_card"] = analyse_card(res["json"], res.get("final_url") or base + LEGACY_CARD_PATH, fetcher)
    res = fetch_if_allowed(base + CATALOG_PATH)
    if res:
        row["catalog"] = analyse_catalog(res.get("json"))
    for remote in remotes[:SERVER_CARDS_PER_HOST]:
        parts = urlsplit(remote)
        card = urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip("/") + "/server-card", "", ""))
        res = fetch_if_allowed(card)
        row["server_cards_checked"] += 1
        doc = (res or {}).get("json")
        if isinstance(doc, dict) and ("name" in doc or "remotes" in doc or "$schema" in doc):
            row["server_cards_found"] += 1
    return row


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def _pct(n: int, d: int) -> float | None:
    return round(100 * n / d, 1) if d else None


def summarise(rows: list[dict], source: str | None = None) -> dict:
    rows = [r for r in rows if source is None or source in r["sources"]]
    reachable = [r for r in rows if r["reachable"]]
    cards = [r["card"] or r["legacy_card"] for r in reachable if r["card"] or r["legacy_card"]]
    signed = [c for c in cards if c["signed"]]
    by_version: dict[str, int] = {}
    for c in cards:
        by_version[c["protocol_version"]] = by_version.get(c["protocol_version"], 0) + 1
    auth: dict[str, int] = {}
    for c in cards:
        for t in c["auth_types"] or ["none declared"]:
            auth[t] = auth.get(t, 0) + 1
    checked = sum(r["server_cards_checked"] for r in reachable)
    return {
        "hosts": len(rows),
        "reachable": len(reachable),
        "robots_blocked_any": sum(1 for r in reachable if r["robots_blocked"]),
        "cards": len(cards),
        "cards_pct_of_reachable": _pct(len(cards), len(reachable)),
        "legacy_path_only": sum(1 for r in reachable if r["legacy_card"] and not r["card"]),
        "v1_valid": sum(1 for c in cards if c["v1_valid"]),
        "protocol_versions": dict(sorted(by_version.items(), key=lambda kv: -kv[1])),
        "https_interfaces": sum(1 for c in cards if c["interfaces_https"]),
        "interfaces_same_site": sum(1 for c in cards if c["interfaces_same_site"]),
        "auth_declared": sum(1 for c in cards if c["auth_types"]),
        "auth_required": sum(1 for c in cards if c["auth_required"]),
        "auth_types": dict(sorted(auth.items(), key=lambda kv: -kv[1])),
        "provider_declared": sum(1 for c in cards if c["provider_declared"]),
        "median_skills": statistics.median([c["skills"] for c in cards]) if cards else None,
        "signed": len(signed),
        "signed_key_same_site": sum(1 for c in signed if c["jku_same_site"]),
        "signed_verified": sum(1 for c in signed if c["verified"]),
        "ai_catalogs": sum(1 for r in reachable if r["catalog"]),
        "ai_catalogs_nonempty": sum(1 for r in reachable if r["catalog"] and r["catalog"]["entries"]),
        "ai_catalogs_listing_a2a": sum(1 for r in reachable if r["catalog"] and r["catalog"]["lists_a2a"]),
        "ai_catalogs_with_trust_manifest": sum(1 for r in reachable
                                               if r["catalog"] and r["catalog"].get("trust_manifests")),
        "server_cards_checked": checked,
        "server_cards_found": sum(r["server_cards_found"] for r in reachable),
    }


# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True)
    ap.add_argument("--sources", default="roster,mcp,a2areg")
    ap.add_argument("--limit", type=int, default=0, help="probe at most N hosts (testing)")
    args = ap.parse_args()
    wanted = set(args.sources.split(","))
    fetcher = Fetcher()
    started = datetime.now(timezone.utc)

    sources: dict[str, set[str]] = {}
    remotes: dict[str, list[str]] = {}
    card_urls: dict[str, list[str]] = {}
    inputs: dict[str, int] = {}
    if "roster" in wanted:
        board = load_board(fetcher)
        for host in roster_hosts(board):
            sources.setdefault(host, set()).add("roster")
        inputs["roster_listings"] = len(board)
    if "mcp" in wanted:
        entries = load_mcp_registry(fetcher)
        by_host = mcp_remote_urls(entries)
        for host, urls in by_host.items():
            sources.setdefault(host, set()).add("mcp")
            remotes[host] = urls
        inputs["mcp_registry_servers"] = len(entries)
        inputs["mcp_remote_urls"] = sum(len(v) for v in by_host.values())
    if "a2areg" in wanted:
        sample = load_a2a_registry_sample(fetcher)
        for url in sample:
            host = norm_host(url)
            if host:
                sources.setdefault(host, set()).add("a2areg")
                card_urls.setdefault(host, []).append(url)
        inputs["a2a_registry_sample_cards"] = len(sample)

    hosts = sorted(sources)
    if args.limit:
        hosts = hosts[:args.limit]
    print(f"probing {len(hosts)} hosts ({inputs})", file=sys.stderr)
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        rows = list(pool.map(lambda h: probe_host(fetcher, h, list(sources[h]), remotes.get(h, []),
                                                  card_urls.get(h, [])), hosts))

    doc = {
        "study": "State of public A2A agents",
        "generated_at": started.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "finished_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "method": "https://github.com/YugantM/hvtracker/blob/main/scripts/a2a_card_study.py",
        "inputs": inputs,
        "metrics": {"all": summarise(rows), **{s: summarise(rows, s) for s in sorted(wanted)}},
        "rows": [r for r in rows if r["card"] or r["legacy_card"] or r["catalog"] or r["server_cards_found"]],
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    m = doc["metrics"]["all"]
    print(f"{m['reachable']} of {m['hosts']} hosts reachable; {m['cards']} publish an Agent Card "
          f"({m['signed']} signed, {m['signed_verified']} verified); {m['ai_catalogs']} AI Catalogs; "
          f"{m['server_cards_found']} of {m['server_cards_checked']} MCP server cards -> {args.out}",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
