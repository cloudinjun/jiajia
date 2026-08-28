from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .body import JiajiaApp
from .brain_ollama import OllamaBrain
from .chat_language import install_chat_language_support
from .language import load_language_setting, soul_path_for_language
from .soul import load_soul


def _make_stdout_printable() -> None:
    """Every line Jiajia can say is printable, whatever the console is set to.

    A Windows console defaults to a regional code page, not UTF-8, and the
    lines are Chinese by default. Printing one raised UnicodeEncodeError and
    took the whole self-test down with it — a check that was meant to prove
    the app loads instead failed on the terminal it was loading in.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError, ValueError):
            pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Jiajia Python prototype")
    parser.add_argument("--self-test", action="store_true", help="Load config and make one local-brain/fallback reaction without opening the window.")
    parser.add_argument("--demo", action="store_true", help="Open the desktop pet and run the scripted behavior demo.")
    args = parser.parse_args()
    package_root = Path(__file__).resolve().parent
    project_root = package_root.parent
    language = load_language_setting(project_root)
    soul = load_soul(soul_path_for_language(package_root, language))
    soul.language = language
    if args.self_test:
        _make_stdout_printable()
        brain = OllamaBrain(soul, project_root=project_root)
        reaction = brain.react("self-test", {"active_window_title": "Codex", "idle_seconds": 0})
        print(f"{soul.name}: {reaction.line}")
        return
    install_chat_language_support(JiajiaApp)
    app = JiajiaApp(soul, project_root)
    if args.demo:
        app.root.after(1000, app._run_scripted_demo)
    app.run()


if __name__ == "__main__":
    main()
