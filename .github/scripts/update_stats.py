import os
import re
import math
import datetime
import urllib.request
import urllib.error
import json

GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
USERNAME = "GabrielTecuceanu"

QUERY = """
query($login: String!) {
  user(login: $login) {
    followers { totalCount }
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false) {
      nodes {
        stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges {
            size
            node { name }
          }
        }
      }
    }
    contributionsCollection {
      totalCommitContributions
      totalPullRequestContributions
      totalIssueContributions
      restrictedContributionsCount
    }
    pullRequests(states: MERGED) { totalCount }
    issues { totalCount }
    contributionsCollection {
      contributionCalendar {
        weeks {
          contributionDays {
            contributionCount
            date
          }
        }
      }
    }
  }
}
"""


def graphql(query, variables):
    payload = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=payload,
        headers={
            "Authorization": f"bearer {GITHUB_TOKEN}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def calculate_streak(weeks):
    days = []
    for week in weeks:
        for day in week["contributionDays"]:
            days.append((day["date"], day["contributionCount"]))
    days.sort(key=lambda x: x[0], reverse=True)

    today = datetime.date.today().isoformat()
    yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()

    # Start counting only if contributed today or yesterday
    if days and days[0][1] == 0 and days[0][0] == today:
        days = days[1:]

    streak = 0
    for date, count in days:
        if count > 0:
            streak += 1
        else:
            break
    return streak


def calculate_rank(stars, commits, prs, issues, followers):
    weights = {
        "stars": 4,
        "commits": 2,
        "prs": 3,
        "issues": 1,
        "followers": 1,
    }

    score = (
        stars * weights["stars"]
        + commits * weights["commits"]
        + prs * weights["prs"]
        + issues * weights["issues"]
        + followers * weights["followers"]
    )

    thresholds = [
        (800,  "S"),
        (600,  "A+"),
        (400,  "A"),
        (250,  "B+"),
        (150,  "B"),
        (50,   "C+"),
    ]

    for threshold, rank in thresholds:
        if score >= threshold:
            return rank

    return "C"


def top_languages(repos, top_n=5):
    lang_bytes = {}
    for repo in repos:
        for edge in repo["languages"]["edges"]:
            name = edge["node"]["name"]
            size = edge["size"]
            lang_bytes[name] = lang_bytes.get(name, 0) + size

    total = sum(lang_bytes.values()) or 1
    sorted_langs = sorted(lang_bytes.items(), key=lambda x: x[1], reverse=True)[:top_n]
    return [(name, round(size / total * 100, 1)) for name, size in sorted_langs]


def bar(pct, width=10):
    filled = round(pct / 100 * width)
    return "█" * filled + "░" * (width - filled)


def build_terminal(data):
    user = data["data"]["user"]

    stars = sum(r["stargazerCount"] for r in user["repositories"]["nodes"])
    commits = (
        user["contributionsCollection"]["totalCommitContributions"]
        + user["contributionsCollection"]["restrictedContributionsCount"]
    )
    prs = user["pullRequests"]["totalCount"]
    issues = user["issues"]["totalCount"]
    followers = user["followers"]["totalCount"]
    streak = calculate_streak(
        user["contributionsCollection"]["contributionCalendar"]["weeks"]
    )
    rank = calculate_rank(stars, commits, prs, issues, followers)
    langs = top_languages(user["repositories"]["nodes"])

    lang_lines = ""
    for name, pct in langs:
        lang_lines += f"  {name:<12} {bar(pct)}  {pct}%\n"

    terminal = f"""\
```bash
gabriel@github:~$ cat flower.txt

                .--.
              .'_\\/_'.
              '. /\\ .'
                "||"
                 || /\\
              /\\ ||//\\)
             (/\\\\||/
          ______\\||/_______

gabriel@github:~$ cat about.txt

  Hello, I am Gabi.

  I like neovim and low-level programming.

  Currently Reading:     Gödel, Escher, Bach: An Eternal Golden Braid
  CUrrently Working on:  tsman - a rust-based tmux session manager

gabriel@github:~$ cat stats.txt

  Stars       {bar(min(stars/200*100,100))}  {stars}
  Commits     {bar(min(commits/500*100,100))}  {commits}  (this year)
  PRs         {bar(min(prs/100*100,100))}  {prs}
  Issues      {bar(min(issues/50*100,100))}  {issues}
  Followers   {bar(min(followers/50*100,100))}  {followers}
  Streak      {bar(min(streak/30*100,100))}  {streak} days
  Rank        {rank}

gabriel@github:~$ cat languages.txt

{lang_lines}
gabriel@github:~$ \
```"""
    return terminal


def update_readme(terminal_block):
    with open("README.md", "r") as f:
        content = f.read()

    pattern = r"<!-- TERMINAL_START -->.*?<!-- TERMINAL_END -->"
    if not re.search(pattern, content, flags=re.DOTALL):
        raise RuntimeError("Markers <!-- TERMINAL_START --> / <!-- TERMINAL_END --> not found in README.md")

    replacement = f"<!-- TERMINAL_START -->\n{terminal_block}\n<!-- TERMINAL_END -->"
    new_content = re.sub(pattern, replacement, content, flags=re.DOTALL)

    with open("README.md", "w") as f:
        f.write(new_content)


if __name__ == "__main__":
    data = graphql(QUERY, {"login": USERNAME})
    terminal = build_terminal(data)
    update_readme(terminal)
    print("README updated.")
