# Demo Media

These GIFs are generated assets for the public README.

Regenerate them from the repository root:

```powershell
python scripts\generate_demo_gifs.py
python scripts\generate_quote_gifs.py
python scripts\generate_quote_gifs.py --language en
```

The generator renders the flat character asset with the app's current demo
definitions.

- Interaction: `user-chat.gif`, `active-talking.gif`, `user-poke.gif`,
  `user-drag.gif`.
- Ambient state: `idle-breathe.gif`, `cold-arrow-then-innocent.gif`,
  `sleepy-sag.gif`, `status-colors.gif`, `tail-wag.gif`.
- Full loop: `hero-interaction.gif`.
- Roast galleries: `quotes/` (Chinese), `quotes/en/` (English).

Do not hand-edit the GIFs unless the generator cannot represent the needed
behavior.
