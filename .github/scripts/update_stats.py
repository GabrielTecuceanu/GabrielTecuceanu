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
    createdAt
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
      contributionCalendar {
        weeks {
          contributionDays {
            contributionCount
            date
          }
        }
      }
    }
    pullRequests(states: MERGED) { totalCount }
    issues { totalCount }
  }
}
"""

YEAR_QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      totalCommitContributions
      restrictedContributionsCount
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


def fetch_total_commits(login, created_at):
    joined_year = int(created_at[:4])
    current_year = datetime.date.today().year
    total = 0
    for year in range(joined_year, current_year + 1):
        data = graphql(YEAR_QUERY, {
            "login": login,
            "from": f"{year}-01-01T00:00:00Z",
            "to":   f"{year}-12-31T23:59:59Z",
        })
        c = data["data"]["user"]["contributionsCollection"]
        total += c["totalCommitContributions"] + c["restrictedContributionsCount"]
    return total


def calculate_streaks(weeks):
    days = []
    for week in weeks:
        for day in week["contributionDays"]:
            days.append((day["date"], day["contributionCount"]))
    days.sort(key=lambda x: x[0], reverse=True)

    today = datetime.date.today().isoformat()

    if days and days[0][1] == 0 and days[0][0] == today:
        days = days[1:]

    current = 0
    for _, count in days:
        if count > 0:
            current += 1
        else:
            break

    max_streak = 0
    running = 0
    for _, count in days:
        if count > 0:
            running += 1
            max_streak = max(max_streak, running)
        else:
            running = 0

    return current, max_streak


def calculate_rank(stars, commits, prs, issues, followers):
    # Based on github-readme-stats methodology:
    # normalize each metric via CDF, compute weighted percentile
    MEDIANS = {
        "commits":   250,
        "prs":        50,
        "issues":     25,
        "stars":      50,
        "followers":  10,
    }
    WEIGHTS = {
        "commits":   2,
        "prs":       3,
        "issues":    1,
        "stars":     4,
        "followers": 1,
    }
    TOTAL_WEIGHT = sum(WEIGHTS.values())

    def exp_cdf(x):
        return 1 - 2 ** (-x)

    def log_cdf(x):
        return x / (1 + x)

    metrics = {
        "commits":   (commits,   exp_cdf),
        "prs":       (prs,       exp_cdf),
        "issues":    (issues,    exp_cdf),
        "stars":     (stars,     log_cdf),
        "followers": (followers, log_cdf),
    }

    weighted_sum = sum(
        WEIGHTS[k] * cdf(value / MEDIANS[k])
        for k, (value, cdf) in metrics.items()
    )

    percentile = (1 - weighted_sum / TOTAL_WEIGHT) * 100

    thresholds = [
        (1,    "S"),
        (12.5, "A+"),
        (25,   "A"),
        (37.5, "A-"),
        (50,   "B+"),
        (62.5, "B"),
        (75,   "B-"),
        (87.5, "C+"),
    ]

    for cutoff, grade in thresholds:
        if percentile <= cutoff:
            return grade

    return "C"


def top_languages(repos, top_n=6):
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
    commits_this_year = (
        user["contributionsCollection"]["totalCommitContributions"]
        + user["contributionsCollection"]["restrictedContributionsCount"]
    )
    commits_total = fetch_total_commits(USERNAME, user["createdAt"])
    prs = user["pullRequests"]["totalCount"]
    issues = user["issues"]["totalCount"]
    followers = user["followers"]["totalCount"]
    streak, max_streak = calculate_streaks(
        user["contributionsCollection"]["contributionCalendar"]["weeks"]
    )
    rank = calculate_rank(stars, commits_this_year, prs, issues, followers)
    langs = top_languages(user["repositories"]["nodes"])

    lang_lines = ""
    for name, pct in langs:
        lang_lines += f"  {name:<12} {bar(pct)}  {pct}%\n"

    terminal = (
        "```bash\n"
        "gabriel@github:~$ cat flower.txt\n"
        "\n"
        "                .--.\n"
        "              .'_\\/_'.\n"
        "              '. /\\ .'\n"
        '                "||"\n'
        "                 || /\\\n"
        "              /\\ ||//\\)\n"
        "             (/\\\\||/\n"
        "          ______\\||/_______\n"
        "\n"
        "gabriel@github:~$ cat about.txt\n"
        "\n"
        "  Hello, I am Gabi.\n"
        "\n"
        "  I like neovim and low-level programming.\n"
        "\n"
        "  Currently Reading:     Gödel, Escher, Bach: An Eternal Golden Braid\n"
        "  Currently Working on:  tsman, a rust-based tmux session manager\n"
        "\n"
        "gabriel@github:~$ cat stats.txt\n"
        "\n"
        f"  Stars       {bar(min(stars/200*100,100))}  {stars}\n"
        f"  Commits     {bar(min(commits_total/2000*100,100))}  {commits_total}  (total) / {commits_this_year}  (this year)\n"
        f"  PRs         {bar(min(prs/100*100,100))}  {prs}\n"
        f"  Issues      {bar(min(issues/50*100,100))}  {issues}\n"
        f"  Followers   {bar(min(followers/50*100,100))}  {followers}\n"
        f"  Rank        {rank}\n"
        "\n"
        f"  Streak      {bar(min(streak/30*100,100))}  {streak} days\n"
        f"  Max Streak  {bar(min(max_streak/30*100,100))}  {max_streak} days\n"
        "\n"
        "gabriel@github:~$ cat languages.txt\n"
        "\n"
        + lang_lines
        + "gabriel@github:~$ systemctl sleep\n"
        "```"
    )
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
