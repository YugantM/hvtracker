"""Top-level modules must compile without SyntaxWarning.

An invalid string escape (the GA bot regex's `\\/` and `\\d` in app.py's
marketing page) is a SyntaxWarning on the image's Python 3.12, printed at
every boot, and is slated to become a SyntaxError in a future Python.
"""
import ast
import os
import warnings

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_top_level_modules_compile_without_syntax_warnings():
    offenders = []
    for name in sorted(os.listdir(ROOT)):
        if not name.endswith(".py"):
            continue
        with open(os.path.join(ROOT, name), encoding="utf-8") as f:
            source = f.read()
        with warnings.catch_warnings():
            warnings.simplefilter("error", SyntaxWarning)
            try:
                ast.parse(source, name)
            except SyntaxError as exc:  # a SyntaxWarning raised as an error
                offenders.append(f"{name}:{exc.lineno}: {exc.msg}")
    assert not offenders, offenders
