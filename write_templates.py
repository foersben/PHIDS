"""Write all Jinja2 templates for the PHIDS HTMX UI."""

import pathlib

BASE = pathlib.Path("src/phids/api/templates")
PARTIALS = BASE / "partials"
BASE.mkdir(parents=True, exist_ok=True)
PARTIALS.mkdir(parents=True, exist_ok=True)

# ── index.html ─────────────────────────────────────────────────────────────
(BASE / "index.html").write_text(
    '{% extends "base.html" %}\n'
    "{% block content %}\n"
    '{% include "partials/dashboard.html" %}\n'
    "{% endblock %}\n"
)

# ── partials/dashboard.html ────────────────────────────────────────────────
(PARTIALS / "dashboard.html").write_text("""\
<div id="dashboard-view" class="space-y-6">

  <!-- Live canvas -->
  <div class="bg-white rounded-xl shadow-sm border p-4">
    <h2 class="text-lg font-semibold text-slate-700 mb-4">📊 Live Simulation Grid</h2>
    <div class="relative">
      <canvas id="biotope-canvas" width="800" height="400"
        style="width:100%;image-rendering:pixelated;background:#0f172a;"
        class="rounded w-full"></canvas>
      <div id="canvas-overlay"
        class="absolute inset-0 flex items-center justify-center pointer-events-none">
        <span class="text-slate-400 text-sm" id="canvas-hint">Load a scenario to begin.</span>
      </div>
    </div>
  </div>

  <!-- Lotka-Volterra telemetry chart (HTMX-polled) -->
  <div class="bg-white rounded-xl shadow-sm border p-4">
    <h2 class="text-lg font-semibold text-slate-700 mb-2">📈 Lotka-Volterra Telemetry</h2>
    <div id="telemetry-chart"
      hx-get="/api/telemetry" hx-trigger="every 1s" hx-swap="innerHTML"
      class="min-h-[80px] flex items-center justify-center">
      <span class="text-slate-400 text-sm">No telemetry data yet.</span>
    </div>
  </div>
</div>

<!-- Isolated WebSocket canvas renderer -->
<script>
(function () {
  const canvas = document.getElementById('biotope-canvas');
  const ctx = canvas.getContext('2d');
  const W = canvas.width;
  const H = canvas.height;
  const hint = document.getElementById('canvas-hint');
  let ws = null;

  function connect() {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    ws = new WebSocket(proto + '://' + location.host + '/ws/ui/stream');

    ws.onopen = function () {
      if (hint) hint.textContent = '';
    };

    ws.onmessage = function (evt) {
      let data;
      try { data = JSON.parse(evt.data); } catch (e) { return; }
      if (!data || !data.plant_energy) return;

      const grid = data.plant_energy;
      const gridW = grid.length;
      if (!gridW) return;
      const gridH = grid[0].length;
      const cellW = W / gridW;
      const cellH = H / gridH;
      const maxE = data.max_energy || 100;

      ctx.fillStyle = '#0f172a';
      ctx.fillRect(0, 0, W, H);

      for (let x = 0; x < gridW; x++) {
        for (let y = 0; y < gridH; y++) {
          const e = grid[x][y];
          if (e > 0) {
            const v = Math.min(255, Math.round((e / maxE) * 220) + 35);
            ctx.fillStyle = 'rgb(0,' + v + ',0)';
            ctx.fillRect(x * cellW, y * cellH, cellW, cellH);
          }
        }
      }

      for (const s of (data.swarms || [])) {
        ctx.fillStyle = '#ef4444';
        ctx.fillRect(s.x * cellW, s.y * cellH, cellW, cellH);
      }

      const tc = document.getElementById('tick-counter');
      if (tc && data.tick != null) tc.textContent = data.tick;
    };

    ws.onclose = function () { setTimeout(connect, 3000); };
    ws.onerror = function () { ws.close(); };
  }

  connect();
})();
</script>
""")

# ── partials/biotope_config.html ───────────────────────────────────────────
(PARTIALS / "biotope_config.html").write_text("""\
<div id="biotope-config-view" class="max-w-2xl">
  <h2 class="text-xl font-semibold text-slate-800 mb-6">🌍 Biotope Configuration</h2>
  <div class="bg-white rounded-xl shadow-sm border p-6">
    <form hx-post="/api/config/biotope" hx-target="#biotope-config-view" hx-swap="outerHTML"
      hx-trigger="change" class="grid grid-cols-2 gap-6">

      <div>
        <label class="block text-sm font-medium text-slate-700 mb-1">Grid Width</label>
        <input type="number" name="grid_width" min="10" max="80"
          value="{{ draft.grid_width }}"
          class="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none">
      </div>
      <div>
        <label class="block text-sm font-medium text-slate-700 mb-1">Grid Height</label>
        <input type="number" name="grid_height" min="10" max="80"
          value="{{ draft.grid_height }}"
          class="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none">
      </div>

      <div>
        <label class="block text-sm font-medium text-slate-700 mb-1">Max Ticks</label>
        <input type="number" name="max_ticks" min="1"
          value="{{ draft.max_ticks }}"
          class="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none">
      </div>
      <div>
        <label class="block text-sm font-medium text-slate-700 mb-1">Tick Rate (Hz)</label>
        <input type="number" name="tick_rate_hz" min="0.1" step="0.1"
          value="{{ draft.tick_rate_hz }}"
          class="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none">
      </div>

      <div>
        <label class="block text-sm font-medium text-slate-700 mb-1">Wind Vector X</label>
        <input type="number" name="wind_x" step="0.1"
          value="{{ draft.wind_x }}"
          class="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none">
      </div>
      <div>
        <label class="block text-sm font-medium text-slate-700 mb-1">Wind Vector Y</label>
        <input type="number" name="wind_y" step="0.1"
          value="{{ draft.wind_y }}"
          class="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none">
      </div>

      <div>
        <label class="block text-sm font-medium text-slate-700 mb-1">Signal Layers</label>
        <input type="number" name="num_signals" min="1" max="16"
          value="{{ draft.num_signals }}"
          class="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none">
      </div>
      <div>
        <label class="block text-sm font-medium text-slate-700 mb-1">Toxin Layers</label>
        <input type="number" name="num_toxins" min="1" max="16"
          value="{{ draft.num_toxins }}"
          class="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none">
      </div>

      <div class="col-span-2 flex items-center gap-3">
        <input type="checkbox" name="mycorrhizal_inter_species" id="myco_inter"
          {% if draft.mycorrhizal_inter_species %}checked{% endif %}
          class="h-4 w-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500">
        <label for="myco_inter" class="text-sm text-slate-700">
          Allow inter-species mycorrhizal connections
        </label>
      </div>

      <div>
        <label class="block text-sm font-medium text-slate-700 mb-1">Root Link Cost</label>
        <input type="number" name="mycorrhizal_connection_cost" min="0" step="0.1"
          value="{{ draft.mycorrhizal_connection_cost }}"
          class="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none">
      </div>
      <div>
        <label class="block text-sm font-medium text-slate-700 mb-1">Signal Velocity</label>
        <input type="number" name="mycorrhizal_signal_velocity" min="1" step="1"
          value="{{ draft.mycorrhizal_signal_velocity }}"
          class="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none">
      </div>

    </form>
    <p class="mt-4 text-xs text-slate-400">Changes apply automatically on field blur/change.</p>
  </div>
</div>
""")

# ── partials/flora_config.html ─────────────────────────────────────────────
(PARTIALS / "flora_config.html").write_text("""\
<div id="flora-config-view">
  <div class="flex items-center justify-between mb-4">
    <h2 class="text-xl font-semibold text-slate-800">🌿 Flora Species</h2>
    {% if flora_species|length < 16 %}
    <button hx-post="/api/config/flora" hx-target="#flora-config-view" hx-swap="outerHTML"
      hx-vals='{"name":"NewFlora","base_energy":"10","max_energy":"100","growth_rate":"5","survival_threshold":"1","reproduction_interval":"10","seed_min_dist":"1","seed_max_dist":"3","seed_energy_cost":"5"}'
      class="px-4 py-2 bg-emerald-500 hover:bg-emerald-600 text-white rounded-lg text-sm font-medium transition-colors">
      + Add Species
    </button>
    {% else %}
    <button disabled class="px-4 py-2 bg-slate-300 text-slate-500 rounded-lg text-sm font-medium cursor-not-allowed">
      + Add Species (max 16)
    </button>
    {% endif %}
  </div>

  <div class="bg-white rounded-xl shadow-sm border overflow-auto">
    <table class="w-full divide-y divide-slate-200 text-sm">
      <thead class="bg-slate-50">
        <tr>
          <th class="px-3 py-3 text-left text-xs font-semibold text-slate-500 uppercase">ID</th>
          <th class="px-3 py-3 text-left text-xs font-semibold text-slate-500 uppercase">Name</th>
          <th class="px-3 py-3 text-left text-xs font-semibold text-slate-500 uppercase">Base E</th>
          <th class="px-3 py-3 text-left text-xs font-semibold text-slate-500 uppercase">Max E</th>
          <th class="px-3 py-3 text-left text-xs font-semibold text-slate-500 uppercase">Growth</th>
          <th class="px-3 py-3 text-left text-xs font-semibold text-slate-500 uppercase">Surv. Thr.</th>
          <th class="px-3 py-3 text-left text-xs font-semibold text-slate-500 uppercase">Repr. Int.</th>
          <th class="px-3 py-3 text-left text-xs font-semibold text-slate-500 uppercase">Camo</th>
          <th class="px-3 py-3 text-left text-xs font-semibold text-slate-500 uppercase">Actions</th>
        </tr>
      </thead>
      <tbody class="divide-y divide-slate-100" id="flora-table-body">
        {% for fp in flora_species %}
        <tr id="flora-row-{{ fp.species_id }}">
          <td class="px-3 py-2 font-mono text-slate-400">{{ fp.species_id }}</td>
          <td class="px-3 py-2">
            <input type="text" value="{{ fp.name }}"
              hx-put="/api/config/flora/{{ fp.species_id }}" hx-trigger="change"
              hx-target="#flora-row-{{ fp.species_id }}" hx-swap="outerHTML"
              name="name"
              class="border-0 bg-transparent focus:ring-1 focus:ring-indigo-400 rounded px-1 w-32">
          </td>
          <td class="px-3 py-2">
            <input type="number" value="{{ fp.base_energy }}" step="0.1" min="0.1" name="base_energy"
              hx-put="/api/config/flora/{{ fp.species_id }}" hx-trigger="change"
              hx-target="#flora-row-{{ fp.species_id }}" hx-swap="outerHTML"
              class="border-0 bg-transparent focus:ring-1 focus:ring-indigo-400 rounded px-1 w-20">
          </td>
          <td class="px-3 py-2">
            <input type="number" value="{{ fp.max_energy }}" step="0.1" min="0.1" name="max_energy"
              hx-put="/api/config/flora/{{ fp.species_id }}" hx-trigger="change"
              hx-target="#flora-row-{{ fp.species_id }}" hx-swap="outerHTML"
              class="border-0 bg-transparent focus:ring-1 focus:ring-indigo-400 rounded px-1 w-20">
          </td>
          <td class="px-3 py-2">
            <input type="number" value="{{ fp.growth_rate }}" step="0.1" min="0" name="growth_rate"
              hx-put="/api/config/flora/{{ fp.species_id }}" hx-trigger="change"
              hx-target="#flora-row-{{ fp.species_id }}" hx-swap="outerHTML"
              class="border-0 bg-transparent focus:ring-1 focus:ring-indigo-400 rounded px-1 w-20">
          </td>
          <td class="px-3 py-2">
            <input type="number" value="{{ fp.survival_threshold }}" step="0.1" min="0" name="survival_threshold"
              hx-put="/api/config/flora/{{ fp.species_id }}" hx-trigger="change"
              hx-target="#flora-row-{{ fp.species_id }}" hx-swap="outerHTML"
              class="border-0 bg-transparent focus:ring-1 focus:ring-indigo-400 rounded px-1 w-20">
          </td>
          <td class="px-3 py-2">
            <input type="number" value="{{ fp.reproduction_interval }}" step="1" min="1" name="reproduction_interval"
              hx-put="/api/config/flora/{{ fp.species_id }}" hx-trigger="change"
              hx-target="#flora-row-{{ fp.species_id }}" hx-swap="outerHTML"
              class="border-0 bg-transparent focus:ring-1 focus:ring-indigo-400 rounded px-1 w-20">
          </td>
          <td class="px-3 py-2 text-center">
            <input type="checkbox" {% if fp.camouflage %}checked{% endif %} name="camouflage"
              hx-put="/api/config/flora/{{ fp.species_id }}" hx-trigger="change"
              hx-target="#flora-row-{{ fp.species_id }}" hx-swap="outerHTML"
              class="h-4 w-4 rounded border-slate-300 text-indigo-600">
          </td>
          <td class="px-3 py-2">
            <button hx-delete="/api/config/flora/{{ fp.species_id }}"
              hx-target="#flora-row-{{ fp.species_id }}" hx-swap="outerHTML swap:0.5s"
              hx-confirm="Delete {{ fp.name }}?"
              class="text-red-500 hover:text-red-700 text-xs font-medium transition-colors">
              Delete
            </button>
          </td>
        </tr>
        {% else %}
        <tr>
          <td colspan="9" class="px-3 py-6 text-center text-slate-400">
            No flora species defined yet.
          </td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
</div>
""")

# ── partials/herbivore_config.html ─────────────────────────────────────────
(PARTIALS / "herbivore_config.html").write_text("""\
<div id="herbivore-config-view">
  <div class="flex items-center justify-between mb-4">
    <h2 class="text-xl font-semibold text-slate-800">🐛 Herbivore Species</h2>
    {% if herbivore_species|length < 16 %}
    <button hx-post="/api/config/herbivores" hx-target="#herbivore-config-view" hx-swap="outerHTML"
      hx-vals='{"name":"NewHerbivore","energy_min":"5","velocity":"2","consumption_rate":"10"}'
      class="px-4 py-2 bg-emerald-500 hover:bg-emerald-600 text-white rounded-lg text-sm font-medium transition-colors">
      + Add Species
    </button>
    {% else %}
    <button disabled class="px-4 py-2 bg-slate-300 text-slate-500 rounded-lg text-sm font-medium cursor-not-allowed">
      + Add Species (max 16)
    </button>
    {% endif %}
  </div>

  <div class="bg-white rounded-xl shadow-sm border overflow-auto">
    <table class="w-full divide-y divide-slate-200 text-sm">
      <thead class="bg-slate-50">
        <tr>
          <th class="px-3 py-3 text-left text-xs font-semibold text-slate-500 uppercase">ID</th>
          <th class="px-3 py-3 text-left text-xs font-semibold text-slate-500 uppercase">Name</th>
          <th class="px-3 py-3 text-left text-xs font-semibold text-slate-500 uppercase">Energy Min</th>
          <th class="px-3 py-3 text-left text-xs font-semibold text-slate-500 uppercase">Speed</th>
          <th class="px-3 py-3 text-left text-xs font-semibold text-slate-500 uppercase">Eating Rate</th>
          <th class="px-3 py-3 text-left text-xs font-semibold text-slate-500 uppercase">Repr. Divisor</th>
          <th class="px-3 py-3 text-left text-xs font-semibold text-slate-500 uppercase">Actions</th>
        </tr>
      </thead>
      <tbody class="divide-y divide-slate-100">
        {% for pp in herbivore_species %}
        <tr id="herbivore-row-{{ pp.species_id }}">
          <td class="px-3 py-2 font-mono text-slate-400">{{ pp.species_id }}</td>
          <td class="px-3 py-2">
            <input type="text" value="{{ pp.name }}" name="name"
              hx-put="/api/config/herbivores/{{ pp.species_id }}" hx-trigger="change"
              hx-target="#herbivore-row-{{ pp.species_id }}" hx-swap="outerHTML"
              class="border-0 bg-transparent focus:ring-1 focus:ring-indigo-400 rounded px-1 w-32">
          </td>
          <td class="px-3 py-2">
            <input type="number" value="{{ pp.energy_min }}" step="0.1" min="0.1" name="energy_min"
              hx-put="/api/config/herbivores/{{ pp.species_id }}" hx-trigger="change"
              hx-target="#herbivore-row-{{ pp.species_id }}" hx-swap="outerHTML"
              class="border-0 bg-transparent focus:ring-1 focus:ring-indigo-400 rounded px-1 w-20">
          </td>
          <td class="px-3 py-2">
            <input type="number" value="{{ pp.velocity }}" step="1" min="1" name="velocity"
              hx-put="/api/config/herbivores/{{ pp.species_id }}" hx-trigger="change"
              hx-target="#herbivore-row-{{ pp.species_id }}" hx-swap="outerHTML"
              class="border-0 bg-transparent focus:ring-1 focus:ring-indigo-400 rounded px-1 w-20">
          </td>
          <td class="px-3 py-2">
            <input type="number" value="{{ pp.consumption_rate }}" step="0.1" min="0.1" name="consumption_rate"
              hx-put="/api/config/herbivores/{{ pp.species_id }}" hx-trigger="change"
              hx-target="#herbivore-row-{{ pp.species_id }}" hx-swap="outerHTML"
              class="border-0 bg-transparent focus:ring-1 focus:ring-indigo-400 rounded px-1 w-20">
          </td>
          <td class="px-3 py-2">
            <input type="number" value="{{ pp.reproduction_energy_divisor }}" step="0.1" min="0.1" name="reproduction_energy_divisor"
              hx-put="/api/config/herbivores/{{ pp.species_id }}" hx-trigger="change"
              hx-target="#herbivore-row-{{ pp.species_id }}" hx-swap="outerHTML"
              class="border-0 bg-transparent focus:ring-1 focus:ring-indigo-400 rounded px-1 w-20">
          </td>
          <td class="px-3 py-2">
            <button hx-delete="/api/config/herbivores/{{ pp.species_id }}"
              hx-target="#herbivore-row-{{ pp.species_id }}" hx-swap="outerHTML swap:0.5s"
              hx-confirm="Delete {{ pp.name }}?"
              class="text-red-500 hover:text-red-700 text-xs font-medium transition-colors">
              Delete
            </button>
          </td>
        </tr>
        {% else %}
        <tr>
          <td colspan="7" class="px-3 py-6 text-center text-slate-400">
            No herbivore species defined yet.
          </td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
</div>
""")

# ── partials/substance_config.html ─────────────────────────────────────────
(PARTIALS / "substance_config.html").write_text("""\
<div id="substance-config-view">
  <div class="flex items-center justify-between mb-4">
    <h2 class="text-xl font-semibold text-slate-800">🧪 Substance Definitions</h2>
    {% if substances|length < 16 %}
    <button hx-post="/api/config/substances" hx-target="#substance-config-view" hx-swap="outerHTML"
      hx-vals='{"name":"Signal","is_toxin":"false","lethal":"false","repellent":"false","synthesis_duration":"3","aftereffect_ticks":"0","lethality_rate":"0","repellent_walk_ticks":"3","energy_cost_per_tick":"1","min_herbivore_population":"5"}'
      class="px-4 py-2 bg-emerald-500 hover:bg-emerald-600 text-white rounded-lg text-sm font-medium transition-colors">
      + Add Substance
    </button>
    {% else %}
    <button disabled class="px-4 py-2 bg-slate-300 text-slate-500 rounded-lg text-sm font-medium cursor-not-allowed">
      + Add Substance (max 16)
    </button>
    {% endif %}
  </div>

  <div class="bg-white rounded-xl shadow-sm border overflow-auto">
    <table class="w-full divide-y divide-slate-200 text-sm">
      <thead class="bg-slate-50">
        <tr>
          <th class="px-3 py-3 text-left text-xs font-semibold text-slate-500 uppercase">ID</th>
          <th class="px-3 py-3 text-left text-xs font-semibold text-slate-500 uppercase">Name</th>
          <th class="px-3 py-3 text-left text-xs font-semibold text-slate-500 uppercase">Type</th>
          <th class="px-3 py-3 text-left text-xs font-semibold text-slate-500 uppercase">Synth. Dur.</th>
          <th class="px-3 py-3 text-left text-xs font-semibold text-slate-500 uppercase">Aftereffect</th>
          <th class="px-3 py-3 text-left text-xs font-semibold text-slate-500 uppercase">Lethality</th>
          <th class="px-3 py-3 text-left text-xs font-semibold text-slate-500 uppercase">Min Pop.</th>
          <th class="px-3 py-3 text-left text-xs font-semibold text-slate-500 uppercase">Actions</th>
        </tr>
      </thead>
      <tbody class="divide-y divide-slate-100">
        {% for sub in substances %}
        <tr id="substance-row-{{ sub.substance_id }}">
          <td class="px-3 py-2 font-mono text-slate-400">{{ sub.substance_id }}</td>
          <td class="px-3 py-2">
            <input type="text" value="{{ sub.name }}" name="name"
              hx-put="/api/config/substances/{{ sub.substance_id }}" hx-trigger="change"
              hx-target="#substance-row-{{ sub.substance_id }}" hx-swap="outerHTML"
              class="border-0 bg-transparent focus:ring-1 focus:ring-indigo-400 rounded px-1 w-28">
          </td>
          <td class="px-3 py-2">
            <select name="type_label"
              hx-put="/api/config/substances/{{ sub.substance_id }}" hx-trigger="change"
              hx-target="#substance-row-{{ sub.substance_id }}" hx-swap="outerHTML"
              class="border-0 bg-transparent focus:ring-1 focus:ring-indigo-400 rounded px-1 text-sm">
              <option value="Signal" {% if sub.type_label == 'Signal' %}selected{% endif %}>Signal</option>
              <option value="Lethal Toxin" {% if sub.type_label == 'Lethal Toxin' %}selected{% endif %}>Lethal Toxin</option>
              <option value="Repellent Toxin" {% if sub.type_label == 'Repellent Toxin' %}selected{% endif %}>Repellent Toxin</option>
              <option value="Toxin" {% if sub.type_label == 'Toxin' %}selected{% endif %}>Toxin</option>
            </select>
          </td>
          <td class="px-3 py-2">
            <input type="number" value="{{ sub.synthesis_duration }}" min="1" step="1" name="synthesis_duration"
              hx-put="/api/config/substances/{{ sub.substance_id }}" hx-trigger="change"
              hx-target="#substance-row-{{ sub.substance_id }}" hx-swap="outerHTML"
              class="border-0 bg-transparent focus:ring-1 focus:ring-indigo-400 rounded px-1 w-16">
          </td>
          <td class="px-3 py-2">
            <input type="number" value="{{ sub.aftereffect_ticks }}" min="0" step="1" name="aftereffect_ticks"
              hx-put="/api/config/substances/{{ sub.substance_id }}" hx-trigger="change"
              hx-target="#substance-row-{{ sub.substance_id }}" hx-swap="outerHTML"
              class="border-0 bg-transparent focus:ring-1 focus:ring-indigo-400 rounded px-1 w-16">
          </td>
          <td class="px-3 py-2">
            <input type="number" value="{{ sub.lethality_rate }}" min="0" step="0.01" name="lethality_rate"
              hx-put="/api/config/substances/{{ sub.substance_id }}" hx-trigger="change"
              hx-target="#substance-row-{{ sub.substance_id }}" hx-swap="outerHTML"
              class="border-0 bg-transparent focus:ring-1 focus:ring-indigo-400 rounded px-1 w-16">
          </td>
          <td class="px-3 py-2">
            <input type="number" value="{{ sub.min_herbivore_population }}" min="1" step="1" name="min_herbivore_population"
              hx-put="/api/config/substances/{{ sub.substance_id }}" hx-trigger="change"
              hx-target="#substance-row-{{ sub.substance_id }}" hx-swap="outerHTML"
              class="border-0 bg-transparent focus:ring-1 focus:ring-indigo-400 rounded px-1 w-16">
          </td>
          <td class="px-3 py-2">
            <button hx-delete="/api/config/substances/{{ sub.substance_id }}"
              hx-target="#substance-row-{{ sub.substance_id }}" hx-swap="outerHTML swap:0.5s"
              hx-confirm="Delete {{ sub.name }}?"
              class="text-red-500 hover:text-red-700 text-xs font-medium transition-colors">
              Delete
            </button>
          </td>
        </tr>
        {% else %}
        <tr>
          <td colspan="8" class="px-3 py-6 text-center text-slate-400">
            No substances defined. Add one to enable chemical signaling.
          </td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
  <p class="mt-3 text-xs text-slate-400">
    Assign substances to (Flora, Herbivore) pairs in the ⚡ Trigger Matrix.
  </p>
</div>
""")

# ── partials/diet_matrix.html ──────────────────────────────────────────────
(PARTIALS / "diet_matrix.html").write_text("""\
<div id="diet-matrix-view">
  <h2 class="text-xl font-semibold text-slate-800 mb-4">🍽️ Diet Compatibility Matrix</h2>
  <p class="text-sm text-slate-500 mb-4">
    Rows = Herbivore species (E<sub>i</sub>), Columns = Flora species (P<sub>j</sub>).
    ✅ = herbivore can consume that flora.
  </p>

  {% if not flora_species or not herbivore_species %}
  <div class="bg-amber-50 border border-amber-200 rounded-xl p-4 text-amber-700 text-sm">
    Define at least one flora species and one herbivore species first.
  </div>
  {% else %}
  <div class="bg-white rounded-xl shadow-sm border overflow-auto">
    <table class="divide-y divide-slate-200 text-sm">
      <thead class="bg-slate-50">
        <tr>
          <th class="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase">
            Herbivore \\ Flora
          </th>
          {% for fp in flora_species %}
          <th class="px-4 py-3 text-center text-xs font-semibold text-slate-500 uppercase">
            {{ fp.name }}
          </th>
          {% endfor %}
        </tr>
      </thead>
      <tbody class="divide-y divide-slate-100">
        {% for pp in herbivore_species %}
        <tr>
          <td class="px-4 py-3 font-medium text-slate-700">{{ pp.name }}</td>
          {% for fp in flora_species %}
          <td class="px-4 py-3 text-center">
            <input type="checkbox"
              {% if diet_matrix[loop.parent.index0][loop.index0] %}checked{% endif %}
              hx-post="/api/matrices/diet"
              hx-vals='{"herbivore_idx": {{ loop.parent.index0 }}, "flora_idx": {{ loop.index0 }}, "compatible": "toggle"}'
              hx-trigger="change"
              hx-target="#diet-matrix-view" hx-swap="outerHTML"
              class="h-4 w-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500 cursor-pointer">
          </td>
          {% endfor %}
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
  {% endif %}
</div>
""")

# ── partials/trigger_matrix.html ───────────────────────────────────────────
(PARTIALS / "trigger_matrix.html").write_text("""\
<div id="trigger-matrix-view">
  <h2 class="text-xl font-semibold text-slate-800 mb-4">⚡ Substance Trigger Matrix</h2>
  <p class="text-sm text-slate-500 mb-4">
    Rows = Flora species (P<sub>j</sub>), Columns = Herbivore attacker (E<sub>i</sub>).
    Select the substance synthesised when that herbivore attacks that plant.
  </p>

  {% if not flora_species or not herbivore_species %}
  <div class="bg-amber-50 border border-amber-200 rounded-xl p-4 text-amber-700 text-sm">
    Define at least one flora species and one herbivore species first.
  </div>
  {% else %}
  <div class="bg-white rounded-xl shadow-sm border overflow-auto">
    <table class="divide-y divide-slate-200 text-sm">
      <thead class="bg-slate-50">
        <tr>
          <th class="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase">
            Flora \\ Herbivore
          </th>
          {% for pp in herbivore_species %}
          <th class="px-4 py-3 text-center text-xs font-semibold text-slate-500 uppercase">
            {{ pp.name }}
          </th>
          {% endfor %}
        </tr>
      </thead>
      <tbody class="divide-y divide-slate-100">
        {% for fp in flora_species %}
        <tr>
          <td class="px-4 py-3 font-medium text-slate-700">{{ fp.name }}</td>
          {% for pp in herbivore_species %}
          <td class="px-4 py-3 text-center">
            <select
              hx-post="/api/matrices/trigger"
              hx-vals='{"flora_idx": {{ loop.parent.index0 }}, "herbivore_idx": {{ loop.index0 }}}'
              hx-trigger="change"
              hx-target="#trigger-matrix-view" hx-swap="outerHTML"
              hx-include="this"
              name="substance_id"
              class="border border-slate-300 rounded px-2 py-1 text-xs focus:ring-1 focus:ring-indigo-500 focus:outline-none">
              <option value="-1"
                {% if trigger_matrix[loop.parent.index0][loop.index0] == -1 %}selected{% endif %}>
                — none —
              </option>
              {% for sub in substances %}
              <option value="{{ sub.substance_id }}"
                {% if trigger_matrix[loop.parent.index0][loop.index0] == sub.substance_id %}selected{% endif %}>
                {{ sub.name }}
              </option>
              {% endfor %}
            </select>
          </td>
          {% endfor %}
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
  {% endif %}
</div>
""")

# ── partials/telemetry_chart.html ──────────────────────────────────────────
(PARTIALS / "telemetry_chart.html").write_text("""\
{{ svg_content | safe }}
{% if legend %}
<div class="flex gap-6 mt-2 text-xs text-slate-500">
  <span class="flex items-center gap-1">
    <span class="inline-block w-4 h-1 bg-green-500 rounded"></span> Flora population
  </span>
  <span class="flex items-center gap-1">
    <span class="inline-block w-4 h-1 bg-red-500 rounded"></span> Herbivore population
  </span>
  <span class="flex items-center gap-1">
    <span class="inline-block w-4 h-1 bg-blue-400 rounded"></span> Flora energy (×0.1)
  </span>
</div>
{% endif %}
""")

print("All templates written successfully.")
