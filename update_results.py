#!/usr/bin/env python3
"""
World Club of Challenge — automated results updater.

Pulls FIFA World Cup 2026 results from football-data.org (free tier),
recomputes every team's record, writes results.json, and commits/pushes
if anything changed. Designed to run on a daily cron/launchd schedule.

Setup:
  1. Get a free API key at https://www.football-data.org/client/register
  2. export FOOTBALL_DATA_TOKEN="your-key"   (or put it in the cron line)
  3. Run from inside the git repo:  python3 update_results.py

Exit codes: 0 = success (changed or unchanged), 1 = error.
"""

import json
import os
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone

API_URL = "https://api.football-data.org/v4/competitions/WC/matches"
RESULTS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results.json")

# Map football-data.org team names -> names used in index.html
NAME_MAP = {
    "Côte d'Ivoire": "Ivory Coast", "Ivory Coast": "Ivory Coast",
    "Korea Republic": "South Korea", "South Korea": "South Korea",
    "Czech Republic": "Czechia", "Czechia": "Czechia",
    "Turkey": "Türkiye", "Türkiye": "Türkiye",
    "Bosnia and Herzegovina": "Bosnia & Herzegovina",
    "Bosnia-Herzegovina": "Bosnia & Herzegovina",
    "Congo DR": "DR Congo", "DR Congo": "DR Congo",
    "Democratic Republic of the Congo": "DR Congo",
    "Cabo Verde": "Cape Verde", "Cape Verde Islands": "Cape Verde", "Cape Verde": "Cape Verde",
    "United States": "USA", "USA": "USA",
    "Iran": "Iran", "IR Iran": "Iran",
    "Curacao": "Curaçao", "Curaçao": "Curaçao",
    "Saudi Arabia": "Saudi Arabia",
    "New Zealand": "New Zealand",
}

# All 48 pool teams (canonical names from index.html)
POOL_TEAMS = {
    "Portugal","Norway","Türkiye","Ivory Coast","Jordan","France","Colombia","Egypt",
    "Saudi Arabia","Ghana","Spain","Japan","Canada","Paraguay","Curaçao","England",
    "Mexico","Austria","Iraq","Haiti","Brazil","USA","Panama","Uzbekistan","New Zealand",
    "Germany","Uruguay","Algeria","Qatar","Argentina","Morocco","Iran","Tunisia",
    "Bosnia & Herzegovina","Netherlands","Switzerland","Scotland","DR Congo","South Africa",
    "Belgium","Senegal","Australia","Czechia","Cape Verde","Croatia","Ecuador",
    "South Korea","Sweden",
}

def canon(name: str) -> str:
    return NAME_MAP.get(name, name)

def stage_key(stage: str):
    """Map API stage string to our scoring keys."""
    s = (stage or "").upper()
    if "GROUP" in s:
        return "group"
    if "32" in s:
        return "r32"
    if "16" in s:
        return "r16"
    if "QUARTER" in s:
        return "qf"
    if "SEMI" in s:
        return "sf"
    if "THIRD" in s:
        return "third"
    if "FINAL" in s:  # checked after SEMI/QUARTER so plain FINAL remains
        return "champ"
    return None

def fetch_matches(token: str):
    req = urllib.request.Request(API_URL, headers={"X-Auth-Token": token})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8")).get("matches", [])

def build_results(matches):
    results = {}

    def team_rec(name):
        if name not in results:
            results[name] = {"w": 0, "d": 0, "adv": False, "r32": False, "r16": False,
                             "qf": False, "sf": False, "third": False, "champ": False}
        return results[name]

    for m in matches:
        if m.get("status") != "FINISHED":
            continue
        stage = stage_key(m.get("stage", ""))
        if stage is None:
            continue

        home = canon((m.get("homeTeam") or {}).get("name", ""))
        away = canon((m.get("awayTeam") or {}).get("name", ""))
        if home not in POOL_TEAMS or away not in POOL_TEAMS:
            # Unrecognized name — log it so the mapping can be fixed
            print(f"  WARNING: unmapped team(s): '{home}' vs '{away}'", file=sys.stderr)

        winner_side = (m.get("score") or {}).get("winner")  # HOME_TEAM / AWAY_TEAM / DRAW
        winner = home if winner_side == "HOME_TEAM" else away if winner_side == "AWAY_TEAM" else None

        if stage == "group":
            if winner is None:
                team_rec(home)["d"] += 1
                team_rec(away)["d"] += 1
            else:
                team_rec(winner)["w"] += 1
        else:
            # Any team appearing in a knockout match has advanced past groups
            team_rec(home)["adv"] = True
            team_rec(away)["adv"] = True
            if winner:
                team_rec(winner)[stage] = True

    # Strip teams with zero activity to keep the JSON tidy
    cleaned = {}
    for team, r in results.items():
        if r["w"] or r["d"] or r["adv"]:
            cleaned[team] = {k: v for k, v in r.items() if v}
    return cleaned

def git(*args):
    return subprocess.run(["git", *args], cwd=os.path.dirname(RESULTS_FILE),
                          capture_output=True, text=True)

def main():
    token = os.environ.get("FOOTBALL_DATA_TOKEN", "").strip()
    if not token:
        print("ERROR: set FOOTBALL_DATA_TOKEN env var (free key: football-data.org)", file=sys.stderr)
        return 1

    print(f"[{datetime.now(timezone.utc).isoformat()}] Fetching World Cup results...")
    try:
        matches = fetch_matches(token)
    except Exception as e:
        print(f"ERROR: API fetch failed: {e}", file=sys.stderr)
        return 1

    finished = [m for m in matches if m.get("status") == "FINISHED"]
    print(f"  {len(matches)} matches in competition, {len(finished)} finished.")

    new_results = build_results(matches)
    stamp = datetime.now().strftime("%B %-d, %Y")
    payload = {
        "lastUpdated": f"{stamp} \u00b7 {len(finished)} matches played",
        "results": new_results,
    }

    # Compare against current file (ignoring the timestamp) to avoid empty commits
    try:
        with open(RESULTS_FILE, "r", encoding="utf-8") as f:
            old = json.load(f).get("results", {})
    except Exception:
        old = None

    if old == new_results:
        print("  No new results. Nothing to do.")
        return 0

    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"  Wrote {RESULTS_FILE}")

    # Commit & push
    git("add", "results.json")
    c = git("commit", "-m", f"Update standings: {len(finished)} matches played")
    if c.returncode != 0:
        print(f"  git commit: {c.stdout}{c.stderr}".strip())
        return 0
    p = git("push")
    if p.returncode != 0:
        print(f"ERROR: git push failed: {p.stderr}", file=sys.stderr)
        return 1
    print("  Pushed. Standings are live.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
