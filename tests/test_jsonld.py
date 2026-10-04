"""JSON-LD carries text values JSON-encoded, not HTML-escaped.

Browsers don't decode HTML entities inside <script>, so an autoescaped
"{{ row.category }}" reached Google as "Protocols &amp; Tool Integration" on
~300 profiles (Phase 10 rich-results audit, 4 Oct)."""
import json
import re

from tests.test_ctr_overrides import _render_category
from tests.test_custody_chain import _render as render_profile

TRICKY = 'Tom & "Jerry" <Agents> it\'s Café'


def _blocks(html):
    return [json.loads(b) for b in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)]


def _strings(obj):
    if isinstance(obj, dict):
        for v in obj.values():
            yield from _strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _strings(v)
    elif isinstance(obj, str):
        yield obj


def test_profile_jsonld_keeps_names_and_categories_verbatim():
    app, faq, crumbs = _blocks(render_profile(name=TRICKY, category="Sandboxes & Runtimes",
                                              description=TRICKY))
    assert app["name"] == app["description"] == TRICKY
    assert app["applicationCategory"] == "Sandboxes & Runtimes"
    assert app["review"]["reviewBody"].startswith(f"Evidence-based trust review of {TRICKY}:")
    assert faq["mainEntity"][0]["name"] == f"Is {TRICKY} safe to use?"
    assert faq["mainEntity"][1]["acceptedAnswer"]["text"].endswith("categorized under Sandboxes & Runtimes.")
    assert [i["name"] for i in crumbs["itemListElement"]][1:] == ["Sandboxes & Runtimes", TRICKY]
    assert not any(re.search(r"&(amp|quot|lt|gt|#\d+);", s) for b in (app, faq, crumbs) for s in _strings(b))


def test_category_jsonld_keeps_the_category_verbatim():
    page, crumbs = _blocks(_render_category(category="Security & Guardrails"))
    assert page["name"] == "Best AI Security & Guardrails"
    assert "security & guardrails ranked" in page["description"]
    assert crumbs["itemListElement"][1]["name"] == "Security & Guardrails"
