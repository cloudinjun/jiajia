"""Keep the public roast GIF gallery aligned with the live Chinese line bank."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import unittest


REPO_ROOT = Path(__file__).resolve().parent.parent
QUOTE_ROOT = REPO_ROOT / "docs" / "media" / "quotes"
CASES = {
    "zh": QUOTE_ROOT,
    "en": QUOTE_ROOT / "en",
}
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

    def test_manifest_covers_selected_quotes(self) -> None:
        for language, gif_dir in CASES.items():
            with self.subTest(language=language):
                manifest = self._manifest(gif_dir)
                expected = {demo.slug for demo in self.generator.quote_demos(language)}
                recorded = set(manifest.get("quotes", {}))
                self.assertEqual(recorded, expected, REGENERATE)

    def test_gif_files_exist(self) -> None:
        for language, gif_dir in CASES.items():
            with self.subTest(language=language):
                manifest = self._manifest(gif_dir)
                missing = sorted(
                    slug for slug in manifest.get("quotes", {})
                    if not (gif_dir / f"{slug}.gif").exists()
                )
                self.assertFalse(missing, f"missing quote GIFs: {missing} — {REGENERATE}")

    def test_line_bank_and_render_signatures_are_current(self) -> None:
        for language, gif_dir in CASES.items():
            with self.subTest(language=language):
                self.assertEqual(
                    self._manifest(gif_dir),
                    self.generator.build_manifest(language=language),
                    REGENERATE,
                )

    def _manifest(self, gif_dir: Path) -> dict[str, object]:
        path = gif_dir / "manifest.json"
        if not path.exists():
            self.fail(f"no quote GIF manifest at {path} — {REGENERATE}")
        return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
