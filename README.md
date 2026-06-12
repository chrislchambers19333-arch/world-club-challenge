# World Club of Challenge — Deployment Guide

Three files, one cron job, zero maintenance.

## Files

- `index.html` — the app. Self-contained; reads scores from `results.json` at load time (cache-busted).
- `results.json` — the live scores data. This is the only file that ever changes.
- `update_results.py` — daily updater: pulls World Cup results, rewrites `results.json`, commits, pushes.

## One-time setup (~30 min)

### 1. GitHub Pages

```bash
# new public repo, e.g. world-club-challenge
git init && git add index.html results.json update_results.py
git commit -m "World Club of Challenge 2026"
git branch -M main
git remote add origin git@github.com:YOURUSER/world-club-challenge.git
git push -u origin main
```

Repo → Settings → Pages → Source: `main` branch, root folder.
Family link: `https://YOURUSER.github.io/world-club-challenge/`

### 2. API key (free)

Register at <https://www.football-data.org/client/register> — the free tier
includes the FIFA World Cup (competition code `WC`). Copy your token.

### 3. Test the updater on the Mac Mini

```bash
cd ~/path/to/world-club-challenge
FOOTBALL_DATA_TOKEN="your-token" python3 update_results.py
```

You should see match counts, then either “No new results” or a commit+push.
Reload the family link — the “Results updated” badge should reflect it.

### 4. Schedule it (cron, runs 7am + 11pm ET daily)

```bash
crontab -e
```

```
0 7,23 * * * cd /Users/spockjenkins/world-club-challenge && FOOTBALL_DATA_TOKEN="your-token" /usr/bin/python3 update_results.py >> update.log 2>&1
```

(Use launchd if you prefer; cron is fine for this.) Requires the Mini’s git
to have push access to the repo (SSH key or gh auth).

## How scoring is computed

Group: win 3 / draw 1. Advance to R32: +4 (inferred when a team appears in
any knockout match). Knockout wins: R32 5, R16 7, QF 10, SF 14, 3rd-place 7,
Final 20. Underdog Booster applied client-side: Pot 4 ×1.5, Pot 5 ×2, ceil.

## Manual override

If the API ever lags or misnames a team (warnings appear in update.log),
edit `results.json` by hand and push. Schema per team — include only true/nonzero fields:

```json
"Brazil": { "w": 2, "d": 1, "adv": true, "r32": true }
```

## Agent alternative

If you’d rather skip the API key, point Spock at this on a daily schedule:
“Fetch yesterday’s World Cup results, update results.json in
~/world-club-challenge following the schema in README.md, commit and push.”
The deterministic script is more reliable; the agent is a fine backup.