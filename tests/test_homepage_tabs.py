"""Homepage category tabs: "Newly added" sits next to Global.

At the end of the horizontally scrolling strip it was off-screen, so new
listings went unseen."""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_newly_added_tab_follows_global():
    src = open(os.path.join(ROOT, "template.html"), encoding="utf-8").read()
    strip = re.search(r'<div class="cat-tabs" id="catTabs".*?</div>', src, re.S).group(0)
    tabs = re.findall(r'data-tab="([^"]+)"', strip)
    assert tabs[:3] == ["__all__", "__new__", "{{ cat.name }}"], tabs
