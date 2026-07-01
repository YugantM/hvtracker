"""Regression tests for the /changes/ RSS feed (v3.2 T2.2).

Locks the acceptance criterion "xml.etree parses the feed" and guards the
XML-escaping fix: a project name with an ampersand (e.g. "Weights & Biases
Weave") must not produce malformed XML.
"""
import xml.etree.ElementTree as ET

import fetch_and_build as fb

BASE = "https://hvtracker.net/changes/"


def test_feed_escapes_special_chars_and_parses():
    sections = [
        ("Trust Score Up", [{"name": "Weights & Biases Weave"}, {"name": "a<b>c"}]),
        ("Newly Listed Projects", []),  # empty section is omitted
    ]
    root = ET.fromstring(fb.build_changes_rss(sections, BASE, "2026-07-01"))
    items = root.findall("./channel/item")
    assert len(items) == 1
    desc = items[0].find("description").text
    # Parsed text round-trips to the raw name -> escaping happened correctly.
    assert "Weights & Biases Weave" in desc
    assert "a<b>c" in desc


def test_feed_valid_when_no_changes():
    root = ET.fromstring(fb.build_changes_rss([("Trust Score Up", [])], BASE, "2026-07-01"))
    assert root.findall("./channel/item") == []
    assert root.find("./channel/title").text == "HVTracker Weekly Changes"
