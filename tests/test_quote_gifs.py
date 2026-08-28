"""Keep the public roast GIF gallery aligned with the live Chinese line bank."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import unittest


REPO_ROOT = Path(__file__).resolve().parent.parent
GIF_DIR = REPO_ROOT / "docs" / "media" / "quotes"
MANIFEST = GIF_DIR / "manifest.json"
REGENERATE = "run: python scripts/generate_quote_gifs.py"


def _load_generator():
    spec = importlib.util.spec_from_file_location(
        "_quote_gif_gen", REPO_ROOT / "scripts" / "generate_quote_gifs.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class QuoteGifLibraryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        try:
            import PIL
        except ImportError as exc:
            raise unittest.SkipTest("Pillow not installed; cannot verify quote GIFs") from exc
        cls.generator = _load_generator()

    def setUp(self) -> None:
        if not MANIFEST.exists():
            self.fail(f"no quote GIF manifest — {REGENERATE}")
        self.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    def test_manifest_covers_selected_quotes(self) -> None:
        expected = {demo.slug for demo in self.generator.QUOTE_DEMOS}
        recorded = set(self.manifest.get("quotes", {}))
        self.assertEqual(recorded, expected, REGENERATE)

    def test_gif_files_exist(self) -> None:
        missing = sorted(
            slug for slug in self.manifest.get("quotes", {})
            if not (GIF_DIR / f"{slug}.gif").exists()
        )
        self.assertFalse(missing, f"missing quote GIFs: {missing} — {REGENERATE}")

    def test_line_bank_and_render_signatures_are_current(self) -> None:
        self.assertEqual(self.manifest, self.generator.build_manifest(), REGENERATE)


if __name__ == "__main__":
    unittest.main()
