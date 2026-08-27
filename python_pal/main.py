from __future__ import annotations

import argparse
from pathlib import Path

from .body import PaperclipPalApp
from .brain_ollama import OllamaBrain
from .chat_language import install_chat_language_support
from .language import load_language_setting, soul_path_for_language
from .soul import load_soul


def main() -> None:
    parser = argparse.ArgumentParser(description="Paperclip Pal Python prototype")
    parser.add_argument("--self-test", action="store_true", help="Load config and make one local-brain/fallback reaction without opening the window.")
    parser.add_argument("--demo", action="store_true", help="Open the desktop pet and run the scripted behavior demo.")
    args = parser.parse_args()
    package_root = Path(__file__).resolve().parent
    project_root = package_root.parent
    language = load_language_setting(project_root)
    soul = load_soul(soul_path_for_language(package_root, language))
    soul.language = language
    if args.self_test:
        brain = OllamaBrain(soul, project_root=project_root)
        reaction = brain.react("self-test", {"active_window_title": "Codex", "idle_seconds": 0})
        print(f"{soul.name}: {reaction.line}")
        return
    install_chat_language_support(PaperclipPalApp)
    app = PaperclipPalApp(soul, project_root)
    if args.demo:
        app.root.after(1000, app._run_scripted_demo)
    app.run()


if __name__ == "__main__":
    main()
