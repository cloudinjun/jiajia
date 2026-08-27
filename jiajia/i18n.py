"""Language identifiers for the pal.

This module used to carry a `t()` string registry and locale file resolvers as
well. Nothing ever called them — the project settled on two other mechanisms:
side-by-side ZH/EN constants inside each module (care.py, brain_ollama.py,
actions.py …) and locale YAML files resolved by `language.py`. The dead
registry was removed rather than left as a third, misleading option.

Path resolution lives in `language.py`:
    soul_path_for_language()        locales/en_soul.yaml
    identities_path_for_language()  locales/en_identities.yaml
    seed_path_for_language()        locales/{zh,en}_seeds.yaml
"""
from __future__ import annotations


SUPPORTED_LANGUAGES = ("zh-CN", "en")
DEFAULT_LANGUAGE = "zh-CN"
