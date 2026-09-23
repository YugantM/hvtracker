"""The Docker image must contain everything the runtime reads.

The Dockerfile COPYs by filename, so a new module or asset that isn't added
there passes every local gate (they run against the working tree) and then
fails in production: on 2026-09-17 a missing usage.py crash-looped the boot
and the site served 502s. Running the image check in CI moves that failure to
the PR. (The live-roster half of scripts/predeploy_check.py needs the network
and runs at deploy time.)
"""
import importlib.util
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location(
    "predeploy_check", os.path.join(ROOT, "scripts", "predeploy_check.py"))
pc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pc)


def test_image_contains_every_runtime_module_and_base_dir_path():
    assert pc.image_gaps(ROOT) == []


def test_import_graph_reaches_the_modules_that_broke_prod():
    mods = pc.runtime_modules(ROOT)
    # usage.py is the one that took the site down; mcp_server/auth hang off app.
    assert {"app", "usage", "mcp_server", "auth", "db"} <= mods


def test_gap_detection_catches_a_missing_copy(tmp_path):
    (tmp_path / "app.py").write_text(
        "import os\nimport helper\nBASE_DIR = '.'\n"
        "os.path.join(BASE_DIR, 'assets', 'logo.png')\n"
        "os.path.join(BASE_DIR, 'avatars', f'{1}.png')\n")
    (tmp_path / "helper.py").write_text("")
    for name in ("mcp_server.py", "auth.py"):
        (tmp_path / name).write_text("")
    (tmp_path / "Dockerfile").write_text(
        "FROM python\nCOPY app.py ./\nCOPY avatars/ avatars/\n")
    assert pc.image_gaps(str(tmp_path)) == ["module helper.py", "file assets/logo.png"]
