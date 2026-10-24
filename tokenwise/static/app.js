/* TokenWise dashboard. All figures are simulations unless explicitly labeled. */
"use strict";

const $ = (id) => document.getElementById(id);
const formatMoney = (value) => new Intl.NumberFormat("en-US", {
  style: "currency", currency: "USD", minimumFractionDigits: 2,
  maximumFractionDigits: 2
}).format(Number(value));
const formatInt = (value) => new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(Number(value));
const formatCompact = (value) => new Intl.NumberFormat("en-US", {
  notation: "compact", maximumFractionDigits: 1
}).format(Number(value));

const controlMap = {
  "requests": "requests_per_day", "input-tokens": "input_tokens",
  "output-tokens": "output_tokens", "prompt-trim": "prompt_trim_pct",
  "output-trim": "output_trim_pct", "cache-hit": "cache_hit_pct",
  "cache-prefix": "cacheable_prefix_pct", "compact-route": "compact_route_pct"
};

let toastTimeout;
function toast(message) {
  const item = $("toast");
  item.textContent = message;
  item.classList.add("visible");
  clearTimeout(toastTimeout);
  toastTimeout = setTimeout(() => item.classList.remove("visible"), 4000);
}

async function api(path, data) {
  const options = data === undefined ? {} : {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data)
  };
  const response = await fetch(path, options);
  let result;
  try { result = await response.json(); }
  catch { throw new Error("Server did not return valid JSON"); }
  if (!response.ok) throw new Error(result.error || `Request failed (${response.status})`);
  return result;
}

function readScenario() {
  const s = { days: 30 };
  for (const [element, name] of Object.entries(controlMap)) {
    const value = Number($(element).value);
    if (!Number.isInteger(value)) throw new Error(`${name}: enter a whole number`);
    s[name] = value;
  }
  return s;
}

function setScenario(data) {
  for (const [element, name] of Object.entries(controlMap)) $(element).value = data[name];
  for (const element of ["prompt-trim", "output-trim", "cache-hit", "cache-prefix", "compact-route"]) {
    $(`${element}-value`).textContent = `${$(element).value}%`;
  }
}

function renderWaterfall(rows) {
  const host = $("waterfall");
  host.replaceChildren();
  const maximum = Math.max(0.001, Number(rows[0].usd));
  rows.forEach((row, index) => {
    const wrap = document.createElement("div"); wrap.className = "water-row";
    const label = document.createElement("div"); label.className = "water-row-top";
    const title = document.createElement("span"); title.textContent = `0${index + 1}  ${row.label}`;
    const right = document.createElement("span");
    const price = document.createElement("strong"); price.textContent = formatMoney(row.usd);
    right.append(price);
    if (index > 0) {
      const savings = document.createElement("small");
      savings.textContent = `−${formatMoney(row.gain)}`;
      right.append(savings);
    }
    label.append(title, right);
    const track = document.createElement("div"); track.className = "bar-track";
    const bar = document.createElement("div"); bar.className = "bar-fill";
    bar.style.width = `${Math.max(0, Math.min(100, Number(row.usd) / maximum * 100))}%`;
    track.append(bar); wrap.append(label, track); host.append(wrap);
  });
}

function renderHistory(result) {
  const baseline = Number(result.baseline_usd) / 30;
  const optimized = Number(result.projected_usd) / 30;
  const points = Array.from({ length: 14 }, (_, i) => {
    const factor = .82 + (i % 5) * .045 + Math.floor(i / 5) * .012;
    return { baseline: baseline * factor, optimized: optimized * factor };
  });
  const ceiling = Math.max(.001, ...points.map((point) => point.baseline)) * 1.12;
  function path(key) {
    return points.map((point, index) => {
      const x = 12 + index * (596 / (points.length - 1));
      const y = 184 - point[key] / ceiling * 157;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(" ");
  }
  $("original-path").setAttribute("points", path("baseline"));
  $("optimized-path").setAttribute("points", path("optimized"));
}

function renderSimulation(result) {
  $("baseline-value").textContent = formatMoney(result.baseline_usd);
  $("optimized-value").textContent = formatMoney(result.projected_usd);
  $("savings-value").textContent = formatMoney(result.savings_usd);
  $("savings-pct").textContent = `↘ ${Number(result.savings_pct).toFixed(1)}%`;
  $("requests-value").textContent = formatCompact(result.requests);
  $("outcome-percent").textContent = `${Number(result.savings_pct).toFixed(1)}%`;
  $("outcome-dollar").textContent = `${formatMoney(result.savings_usd)} / 30 DAYS`;
  $("cost-per-k").textContent = formatMoney(result.cost_per_1000_usd);
  $("cached-tokens").textContent = formatCompact(result.cache_read_tokens);
  $("optimized-input").textContent = formatCompact(result.optimized_input_tokens);
  $("risk-pill").textContent = `${result.risk} / QUALITY NOT TESTED`;
  $("risk-message").textContent = result.risk_note;
  renderWaterfall(result.waterfall);
  renderHistory(result);
}

function renderEvidence(evidence, source = "SYNTHETIC") {
  const { baseline, candidate } = evidence;
  $("baseline-pass").textContent = `${baseline.pass_rate.toFixed(1)}%`;
  $("candidate-pass").textContent = `${candidate.pass_rate.toFixed(1)}%`;
  $("baseline-cost-pass").textContent = baseline.cost_per_pass == null ? "N/A" : formatMoney(baseline.cost_per_pass);
  $("candidate-cost-pass").textContent = candidate.cost_per_pass == null ? "N/A" : formatMoney(candidate.cost_per_pass);
  $("gate-pill").textContent = `GATE: ${evidence.gate} / ${source}`;
  $("gate-pill").style.color = evidence.gate === "PASS" ? "var(--lime)" : "var(--orange)";
}

async function refreshRuns() {
  const { runs } = await api("/api/runs");
  const tbody = $("run-rows"); tbody.replaceChildren();
  if (!runs.length) {
    const row = tbody.insertRow(); const cell = row.insertCell(); cell.colSpan = 4;
    cell.className = "empty-state"; cell.textContent = "Run a simulation to start your evidence ledger.";
    return;
  }
  for (const run of runs) {
    const row = tbody.insertRow();
    const created = new Date(run.created_utc);
    const fields = [created.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }),
      formatCompact(run.result.requests), `${run.result.savings_pct}%`, run.result.risk];
    fields.forEach((value) => { const cell = row.insertCell(); cell.textContent = value; });
  }
}

async function runScenario() {
  const button = $("run-scenario");
  button.disabled = true; button.textContent = "CALCULATING...";
  try {
    const data = await api("/api/simulate", readScenario());
    renderSimulation(data.result);
    await refreshRuns();
    toast("Scenario saved locally · No model was invoked");
  } catch (error) { toast(error.message); }
  finally { button.disabled = false; button.innerHTML = "RUN SIMULATION <span>→</span>"; }
}

async function inspect() {
  try {
    const report = await api("/api/inspect", { prompt: $("prompt-text").value });
    $("prompt-token-count").textContent = formatInt(report.estimated_tokens);
    $("prompt-chars").textContent = `${formatInt(report.characters)} characters`;
    $("prompt-dupes").textContent = `${report.duplicate_lines} repeated lines`;
    const host = $("prompt-tips"); host.replaceChildren();
    report.tips.forEach((tip) => { const p = document.createElement("p"); p.textContent = tip; host.append(p); });
  } catch (error) { toast(error.message); }
}

document.addEventListener("DOMContentLoaded", async () => {
  $("today").textContent = new Intl.DateTimeFormat("en-US", { month: "short", day: "2-digit", year: "numeric" }).format(new Date()).toUpperCase();
  for (const element of ["prompt-trim", "output-trim", "cache-hit", "cache-prefix", "compact-route"]) {
    $(element).addEventListener("input", () => { $(`${element}-value`).textContent = `${$(element).value}%`; });
  }
  document.querySelectorAll("a[data-view]").forEach((link) => link.addEventListener("click", () => {
    document.querySelectorAll(".nav-item").forEach((node) => node.classList.remove("active"));
    const active = document.querySelector(`.nav-item[data-view="${link.dataset.view}"]`);
    if (active) active.classList.add("active");
  }));
  $("run-scenario").addEventListener("click", runScenario);
  $("reset-scenario").addEventListener("click", async () => {
    try { const { scenario, result } = await api("/api/overview"); setScenario(scenario); renderSimulation(result); toast("Reset to the original demonstration scenario"); }
    catch (error) { toast(error.message); }
  });
  $("inspect-prompt").addEventListener("click", inspect);
  $("benchmark-file").addEventListener("change", async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    if (file.size > 70_000) { toast("Benchmark file must be under 70 KB"); return; }
    try {
      const payload = JSON.parse(await file.text());
      const evidence = await api("/api/compare", payload);
      renderEvidence(evidence, "USER DATA");
      $("benchmark-source").textContent = `${evidence.count} imported observation pairs`;
      toast("Evidence gate evaluated your supplied benchmark results");
    } catch (error) { toast(`Benchmark rejected: ${error.message}`); }
    finally { event.target.value = ""; }
  });
  $("refresh-runs").addEventListener("click", () => refreshRuns().catch((error) => toast(error.message)));
  try {
    const demo = await api("/api/overview");
    setScenario(demo.scenario);
    renderSimulation(demo.result);
    renderEvidence(demo.evidence);
    await refreshRuns();
  } catch (error) { toast(`Unable to load the local engine: ${error.message}`); }
});
