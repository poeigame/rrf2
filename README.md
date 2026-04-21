# Python RRF Backend

Backend service for parsing `.rrf` replay files and returning structured JSON.

## Run

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

## API

`POST /parse`

- multipart form field: `file` (`.rrf`)
- query params:
  - `mode`: `decoded` or `raw` (default `decoded`)
  - `include_events`: `true` or `false` (default `true`)
  - `include_aggregates`: `true` or `false` (default `true`)

Aggregates include skill metrics such as:

- per-skill `dps`
- per-skill `uses_per_second`
- per-skill `hits_per_second`
- per-skill `skill_name`
- global `overall_skill_dps`
- global `overall_skill_uses_per_second`
- global `overall_skill_hits_per_second`

You can provide optional skill names by creating `python_backend/data/skill_names.json`:

```json
{
  "100": "Bash",
  "429": "Teleport"
}
```

If no mapping is provided, fallback names are returned like `skill_100`.

You can auto-sync names from Divine Pride API into `data/skill_names.json`:

```bash
python tools/sync_skill_names.py --api-key "YOUR_API_KEY" --skills 1 2 3 4
```

Or from a parser result JSON:

```bash
python tools/sync_skill_names.py --api-key "YOUR_API_KEY" --report-json result.json
```

Tip: set env var so parser can auto-fetch missing names during runtime:

```bash
set DIVINE_PRIDE_API_KEY=YOUR_API_KEY
```

Example:

```bash
curl -X POST "http://localhost:8000/parse?mode=decoded&include_events=true&include_aggregates=true" \
  -F "file=@sample.rrf"
```

`POST /summary/skills`

- multipart form field: `file` (`.rrf`)
- query params:
  - `top_n`: max skill rows to return (default `20`, range `1..200`)

This endpoint is optimized for skill summary only (`skill_name`, `dps`, `uses_per_second`, damage, counts).
It also returns `player_mapping` (player name and GID map) and hit-rate metrics.
It also returns `skill_by_player` to split skill metrics per `player_aid` / `player_name`.

Example:

```bash
curl -X POST "http://localhost:8000/summary/skills?top_n=30" \
  -F "file=@sample.rrf"
```

`POST /skills/sync`

- body JSON:
  - `skill_ids`: array of integers
  - `api_key`: Divine Pride API key (optional if env `DIVINE_PRIDE_API_KEY` is set)

Example:

```bash
curl -X POST "http://localhost:8000/skills/sync" \
  -H "Content-Type: application/json" \
  -d "{\"skill_ids\":[1,2,5],\"api_key\":\"YOUR_API_KEY\"}"
```

## Web UI

Open:

```text
http://localhost:8000/
```

Upload `.rrf` and it will show overall DPS/uses/hits per second and a per-skill summary table.
It also shows:

- top skill charts (DPS and hits/sec)
- players mapping table (player name -> GID)

UI also has **Sync Missing Skill Names** button that calls `/skills/sync` using current parsed skill IDs.

Notes:

- player name decode prefers UTF-8 (for Thai text)
- player lists in UI/summary are filtered to `player_aid` in `100xxx`

## Parity Harness

Generate a parser fingerprint from a folder of replay files:

```bash
python tools/parity_harness.py path/to/replays --output parity_fingerprint.json
```

Compare against an existing baseline:

```bash
python tools/parity_harness.py path/to/replays --baseline baseline.json --output current.json
```
"# rrf_calculator" 
