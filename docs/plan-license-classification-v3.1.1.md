# Plan: Fix license classification (v3.1.1)

**For:** opus 4.6 medium · **Repo:** `hvtracker` (`main`) · **Core file:** `fetch_and_build.py`

## Problem (confirmed by live probing 2026-05-31)

`license_type` on hvtracker.net collapsed to `open:141 / unlicensed:30 / proprietary:1 / source-available:0`.
Mislabeled (all have reachable LICENSE files): Claude Code, n8n, Vercel AI SDK, Dify, Open WebUI → all `unlicensed`.

Root cause is **not** the network (raw LICENSE fetches return 200). Three compounding logic bugs:

1. **Sticky short-circuit** — `normalize_license_type()` (line 339-344): `return row.get("license_type") or classify_license(...)`. `"unlicensed"` is truthy → row is never reclassified. Bad values are permanent.
2. **7-day cache** — `@cache.cached("license_type", ttl=604800)` pins early wrong results in Redis.
3. **No deterministic override + weak markers** — even when it runs, Claude Code's `LICENSE.md` matches no `_PROPRIETARY_MARKERS` → would fall through to `"open"`. Content-marker guessing can't reliably catch known proprietary/source-available tools.

## Success criteria

- Claude Code → `proprietary`; n8n, Dify → `source-available`; Vercel AI SDK, Open WebUI → `open`.
- Fresh full build: `source-available > 0` and `proprietary > 1`.
- No agent with a reachable, recognizable LICENSE labeled `unlicensed`.
- Guard rail: top 5 leaderboard stays open-source verified tools.

---

## Step 1 — Audit ALL 30 `unlicensed` agents (decided: full audit)

Pull the current unlicensed list:
```bash
curl -s https://hvtracker.net/data/latest.json | python3 -c "
import sys,json
for a in json.load(sys.stdin)['agents']:
    if a.get('license_type')=='unlicensed': print(a['name'], a.get('repo',''))
"
```
For each, check the real license (GitHub API spdx + raw LICENSE file) and decide the correct bucket: `open` / `source-available` / `proprietary` / genuinely `unlicensed`. Add a `"license_override"` key in `agents.json` for every one the heuristic can't get right on its own. Known so far:

| Agent (repo) | override |
|---|---|
| Claude Code (`anthropics/claude-code`) | `proprietary` |
| n8n (`n8n-io/n8n`) | `source-available` |
| Dify (`langgenius/dify`) | `source-available` |

**Verify:** `python3 -c "import json;print({a['name']:a['license_override'] for a in json.load(open('agents.json')) if a.get('license_override')})"`

## Step 2 — Make override authoritative in the build path

`fetch_and_build.py` ~line 1576-1577, change:
```python
"license_type": classify_license(repo_id, (repo.get("license") or {}).get("spdx_id")),
```
to:
```python
"license_type": agent_cfg.get("license_override") or classify_license(repo_id, (repo.get("license") or {}).get("spdx_id")),
```
(Confirm the actual variable name holding the per-agent config dict at that scope.)

## Step 3 — Fix sticky short-circuit (line 339-344)

```python
def normalize_license_type(row: dict) -> str:
    if row.get("license_override"):
        return row["license_override"]
    spdx_id = row.get("license_spdx")
    if spdx_id and spdx_id != "NOASSERTION":
        return "open"
    current = row.get("license_type")
    if current and current != "unlicensed":
        return current            # trust a real prior classification
    return classify_license(row.get("repo", ""), spdx_id)
```
Makes `unlicensed` self-healing without re-fetching already-classified rows.
Also ensure `license_override` is persisted onto the row wherever rows are assembled (so it survives into `normalize_license_type`).

## Step 4 — Strengthen `classify_license` fall-through (line 311-336)

- Track whether any LICENSE filename returned 200. File found but unmatched → `"open"`. **Every** filename failed → `"unlicensed"` only as last resort (don't let a transient failure brand a project).
- Add to `_SOURCE_AVAILABLE_MARKERS`: `"sustainable use license"`, `"fair-code"`, `"fair source"`.
- Do NOT broaden `_PROPRIETARY_MARKERS` for Claude Code — the override handles it.

## Step 5 — Bust the stale cache (decided: bump key)

Rename the cache key:
```python
@cache.cached("license_type_v2", ttl=604800)
```
Invalidates all old entries cleanly; no Redis access needed.

## Step 6 — Verify locally

```bash
./dev.sh --rebuild
python3 -c "
import json; d=json.load(open('data.json'))   # confirm which file holds rows
ags={a['name']:a.get('license_type') for a in d['agents']}
for n in ['Claude Code','n8n','Dify','Vercel AI SDK','Open WebUI']: print(n, ags.get(n))
"
```
Overrides (Steps 1-3) flip on a `--rebuild`. Heuristic improvements (Step 4) for non-override agents only fully apply on the next **full** cron run.

## Step 7 — Guard rail + deploy

- Re-check leaderboard top 5 stays open verified; Claude Code must not jump into the top tier from relabeling.
- Single commit: `fix: license classification v3.1.1 — overrides, self-healing normalize, cache bust`. Push `main`; Railway deploys.
- After first full Railway cron run, re-run the live distribution check; confirm `source-available > 0` and Claude Code = `proprietary`.

## Out of scope (do not touch)

- Codex's v2 UI layer (`template.html`, `agent.html.j2` cosmetics).
- Trust-score weights, grade bands, adoption logic.
- GitHub PR automation (stays frozen).
