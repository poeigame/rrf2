from __future__ import annotations

import os

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import HTMLResponse

from app.parser_service import safe_parse_rrf_bytes
from app.schemas import ParseResponse, SkillSummaryResponse, SkillSyncRequest, SkillSyncResponse
from app.skill_names import update_skill_names


MAX_UPLOAD_BYTES = 50 * 1024 * 1024


app = FastAPI(
    title="RRF Parser Backend",
    version="0.1.0",
    description="Parse Ragnarok .rrf replay files into structured JSON.",
)


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>RRF Skill Summary</title>
  <style>
    :root { color-scheme: light; }
    body { font-family: Segoe UI, Arial, sans-serif; margin: 24px; background: #f6f8fb; color: #17212f; }
    .card { background: #fff; border: 1px solid #d8e0ea; border-radius: 10px; padding: 16px; margin-bottom: 16px; }
    .row { display: flex; gap: 12px; flex-wrap: wrap; align-items: center; }
    input[type=file], input[type=number], input[type=text], button { padding: 8px; }
    button { border: 1px solid #2f6fed; background: #2f6fed; color: #fff; border-radius: 8px; cursor: pointer; }
    button:disabled { opacity: 0.6; cursor: not-allowed; }
    table { width: 100%; border-collapse: collapse; font-size: 14px; }
    th, td { padding: 8px; border-bottom: 1px solid #e5ebf2; text-align: left; }
    th { background: #f0f4fa; }
    .kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; }
    .kpi { background: #f9fbfe; border: 1px solid #dce6f3; border-radius: 8px; padding: 10px; }
    .label { font-size: 12px; color: #557; }
    .value { font-size: 20px; font-weight: 700; }
    .chart-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 14px; }
    .chart-box { border: 1px solid #dce6f3; border-radius: 8px; padding: 10px; background: #f9fbfe; }
    .bars { display: grid; gap: 8px; }
    .bar-row { display: grid; grid-template-columns: 120px 1fr 64px; gap: 8px; align-items: center; }
    .bar-label { font-size: 12px; color: #334; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .bar-track { height: 12px; border-radius: 8px; background: #e5edf7; overflow: hidden; }
    .bar-fill { height: 100%; background: linear-gradient(90deg, #2f6fed, #47a3ff); }
    .bar-val { font-size: 12px; color: #334; text-align: right; }
    #status { margin-top: 8px; color: #445; }
    #error { color: #c43232; white-space: pre-wrap; }
  </style>
</head>
<body>
  <div class="card">
    <h2>RRF Skill Summary</h2>
    <div class="row">
      <input id="file" type="file" accept=".rrf" />
      <label>Top N <input id="topn" type="number" value="20" min="1" max="200" /></label>
      <label>API Key <input id="apiKey" type="text" placeholder="Divine Pride API key" style="min-width:320px" /></label>
      <button id="uploadBtn">Upload and Calculate</button>
      <button id="syncBtn">Sync Missing Skill Names</button>
    </div>
    <div id="status"></div>
    <div id="error"></div>
  </div>

  <div class="card" style="display:none">
    <h3>Overall</h3>
    <div class="kpis">
      <div class="kpi"><div class="label">Player Name</div><div id="playerName" class="value" style="font-size:18px">-</div></div>
      <div class="kpi"><div class="label">Player AID</div><div id="playerAid" class="value" style="font-size:18px">-</div></div>
      <div class="kpi"><div class="label">Players Found</div><div id="playerCount" class="value">0</div></div>
      <div class="kpi"><div class="label">Overall DPS</div><div id="overallDps" class="value">-</div></div>
      <div class="kpi"><div class="label">Skill Uses / sec</div><div id="overallUses" class="value">-</div></div>
      <div class="kpi"><div class="label">Skill Hits / sec</div><div id="overallHits" class="value">-</div></div>
    </div>
  </div>

  <div class="card" style="display:none">
    <h3>Top Skill Charts</h3>
    <div class="chart-grid">
      <div class="chart-box">
        <div class="label" style="margin-bottom:8px">Top Skills by DPS</div>
        <div id="chartDps" class="bars"></div>
      </div>
      <div class="chart-box">
        <div class="label" style="margin-bottom:8px">Top Skills by Hits/sec</div>
        <div id="chartHits" class="bars"></div>
      </div>
    </div>
  </div>

  <div class="card" style="display:none">
    <h3>Per Skill</h3>
    <table>
      <thead>
        <tr>
          <th>Skill</th>
          <th>Skill ID</th>
          <th>DPS</th>
          <th>Uses/sec</th>
          <th>Hits/sec</th>
          <th>Total Damage</th>
          <th>Uses</th>
          <th>Hits</th>
        </tr>
      </thead>
      <tbody id="skillRows"></tbody>
    </table>
  </div>

  <div class="card" style="display:none">
    <h3>Players Mapping (player_aid only: 100xxx)</h3>
    <table>
      <thead>
        <tr>
          <th>Player AID</th>
          <th>Player Name</th>
          <th>Seen Count</th>
        </tr>
      </thead>
      <tbody id="playerRows"></tbody>
    </table>
  </div>

  <div class="card">
    <h3>Split Skills By Player</h3>
      <div class="chart-box" style="margin-bottom:12px">
      <div class="label" style="margin-bottom:8px">Total Damage per Player</div>
      <div id="chartPlayerDps" class="bars"></div>
    </div>
    <div id="splitByPlayer"></div>
  </div>

  <script>
    const fileInput = document.getElementById('file');
    const topNInput = document.getElementById('topn');
    const apiKeyInput = document.getElementById('apiKey');
    const button = document.getElementById('uploadBtn');
    const syncButton = document.getElementById('syncBtn');
    const status = document.getElementById('status');
    const error = document.getElementById('error');
    const rows = document.getElementById('skillRows');
    const playerRows = document.getElementById('playerRows');
    const splitByPlayer = document.getElementById('splitByPlayer');
    const chartPlayerDps = document.getElementById('chartPlayerDps');
    const playerName = document.getElementById('playerName');
    const playerAid = document.getElementById('playerAid');
    const playerCount = document.getElementById('playerCount');
    const chartDps = document.getElementById('chartDps');
    const chartHits = document.getElementById('chartHits');

    const overallDps = document.getElementById('overallDps');
    const overallUses = document.getElementById('overallUses');
    const overallHits = document.getElementById('overallHits');
    let lastSkillIds = [];

    apiKeyInput.value = localStorage.getItem('divine_pride_api_key') || '';

    apiKeyInput.addEventListener('change', () => {
      localStorage.setItem('divine_pride_api_key', apiKeyInput.value || '');
    });

    function clearView() {
      rows.innerHTML = '';
      playerRows.innerHTML = '';
      splitByPlayer.innerHTML = '';
      chartPlayerDps.innerHTML = '';
      chartDps.innerHTML = '';
      chartHits.innerHTML = '';
      error.textContent = '';
      playerName.textContent = '-';
      playerAid.textContent = '-';
      playerCount.textContent = '0';
      overallDps.textContent = '-';
      overallUses.textContent = '-';
      overallHits.textContent = '-';
      lastSkillIds = [];
    }

    function renderSkills(skillSummary) {
      rows.innerHTML = '';
      if (!skillSummary || skillSummary.length === 0) {
        rows.innerHTML = '<tr><td colspan="8">No skill data found.</td></tr>';
        return;
      }

      for (const skill of skillSummary) {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td>${skill.skill_name ?? ''}</td>
          <td>${skill.skill_id ?? ''}</td>
          <td>${skill.dps ?? 0}</td>
          <td>${skill.uses_per_second ?? 0}</td>
          <td>${skill.hits_per_second ?? 0}</td>
          <td>${skill.total_damage ?? 0}</td>
          <td>${skill.uses ?? 0}</td>
          <td>${skill.hits ?? 0}</td>
        `;
        rows.appendChild(tr);
      }
    }

    function renderPlayers(players) {
      playerRows.innerHTML = '';
      if (!players || players.length === 0) {
        playerRows.innerHTML = '<tr><td colspan="3">No players found in replay packets.</td></tr>';
        playerCount.textContent = '0';
        return;
      }

      playerCount.textContent = String(players.length);
      for (const p of players) {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td>${p.player_aid ?? p.gid ?? ''}</td>
          <td>${p.player_name ?? ''}</td>
          <td>${p.seen_count ?? 0}</td>
        `;
        playerRows.appendChild(tr);
      }
    }

    function renderSplitByPlayer(data) {
      splitByPlayer.innerHTML = '';
      if (!data || data.length === 0) {
        splitByPlayer.innerHTML = '<div class="label">No player skill split available.</div>';
        return;
      }

      for (const entry of data) {
        const wrap = document.createElement('div');
        wrap.className = 'card';
        wrap.style.margin = '8px 0';
        const rows = (entry.skill_summary || []).slice(0, 10).map((s) =>
          `<tr><td>${s.skill_name ?? ''}</td><td>${s.hits ?? 0}</td><td>${s.dps ?? 0}</td><td>${s.hits_per_second ?? 0}</td><td>${s.total_damage ?? 0}</td></tr>`
        ).join('');
        wrap.innerHTML = `
          <div class="row" style="justify-content:space-between">
            <div><strong>${entry.player_name ?? ''}</strong> (AID: ${entry.player_aid ?? ''})</div>
            <div class="label">DPS: ${entry.player_dps ?? 0}, Damage: ${entry.total_skill_damage ?? 0}, Hits: ${entry.total_skill_hits ?? 0}, Uses: ${entry.total_skill_uses ?? 0}</div>
          </div>
          <table>
            <thead><tr><th>Skill</th><th>Hits</th><th>DPS</th><th>Hits/sec</th><th>Total Damage</th></tr></thead>
            <tbody>${rows || '<tr><td colspan="5">No skills</td></tr>'}</tbody>
          </table>
        `;
        splitByPlayer.appendChild(wrap);
      }
    }

    function renderPlayerDpsChart(players) {
      chartPlayerDps.innerHTML = '';
      if (!players || players.length === 0) {
        chartPlayerDps.innerHTML = '<div class="label">No player data</div>';
        return;
      }

      const top = [...players]
        .sort((a, b) => Number(b.total_skill_damage || 0) - Number(a.total_skill_damage || 0))
        .slice(0, 12);

      const maxVal = Math.max(...top.map(p => Number(p.total_skill_damage || 0)), 1);
      for (const p of top) {
        const value = Number(p.total_skill_damage || 0);
        const width = Math.max(2, (value / maxVal) * 100);
        const row = document.createElement('div');
        row.className = 'bar-row';
        row.innerHTML = `
          <div class="bar-label" title="${p.player_name} (${p.player_aid})">${p.player_name ?? ''}</div>
          <div class="bar-track"><div class="bar-fill" style="width:${width}%"></div></div>
          <div class="bar-val">${Math.round(value)}</div>
        `;
        chartPlayerDps.appendChild(row);
      }
    }

    function renderBarChart(container, skillSummary, metricKey) {
      container.innerHTML = '';
      if (!skillSummary || skillSummary.length === 0) {
        container.innerHTML = '<div class="label">No data</div>';
        return;
      }

      const top = [...skillSummary]
        .sort((a, b) => Number(b[metricKey] || 0) - Number(a[metricKey] || 0))
        .slice(0, 10);

      const maxVal = Math.max(...top.map(s => Number(s[metricKey] || 0)), 1);
      for (const skill of top) {
        const value = Number(skill[metricKey] || 0);
        const width = Math.max(2, (value / maxVal) * 100);
        const row = document.createElement('div');
        row.className = 'bar-row';
        row.innerHTML = `
          <div class="bar-label" title="${skill.skill_name}">${skill.skill_name}</div>
          <div class="bar-track"><div class="bar-fill" style="width:${width}%"></div></div>
          <div class="bar-val">${value.toFixed(2)}</div>
        `;
        container.appendChild(row);
      }
    }

    async function uploadAndParse() {
      clearView();
      const file = fileInput.files[0];
      if (!file) {
        error.textContent = 'Please choose a .rrf file first.';
        return;
      }

      const topN = Number(topNInput.value || 20);
      const form = new FormData();
      form.append('file', file);

      button.disabled = true;
      status.textContent = 'Parsing...';

      try {
        const res = await fetch(`/summary/skills?top_n=${encodeURIComponent(topN)}`, {
          method: 'POST',
          body: form,
        });

        const contentType = res.headers.get('content-type') || '';
        const body = contentType.includes('application/json') ? await res.json() : await res.text();

        if (!res.ok) {
          error.textContent = typeof body === 'string' ? body : JSON.stringify(body, null, 2);
          status.textContent = 'Failed';
          return;
        }

        const damage = (body.summary || {});
        const metadata = (body.metadata || {});
        const skillSummary = body.skill_summary || [];
        const players = body.player_mapping || [];
        const split = body.skill_by_player || [];

        const ids = new Set();
        for (const s of skillSummary) {
          if (Number.isInteger(s.skill_id)) ids.add(s.skill_id);
        }
        for (const p of split) {
          for (const s of (p.skill_summary || [])) {
            if (Number.isInteger(s.skill_id)) ids.add(s.skill_id);
          }
        }
        lastSkillIds = [...ids];

        playerName.textContent = metadata.player_name || '-';
        playerAid.textContent = metadata.player_aid ?? '-';
        overallDps.textContent = damage.overall_skill_dps ?? '-';
        overallUses.textContent = damage.overall_skill_uses_per_second ?? '-';
        overallHits.textContent = damage.overall_skill_hits_per_second ?? '-';

        renderSkills(skillSummary);
        renderPlayers(players);
        renderSplitByPlayer(split);
        renderPlayerDpsChart(split);
        renderBarChart(chartDps, skillSummary, 'dps');
        renderBarChart(chartHits, skillSummary, 'hits_per_second');
        status.textContent = `Done. Returned ${skillSummary.length} skills, ${players.length} players, split for ${split.length} players.`;
      } catch (e) {
        error.textContent = String(e);
        status.textContent = 'Failed';
      } finally {
        button.disabled = false;
      }
    }

    async function syncSkillNames() {
      error.textContent = '';
      const apiKey = (apiKeyInput.value || '').trim();
      if (!apiKey) {
        error.textContent = 'Please input API key first.';
        return;
      }
      if (!lastSkillIds.length) {
        error.textContent = 'No parsed skills yet. Upload and parse a replay first.';
        return;
      }

      syncButton.disabled = true;
      status.textContent = 'Syncing skill names...';
      try {
        const res = await fetch('/skills/sync', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ skill_ids: lastSkillIds, api_key: apiKey }),
        });

        const body = await res.json();
        if (!res.ok) {
          error.textContent = JSON.stringify(body, null, 2);
          status.textContent = 'Failed';
          return;
        }

        status.textContent = `Synced ${body.updated_count} new skill names. Reloading summary...`;
        await uploadAndParse();
      } catch (e) {
        error.textContent = String(e);
        status.textContent = 'Failed';
      } finally {
        syncButton.disabled = false;
      }
    }

    button.addEventListener('click', uploadAndParse);
    syncButton.addEventListener('click', syncSkillNames);
  </script>
</body>
</html>
"""


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


async def _read_rrf_upload(file: UploadFile) -> tuple[str, bytes]:
    filename = file.filename or "upload.rrf"
    if not filename.lower().endswith(".rrf"):
        raise HTTPException(status_code=422, detail="Uploaded file must use .rrf extension")

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=422, detail="Uploaded file is empty")
    if len(file_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Uploaded file is too large")

    return filename, file_bytes


@app.post("/parse", response_model=ParseResponse)
async def parse_rrf(
    file: UploadFile = File(...),
    mode: str = Query(default="decoded", pattern="^(decoded|raw)$"),
    include_events: bool = Query(default=True),
    include_aggregates: bool = Query(default=True),
) -> ParseResponse:
    filename, file_bytes = await _read_rrf_upload(file)

    result = safe_parse_rrf_bytes(
        file_bytes,
        filename=filename,
        mode=mode,
        include_events=include_events,
        include_aggregates=include_aggregates,
    )

    if result["errors"]:
        raise HTTPException(status_code=400, detail=result["errors"])

    return ParseResponse(**result)


@app.post("/summary/skills", response_model=SkillSummaryResponse)
async def summary_skills(
    file: UploadFile = File(...),
    top_n: int = Query(default=20, ge=1, le=200),
) -> SkillSummaryResponse:
    filename, file_bytes = await _read_rrf_upload(file)

    result = safe_parse_rrf_bytes(
        file_bytes,
        filename=filename,
        mode="decoded",
        include_events=False,
        include_aggregates=True,
    )

    if result["errors"]:
        raise HTTPException(status_code=400, detail=result["errors"])

    aggregates = result.get("aggregates") or {}
    skill_summary = aggregates.get("skill_summary") or []
    player_mapping = aggregates.get("player_mapping") or []
    skill_by_player = aggregates.get("skill_by_player") or []

    payload = {
        "metadata": result.get("metadata", {}),
        "summary": result.get("summary", {}),
        "skill_summary": skill_summary[:top_n],
        "player_mapping": player_mapping,
        "skill_by_player": skill_by_player,
        "warnings": result.get("warnings", []),
        "errors": result.get("errors", []),
    }
    return SkillSummaryResponse(**payload)


@app.post("/skills/sync", response_model=SkillSyncResponse)
async def sync_skill_names(payload: SkillSyncRequest) -> SkillSyncResponse:
    skill_ids = sorted({int(s) for s in payload.skill_ids if isinstance(s, int) and s > 0})
    if not skill_ids:
        raise HTTPException(status_code=422, detail="skill_ids is required")

    api_key = (payload.api_key or os.getenv("DIVINE_PRIDE_API_KEY", "")).strip()
    if not api_key:
        raise HTTPException(status_code=422, detail="api_key is required")

    updated = update_skill_names(skill_ids=skill_ids, api_key=api_key)
    response = {
        "requested_count": len(skill_ids),
        "updated_count": len(updated),
        "updated": {str(k): v for k, v in sorted(updated.items(), key=lambda x: x[0])},
    }
    return SkillSyncResponse(**response)
