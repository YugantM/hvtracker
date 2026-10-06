"""A2A Agent Card study (Q4 plan F1): canonicalisation, signature checks and
card analysis, all offline."""
import importlib.util
import json
import os

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, ed25519, padding, rsa
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location("a2a_card_study", os.path.join(ROOT, "scripts", "a2a_card_study.py"))
st = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(st)


def _card(**extra):
    card = {
        "name": "Route Planner",
        "description": "Plans routes",
        "supportedInterfaces": [{"url": "https://agents.example.com/a2a", "protocolBinding": "JSONRPC",
                                 "protocolVersion": "1.0"}],
        "provider": {"organization": "Example Inc", "url": "https://example.com"},
        "version": "1.2.0",
        "capabilities": {"streaming": True, "extensions": []},
        "securitySchemes": {"oauth": {"oauth2SecurityScheme": {"flows": {}}}},
        "securityRequirements": [{"schemes": {"oauth": {"list": []}}}],
        "defaultInputModes": ["text/plain"],
        "defaultOutputModes": ["text/plain"],
        "skills": [{"id": "route", "name": "Route", "description": "Plan a route", "tags": ["maps"]}],
    }
    card.update(extra)
    return card


# --- RFC 8785 ---------------------------------------------------------------

def test_jcs_numbers_follow_ecmascript():
    # RFC 8785 appendix B values plus the 1e-6..1e-4 band where Python's repr differs.
    cases = {1e30: "1e+30", 4.5: "4.5", 0.002: "0.002", 1e-7: "1e-7", 1e21: "1e+21",
             333333333.3333333: "333333333.3333333", 1e-6: "0.000001", 1e-5: "0.00001",
             -0.0: "0", 1.0: "1", 5e-324: "5e-324", 1.7976931348623157e308: "1.7976931348623157e+308"}
    for value, expected in cases.items():
        assert st._jcs_number(value) == expected, value


def test_jcs_sorts_keys_by_utf16_code_units():
    # RFC 8785 section 3.2.3: by UTF-16 code units the emoji (a surrogate pair,
    # D83D DE00) sorts before U+FB33, the opposite of code-point order.
    doc = {"€": 1, "\r": 2, "דּ": 3, "1": 4, "\U0001f600": 5, "\u0080": 6, "ö": 7}
    keys = list(json.loads(st.jcs(doc)))
    assert keys == ["\r", "1", "\u0080", "ö", "€", "\U0001f600", "דּ"]


def test_jcs_has_no_whitespace_and_keeps_unicode():
    assert st.jcs({"b": [1, True, None], "a": "é"}) == '{"a":"é","b":[1,true,null]}'


def test_spec_example_of_default_value_removal():
    # A2A spec 8.4.1: extensions (not REQUIRED, empty) goes; description "" and
    # skills [] (REQUIRED) stay; explicitly set false booleans stay.
    card = {"name": "Example Agent", "description": "",
            "capabilities": {"streaming": False, "pushNotifications": False, "extensions": []},
            "skills": []}
    payloads = dict(st.payload_variants(card))
    assert payloads["empty-stripped"] == (
        b'{"capabilities":{"pushNotifications":false,"streaming":false},'
        b'"description":"","name":"Example Agent","skills":[]}')


# --- signatures ---------------------------------------------------------------

def _sign(card, alg, private_key, header_extra):
    header = {"alg": alg, "typ": "JOSE", "kid": "key-1", **header_extra}
    protected = st.b64url_encode(json.dumps(header).encode())
    payload = dict(st.payload_variants(card))["empty-stripped"]
    signing_input = (protected + "." + st.b64url_encode(payload)).encode()
    if alg == "ES256":
        r, s = decode_dss_signature(private_key.sign(signing_input, ec.ECDSA(hashes.SHA256())))
        raw = r.to_bytes(32, "big") + s.to_bytes(32, "big")
    elif alg == "EdDSA":
        raw = private_key.sign(signing_input)
    else:
        raw = private_key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
    return {"protected": protected, "signature": st.b64url_encode(raw)}


def _jwk(public_key):
    if isinstance(public_key, ec.EllipticCurvePublicKey):
        nums = public_key.public_numbers()
        return {"kty": "EC", "crv": "P-256", "kid": "key-1",
                "x": st.b64url_encode(nums.x.to_bytes(32, "big")),
                "y": st.b64url_encode(nums.y.to_bytes(32, "big"))}
    if isinstance(public_key, ed25519.Ed25519PublicKey):
        from cryptography.hazmat.primitives import serialization
        raw = public_key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        return {"kty": "OKP", "crv": "Ed25519", "kid": "key-1", "x": st.b64url_encode(raw)}
    nums = public_key.public_numbers()
    return {"kty": "RSA", "kid": "key-1",
            "n": st.b64url_encode(nums.n.to_bytes((nums.n.bit_length() + 7) // 8, "big")),
            "e": st.b64url_encode(nums.e.to_bytes(3, "big"))}


def test_signed_cards_verify_for_each_algorithm():
    keys = {"ES256": ec.generate_private_key(ec.SECP256R1()),
            "EdDSA": ed25519.Ed25519PrivateKey.generate(),
            "RS256": rsa.generate_private_key(public_exponent=65537, key_size=2048)}
    for alg, private_key in keys.items():
        card = _card()
        card["signatures"] = [_sign(card, alg, private_key, {"jwk": _jwk(private_key.public_key())})]
        out = st.check_signatures(card, "agents.example.com", None)
        assert out["signed"] and out["verified"], alg
        assert out["verified_variant"] == "empty-stripped"
        assert out["key_source"] == "embedded jwk"


def test_tampered_card_is_reported_unverified_not_forged():
    key = ec.generate_private_key(ec.SECP256R1())
    card = _card()
    card["signatures"] = [_sign(card, "ES256", key, {"jwk": _jwk(key.public_key())})]
    card["description"] = "Plans routes, and also something else"
    out = st.check_signatures(card, "agents.example.com", None)
    assert out["signed"] and not out["verified"]
    assert "did not verify" in out["verify_note"]


def test_jku_site_is_recorded_without_fetching():
    key = ec.generate_private_key(ec.SECP256R1())
    card = _card()
    card["signatures"] = [_sign(card, "ES256", key, {"jku": "https://keys.example.com/jwks.json"})]
    out = st.check_signatures(card, "agents.example.com", None)
    assert out["key_source"] == "jku, same site" and out["jku_same_site"] is True
    assert out["verified"] is False  # no fetcher, so no key, so no claim either way


def test_unsigned_card():
    out = st.check_signatures(_card(), "agents.example.com", None)
    assert out["signed"] is False and out["verified"] is False


# --- card analysis -----------------------------------------------------------

def test_v1_card_analysis():
    a = st.analyse_card(_card(), "https://agents.example.com/.well-known/agent-card.json", None)
    assert a["v1_valid"] and a["protocol_version"] == "1.0"
    assert a["interfaces_https"] and a["interfaces_same_site"]
    assert a["auth_types"] == ["oauth2"] and a["auth_required"]
    assert a["provider_declared"] and a["skills"] == 1


def test_legacy_card_is_not_v1_valid():
    legacy = {"name": "Old Agent", "description": "x", "url": "http://old.example.org/rpc",
              "protocolVersion": "0.2.5", "version": "1", "capabilities": {},
              "securitySchemes": {"key": {"type": "apiKey", "in": "header", "name": "X-Key"}},
              "defaultInputModes": [], "defaultOutputModes": [], "skills": []}
    a = st.analyse_card(legacy, "https://old.example.org/.well-known/agent.json", None)
    assert a["protocol_version"] == "0.2.5" and not a["v1_valid"]
    assert "supportedInterfaces" in a["v1_problems"]
    assert a["auth_types"] == ["apiKey"] and not a["auth_required"]
    assert not a["interfaces_https"]


def test_looks_like_card_rejects_html_and_other_json():
    assert not st.looks_like_card(None)
    assert not st.looks_like_card({"error": "not found"})
    assert st.looks_like_card({"name": "x", "skills": []})


# --- host lists ---------------------------------------------------------------

def test_roster_hosts_skip_shared_platforms():
    rows = [{"slug": "a", "github_homepage": "https://github.com/a/a"},
            {"slug": "b", "github_homepage": "https://b.example.com/docs"},
            {"slug": "c", "github_homepage": "https://user.github.io/c"},
            {"slug": "d", "github_homepage": ""}]
    assert st.roster_hosts(rows) == {"b.example.com": ["b"], "user.github.io": ["c"]}


def test_mcp_remote_urls_skip_templates_and_dedupe():
    entries = [{"server": {"remotes": [{"url": "https://mcp.example.com/mcp"},
                                       {"url": "https://{tenant}.example.com/mcp"}]}},
               {"server": {"remotes": [{"url": "https://mcp.example.com/mcp"}]}}]
    assert st.mcp_remote_urls(entries) == {"mcp.example.com": ["https://mcp.example.com/mcp"]}


def test_card_urls_from_registry_page():
    html = ('<a href="https://x.workers.dev/.well-known/agent-card.json">card</a>'
            '"https://y.example.com/a2a/.well-known/agent.json"')
    assert st.card_urls_from_html(html) == ["https://x.workers.dev/.well-known/agent-card.json",
                                           "https://y.example.com/a2a/.well-known/agent.json"]


def test_catalog_analysis_counts_trust_manifests():
    doc = {"entries": [
        {"identifier": "urn:air:example.com:agent:a", "mediaType": "application/a2a-agent-card+json",
         "url": "https://example.com/a.json",
         "trustManifest": {"identity": "did:web:example.com", "signature": "x..y",
                           "attestations": [{"type": "SOC2-Type2", "uri": "https://example.com/soc2.pdf"}]}},
        {"identifier": "urn:air:example.com:mcp:b", "mediaType": "application/mcp-server-card+json",
         "url": "https://example.com/mcp/server-card"}]}
    c = st.analyse_catalog(doc)
    assert c["entries"] == 2 and c["lists_a2a"] and c["lists_mcp"]
    assert c["trust_manifests"] == 1 and c["signed_trust_manifests"] == 1
    assert c["attestation_types"] == ["SOC2-Type2"]
    assert st.analyse_catalog({"not": "a catalog"})["entries"] == 0


def test_summary_counts():
    signed = {**st.analyse_card(_card(), "https://a.example.com/.well-known/agent-card.json", None),
              "signed": True, "verified": True, "jku_same_site": True}
    rows = [{"host": "a.example.com", "sources": ["mcp"], "reachable": True, "robots_blocked": [],
             "card": signed, "legacy_card": None, "catalog": {"lists_a2a": True},
             "server_cards_checked": 2, "server_cards_found": 1},
            {"host": "b.example.com", "sources": ["roster"], "reachable": False, "robots_blocked": [],
             "card": None, "legacy_card": None, "catalog": None,
             "server_cards_checked": 0, "server_cards_found": 0}]
    m = st.summarise(rows)
    assert (m["hosts"], m["reachable"], m["cards"], m["signed_verified"]) == (2, 1, 1, 1)
    assert m["ai_catalogs_listing_a2a"] == 1 and m["server_cards_found"] == 1
    assert st.summarise(rows, "roster")["cards"] == 0
