# Privacy

Paperclip Pal is intended to be local-first and low-privacy-risk. Its sensing
model should be explicit: it may watch system state, but it should not collect
private content.

## What It May Read

- Foreground app/process name.
- Sanitized window-title category signals.
- Idle time and rough focus duration.
- Window-switch frequency.
- Codex local rate-limit metadata from `token_count.rate_limits`.
- Claude local token usage metadata from `message.usage`.
- Hardware metrics such as CPU, RAM, disk, GPU utilization, temperature, and
  VRAM.
- Optional OpenAI API cost totals through the official organization Costs API.

## What It Should Not Read By Default

- Clipboard text.
- Keystroke text.
- Passwords, tokens, or secrets.
- Chat message contents.
- Raw document text.
- Full screenshot contents.
- Browser cookies or authenticated billing pages.

## Vision And Screen Context

The optional vision layer is meant for high-level scene tags, not text
transcription. If a screen appears privacy-sensitive, the expected behavior is
to tag it as sensitive and stay quiet instead of summarizing the content.

## Local Storage

The app may create local runtime files such as:

- `settings.json`
- `memory/event_log.jsonl`
- `memory/line_bank.json`
- status bridge JSON files

These files are ignored by git. They should not be included in public issues,
release archives, screenshots, or commits unless deliberately sanitized.

## API Keys

API keys should be provided through environment variables or a local `.env`
file. `.env*` files are ignored by git.

Do not commit:

- `OPENAI_ADMIN_KEY`
- `OPENAI_API_KEY`
- `GEMINI_API_KEY`
- `GOOGLE_API_KEY`
- `ANTHROPIC_API_KEY`
- GitHub tokens

## Cost And Balance Reporting

Some providers expose cost usage but not prepaid balance through API keys. In
that case Paperclip Pal should report the limitation clearly and use a manual
snapshot estimate rather than scraping browser sessions or inventing a balance.

## Public Sharing Checklist

Before making a repository, ZIP, screenshot, or demo public:

```powershell
git status --short
git grep -n -E "sk-|AIza|ghp_|github_pat|OPENAI_ADMIN_KEY=|GEMINI_API_KEY=|GOOGLE_API_KEY=|ANTHROPIC_API_KEY="
```

Review any match before publishing.
