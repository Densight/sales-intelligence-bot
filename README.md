# 🎯 Sales Intelligence Bot

**Built live at Applied AI Live — Episode 1 | Densight Labs | 25 May 2026**

Automatically finds outreach opportunities for your sales team — every Monday morning, without anyone lifting a finger.

---

## What It Does

```
GitHub Actions (Monday 8am)
        ↓
Fetches signals from:
  → HackerNews    (hirings, launches, funding)
  → Tech RSS      (TechCrunch, VentureBeat)
  → GitHub        (companies open-sourcing = buying signal)
        ↓
Claude API analyses all signals
  → Who to contact
  → Why right now
  → Suggested first line for cold outreach
        ↓
GitHub Issue created automatically
  → "🎯 Sales Intelligence Brief — 26 May 2026"
  → Structured, actionable, ready to use
```

**Result:** Your sales team starts Monday with a warm brief, not a blank screen.

---

## Setup (5 minutes)

### 1. Fork this repo

### 2. Add your secrets
Go to **Settings → Secrets → Actions** and add:

| Secret | What it is |
|--------|------------|
| `ANTHROPIC_API_KEY` | Get from [console.anthropic.com](https://console.anthropic.com) |

> `GITHUB_TOKEN` is provided automatically — no setup needed.

### 3. Customise for your business
Edit these lines in `.github/workflows/sales-intel.yml`:

```yaml
YOUR_COMPANY:  "Your Company Name"
YOUR_SERVICE:  "What you sell"
TARGET_MARKET: "Who you sell to"
```

### 4. Run it
- **Automatic:** Runs every Monday at 8am
- **Manual:** Go to Actions → Sales Intelligence Brief → Run workflow

---

## The Output

Each run creates a GitHub Issue like this:

```
🎯 Sales Intelligence Brief — 26 May 2026

## Opportunity 1: Fintech startup, Series A just closed
Signal: Raised $4M, posted 3 ops roles this week
Why now: Scaling ops = automation pain incoming
Angle: AI workflow automation for their new ops team
First line: "Congrats on the Series A — scaling ops from 5 to 20 people
            is exactly when manual processes start breaking."
Confidence: High
```

---

## Customise Further

**Change the signal sources** — swap HackerNews for Reddit, LinkedIn, your CRM, or any data source with an API.

**Change Claude's prompt** — tell it to look for different triggers, different industries, different company sizes.

**Change the output** — instead of a GitHub Issue, send to Slack, email, Notion, or Telegram. Same script, 5 lines changed.

---

## The Pattern

```
Any data source  →  Claude API  →  Any output
```

This is the pattern. Everything else is just configuration.

---

Built by [Densight Labs](https://densightlabs.com) — Applied AI. Not just talked about.
