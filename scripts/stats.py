#!/usr/bin/env python3
"""Draw the stats card on the profile README from the GitHub GraphQL API.

Writes assets/stats-light.svg and assets/stats-dark.svg. Needs a token in
STATS_TOKEN or GITHUB_TOKEN; a personal token also counts private work.
"""

import json
import os
import sys
import urllib.request
from datetime import date, timedelta
from pathlib import Path

LOGIN = "deepdave98"
QUERY = """
query($login: String!) {
  user(login: $login) {
    followers { totalCount }
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC) {
      nodes {
        stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name } }
        }
      }
    }
    repositoriesContributedTo(first: 1, contributionTypes: [COMMIT, PULL_REQUEST, ISSUE], includeUserRepositories: false) {
      totalCount
    }
    contributionsCollection {
      totalPullRequestContributions
      totalIssueContributions
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}
"""


def fetch():
    token = os.environ.get("STATS_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        sys.exit("STATS_TOKEN or GITHUB_TOKEN is required")
    body = json.dumps({"query": QUERY, "variables": {"login": LOGIN}}).encode()
    request = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = json.load(response)
    if "errors" in payload:
        sys.exit(json.dumps(payload["errors"], indent=2))
    return payload["data"]["user"]


def streaks(days):
    counts = {date.fromisoformat(day["date"]): day["contributionCount"] for day in days}
    longest = run = 0
    for day in sorted(counts):
        run = run + 1 if counts[day] else 0
        longest = max(longest, run)
    current = 0
    day = max(counts)
    if counts[day] == 0:
        day -= timedelta(days=1)
    while day in counts and counts[day]:
        current += 1
        day -= timedelta(days=1)
    return current, longest


def languages(repos):
    sizes = {}
    for repo in repos:
        for edge in repo["languages"]["edges"]:
            sizes[edge["node"]["name"]] = sizes.get(edge["node"]["name"], 0) + edge["size"]
    total = sum(sizes.values()) or 1
    top = sorted(sizes.items(), key=lambda item: -item[1])[:5]
    return [(name, size / total) for name, size in top]


def compact(number):
    return f"{number / 1000:.1f}k" if number >= 10_000 else f"{number:,}"


def card(figures, langs, colors):
    bg, border, ink, muted, accent, track = colors
    width, height = 1200, 236
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="GitHub stats">',
        f'<rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="14" fill="{bg}" stroke="{border}"/>',
    ]
    sans = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif"
    serif = "Georgia, 'Times New Roman', serif"
    columns = (64, 384, 604, 804, 1004)
    for x, (label, value) in zip(columns, figures):
        parts.append(f'<text x="{x:.0f}" y="96" font-family="{serif}" font-size="44" font-weight="700" fill="{ink}">{value}</text>')
        parts.append(f'<text x="{x:.0f}" y="126" font-family="{sans}" font-size="14" letter-spacing="1.2" fill="{muted}">{label.upper()}</text>')
    parts.append(f'<rect x="64" y="160" width="{width - 128}" height="6" rx="3" fill="{track}"/>')
    x = 64.0
    for name, share in langs:
        w = (width - 128) * share
        parts.append(f'<rect x="{x:.1f}" y="160" width="{max(w - 2, 0):.1f}" height="6" rx="3" fill="{accent}" opacity="{1 - 0.15 * langs.index((name, share)):.2f}"/>')
        x += w
    for index, (name, share) in enumerate(langs):
        parts.append(f'<text x="{64 + index * 176}" y="196" font-family="{sans}" font-size="14" fill="{muted}">{name} {share * 100:.0f}%</text>')
    parts.append("</svg>\n")
    return "\n".join(parts)


def main():
    user = fetch()
    collection = user["contributionsCollection"]
    days = [day for week in collection["contributionCalendar"]["weeks"] for day in week["contributionDays"]]
    current, longest = streaks(days)
    stars = sum(repo["stargazerCount"] for repo in user["repositories"]["nodes"])
    figures = [
        ("Contributions, past year", compact(collection["contributionCalendar"]["totalContributions"])),
        ("Pull requests", compact(collection["totalPullRequestContributions"])),
        ("Stars earned", compact(stars)),
        ("Followers", compact(user["followers"]["totalCount"])),
        ("Longest streak", f"{longest}d"),
    ]
    langs = languages(user["repositories"]["nodes"])
    root = Path(__file__).resolve().parents[1] / "assets"
    root.mkdir(exist_ok=True)
    (root / "stats-light.svg").write_text(card(figures, langs, ("#f7f7f5", "#dde1e2", "#293e49", "#606f77", "#003b73", "#e5e7e9")))
    (root / "stats-dark.svg").write_text(card(figures, langs, ("#161b22", "#30363d", "#e6edf3", "#9aa4ae", "#79a8ff", "#2b3138")))
    print(", ".join(f"{label}: {value}" for label, value in figures), "| current streak", current)


if __name__ == "__main__":
    main()
