"""
Sales Intelligence Bot
Densight Labs — Applied AI Live, Episode 1

What this does:
1. Fetches signals from HackerNews, RSS feeds, GitHub Trending
2. Sends raw signals to Claude API
3. Claude identifies outreach opportunities with reasoning + suggested first lines
4. Creates a GitHub Issue with the structured sales brief
"""

import os
import json
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, date

# ── CONFIG ────────────────────────────────────────────────────────────────────

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
GITHUB_TOKEN      = os.environ["GITHUB_TOKEN"]
GITHUB_REPO       = os.environ["GITHUB_REPO"]   # e.g. "your-org/sales-intel"

YOUR_COMPANY      = os.environ.get("YOUR_COMPANY", "Densight Labs")
YOUR_SERVICE      = os.environ.get("YOUR_SERVICE", "AI implementation and automation for enterprise teams")
TARGET_MARKET     = os.environ.get("TARGET_MARKET", "mid-market companies in Pakistan and GCC that need AI automation")

# ── STEP 1: FETCH SIGNALS ─────────────────────────────────────────────────────

def fetch_hackernews_hiring():
    """Fetch latest 'Who is Hiring' thread from HackerNews."""
    print("📡 Fetching HackerNews hiring signals...")
    try:
        # Get top stories
        top = requests.get(
            "https://hacker-news.firebaseio.com/v0/topstories.json",
            timeout=10
        ).json()

        signals = []
        # Search recent stories for hiring/launch signals
        for story_id in top[:100]:
            story = requests.get(
                f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json",
                timeout=5
            ).json()
            if not story:
                continue
            title = story.get("title", "").lower()
            if any(kw in title for kw in ["hiring", "launched", "show hn", "we built", "series a", "series b", "raised"]):
                signals.append({
                    "source": "HackerNews",
                    "title": story.get("title", ""),
                    "url": story.get("url", f"https://news.ycombinator.com/item?id={story_id}"),
                    "score": story.get("score", 0),
                })
            if len(signals) >= 10:
                break

        print(f"   → Found {len(signals)} HN signals")
        return signals
    except Exception as e:
        print(f"   ⚠️  HN fetch failed: {e}")
        return []


def fetch_rss_signals():
    """Fetch business/funding news from RSS feeds."""
    print("📡 Fetching RSS signals...")

    feeds = [
        ("TechCrunch Startups", "https://techcrunch.com/category/startups/feed/"),
        ("TechCrunch AI",       "https://techcrunch.com/category/artificial-intelligence/feed/"),
        ("VentureBeat AI",      "https://venturebeat.com/category/ai/feed/"),
    ]

    signals = []
    for feed_name, url in feeds:
        try:
            resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            root = ET.fromstring(resp.content)
            items = root.findall(".//item")[:5]
            for item in items:
                title = item.findtext("title", "").strip()
                link  = item.findtext("link", "").strip()
                desc  = item.findtext("description", "")[:300].strip()
                if title:
                    signals.append({
                        "source": feed_name,
                        "title": title,
                        "url": link,
                        "description": desc,
                    })
        except Exception as e:
            print(f"   ⚠️  {feed_name} failed: {e}")

    print(f"   → Found {len(signals)} RSS signals")
    return signals


def fetch_github_trending():
    """Fetch trending repos — companies open-sourcing = buying signal."""
    print("📡 Fetching GitHub trending signals...")
    try:
        resp = requests.get(
            "https://api.github.com/search/repositories",
            params={
                "q": "created:>2026-05-01 stars:>50",
                "sort": "stars",
                "order": "desc",
                "per_page": 10,
            },
            headers={
                "Authorization": f"Bearer {GITHUB_TOKEN}",
                "Accept": "application/vnd.github+json",
            },
            timeout=10,
        )
        repos = resp.json().get("items", [])
        signals = []
        for repo in repos:
            signals.append({
                "source": "GitHub Trending",
                "company": repo.get("owner", {}).get("login", ""),
                "repo": repo.get("full_name", ""),
                "description": repo.get("description", ""),
                "stars": repo.get("stargazers_count", 0),
                "url": repo.get("html_url", ""),
                "language": repo.get("language", ""),
            })
        print(f"   → Found {len(signals)} GitHub signals")
        return signals
    except Exception as e:
        print(f"   ⚠️  GitHub trending failed: {e}")
        return []


# ── STEP 2: CLAUDE API ────────────────────────────────────────────────────────

def analyse_with_claude(signals: dict) -> str:
    """Send raw signals to Claude. Get back a structured sales brief."""
    print("\n🤖 Sending signals to Claude API...")

    prompt = f"""You are a senior sales intelligence analyst for {YOUR_COMPANY}.

Our service: {YOUR_SERVICE}
Our target market: {TARGET_MARKET}

Below are raw signals collected today from HackerNews, tech news RSS feeds, and GitHub.
Your job: identify the 5 best outreach opportunities hidden in these signals.

For each opportunity, provide:
1. **Company / Target** — who to reach out to
2. **Signal** — what happened (the trigger)
3. **Why now** — why this is the right moment to reach out
4. **Outreach angle** — what problem we can solve for them specifically
5. **Suggested first line** — one sentence opener for a cold email or LinkedIn message. Make it specific to their situation, not generic.
6. **Confidence** — High / Medium / Low

Be ruthlessly selective. Only include genuine opportunities. Skip anything vague.
Format your response as clean markdown so it renders well as a GitHub Issue.

--- RAW SIGNALS START ---

HACKERNEWS SIGNALS:
{json.dumps(signals['hackernews'], indent=2)}

RSS / NEWS SIGNALS:
{json.dumps(signals['rss'], indent=2)}

GITHUB TRENDING SIGNALS:
{json.dumps(signals['github'], indent=2)}

--- RAW SIGNALS END ---

Now produce the sales brief:"""

    response = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 2000,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=60,
    )

    result = response.json()
    brief = result["content"][0]["text"]
    print("   → Claude brief generated ✅")
    return brief


# ── STEP 3: CREATE GITHUB ISSUE ───────────────────────────────────────────────

def create_github_issue(brief: str, signal_count: int):
    """Post the sales brief as a GitHub Issue."""
    print("\n📌 Creating GitHub Issue...")

    today = date.today().strftime("%d %b %Y")
    title = f"🎯 Sales Intelligence Brief — {today}"

    body = f"""## Sales Intelligence Brief
**Generated:** {datetime.now().strftime("%d %b %Y, %H:%M PKT")}
**Signals analysed:** {signal_count}
**Powered by:** Claude API + GitHub Actions

---

{brief}

---

*Generated automatically by Densight Labs Sales Intelligence Bot*
*To adjust targeting or prompt, edit `scripts/generate_brief.py`*
"""

    owner, repo = GITHUB_REPO.split("/")
    resp = requests.post(
        f"https://api.github.com/repos/{owner}/{repo}/issues",
        headers={
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json",
        },
        json={
            "title": title,
            "body": body,
            "labels": ["sales-intel", "automated"],
        },
        timeout=15,
    )

    if resp.status_code == 201:
        issue_url = resp.json()["html_url"]
        print(f"   → Issue created: {issue_url}")
        return issue_url
    else:
        print(f"   ⚠️  Issue creation failed: {resp.status_code} — {resp.text}")
        return None


# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  SALES INTELLIGENCE BOT — Densight Labs")
    print(f"  Running at {datetime.now().strftime('%d %b %Y, %H:%M')}")
    print("=" * 60)

    # Step 1: Fetch
    hn_signals     = fetch_hackernews_hiring()
    rss_signals    = fetch_rss_signals()
    github_signals = fetch_github_trending()

    all_signals = {
        "hackernews": hn_signals,
        "rss":        rss_signals,
        "github":     github_signals,
    }
    total = len(hn_signals) + len(rss_signals) + len(github_signals)
    print(f"\n✅ Total signals collected: {total}")

    if total == 0:
        print("⚠️  No signals found. Exiting.")
        return

    # Step 2: Analyse
    brief = analyse_with_claude(all_signals)

    # Step 3: Deliver
    issue_url = create_github_issue(brief, total)

    print("\n" + "=" * 60)
    print("  DONE.")
    if issue_url:
        print(f"  Brief live at: {issue_url}")
    print("=" * 60)


if __name__ == "__main__":
    main()
