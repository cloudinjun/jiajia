# Publishing Checklist

Use this checklist before switching the GitHub repository from private to
public.

## 1. Confirm Ignored Local State

These files should remain untracked:

- `settings.json`
- `memory/`
- `codex_status.json`
- `codex_usage_status.json`
- `claude_account_status.json`
- `.env*`

Check:

```powershell
git status --short --ignored
```

## 2. Scan For Secrets And Local Paths

```powershell
git grep -n -E "sk-|AIza|ghp_|github_pat|OPENAI_ADMIN_KEY=|OPENAI_API_KEY=|GEMINI_API_KEY=|GOOGLE_API_KEY=|ANTHROPIC_API_KEY=|Bearer [A-Za-z0-9._-]{20,}"
```

Inspect matches manually. Documentation may mention environment variable names,
but it should not contain actual values.

## 3. Regenerate Public GIFs

```powershell
python scripts\generate_demo_gifs.py
```

Open `docs/media/` and verify that the character is not clipped and that the
GIFs are not blank.

## 4. Validate Python Files

```powershell
python -m compileall -q jiajia scripts tests
python -m unittest discover -s tests
python -m jiajia.main --self-test
```

## 5. Commit Public Files

Stage only intentional public files. Raw concept exports under
`jiajia/assets/paperclip/` should stay ignored.

```powershell
git status --short
git add -A
git commit -m "Prepare public repository"
git push
```

## 6. Make The GitHub Repository Public

After the checks pass:

```powershell
gh repo edit cloudinjun/jiajia --visibility public
```

GitHub may ask for confirmation. Do not run this until the secret scan and
status check are clean.
