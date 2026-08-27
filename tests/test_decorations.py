"""Decoration rules: an accessory is either a behaviour or a status readout.

The failures these guard were all real: identities wearing two same-meaning
props at once (checklist + clipboard, terminal + code badge), vendor SVG icons
silently pre-empting every native drawing so the pal wore toolbar icons, and a
reaction layer that re-attached caption props by mood (smug -> annotation
circle, sleepy -> Z, dance -> stage) after props had been made opt-in — the
same bypass existed in three places, and none of it raised anything.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from jiajia.identity import load_identity_manifest
from jiajia.pal_decor import reaction_decoration_cues
from jiajia.pal_motion import ACTION_DECORATION_CUES, IDENTITY_STATE_CUES
from jiajia.soul import _load_yaml

ROOT = Path(__file__).resolve().parents[1] / "jiajia"
DECORATIONS = _load_yaml(ROOT / "decorations.yaml")["decorations"]
MANIFEST = load_identity_manifest(ROOT / "identities.yaml")

# Removed as identity accessories because they duplicated or mislead: the coin
# read quota as money, the palette made the critic a painter, the lock read as
# security, the moon turned focus into sleep, the bandage made a meltdown cute.
RETIRED_ADDONS = frozenset({
    "budget_coin", "critic_palette", "tiny_lock", "agent_code_badge",
    "quiet_moon", "bandage_mark", "tiny_checklist",
})

# Symbol decorations that caption a feeling rather than report a state.
CAPTION_DECORATIONS = frozenset({
    "z_symbol", "annotation_circle", "tiny_warning", "paper_stage",
    "paper_oops_cover", "paper_pillow", "paper_peek_curtain", "sleepy_cap",
})


class IdentityPropTests(unittest.TestCase):
    def test_one_persistent_prop_per_identity(self) -> None:
        """Two props per identity is a label collection, not an identity."""
        for pack_id, pack in MANIFEST.packs.items():
            self.assertLessEqual(
                len(pack.visual_addons), 1,
                f"{pack_id} wears {pack.visual_addons}; one object is the identity",
            )

    def test_retired_addons_are_not_worn_by_anyone(self) -> None:
        for pack_id, pack in MANIFEST.packs.items():
            worn = set(pack.visual_addons) & RETIRED_ADDONS
            self.assertFalse(worn, f"{pack_id} still wears retired prop(s) {sorted(worn)}")

    def test_identity_props_draw_native_not_vendor(self) -> None:
        """An `asset:` pointer pre-empts the native drawing entirely."""
        for name, spec in DECORATIONS.items():
            if spec.get("role") != "identity_prop":
                continue
            self.assertFalse(
                spec.get("asset"),
                f"{name} still points at a vendor SVG; the native shape never draws",
            )

    def test_every_worn_prop_has_a_native_shape_branch(self) -> None:
        """Without the asset override, the native branch is all there is."""
        source = (ROOT / "pal_decor.py").read_text(encoding="utf-8")
        branches = set(re.findall(r'\bshape == "(\w+)"', source))
        branches |= set(re.findall(r'\bshape in \{([^}]*)\}', source) and {
            n for group in re.findall(r'\bshape in \{([^}]*)\}', source)
            for n in re.findall(r'"(\w+)"', group)
        })
        for pack_id, pack in MANIFEST.packs.items():
            for addon in pack.visual_addons:
                shape = str(DECORATIONS.get(addon, {}).get("shape_type", ""))
                self.assertIn(
                    shape, branches,
                    f"{pack_id} wears {addon} whose shape {shape!r} has no native drawing",
                )


class CaptionBypassTests(unittest.TestCase):
    """Props became opt-in; these are the three side doors that re-added them."""

    def test_reactions_only_decorate_for_stated_causes(self) -> None:
        # a feeling is not a cause
        self.assertEqual(reaction_decoration_cues("chat", "speech"), ())
        self.assertEqual(reaction_decoration_cues("idle_ambient", "thought"), ())
        # stated causes still decorate
        self.assertEqual(reaction_decoration_cues("hardware_warm", ""), (("heat_puffs", 4200),))
        self.assertEqual(reaction_decoration_cues("codex_usage_low", ""), (("usage_bar", 4200),))
        self.assertEqual(reaction_decoration_cues("usage_reset_soon", ""), (("reset_clock", 4200),))
        self.assertEqual(reaction_decoration_cues("codex_crash", ""), (("bug_marker", 4200),))

    def test_hardware_no_longer_stacks_two_props(self) -> None:
        """Heat plus fan at once was two captions for one temperature."""
        cues = [name for name, _ms in reaction_decoration_cues("hardware_hot", "")]
        self.assertEqual(cues, ["heat_puffs"])

    def test_no_action_carries_a_decoration_caption(self) -> None:
        self.assertEqual(
            dict(ACTION_DECORATION_CUES), {},
            "an action alone earns no decoration; that is the caption system again",
        )

    def test_identity_ambience_uses_no_caption_symbols(self) -> None:
        for identity, cue in IDENTITY_STATE_CUES.items():
            decoration = str(cue.get("decoration", ""))
            self.assertNotIn(
                decoration, CAPTION_DECORATIONS,
                f"{identity}'s ambience captions itself with {decoration}",
            )


class BritclipCaneTests(unittest.TestCase):
    """The cane is punctuation, not wardrobe."""

    SOURCE = (ROOT / "pal_decor.py").read_text(encoding="utf-8")
    ACTIONS = (ROOT / "pal_actions.py").read_text(encoding="utf-8")

    def _method(self, source: str, name: str) -> str:
        start = source.index(f"def {name}")
        nxt = source.find("\n    def ", start + 1)
        return source[start:nxt if nxt != -1 else len(source)]

    def test_static_costume_carries_no_cane(self) -> None:
        for method in ("_equip_britclip_static", "_draw_gentleman_static_props"):
            body = self._method(self.SOURCE, method)
            self.assertNotIn(
                "_draw_gentleman_cane", body,
                f"{method} still equips the cane persistently; hat + tie already say British twice",
            )

    def test_cane_actions_actually_flourish_the_cane(self) -> None:
        for action in ("cane_tap", "polite_bow"):
            handler = self.ACTIONS[self.ACTIONS.index(f'if action == "{action}"'):]
            handler = handler[:handler.index("return")]
            self.assertIn(
                "_flourish_gentleman_cane", handler,
                f"{action} plays without the cane it is named after",
            )

    def test_the_flourish_puts_the_cane_away(self) -> None:
        body = self._method(self.SOURCE, "_flourish_gentleman_cane")
        self.assertIn("put_away", body, "an episodic prop that never leaves is persistent")


class TemporaryLifetimeTests(unittest.TestCase):
    def test_one_temporary_at_a_time(self) -> None:
        """Stacked temporaries shared one clear-all timer: first expiry wiped all."""
        source = (ROOT / "pal_decor.py").read_text(encoding="utf-8")
        start = source.index("def _show_temporary_decoration")
        nxt = source.find("\n    def ", start + 1)
        body = source[start:nxt]
        draw_at = body.index("_draw_decoration")
        clear_at = body.index('_clear_decorations("temporary")')
        self.assertLess(
            clear_at, draw_at,
            "a new temporary must replace the previous one, not stack on it",
        )


if __name__ == "__main__":
    unittest.main()
