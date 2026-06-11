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
rg -n "(sk-|AIza|ghp_|github_pat|OPENAI_ADMIN_KEY|GEMINI_API_KEY|GOOGLE_API_KEY|ANTHROPIC|password|secret|token|C:\\\\Users|D:\\\\)" -S .
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
python -m py_compile scripts\generate_demo_gifs.py
python -m python_pal.main --self-test
```

## 5. Commit Public Files

Stage only intentional public files:

```powershell
git add README.md PRIVACY.md LICENSE .gitignore docs scripts/generate_demo_gifs.py
git commit -m "Prepare public repository docs and demos"
git push
```

## 6. Make The GitHub Repository Public

After the checks pass:

```powershell
gh repo edit cloudinjun/paperclip-pal --visibility public
```

GitHub may ask for confirmation. Do not run this until the secret scan and
status check are clean.
