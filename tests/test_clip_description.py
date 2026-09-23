"""Descriptions are clipped at a word with an ellipsis, never mid-word.

They used to be text[:120]: 138 agents, the #1 and #2 ranked among them,
showed descriptions like "...a sandboxed workbench to help you b".
"""
import fetch_and_build as fb

COMPOSIO = ("Composio powers 1000+ toolkits, tool search, context management, "
            "authentication, and a sandboxed workbench to help you build AI agents "
            "that turn intent into action.")


def test_real_descriptions_are_kept_whole():
    assert len(COMPOSIO) > 120
    assert fb.clip_description(COMPOSIO) == COMPOSIO


def test_long_text_is_cut_at_a_word_with_an_ellipsis():
    text = "word " * 100
    out = fb.clip_description(text.strip(), limit=40)
    assert out.endswith("…")
    assert len(out) <= 40
    assert out[:-1].split()[-1] == "word"  # no partial word before the ellipsis


def test_empty_and_short():
    assert fb.clip_description("") == ""
    assert fb.clip_description(None) == ""
    assert fb.clip_description("Short one.") == "Short one."
