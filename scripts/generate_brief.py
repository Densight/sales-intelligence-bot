"""
Sales Intelligence Bot — v3 (cost-optimised)
Densight Labs · Applied AI Live, Episode 1

FLOW:
  1. Fetch signals (HackerNews + RSS + GitHub) — free
  2. Trim to titles only — ~200 tokens
  3. ONE Haiku call — identifies 3 companies + full brief — ~$0.01
  4. Post to GitHub Issue
"""

import os
import json
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, date

# ── CONFIG ────────────────────────────────────────────────────────────────────

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
GITHUB_TOKEN      = os.environ["GITHUB_TOKEN"]
GITHUB_REPO       = os.environ["GITHUB_REPO"]

YOUR_COMPANY  = os.environ.get("YOUR_COMPANY",  "Densight Labs")
YOUR_SERVICE  = os.environ.get("YOUR_SERVICE",  "AI implementation and workflow automation for enterprise teams")
TARGET_MARKET = os.environ.get("TARGET_MARKET", "US-based mid-market companies scaling their operations or tech teams")

# ── STEP 1: FETCH SIGNALS ─────────────────────────────────────────────────────

def fetch_hackernews():
    print("📡 HackerNews...")
    try:
        top = requests.get("https://hacker-news.firebaseio.com/v0/topstories.json", timeout=10).json()
        signals = []
        for sid in top[:100]:
            s = requests.get(f"https://hacker-news.firebaseio.com/v0/item/{sid}.json", timeout=5).json()
            if not s: continue
            t = s.get("title", "").lower()
            if any(k in t for k in ["hiring", "launched", "show hn", "raised", "series a", "series b", "funding"]):
                signals.append(s.get("title", ""))
            if len(signals) >= 8: break
        print(f"   → {len(signals)}")
        return signals
    except Exception as e:
        print(f"   ⚠️ {e}")
        return []

def fetch_rss():
    print("📡 RSS...")
    feeds = [
        ("TechCrunch", "https://techcrunch.com/category/startups/feed/"),
        ("VentureBeat", "https://venturebeat.com/category/ai/feed/"),
    ]
    signals = []
    for name, url in feeds:
        try:
            resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            root = ET.fromstring(resp.content)
            for item in root.findall(".//item")[:5]:
                t = item.findtext("title", "").strip()
                if t: signals.append(t)
        except: pass
    print(f"   → {len(signals)}")
    return signals

def fetch_github():
    print("📡 GitHub...")
    try:
        resp = requests.get(
            "https://api.github.com/search/repositories",
            params={"q": "created:>2026-05-01 stars:>50", "sort": "stars", "order": "desc", "per_page": 8},
            headers={"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"},
            timeout=10,
        )
        signals = []
        for r in resp.json().get("items", []):
            desc = (r.get("description") or "")[:60]
            signals.append(f"{r.get('full_name','')} — {desc} ({r.get('stargazers_count',0)} stars)")
        print(f"   → {len(signals)}")
        return signals
    except Exception as e:
        print(f"   ⚠️ {e}")
        return []

# ── STEP 2: ONE CLAUDE CALL ───────────────────────────────────────────────────

def generate_brief(hn, rss, github) -> str:
    print("\n🤖 Claude (Haiku) — generating brief...")

    signals_text = "\n".join(
        [f"HN: {s}" for s in hn] +
        [f"NEWS: {s}" for s in rss] +
        [f"GITHUB: {s}" for s in github]
    )

    prompt = f"""You are a sales analyst for {YOUR_COMPANY}.
Service: {YOUR_SERVICE}
Target: {TARGET_MARKET}

From these signals, pick the 3 best US outreach opportunities and write a sales brief.

SIGNALS:
{signals_text}

For each company write exactly this markdown format:

---
### [Company Name] — [Industry] `[High/Medium]`
**Signal:** [what happened]
**Why now:** [1-2 sentences on timing]
**Pain points:** [3 bullet points specific to this company]
**Outreach angle:** [one sentence on what we offer them]
**First line:** [cold email opener]
**Talking points:** [2-3 bullets for the call]
**Watch out:** [one red flag or tip]
---

Be specific. No generic advice."""

    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key":        ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type":     "application/json",
        },
        json={
            "model":     "claude-haiku-4-5-20251001",
            "max_tokens": 1500,
            "messages":  [{"role": "user", "content": prompt}],
        },
        timeout=60,
    )

    result = resp.json()
    usage  = result.get("usage", {})
    cost   = (usage.get("input_tokens", 0) * 0.00000025) + (usage.get("output_tokens", 0) * 0.00000125)
    print(f"   → Tokens: {usage.get('input_tokens',0)} in / {usage.get('output_tokens',0)} out | Cost: ${cost:.4f}")
    return result["content"][0]["text"]

# ── STEP 3: GITHUB ISSUE ─────────────────────────────────────────────────────

def create_issue(brief: str, total_signals: int):
    print("\n📌 Creating GitHub Issue...")
    today = date.today().strftime("%d %b %Y")
    body  = f"""## 🎯 Sales Intelligence Brief
**Date:** {datetime.now().strftime("%d %b %Y, %H:%M PKT")} | **Signals analysed:** {total_signals} | **Powered by:** GitHub Actions + Claude API

---

{brief}

---
*Auto-generated by Densight Labs Sales Intelligence Bot*"""

    owner, repo = GITHUB_REPO.split("/")
    resp = requests.post(
        f"https://api.github.com/repos/{owner}/{repo}/issues",
        headers={"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"},
        json={"title": f"🎯 Sales Intelligence Brief — {today}", "body": body, "labels": ["sales-intel", "automated"]},
        timeout=15,
    )
    if resp.status_code == 201:
        print(f"   → {resp.json()['html_url']}")
    else:
        print(f"   ⚠️ {resp.status_code}: {resp.text[:200]}")

# ── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    print("=" * 50)
    print("  SALES INTELLIGENCE BOT v3 — Densight Labs")
    print(f"  {datetime.now().strftime('%d %b %Y, %H:%M PKT')}")
    print("=" * 50)

    hn     = fetch_hackernews()
    rss    = fetch_rss()
    github = fetch_github()
    total  = len(hn) + len(rss) + len(github)
    print(f"\n✅ {total} signals collected")

    if total == 0:
        print("⚠️  No signals. Exiting.")
        return

    brief = generate_brief(hn, rss, github)
    create_issue(brief, total)

    print("\n✅ DONE")

if __name__ == "__main__":
    main()
