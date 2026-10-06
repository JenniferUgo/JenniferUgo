#!/usr/bin/env python3
"""Build privacy-preserving GitHub profile SVGs using only Python's standard library.

Requires GH_PUBLIC_TOKEN (the profile repo's built-in GITHUB_TOKEN) and
GH_PRIVATE_READ_TOKEN (a read-only fine-grained PAT for selected JunnDigital repos).
Never publishes repository names, URLs, code, secrets, or API responses.
"""
import collections
import datetime as dt
import html
import json
import os
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request

USERNAME = "JenniferUgo"
PRIVATE_OWNER = "junndigital"
OUTPUT_DIR = Path("assets/profile-stats")
README_PATH = Path("README.md")
START_MARKER = "<!-- profile-stats:start -->"
END_MARKER = "<!-- profile-stats:end -->"
COLORS = {"bg": "#0b2432", "panel": "#123748", "text": "#f0f7fa",
          "muted": "#c5d4dc", "accent": "#c7e160", "track": "#315160"}

def api_request(url, token, data=None):
    headers = {"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json",
               "User-Agent": "JenniferUgo-profile-stats/1.0",
               "X-GitHub-Api-Version": "2022-11-28"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    body = json.dumps(data).encode("utf-8") if data is not None else None
    request = urllib.request.Request(url, data=body, headers=headers, method="POST" if body else "GET")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except (urllib.error.HTTPError, urllib.error.URLError, ValueError) as exc:
        # Private repo URLs and API responses must not appear in public Actions logs.
        raise RuntimeError("GitHub API request failed. Check the read-only token, selected repository access and API availability.") from None

def get_pages(endpoint, token):
    records = []
    for page in range(1, 11):
        separator = "&" if "?" in endpoint else "?"
        data = api_request(endpoint + separator + "per_page=100&page=" + str(page), token)
        if not isinstance(data, list):
            raise RuntimeError("GitHub repository listing returned an unexpected format.")
        records.extend(data)
        if len(data) < 100:
            return records
    raise RuntimeError("Repository listing exceeded the safe pagination limit.")

def contributions(token):
    now = dt.datetime.now(dt.timezone.utc)
    since = now - dt.timedelta(days=365)
    query = """
    query ProfileActivity($login: String!, $from: DateTime!, $to: DateTime!) {
      user(login: $login) {
        contributionsCollection(from: $from, to: $to) {
          restrictedContributionsCount
          contributionCalendar { totalContributions }
        }
      }
    }"""
    payload = {"query": query, "variables": {"login": USERNAME, "from": since.isoformat(),
                                               "to": now.isoformat()}}
    result = api_request("https://api.github.com/graphql", token, payload)
    if result.get("errors"):
        raise RuntimeError("GitHub GraphQL contribution query failed.")
    collection = ((result.get("data") or {}).get("user") or {}).get("contributionsCollection")
    if not collection:
        raise RuntimeError("GitHub contribution collection unavailable.")
    total = int(collection["contributionCalendar"]["totalContributions"])
    restricted = int(collection["restrictedContributionsCount"])
    if total < 0 or restricted < 0:
        raise RuntimeError("GitHub returned invalid contribution totals.")
    return total, restricted, since, now

def eligible_repositories(public_token, private_token):
    public = get_pages("https://api.github.com/users/" + USERNAME + "/repos?type=owner", public_token)
    private = get_pages(
        "https://api.github.com/user/repos?affiliation=owner,collaborator,organization_member&visibility=private",
        private_token,
    )
    public = [r for r in public if not r.get("private") and not r.get("fork") and not r.get("archived")
              and (r.get("owner") or {}).get("login", "").lower() == USERNAME.lower()]
    private = [r for r in private if r.get("private") and not r.get("fork") and not r.get("archived")
               and (r.get("owner") or {}).get("login", "").lower() == PRIVATE_OWNER]
    if not private:
        raise RuntimeError("No private JunnDigital repositories are visible to the read-only token. Nothing published.")
    return [(r["full_name"], public_token) for r in public] + [
        (r["full_name"], private_token) for r in private
    ], len(private)

def language_footprint(repositories):
    totals = collections.Counter()
    for full_name, token in repositories:
        owner, repo = full_name.split("/", 1)
        url = ("https://api.github.com/repos/" + urllib.parse.quote(owner, safe="")
               + "/" + urllib.parse.quote(repo, safe="") + "/languages")
        languages = api_request(url, token)
        if not isinstance(languages, dict):
            raise RuntimeError("Unexpected languages response; nothing published.")
        for language, count in languages.items():
            if isinstance(count, int) and count > 0:
                totals[language] += count
    if not totals:
        raise RuntimeError("No languages returned from accessible repositories; nothing published.")
    return totals

def esc(value):
    return html.escape(str(value), quote=True)

def heading(title, subtitle):
    c = COLORS
    return (f'<rect width="800" height="100%" rx="18" fill="{c["bg"]}"/>'
            f'<text x="32" y="49" font-size="24" font-weight="700" fill="{c["text"]}">{esc(title)}</text>'
            f'<text x="32" y="74" font-size="14" fill="{c["muted"]}">{esc(subtitle)}</text>')

def svg_activity(total, restricted, private_repos, total_repos, now):
    c = COLORS
    pieces = [f'<svg xmlns="http://www.w3.org/2000/svg" width="800" height="220" viewBox="0 0 800 220">',
              heading("GitHub Activity", "Rolling 12 months • GitHub contribution calendar")]
    values = [("Contributions", f"{total:,}"),
              ("Private / restricted", f"{restricted:,}"),
              ("Repositories analysed", str(total_repos))]
    for i, (label, value) in enumerate(values):
        x = 32 + i * 252
        pieces.extend([
            f'<rect x="{x}" y="99" width="236" height="81" rx="10" fill="{c["panel"]}"/>',
            f'<text x="{x + 16}" y="133" font-size="25" font-weight="700" fill="{c["accent"]}">{esc(value)}</text>',
            f'<text x="{x + 16}" y="158" font-size="13" fill="{c["text"]}">{esc(label)}</text>'])
    pieces.append(f'<text x="32" y="205" font-size="12" fill="{c["muted"]}">'
                  f'Private contributions are anonymized. {private_repos} private repositories in language analysis. '
                  f'Updated {now:%Y-%m-%d}.</text></svg>')
    return "".join(pieces)

def svg_languages(languages, repo_count):
    c = COLORS
    entries = languages.most_common(7)
    grand = sum(languages.values())
    height = 148 + len(entries) * 44
    pieces = [f'<svg xmlns="http://www.w3.org/2000/svg" width="800" height="{height}" viewBox="0 0 800 {height}">',
              heading("Repository Languages", f"Code footprint across {repo_count} accessible repositories")]
    for i, (lang, count) in enumerate(entries):
        y = 112 + i * 44
        fraction = count / grand
        pieces += [
            f'<text x="32" y="{y}" font-size="14" fill="{c["text"]}">{esc(lang)}</text>',
            f'<rect x="195" y="{y - 14}" width="485" height="13" rx="6" fill="{c["track"]}"/>',
            f'<rect x="195" y="{y - 14}" width="{round(485 * fraction, 1)}" height="13" rx="6" fill="{c["accent"]}"/>',
            f'<text x="698" y="{y - 1}" font-size="13" fill="{c["text"]}">{fraction * 100:.1f}%</text>']
    pieces += [f'<text x="32" y="{height - 21}" font-size="12" fill="{c["muted"]}">'
               'Language bytes across repositories; not personally authored code.</text></svg>']
    return "".join(pieces)

def update_readme():
    current = README_PATH.read_text(encoding="utf-8")
    block = (START_MARKER + '\n'
             '<p>\n'
             '  <img src="./assets/profile-stats/activity.svg" alt="GitHub contributions including anonymized private activity" width="800" />\n'
             '</p>\n'
             '<p>\n'
             '  <img src="./assets/profile-stats/languages.svg" alt="Programming language footprint across accessible public and private repositories" width="800" />\n'
             '</p>\n'
             + END_MARKER)
    if START_MARKER in current and END_MARKER in current:
        start = current.index(START_MARKER)
        end = current.index(END_MARKER, start) + len(END_MARKER)
        revised = current[:start] + block + current[end:]
    elif START_MARKER not in current and END_MARKER not in current:
        revised = current.rstrip() + "\n\n" + block + "\n"
    else:
        raise RuntimeError("README markers are inconsistent; refusing to edit.")
    if revised != current:
        README_PATH.write_text(revised, encoding="utf-8")

def main():
    public_token = os.environ.get("GH_PUBLIC_TOKEN", "")
    private_token = os.environ.get("GH_PRIVATE_READ_TOKEN", "")
    if not public_token or not private_token:
        raise RuntimeError("Missing GitHub credentials; no statistics generated.")
    total, restricted, _since, now = contributions(public_token)
    repos, private_count = eligible_repositories(public_token, private_token)
    langs = language_footprint(repos)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "activity.svg").write_text(svg_activity(total, restricted, private_count, len(repos), now), encoding="utf-8")
    (OUTPUT_DIR / "languages.svg").write_text(svg_languages(langs, len(repos)), encoding="utf-8")
    update_readme()
    print("Profile cards refreshed. No private repository identifiers or source code were published.")

if __name__ == "__main__":
    main()
