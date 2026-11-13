#!/usr/bin/env python3
"""Update public repositories, animated activity cards, and snake blocks in README.md."""

from __future__ import annotations

import html
import json
import os
import pathlib
import re
import urllib.request

REPOS_START = "<!-- REPOS:START -->"
REPOS_END = "<!-- REPOS:END -->"
ACTIVITY_START = "<!-- ACTIVITY:START -->"
ACTIVITY_END = "<!-- ACTIVITY:END -->"
SNAKE_START = "<!-- SNAKE:START -->"
SNAKE_END = "<!-- SNAKE:END -->"
MAX_REPOS = 6

LANG_COLORS = {
    "Python": "#3572A5",
    "Go": "#00ADD8",
    "TypeScript": "#3178c6",
    "JavaScript": "#f1e05a",
    "Kotlin": "#A97BFF",
    "Dockerfile": "#384d54",
    "Shell": "#89e051",
    "HTML": "#e34c26",
    "CSS": "#563d7c",
    "HCL": "#844FBA",
    "Rust": "#dea584",
    "Java": "#b07219",
    "C": "#555555",
    "C++": "#f34b7d",
}

ACTIVITY_THEMES = {
    "light": {
        "card_bg": "#ffffff",
        "card_border": "#d0d7de",
        "panel_bg": "#f6f8fa",
        "grid_line": "#d8dee4",
        "title": "#1f2328",
        "text": "#24292f",
        "muted": "#656d76",
        "pill_bg": "#eff6ff",
        "pill_border": "#bfdbfe",
        "pill_text": "#1d4ed8",
        "accent": "#0969da",
        "accent_soft": "#0ea5e9",
        "live": "#1a7f37",
        "bar_bg": "#eaeef2",
        "shimmer": "#ffffff",
    },
    "dark": {
        "card_bg": "#0d1117",
        "card_border": "#30363d",
        "panel_bg": "#161b22",
        "grid_line": "#21262d",
        "title": "#f0f6fc",
        "text": "#c9d1d9",
        "muted": "#8b949e",
        "pill_bg": "#111c2d",
        "pill_border": "#1f3a5f",
        "pill_text": "#79c0ff",
        "accent": "#38bdf8",
        "accent_soft": "#22d3ee",
        "live": "#3fb950",
        "bar_bg": "#21262d",
        "shimmer": "#ffffff",
    },
}

SNAKE_THEMES = {
    "light": {
        "bg": "#ffffff",
        "border": "#d0d7de",
        "label": "#656d76",
        "levels": ["#ebedf0", "#9be9a8", "#40c463", "#30a14e", "#216e39"],
        "snake": ["#6d28d9", "#7c3aed", "#8b5cf6", "#a78bfa"],
        "bar_bg": "#eaeef2",
        "bar_fill": "#40c463",
    },
    "dark": {
        "bg": "#0d1117",
        "border": "#30363d",
        "label": "#8b949e",
        "levels": ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"],
        "snake": ["#9333ea", "#a855f7", "#c084fc", "#d8b4fe"],
        "bar_bg": "#21262d",
        "bar_fill": "#39d353",
    },
}


def request_text(url: str, token: str | None = None, payload: dict | None = None) -> str:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "sijogom-profile-readme-updater",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read().decode("utf-8", errors="replace")


def request_json(url: str, token: str | None = None, payload: dict | None = None) -> dict | list:
    return json.loads(request_text(url, token=token, payload=payload))


def map_graphql_level(level_name: str) -> int:
    mapping = {
        "NONE": 0,
        "FIRST_QUARTILE": 1,
        "SECOND_QUARTILE": 2,
        "THIRD_QUARTILE": 3,
        "FOURTH_QUARTILE": 4,
    }
    return mapping.get(level_name, 0)


def fetch_via_graphql(owner: str, token: str) -> dict:
    query = """
    query($owner: String!) {
      user(login: $owner) {
        createdAt
        contributionsCollection {
          contributionCalendar {
            totalContributions
            weeks {
              contributionDays {
                date
                contributionCount
                contributionLevel
              }
            }
          }
        }
        pinnedItems(first: 6, types: REPOSITORY) {
          nodes {
            ... on Repository {
              name
              description
              url
              isPrivate
              pushedAt
              stargazerCount
              primaryLanguage { name color }
            }
          }
        }
        repositories(first: 20, ownerAffiliations: OWNER, privacy: PUBLIC, orderBy: {field: PUSHED_AT, direction: DESC}) {
          nodes {
            name
            description
            url
            isPrivate
            isFork
            pushedAt
            stargazerCount
            primaryLanguage { name color }
            languages(first: 8, orderBy: {field: SIZE, direction: DESC}) {
              edges {
                size
                node { name color }
              }
            }
            defaultBranchRef {
              target {
                ... on Commit {
                  history(first: 4) {
                    nodes {
                      messageHeadline
                      committedDate
                      author { name }
                    }
                  }
                }
              }
            }
          }
        }
      }
    }
    """
    resp = request_json(
        "https://api.github.com/graphql",
        token=token,
        payload={"query": query, "variables": {"owner": owner}},
    )
    if not isinstance(resp, dict) or "errors" in resp:
        raise RuntimeError(f"GraphQL error: {resp}")

    user = (resp.get("data") or {}).get("user") or {}
    pinned = (user.get("pinnedItems") or {}).get("nodes") or []
    recent = (user.get("repositories") or {}).get("nodes") or []

    ordered: list[dict] = []
    seen: set[str] = set()
    for repo in [*pinned, *recent]:
        if not repo or repo.get("isPrivate"):
            continue
        name = repo["name"]
        if name.lower() == owner.lower() or name in seen:
            continue
        seen.add(name)
        lang_obj = repo.get("primaryLanguage")
        ordered.append(
            {
                "name": name,
                "url": repo["url"],
                "description": repo.get("description") or "",
                "language": lang_obj.get("name") if isinstance(lang_obj, dict) else "",
                "pushed_at": (repo.get("pushedAt") or "")[:10],
                "stars": repo.get("stargazerCount") or 0,
            }
        )

    lang_bytes: dict[str, tuple[int, str]] = {}
    commits: list[dict] = []
    for repo in recent:
        if not repo or repo.get("isPrivate") or repo.get("isFork"):
            continue
        name = repo["name"]
        if name.lower() == owner.lower():
            continue
        for edge in (repo.get("languages") or {}).get("edges") or []:
            node = edge.get("node") or {}
            lname = node.get("name")
            if not lname:
                continue
            prev_sz, prev_col = lang_bytes.get(lname, (0, node.get("color") or LANG_COLORS.get(lname, "#6e7681")))
            lang_bytes[lname] = (prev_sz + int(edge.get("size") or 0), prev_col)

        history_nodes = (((repo.get("defaultBranchRef") or {}).get("target") or {}).get("history") or {}).get("nodes") or []
        for c in history_nodes:
            author_name = ((c.get("author") or {}).get("name") or "").lower()
            if "github-actions" in author_name:
                continue
            msg = (c.get("messageHeadline") or "").strip()
            cdate = (c.get("committedDate") or "")[:10]
            if msg and cdate:
                commits.append({"repo": name, "message": msg, "date": cdate})

    commits.sort(key=lambda item: item["date"], reverse=True)

    cal = (user.get("contributionsCollection") or {}).get("contributionCalendar") or {}
    weeks: list[list[tuple[str, int, int]]] = []
    for w in cal.get("weeks") or []:
        week_days = []
        for d in w.get("contributionDays") or []:
            week_days.append(
                (
                    d.get("date") or "",
                    map_graphql_level(d.get("contributionLevel") or "NONE"),
                    int(d.get("contributionCount") or 0),
                )
            )
        if week_days:
            weeks.append(week_days)

    return {
        "owner": owner,
        "created_year": (user.get("createdAt") or "")[:4] or "2021",
        "repos": ordered[:MAX_REPOS],
        "public_project_count": len(ordered),
        "languages": normalize_languages(lang_bytes),
        "recent_commits": commits[:3],
        "calendar_weeks": weeks,
        "total_contributions": int(cal.get("totalContributions") or 0),
    }


def scrape_public_calendar(owner: str) -> tuple[list[list[tuple[str, int, int]]], int]:
    try:
        page = request_text(f"https://github.com/users/{owner}/contributions")
    except Exception:
        return [], 0

    tooltips = dict(re.findall(r'for="(contribution-day-component-[^"]+)"[^>]*>([^<]+)<', page))
    days_by_week: dict[int, list[tuple[str, int, int]]] = {}
    total = 0

    for m in re.finditer(r"<td\b([^>]*)>", page):
        attrs = m.group(1)
        if "ContributionCalendar-day" not in attrs:
            continue
        d_m = re.search(r'data-date="([^"]+)"', attrs)
        l_m = re.search(r'data-level="([^"]+)"', attrs)
        ix_m = re.search(r'data-ix="([^"]+)"', attrs)
        id_m = re.search(r'id="([^"]+)"', attrs)
        if not (d_m and l_m and ix_m):
            continue
        date_str = d_m.group(1)
        level = int(l_m.group(1))
        week_ix = int(ix_m.group(1))
        tip = tooltips.get(id_m.group(1), "") if id_m else ""
        cnt_m = re.search(r"^(\d+)\s+contribution", tip.strip())
        count = int(cnt_m.group(1)) if cnt_m else (level if level > 0 else 0)
        total += count
        days_by_week.setdefault(week_ix, []).append((date_str, level, count))

    weeks = []
    for ix in sorted(days_by_week):
        week = sorted(days_by_week[ix], key=lambda item: item[0])
        weeks.append(week)
    return weeks, total


def fetch_via_rest(owner: str, token: str | None) -> dict:
    user = request_json(f"https://api.github.com/users/{owner}", token=token)
    repos = request_json(
        f"https://api.github.com/users/{owner}/repos?type=owner&sort=pushed&per_page=30",
        token=token,
    )
    if not isinstance(repos, list):
        repos = []

    ordered: list[dict] = []
    lang_bytes: dict[str, tuple[int, str]] = {}
    commits: list[dict] = []

    for repo in repos:
        if repo.get("private"):
            continue
        name = repo["name"]
        if name.lower() == owner.lower():
            continue
        ordered.append(
            {
                "name": name,
                "url": repo["html_url"],
                "description": repo.get("description") or "",
                "language": repo.get("language") or "",
                "pushed_at": (repo.get("pushed_at") or "")[:10],
                "stars": repo.get("stargazers_count") or 0,
            }
        )

        if not repo.get("fork") and len(ordered) <= 6:
            try:
                langs = request_json(f"https://api.github.com/repos/{owner}/{name}/languages", token=token)
                if isinstance(langs, dict):
                    for lname, sz in langs.items():
                        prev_sz, prev_col = lang_bytes.get(
                            lname,
                            (0, LANG_COLORS.get(lname, "#6e7681")),
                        )
                        lang_bytes[lname] = (prev_sz + int(sz), prev_col)
            except Exception:
                pass

            try:
                repo_commits = request_json(
                    f"https://api.github.com/repos/{owner}/{name}/commits?per_page=3",
                    token=token,
                )
                if isinstance(repo_commits, list):
                    for c in repo_commits:
                        commit_obj = c.get("commit") or {}
                        author_name = ((commit_obj.get("author") or {}).get("name") or "").lower()
                        if "github-actions" in author_name:
                            continue
                        msg = (commit_obj.get("message") or "").splitlines()[0].strip()
                        cdate = ((commit_obj.get("committer") or {}).get("date") or "")[:10]
                        if msg and cdate:
                            commits.append({"repo": name, "message": msg, "date": cdate})
            except Exception:
                pass

    commits.sort(key=lambda item: item["date"], reverse=True)
    weeks, total = scrape_public_calendar(owner)

    return {
        "owner": owner,
        "created_year": (user.get("created_at") if isinstance(user, dict) else "")[:4] or "2021",
        "repos": ordered[:MAX_REPOS],
        "public_project_count": len(ordered),
        "languages": normalize_languages(lang_bytes),
        "recent_commits": commits[:3],
        "calendar_weeks": weeks,
        "total_contributions": total,
    }


def normalize_languages(lang_bytes: dict[str, tuple[int, str]]) -> list[dict]:
    total = sum(sz for sz, _ in lang_bytes.values())
    if total <= 0:
        return []
    items = sorted(
        ((name, sz, color) for name, (sz, color) in lang_bytes.items() if sz > 0),
        key=lambda item: item[1],
        reverse=True,
    )[:5]
    return [
        {
            "name": name,
            "color": color,
            "pct": round((sz / total) * 100.0, 1),
            "bytes": sz,
        }
        for name, sz, color in items
    ]


def get_profile_data(owner: str, token: str | None) -> dict:
    if token:
        try:
            return fetch_via_graphql(owner, token)
        except Exception as exc:
            print(f"GraphQL fallback to REST: {exc}")
    return fetch_via_rest(owner, token)


def truncate_text(text: str, limit: int) -> str:
    clean = " ".join(text.split())
    if len(clean) <= limit:
        return clean
    return clean[: max(0, limit - 3)].rstrip() + "..."


def build_smooth_path(points: list[tuple[float, float]]) -> str:
    if not points:
        return ""
    if len(points) == 1:
        x, y = points[0]
        return f"M {x:.1f} {y:.1f}"
    parts = [f"M {points[0][0]:.1f} {points[0][1]:.1f}"]
    for idx in range(len(points) - 1):
        x0, y0 = points[idx]
        x1, y1 = points[idx + 1]
        cx = (x0 + x1) / 2.0
        parts.append(f"C {cx:.1f} {y0:.1f}, {cx:.1f} {y1:.1f}, {x1:.1f} {y1:.1f}")
    return " ".join(parts)


def render_activity_svg(theme_name: str, data: dict) -> str:
    t = ACTIVITY_THEMES[theme_name]
    weeks = data.get("calendar_weeks") or []
    recent_weeks = weeks[-16:] if weeks else []
    weekly_counts = [sum(day[2] for day in week) for week in recent_weeks]
    if not weekly_counts:
        weekly_counts = [0] * 16

    chart_x, chart_y, chart_w, chart_h = 26.0, 58.0, 380.0, 94.0
    max_val = max(max(weekly_counts), 1)
    n_pts = len(weekly_counts)
    points: list[tuple[float, float]] = []
    for idx, val in enumerate(weekly_counts):
        px = chart_x + (idx / max(n_pts - 1, 1)) * chart_w
        ratio = val / max_val
        py = chart_y + chart_h - (ratio * (chart_h - 14.0)) - 6.0
        points.append((px, py))

    line_d = build_smooth_path(points)
    area_d = f"{line_d} L {points[-1][0]:.1f} {chart_y + chart_h:.1f} L {points[0][0]:.1f} {chart_y + chart_h:.1f} Z"

    last_push = "-"
    if data.get("repos"):
        last_push = data["repos"][0].get("pushed_at") or "-"

    active_dots = []
    for (px, py), cnt in zip(points, weekly_counts):
        if cnt > 0:
            active_dots.append(
                f'    <circle cx="{px:.1f}" cy="{py:.1f}" r="3.5" fill="{t["card_bg"]}" stroke="{t["accent"]}" stroke-width="2"/>'
            )

    last_px, last_py = points[-1]
    langs = data.get("languages") or []
    bar_x, bar_y, bar_w, bar_h = 468.0, 58.0, 392.0, 10.0

    bar_segments = []
    legend_items = []
    cursor_x = bar_x
    for idx, lang in enumerate(langs[:4]):
        pct = float(lang["pct"])
        seg_w = (bar_w * pct / 100.0) if idx < len(langs[:4]) - 1 else max(0.0, (bar_x + bar_w) - cursor_x)
        if seg_w > 0:
            bar_segments.append(
                f'      <rect x="{cursor_x:.1f}" y="{bar_y:.1f}" width="{seg_w:.1f}" height="{bar_h:.1f}" fill="{html.escape(lang["color"])}"/>'
            )
            cursor_x += seg_w
        lx = 468.0 + (idx % 2) * 196.0
        ly = 84.0 if idx < 2 else 101.0
        legend_items.append(
            f'  <circle cx="{lx + 4:.1f}" cy="{ly - 4:.1f}" r="4" fill="{html.escape(lang["color"])}"/>\n'
            f'  <text x="{lx + 14:.1f}" y="{ly:.1f}" fill="{t["text"]}" font-size="11.5" font-weight="600">{html.escape(lang["name"])} <tspan fill="{t["muted"]}" font-weight="400">{pct:.1f}%</tspan></text>'
        )

    if not bar_segments:
        bar_segments.append(
            f'      <rect x="{bar_x:.1f}" y="{bar_y:.1f}" width="{bar_w:.1f}" height="{bar_h:.1f}" fill="{t["bar_bg"]}"/>'
        )
        legend_items.append(
            f'  <text x="468" y="86" fill="{t["muted"]}" font-size="11.5">No language data yet</text>'
        )

    commit_rows = []
    commits = data.get("recent_commits") or []
    for idx, c in enumerate(commits[:3]):
        cy = 136.0 + idx * 24.0
        repo_short = truncate_text(c["repo"], 22)
        msg_budget = max(14, 46 - len(repo_short))
        msg_short = truncate_text(c["message"], msg_budget)
        cdate = html.escape(c["date"])
        commit_rows.append(
            f'  <circle cx="473" cy="{cy - 4:.1f}" r="3" fill="{t["live"]}"/>\n'
            f'  <text x="484" y="{cy:.1f}" fill="{t["text"]}" font-size="11.5" font-weight="600">{html.escape(repo_short)} <tspan fill="{t["muted"]}" font-weight="400">· {html.escape(msg_short)}</tspan></text>\n'
            f'  <text x="860" y="{cy:.1f}" text-anchor="end" fill="{t["muted"]}" font-family="\'Cascadia Mono\', Consolas, monospace" font-size="11">{cdate}</text>'
        )
    if not commit_rows:
        commit_rows.append(
            f'  <text x="468" y="142" fill="{t["muted"]}" font-size="11.5">No recent public commits</text>'
        )

    grad_id = f"actFill-{theme_name}"
    path_id = f"actLine-{theme_name}"
    clip_bar_id = f"langBarClip-{theme_name}"
    shimmer_id = f"barShimmer-{theme_name}"

    return "\n".join(
        [
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 880 214" width="880" height="214" role="img" aria-label="GitHub Activity Overview" font-family="\'Segoe UI\', \'Malgun Gothic\', \'Apple SD Gothic Neo\', sans-serif">',
            "  <defs>",
            f'    <linearGradient id="{grad_id}" x1="0%" y1="0%" x2="0%" y2="100%">',
            f'      <stop offset="0%" stop-color="{t["accent"]}" stop-opacity="0.24"/>',
            f'      <stop offset="100%" stop-color="{t["accent"]}" stop-opacity="0.02"/>',
            "    </linearGradient>",
            f'    <linearGradient id="{shimmer_id}" x1="-100%" y1="0%" x2="0%" y2="0%">',
            f'      <stop offset="0%" stop-color="{t["shimmer"]}" stop-opacity="0"/>',
            f'      <stop offset="50%" stop-color="{t["shimmer"]}" stop-opacity="0.32"/>',
            f'      <stop offset="100%" stop-color="{t["shimmer"]}" stop-opacity="0"/>',
            f'      <animate attributeName="x1" values="-100%;150%" dur="3.8s" repeatCount="indefinite"/>',
            f'      <animate attributeName="x2" values="0%;250%" dur="3.8s" repeatCount="indefinite"/>',
            "    </linearGradient>",
            f'    <clipPath id="{clip_bar_id}">',
            f'      <rect x="{bar_x:.1f}" y="{bar_y:.1f}" width="{bar_w:.1f}" height="{bar_h:.1f}" rx="5"/>',
            "    </clipPath>",
            "  </defs>",
            "",
            "  <!-- Left Card: Weekly Activity -->",
            f'  <rect x="0.5" y="0.5" width="431" height="213" rx="12" fill="{t["card_bg"]}" stroke="{t["card_border"]}"/>',
            f'  <circle cx="26" cy="29" r="4" fill="{t["live"]}"/>',
            f'  <circle cx="26" cy="29" r="4" fill="{t["live"]}" opacity="0.5">',
            '    <animate attributeName="r" values="4;10;4" dur="2.6s" repeatCount="indefinite"/>',
            '    <animate attributeName="opacity" values="0.55;0;0.55" dur="2.6s" repeatCount="indefinite"/>',
            "  </circle>",
            f'  <text x="38" y="34" fill="{t["title"]}" font-size="14" font-weight="700">Activity</text>',
            f'  <text x="410" y="34" text-anchor="end" fill="{t["muted"]}" font-size="11.5">Last 16 weeks</text>',
            "",
            f'  <rect x="20" y="50" width="392" height="110" rx="8" fill="{t["panel_bg"]}"/>',
            f'  <line x1="26" y1="84" x2="406" y2="84" stroke="{t["grid_line"]}" stroke-dasharray="3 3"/>',
            f'  <line x1="26" y1="118" x2="406" y2="118" stroke="{t["grid_line"]}" stroke-dasharray="3 3"/>',
            f'  <line x1="26" y1="152" x2="406" y2="152" stroke="{t["grid_line"]}"/>',
            f'  <path d="{area_d}" fill="url(#{grad_id})"/>',
            f'  <path id="{path_id}" d="{line_d}" fill="none" stroke="{t["accent"]}" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>',
            *active_dots,
            f'  <circle cx="{last_px:.1f}" cy="{last_py:.1f}" r="4.5" fill="{t["live"]}"/>',
            f'  <circle r="4" fill="{t["accent_soft"]}" opacity="0.9">',
            '    <animateMotion dur="5.5s" repeatCount="indefinite">',
            f'      <mpath href="#{path_id}"/>',
            "    </animateMotion>",
            "  </circle>",
            "",
            f'  <rect x="20" y="172" width="191" height="24" rx="6" fill="{t["pill_bg"]}" stroke="{t["pill_border"]}"/>',
            f'  <text x="115.5" y="188" text-anchor="middle" fill="{t["pill_text"]}" font-size="11.5" font-weight="600">Public Repos: {data["public_project_count"]}</text>',
            f'  <rect x="221" y="172" width="191" height="24" rx="6" fill="{t["pill_bg"]}" stroke="{t["pill_border"]}"/>',
            f'  <text x="316.5" y="188" text-anchor="middle" fill="{t["pill_text"]}" font-size="11.5" font-weight="600">Last Push: {html.escape(last_push)}</text>',
            "",
            "  <!-- Right Card: Languages & Recent Commits -->",
            f'  <rect x="448.5" y="0.5" width="431" height="213" rx="12" fill="{t["card_bg"]}" stroke="{t["card_border"]}"/>',
            f'  <text x="468" y="34" fill="{t["title"]}" font-size="14" font-weight="700">Languages &amp; Recent Commits</text>',
            f'  <text x="860" y="34" text-anchor="end" fill="{t["muted"]}" font-size="11.5">Public Repos</text>',
            f'  <g clip-path="url(#{clip_bar_id})">',
            f'    <rect x="{bar_x:.1f}" y="{bar_y:.1f}" width="{bar_w:.1f}" height="{bar_h:.1f}" fill="{t["bar_bg"]}"/>',
            *bar_segments,
            f'    <rect x="{bar_x:.1f}" y="{bar_y:.1f}" width="{bar_w:.1f}" height="{bar_h:.1f}" fill="url(#{shimmer_id})"/>',
            "  </g>",
            *legend_items,
            f'  <line x1="468" y1="114" x2="860" y2="114" stroke="{t["grid_line"]}"/>',
            *commit_rows,
            "</svg>",
        ]
    )


def build_snake_waypoints() -> list[tuple[int, int]]:
    """Return a single-cell-step closed loop across 53x7 cells so snake segments stay contiguous."""
    corners = [
        (14, 3),
        (20, 3),
        (20, 5),
        (28, 5),
        (28, 2),
        (36, 2),
        (36, 4),
        (44, 4),
        (44, 1),
        (49, 1),
        (49, 3),
        (52, 3),
        (52, 6),
        (10, 6),
        (10, 3),
    ]
    path: list[tuple[int, int]] = []
    for idx in range(len(corners)):
        x0, y0 = corners[idx]
        x1, y1 = corners[(idx + 1) % len(corners)]
        cx, cy = x0, y0
        while (cx, cy) != (x1, y1):
            path.append((cx, cy))
            if cx < x1:
                cx += 1
            elif cx > x1:
                cx -= 1
            elif cy < y1:
                cy += 1
            elif cy > y1:
                cy -= 1
    return path


def render_snake_svg(theme_name: str, weeks: list[list[tuple[str, int, int]]]) -> str:
    """Render an initial animated contribution snake SVG until Platane/snk updates it in Actions."""
    t = SNAKE_THEMES[theme_name]
    cols = 53
    rows = 7
    cell = 12
    gap = 4
    step = cell + gap
    origin_x = 18
    origin_y = 18

    grid_levels = [[0] * rows for _ in range(cols)]
    offset = max(0, cols - len(weeks))
    for c_idx, week in enumerate(weeks[-cols:]):
        target_col = offset + c_idx
        for r_idx, day in enumerate(week[:rows]):
            grid_levels[target_col][r_idx] = min(4, max(0, int(day[1])))

    cells_svg = []
    for c in range(cols):
        for r in range(rows):
            lvl = grid_levels[c][r]
            color = t["levels"][lvl]
            x = origin_x + c * step
            y = origin_y + r * step
            cells_svg.append(
                f'  <rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2.5" fill="{color}"/>'
            )

    cycle = build_snake_waypoints()
    n_cycle = len(cycle)
    segments_svg = []
    css_keyframes = []
    for seg_idx, seg_color in enumerate(t["snake"]):
        cls = f"snk-{theme_name}-{seg_idx}"
        kf_name = f"snkMove-{theme_name}-{seg_idx}"
        frames = []
        for idx in range(n_cycle + 1):
            pct = (idx / n_cycle) * 100.0
            wp_c, wp_r = cycle[(idx - seg_idx) % n_cycle]
            tx = origin_x + wp_c * step
            ty = origin_y + wp_r * step
            frames.append(f"      {pct:.2f}% {{ transform: translate({tx}px, {ty}px); }}")
        css_keyframes.append(f"    @keyframes {kf_name} {{\n" + "\n".join(frames) + "\n    }")
        css_keyframes.append(f"    .{cls} {{ animation: {kf_name} 16s linear infinite; }}")
        seg_size = cell if seg_idx == 0 else cell - 1
        pad = 0 if seg_idx == 0 else 0.5
        rx = 3.5 if seg_idx == 0 else 2.8
        segments_svg.append(
            f'  <g class="{cls}">\n'
            f'    <rect x="{pad}" y="{pad}" width="{seg_size}" height="{seg_size}" rx="{rx}" fill="{seg_color}"/>\n'
            f"  </g>"
        )

    bar_w = cols * step - gap
    return "\n".join(
        [
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 880 164" width="880" height="164" role="img" aria-label="Contribution Snake Animation">',
            "  <style>",
            *css_keyframes,
            "  </style>",
            f'  <rect x="0.5" y="0.5" width="879" height="163" rx="12" fill="{t["bg"]}" stroke="{t["border"]}"/>',
            *cells_svg,
            *segments_svg,
            f'  <rect x="{origin_x}" y="142" width="{bar_w}" height="6" rx="3" fill="{t["bar_bg"]}"/>',
            f'  <rect x="{origin_x}" y="142" width="160" height="6" rx="3" fill="{t["bar_fill"]}">',
            f'    <animate attributeName="width" values="160;{bar_w};160" dur="16s" repeatCount="indefinite"/>',
            "  </rect>",
            "</svg>",
        ]
    )


def render_repos_table(repos: list[dict]) -> str:
    if not repos:
        return "공개된 저장소가 아직 없습니다."

    rows = []
    for r in repos:
        name = html.escape(r["name"])
        url = html.escape(r["url"], quote=True)
        desc = html.escape(r["description"].strip()) if r["description"].strip() else "-"
        lang = f"<code>{html.escape(r['language'])}</code>" if r["language"] else "-"
        updated_text = html.escape(r["pushed_at"][:7]).replace("-", "&#8209;") if r["pushed_at"] else ""
        updated = f"<code>{updated_text}</code>" if updated_text else "-"
        rows.append(
            "    <tr>\n"
            f'      <td><a href="{url}"><strong>{name}</strong></a></td>\n'
            f"      <td>{desc}</td>\n"
            f'      <td align="center">{lang}</td>\n'
            f'      <td align="center">{updated}</td>\n'
            "    </tr>"
        )

    return (
        "<table>\n"
        "  <thead>\n"
        "    <tr>\n"
        '      <th width="240">Repository</th>\n'
        '      <th width="410">Description</th>\n'
        '      <th width="120">Language</th>\n'
        '      <th width="110">Updated</th>\n'
        "    </tr>\n"
        "  </thead>\n"
        "  <tbody>\n"
        + "\n".join(rows)
        + "\n  </tbody>\n"
        "</table>"
    )


def render_picture_block(light_path: str, dark_path: str, alt: str) -> str:
    return (
        '<p align="center">\n'
        "  <picture>\n"
        f'    <source media="(prefers-color-scheme: dark)" srcset="{dark_path}" />\n'
        f'    <source media="(prefers-color-scheme: light)" srcset="{light_path}" />\n'
        f'    <img src="{light_path}" alt="{alt}" width="100%" />\n'
        "  </picture>\n"
        "</p>"
    )


def replace_block(content: str, start: str, end: str, body: str) -> str:
    pattern = re.compile(rf"{re.escape(start)}.*?{re.escape(end)}", flags=re.DOTALL)
    if not pattern.search(content):
        raise SystemExit(f"Markers {start} / {end} not found")
    replacement = f"{start}\n{body}\n{end}" if body else f"{start}\n{end}"
    return pattern.sub(lambda _: replacement, content, count=1)


def write_if_changed(path: pathlib.Path, text: str) -> bool:
    if path.is_file() and path.read_text(encoding="utf-8") == text:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return True


def main() -> int:
    owner = os.environ.get("GITHUB_REPOSITORY_OWNER") or "sijogom"
    token = os.environ.get("GITHUB_TOKEN") or None
    root_dir = pathlib.Path(__file__).resolve().parents[2]
    assets_dir = root_dir / "assets"
    readme_path = root_dir / "README.md"
    content = readme_path.read_text(encoding="utf-8")

    data = get_profile_data(owner, token)

    for theme_name in ("light", "dark"):
        write_if_changed(assets_dir / f"activity-{theme_name}.svg", render_activity_svg(theme_name, data))

    snake_light = assets_dir / "snake-light.svg"
    snake_dark = assets_dir / "snake-dark.svg"
    # Seed initial snake SVGs when Platane/snk hasn't generated them yet (e.g. local run).
    if not (snake_light.is_file() and snake_dark.is_file()):
        for theme_name in ("light", "dark"):
            write_if_changed(
                assets_dir / f"snake-{theme_name}.svg",
                render_snake_svg(theme_name, data.get("calendar_weeks") or []),
            )

    new_content = replace_block(content, REPOS_START, REPOS_END, render_repos_table(data["repos"]))
    if ACTIVITY_START in new_content and ACTIVITY_END in new_content:
        new_content = replace_block(
            new_content,
            ACTIVITY_START,
            ACTIVITY_END,
            render_picture_block("./assets/activity-light.svg", "./assets/activity-dark.svg", "GitHub Activity Overview"),
        )
    if SNAKE_START in new_content and SNAKE_END in new_content and snake_light.is_file() and snake_dark.is_file():
        new_content = replace_block(
            new_content,
            SNAKE_START,
            SNAKE_END,
            render_picture_block("./assets/snake-light.svg", "./assets/snake-dark.svg", "Contribution Snake Animation"),
        )

    if new_content != content:
        readme_path.write_text(new_content, encoding="utf-8")
        print(f"Updated {readme_path} and activity SVGs ({len(data['repos'])} public repositories).")
    else:
        print(f"README already up to date ({len(data['repos'])} public repositories).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
