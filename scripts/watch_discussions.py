"""Weekly Galaxy-Brain radar: fresh unanswered Q&A in Arda's domains.

Scans Textualize/textual, flet-dev/flet, thonny/thonny (all Tkinter/desktop
adjacent) for Q&A discussions from the last LOOKBACK_DAYS with no chosen
answer and <3 comments. New hits -> one GitHub issue in this repo (Arda gets
notified); seen URLs are stored in data/watch_state.json.
Usage: python scripts/watch_discussions.py [--dry-run]
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone

BASE = os.path.join(os.path.dirname(__file__), "..")
STATE = os.path.join(BASE, "data", "watch_state.json")
LOOKBACK_DAYS = 10
REPOS = [("Textualize", "textual"), ("flet-dev", "flet"), ("thonny", "thonny")]

QUERY = """query($owner: String!, $name: String!) {
  repository(owner: $owner, name: $name) {
    discussions(first: 30, orderBy: {field: UPDATED_AT, direction: DESC}) {
      nodes { title url number createdAt answerChosenAt
        category { name } comments { totalCount } author { login } }
    }
  }
}"""


def gh_api(payload: dict) -> dict:
    p = subprocess.run(["gh", "api", "graphql", "--input", "-"],
                       input=json.dumps(payload), capture_output=True, text=True)
    p.check_returncode()
    return json.loads(p.stdout)


def main() -> None:
    dry = "--dry-run" in sys.argv
    cutoff = datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)
    state = json.load(open(STATE, encoding="utf-8")) if os.path.exists(STATE) else {"seen": []}
    seen = set(state["seen"])
    fresh = []
    for owner, name in REPOS:
        try:
            nodes = gh_api({"query": QUERY, "variables": {"owner": owner, "name": name}}
                           )["data"]["repository"]["discussions"]["nodes"]
        except Exception as e:
            print(f"WARN {owner}/{name}: {e}")
            continue
        for n in nodes:
            cat = (n["category"] or {}).get("name", "")
            if "Q" not in cat and "uestion" not in cat and "Help" not in cat:
                continue
            if n.get("answerChosenAt"):
                continue
            if datetime.fromisoformat(n["createdAt"].replace("Z", "+00:00")) < cutoff:
                continue
            if n["comments"]["totalCount"] >= 3:
                continue
            if n["url"] in seen:
                continue
            fresh.append((owner, name, n))
    if not fresh:
        print("No fresh candidates.")
        return
    lines = ["Haftanin cevaplanabilir tartismalari (Galaxy Brain radari):", ""]
    for owner, name, n in fresh:
        lines.append(f"- [{n['title']}]({n['url']}) — `{owner}/{name}`, "
                     f"{n['comments']['totalCount']} yorum, {n['createdAt'][:10]}")
        seen.add(n["url"])
    body = "\n".join(lines)
    print(body)
    state["seen"] = sorted(seen)[-200:]
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    json.dump(state, open(STATE, "w", encoding="utf-8"), indent=2)
    if not dry:
        subprocess.run(["gh", "issue", "create", "--title",
                        "🎯 Cevaplanabilir tartışmalar (haftalık radar)",
                        "--body", body], check=True, cwd=BASE)
        subprocess.run(["git", "add", "data/watch_state.json"], check=True, cwd=BASE)
        subprocess.run(["git", "-c", "user.name=radar-bot",
                        "-c", "user.email=radar@local",
                        "commit", "-m", "chore: radar state [skip ci]"],
                       check=True, cwd=BASE)
        subprocess.run(["git", "push"], check=True, cwd=BASE)
        print("Issue opened + state pushed.")


if __name__ == "__main__":
    main()
