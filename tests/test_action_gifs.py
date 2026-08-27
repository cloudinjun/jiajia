"""Guard that the per-action GIF library stays in sync with the action tables.

Rendering needs Pillow, but this check only hashes keyframe data, so it runs
everywhere. If it fails, regenerate:

    python scripts/generate_action_gifs.py
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from jiajia.actions import ACTION_LABELS


REPO_ROOT = Path(__file__).resolve().parent.parent
GIF_DIR = REPO_ROOT / "docs" / "media" / "actions"
MANIFEST = GIF_DIR / "manifest.json"
REGENERATE = "run: python scripts/generate_action_gifs.py"


def _load_signatures() -> dict[str, str]:
    """Import the generator's signature function without invoking Pillow."""
    import importlib.util
    import sys

    spec = importlib.util.spec_from_file_location(
        "_action_gif_gen", REPO_ROOT / "scripts" / "generate_action_gifs.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.build_manifest()["actions"]


class ActionGifLibraryTest(unittest.TestCase):
    def setUp(self) -> None:
        try:
            import PIL  # noqa: F401
        except ImportError:
            self.skipTest("Pillow not installed; cannot verify the action GIF library")
        if not MANIFEST.exists():
            self.fail(f"no GIF manifest at {MANIFEST} — {REGENERATE}")
        self.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    def test_every_action_has_a_gif(self) -> None:
        recorded = set(self.manifest.get("actions", {}))
        missing = sorted(set(ACTION_LABELS) - recorded)
        self.assertFalse(missing, f"actions added without a GIF: {missing} — {REGENERATE}")

    def test_no_gifs_for_removed_actions(self) -> None:
        recorded = set(self.manifest.get("actions", {}))
        removed = sorted(recorded - set(ACTION_LABELS))
        self.assertFalse(removed, f"GIFs left behind by removed actions: {removed} — {REGENERATE}")

    def test_gif_files_exist(self) -> None:
        missing = sorted(
            name for name in self.manifest.get("actions", {})
            if not (GIF_DIR / f"{name}.gif").exists()
        )
        self.assertFalse(missing, f"manifest lists GIFs that are not on disk: {missing} — {REGENERATE}")

    def test_keyframes_unchanged_since_render(self) -> None:
        recorded = self.manifest.get("actions", {})
        current = _load_signatures()
        stale = sorted(
            name for name in set(recorded) & set(current)
            if recorded[name] != current[name]
        )
        self.assertFalse(stale, f"keyframes changed since these GIFs were rendered: {stale} — {REGENERATE}")


if __name__ == "__main__":
    unittest.main()
