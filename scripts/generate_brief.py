"""
Sales Intelligence Bot — v2
Densight Labs · Applied AI Live, Episode 1 · 25 May 2026

ARCHITECTURE (3 steps, 2 Claude calls):

  Step 1 — FETCH
    GitHub API   → trending repos (companies open-sourcing = buying signal)
    HackerNews   → hirings, launches, funding announcements
    RSS feeds    → TechCrunch, VentureBeat

  Step 2 — ANALYSE  (Claude Call 1 — no tools)
    Raw signals → Claude identifies 5 US companies worth contacting
    Returns structured JSON: company names, domains, why now, outreach angle

  Step 3 — ENRICH  (Claude Call 2 — with Vibe Prospecting MCP)
    Claude autonomously calls Vibe Prospecting for each company:
      → Website, LinkedIn, employee count, revenue, industry
      → Decision makers: CEO / CTO / VP Sales — names, emails, LinkedIn
    Returns fully enriched brief as markdown

  Step 4 — DELIVER
    GitHub Issue  → clean public summary (no emails)
    Google Doc    → new tab with full brief including all contact data
"""

import os
import json
import time
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, date

# ── CONFIG ────────────────────────────────────────────────────────────────────

ANTHROPIC_API_KEY  = os.environ["ANTHROPIC_API_KEY"]
GITHUB_TOKEN       = os.environ["GITHUB_TOKEN"]
GITHUB_REPO        = os.environ["GITHUB_REPO"]          # "owner/repo"
GOOGLE_DOC_ID      = os.environ["GOOGLE_DOC_ID"]        # from Doc URL
GOOGLE_CREDENTIALS = os.environ["GOOGLE_CREDENTIALS"]   # service account JSON string

YOUR_COMPANY  = os.environ.get("YOUR_COMPANY",  "Densight Labs")
YOUR_SERVICE  = os.environ.get("YOUR_SERVICE",  "AI implementation and workflow automation for enterprise teams")
TARGET_MARKET = os.environ.get("TARGET_MARKET", "US-based mid-market companies scaling their operations or tech teams")

VIBE_MCP_URL   = "https://vibeprospecting.explorium.ai/mcp"
VIBE_MCP_TOKEN = os.environ["VIBE_PROSPECTING_TOKEN"]

# ── STEP 1: FETCH SIGNALS ─────────────────────────────────────────────────────

def fetch_hackernews():
    print("📡 Fetching HackerNews signals...")
    try:
        top = requests.get(
            "https://hacker-news.firebaseio.com/v0/topstories.json",
            timeout=10
        ).json()
        signals = []
        for story_id in top[:100]:
            story = requests.get(
                f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json",
                timeout=5
            ).json()
            if not story:
                continue
            title = story.get("title", "").lower()
            if any(kw in title for kw in ["hiring", "launched", "show hn", "we built", "series a", "series b", "raised", "funding"]):
                signals.append({
                    "source": "HackerNews",
                    "title": story.get("title", ""),
                    "url": story.get("url", f"https://news.ycombinator.com/item?id={story_id}"),
                    "score": story.get("score", 0),
                })
            if len(signals) >= 10:
                break
        print(f"   → {len(signals)} signals")
        return signals
    except Exception as e:
        print(f"   ⚠️  Failed: {e}")
        return []


def fetch_rss():
    print("📡 Fetching RSS signals...")
    feeds = [
        ("TechCrunch Startups", "https://techcrunch.com/category/startups/feed/"),
        ("TechCrunch AI",       "https://techcrunch.com/category/artificial-intelligence/feed/"),
        ("VentureBeat AI",      "https://venturebeat.com/category/ai/feed/"),
    ]
    signals = []
    for name, url in feeds:
        try:
            resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            root = ET.fromstring(resp.content)
            for item in root.findall(".//item")[:5]:
                title = item.findtext("title", "").strip()
                if title:
                    signals.append({
                        "source": name,
                        "title": title,
                        "url": item.findtext("link", "").strip(),
                        "description": item.findtext("description", "")[:300].strip(),
                    })
        except Exception as e:
            print(f"   ⚠️  {name} failed: {e}")
    print(f"   → {len(signals)} signals")
    return signals


def fetch_github_trending():
    print("📡 Fetching GitHub trending signals...")
    try:
        resp = requests.get(
            "https://api.github.com/search/repositories",
            params={"q": "created:>2026-05-01 stars:>50", "sort": "stars", "order": "desc", "per_page": 10},
            headers={"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"},
            timeout=10,
        )
        signals = []
        for repo in resp.json().get("items", []):
            signals.append({
                "source": "GitHub Trending",
                "company": repo.get("owner", {}).get("login", ""),
                "repo": repo.get("full_name", ""),
                "description": repo.get("description", ""),
                "stars": repo.get("stargazers_count", 0),
                "url": repo.get("html_url", ""),
                "language": repo.get("language", ""),
            })
        print(f"   → {len(signals)} signals")
        return signals
    except Exception as e:
        print(f"   ⚠️  Failed: {e}")
        return []


# ── STEP 2: CLAUDE CALL 1 — IDENTIFY COMPANIES ───────────────────────────────

def identify_companies(signals: dict) -> list:
    """
    Claude Call 1 — no MCP tools.
    Reads raw signals, returns 5 US companies as structured JSON.
    """
    print("\n🤖 Claude Call 1 — identifying companies from signals...")

    # Trim signals to keep costs low — titles only, no full descriptions
    trimmed = {
        "hackernews": [{"title": s.get("title",""), "url": s.get("url","")} for s in signals.get("hackernews", [])],
        "rss":        [{"title": s.get("title",""), "source": s.get("source","")} for s in signals.get("rss", [])],
        "github":     [{"company": s.get("company",""), "repo": s.get("repo",""), "description": (s.get("description") or "")[:80], "stars": s.get("stars",0)} for s in signals.get("github", [])],
    }


    prompt = f"""You are a senior sales intelligence analyst for {YOUR_COMPANY}.

Our service: {YOUR_SERVICE}
Target: {TARGET_MARKET}

Analyse the signals below and identify exactly 3 US-based companies that are
the strongest outreach opportunities RIGHT NOW. Quality over quantity — pick the 3 best.

Return ONLY a JSON array. No preamble, no markdown. Example format:
[
  {{
    "company_name": "Acme Corp",
    "domain": "acme.com",
    "industry": "Fintech",
    "estimated_size": "201-500 employees",
    "signal": "Raised $20M Series A, hiring 50 engineers across ops and engineering",
    "trigger_date": "This week",
    "why_now": "Scaling from 50 to 100 people is exactly when manual processes collapse. They will feel this pain within 30 days.",
    "pain_points": [
      "Engineer onboarding taking 2-3 weeks manually",
      "Status updates still happening over Slack and email",
      "No automated reporting to leadership"
    ],
    "outreach_angle": "Automate their engineering onboarding, weekly status reporting, and internal approvals",
    "suggested_first_line": "Congrats on the Series A — onboarding 50 engineers manually is exactly when workflows start breaking.",
    "follow_up_angle": "Offer a free 2-hour workflow audit — map their top 3 manual processes and show what automation looks like",
    "talking_points": [
      "Companies at this stage spend 8-12 hours/week on status updates alone",
      "Automation ROI is fastest during hiring spikes — not after",
      "We have done this for 3 companies at the same stage"
    ],
    "red_flags": "Decision maker may be too busy — target ops lead not CEO",
    "confidence": "High"
  }}
]

Only US companies. Only genuine opportunities. Be ruthlessly selective.
Make pain_points and talking_points specific to THIS company — not generic.

SIGNALS:
{json.dumps(trimmed, indent=2)}"""

    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 2000,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=60,
    )

    raw = resp.json()["content"][0]["text"].strip()

    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    companies = json.loads(raw)
    print(f"   → Identified {len(companies)} companies: {[c['company_name'] for c in companies]}")
    return companies


# ── STEP 3: CLAUDE CALL 2 — ENRICH WITH VIBE PROSPECTING MCP ─────────────────

def enrich_one_company(company: dict) -> str:
    """
    Enrich a single company via one Claude + Vibe Prospecting MCP call.
    Splitting per-company keeps each call under 60s.
    """
    prompt = f"""You are a sales intelligence assistant for {YOUR_COMPANY}.

Enrich this ONE company using Vibe Prospecting tools:

Company: {company['company_name']}
Domain:  {company['domain']}
Signal:  {company['signal']}
Angle:   {company['outreach_angle']}
First line: {company['suggested_first_line']}

Steps:
1. Call match-business with the company name and domain
2. Call fetch-entities or match-prospects to find CEO, CTO, or VP Operations/Sales
3. Return a markdown section in this exact format:

---
## {company['company_name']}
**Website:** | **LinkedIn:** | **Industry:** | **Size:** | **Revenue:**

**Signal:** {company['signal']}
**Why now:** {company['why_now']}
**Outreach angle:** {company['outreach_angle']}
**Suggested first line:** {company['suggested_first_line']}
**Confidence:** {company['confidence']}

### Decision Makers
| Name | Title | Email | LinkedIn |
|------|-------|-------|----------|
| ... | ... | ... | ... |
---

Fill in all fields from the Vibe Prospecting data. If data is unavailable write N/A."""

    messages = [{"role": "user", "content": prompt}]
    full_text = ""
    max_turns = 10

    for turn in range(max_turns):
        try:
            resp = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key":         ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type":      "application/json",
                    "anthropic-beta":    "mcp-client-2025-04-04",
                },
                json={
                    "model":       "claude-sonnet-4-20250514",
                    "max_tokens":  2000,
                    "messages":    messages,
                    "mcp_servers": [
                        {
                            "type":                "url",
                            "url":                 VIBE_MCP_URL,
                            "name":                "vibe-prospecting",
                            "authorization_token": VIBE_MCP_TOKEN,
                        }
                    ],
                },
                timeout=120,  # 2 min per company
            )
        except requests.exceptions.Timeout:
            print(f"      ⚠️  Timeout on turn {turn+1} — moving on")
            break

        if resp.status_code != 200:
            print(f"      ⚠️  API error: {resp.status_code} — {resp.text[:200]}")
            break

        result      = resp.json()
        stop_reason = result.get("stop_reason", "")
        content     = result.get("content", [])

        for block in content:
            if block.get("type") == "text":
                full_text += block.get("text", "")
            elif block.get("type") == "tool_use":
                print(f"      → Called: {block.get('name', 'unknown')}")

        if stop_reason == "end_turn":
            break
        if stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": content})
            messages.append({"role": "user", "content": "Continue."})
        else:
            break

    return full_text or f"\n---\n## {company['company_name']}\n*Enrichment unavailable*\n---\n"


def enrich_with_claude_mcp(companies: list) -> str:
    """Enrich all companies one at a time — avoids timeout."""
    print("\n🤖 Claude Call 2 — enriching companies via Vibe Prospecting MCP...")
    all_sections = []

    for i, company in enumerate(companies, 1):
        print(f"   [{i}/5] Enriching {company['company_name']}...")
        section = enrich_one_company(company)
        all_sections.append(section)
        print(f"   ✅ {company['company_name']} done")

    print("   → All companies enriched")
    return "\n".join(all_sections)



# ── STEP 4a: CREATE GITHUB ISSUE ─────────────────────────────────────────────

def create_github_issue(companies: list, signal_count: int) -> str:
    """Post clean summary to GitHub Issue — no emails, no private data."""
    print("\n📌 Creating GitHub Issue...")

    today = date.today().strftime("%d %b %Y")
    title = f"🎯 Sales Intelligence Brief — {today}"

    # Build rich summary
    summary_lines = []
    for i, c in enumerate(companies, 1):
        pain  = chr(10).join(f"  - {p}" for p in c.get("pain_points", []))
        talks = chr(10).join(f"  - {t}" for t in c.get("talking_points", []))
        summary_lines.append(f"""### {i}. {c['company_name']} — {c.get('industry','')}&nbsp;&nbsp;`{c.get('confidence','')}`
> **Signal ({c.get('trigger_date','this week')}):** {c['signal']}

**Why contact them NOW:**
{c.get('why_now', '')}

**Their pain points:**
{pain}

**Your outreach angle:**
{c['outreach_angle']}

**Suggested first line:**
> _{c['suggested_first_line']}_

**Follow-up angle:**
{c.get('follow_up_angle', '')}

**Talking points for the call:**
{talks}

⚠️ **Watch out:** {c.get('red_flags', 'N/A')}

---
""")

    body = f"""## 🎯 Sales Intelligence Brief
**Date:** {datetime.now().strftime("%d %b %Y, %H:%M PKT")}
**Signals analysed:** {signal_count}
**Powered by:** GitHub Actions + Claude API + Vibe Prospecting

> Full brief with decision maker contacts is in Google Docs.

---

{''.join(summary_lines)}

---
*Auto-generated by Densight Labs Sales Intelligence Bot*
"""

    owner, repo = GITHUB_REPO.split("/")
    resp = requests.post(
        f"https://api.github.com/repos/{owner}/{repo}/issues",
        headers={"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"},
        json={"title": title, "body": body, "labels": ["sales-intel", "automated"]},
        timeout=15,
    )

    if resp.status_code == 201:
        url = resp.json()["html_url"]
        print(f"   → Issue created: {url}")
        return url
    else:
        print(f"   ⚠️  Issue failed: {resp.status_code}")
        return ""


# ── STEP 4b: WRITE TO GOOGLE DOC ─────────────────────────────────────────────

def write_to_google_doc(enriched_brief: str, companies: list):
    """
    Appends a new section to the Google Doc for today's brief.
    Uses Google Docs API with service account credentials.
    """
    print("\n📄 Writing to Google Doc...")

    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        # Load credentials from environment variable (JSON string)
        creds_info = json.loads(GOOGLE_CREDENTIALS)
        creds = service_account.Credentials.from_service_account_info(
            creds_info,
            scopes=["https://www.googleapis.com/auth/documents"]
        )
        service = build("docs", "v1", credentials=creds)

        today = datetime.now().strftime("%d %b %Y, %H:%M PKT")
        header = f"\n\n{'='*60}\nSALES INTELLIGENCE BRIEF — {today}\n{'='*60}\n\n"
        full_content = header + enriched_brief + "\n\n"

        # Append to end of document
        doc = service.documents().get(documentId=GOOGLE_DOC_ID).execute()
        end_index = doc["body"]["content"][-1]["endIndex"] - 1

        service.documents().batchUpdate(
            documentId=GOOGLE_DOC_ID,
            body={
                "requests": [
                    {
                        "insertText": {
                            "location": {"index": end_index},
                            "text": full_content,
                        }
                    }
                ]
            }
        ).execute()

        doc_url = f"https://docs.google.com/document/d/{GOOGLE_DOC_ID}/edit"
        print(f"   → Written to Google Doc: {doc_url}")
        return doc_url

    except ImportError:
        print("   ⚠️  google-api-python-client not installed — skipping Google Doc")
        return ""
    except Exception as e:
        print(f"   ⚠️  Google Doc write failed: {e}")
        return ""


# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  SALES INTELLIGENCE BOT v2 — Densight Labs")
    print(f"  {datetime.now().strftime('%d %b %Y, %H:%M PKT')}")
    print("=" * 60)

    # ── Step 1: Fetch signals
    hn      = fetch_hackernews()
    rss     = fetch_rss()
    github  = fetch_github_trending()
    signals = {"hackernews": hn, "rss": rss, "github": github}
    total   = len(hn) + len(rss) + len(github)
    print(f"\n✅ Total signals collected: {total}")

    if total == 0:
        print("⚠️  No signals. Exiting.")
        return

    # ── Step 2: Claude Call 1 — identify companies
    companies = identify_companies(signals)

    # ── Step 3: Claude Call 2 — enrich via Vibe Prospecting MCP
    enriched_brief = enrich_with_claude_mcp(companies)

    # ── Step 4: Deliver
    issue_url = create_github_issue(companies, total)
    doc_url   = write_to_google_doc(enriched_brief, companies)

    # ── Summary
    print("\n" + "=" * 60)
    print("  ✅ DONE")
    print(f"  GitHub Issue : {issue_url}")
    print(f"  Google Doc   : {doc_url}")
    print("=" * 60)


if __name__ == "__main__":
    main()
