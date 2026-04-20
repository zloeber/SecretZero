"""Jinja2 template strings for ``secretzero web`` (avoids non-Python package data)."""

# Shared layout CSS: light/dark, card, focus states
_BASE_STYLE = """
:root {
  --bg: #f4f6f8;
  --surface: #fff;
  --text: #1a1d21;
  --muted: #5c6570;
  --border: #d8dee6;
  --accent: #0d6efd;
  --accent-hover: #0b5ed7;
  --danger: #b02a37;
  --shadow: 0 4px 24px rgba(0,0,0,.08);
  --radius: 12px;
  --font: ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  --flow-synced: #198754;
  --flow-pending: #e97109;
  --flow-drift: #c82832;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #121418;
    --surface: #1c2028;
    --text: #e8eaed;
    --muted: #9aa3ad;
    --border: #2f3640;
    --accent: #4d9fff;
    --accent-hover: #6eb0ff;
    --danger: #f4717a;
    --shadow: 0 4px 24px rgba(0,0,0,.45);
    --flow-synced: #3dd68c;
    --flow-pending: #ffb347;
    --flow-drift: #ff7b7b;
  }
}
* { box-sizing: border-box; }
body {
  margin: 0;
  min-height: 100vh;
  font-family: var(--font);
  background: var(--bg);
  color: var(--text);
  line-height: 1.5;
}
main {
  max-width: min(88rem, 100%);
  margin: 0 auto;
  padding: clamp(1.5rem, 4vw, 3rem) 1.25rem;
}
.manifest-meta {
  font-size: 0.88rem;
  color: var(--muted);
  display: grid;
  gap: 0.35rem;
  margin-bottom: 1.25rem;
  padding: 0.75rem 1rem;
  background: rgba(127,127,127,0.06);
  border-radius: 8px;
  border: 1px solid var(--border);
}
.pi-status { font-weight: 600; font-size: 0.82rem; }
.pi-status--ok { color: #1a7f37; }
.pi-status--local { color: var(--muted); }
.pi-status--unauthenticated { color: #9a6700; }
.pi-status--error, .pi-status--unregistered, .pi-status--unknown { color: #cf222e; }
.pi-ident code { font-size: 0.85em; }
.identity-preflight-wrap strong { color: var(--text); }
.identity-preflight {
  margin-top: 0.45rem;
  padding: 0.55rem 0.75rem;
  border-radius: 8px;
  font-size: 0.9rem;
  line-height: 1.45;
}
.identity-preflight--ok {
  background: rgba(25, 135, 84, 0.12);
  border: 1px solid rgba(25, 135, 84, 0.35);
}
.identity-preflight--bad {
  background: rgba(207, 34, 46, 0.1);
  border: 1px solid rgba(207, 34, 46, 0.4);
}
.identity-preflight--neutral {
  background: rgba(127, 127, 127, 0.08);
  border: 1px solid var(--border);
}
.pi-pf-status { font-weight: 600; font-size: 0.8rem; text-transform: none; }
.pi-pf-status--ok { color: #1a7f37; }
.pi-pf-status--provider_missing,
.pi-pf-status--auth_failed,
.pi-pf-status--actor_failed,
.pi-pf-status--policy_failed { color: #cf222e; }
td.pi-pf-detail { font-size: 0.82rem; word-break: break-word; max-width: 28rem; }
.toolbar { display: flex; flex-wrap: wrap; gap: 0.5rem; margin-bottom: 1rem; align-items: center; }
.toolbar--secondary { margin-bottom: 0.65rem; }
.toolbar form { display: inline; margin: 0; }
.tabbar { display: flex; flex-wrap: wrap; gap: 0.4rem; margin-bottom: 0.9rem; }
.tabbar .btn { font-size: 0.82rem; }
.tab-panel { margin-top: 0.75rem; }
.graph-controls {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  margin-bottom: 0.7rem;
}
.graph-render {
  margin-top: 0.7rem;
  padding: 0.8rem;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: rgba(127,127,127,0.06);
  overflow: auto;
}
.sz-tool-pre {
  margin: 1rem 0 0;
  padding: 1rem;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: rgba(127,127,127,0.06);
  font-size: 0.8rem;
  line-height: 1.45;
  white-space: pre-wrap;
  word-break: break-word;
  overflow-x: auto;
}
.btn {
  display: inline-block;
  padding: 0.45rem 0.85rem;
  font: inherit;
  font-size: 0.875rem;
  font-weight: 600;
  border-radius: 8px;
  border: 1px solid var(--border);
  cursor: pointer;
  background: var(--surface);
  color: var(--text);
  text-decoration: none;
}
.btn-primary { background: var(--accent); color: #fff; border-color: transparent; }
.btn-primary:hover { background: var(--accent-hover); }
.btn-danger { background: var(--danger); color: #fff; border-color: transparent; }
.btn-sm { padding: 0.3rem 0.55rem; font-size: 0.8rem; }
.table-wrap { overflow-x: auto; margin-top: 0.5rem; }
table.sz { width: 100%; border-collapse: collapse; font-size: 0.82rem; }
table.sz th, table.sz td {
  border: 1px solid var(--border);
  padding: 0.5rem 0.6rem;
  text-align: left;
  vertical-align: top;
}
table.sz th { background: rgba(127,127,127,0.08); font-weight: 600; }
table.sz td.targets { max-width: 14rem; word-break: break-word; }
table.sz td.actions { white-space: nowrap; }
table.sz td.actions form { display: inline; margin-right: 0.25rem; }
/* Secret → targets flow (dashboard): one arrow per target, grouped by provider/kind */
.flow-list { display: flex; flex-direction: column; gap: 1rem; margin-top: 0.5rem; }
.sync-legend {
  font-size: 0.78rem;
  color: var(--muted);
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.65rem 1rem;
  margin: 0 0 0.75rem;
}
.sync-legend__i {
  display: inline-block;
  width: 1.6rem;
  height: 4px;
  border-radius: 2px;
  vertical-align: middle;
  margin-right: 0.25rem;
}
.sync-legend__i--synced { background: var(--flow-synced); }
.sync-legend__i--pending { background: var(--flow-pending); }
.sync-legend__i--drift { background: var(--flow-drift); }
.sz-flow {
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 1rem 1.15rem;
  background: rgba(127,127,127,0.05);
  box-shadow: 0 1px 0 rgba(0,0,0,.04);
}
.sz-flow__top {
  display: flex;
  align-items: flex-start;
  gap: 1rem;
  min-width: 0;
}
.sz-flow__source {
  flex: 0 0 auto;
  min-width: 10.5rem;
  max-width: 17rem;
  padding: 0.65rem 0.85rem;
  border-radius: 10px;
  border: 1px solid var(--border);
  background: var(--surface);
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}
.sz-flow__name { font-weight: 700; font-size: 0.95rem; letter-spacing: -0.02em; word-break: break-word; }
.sz-flow__kind code { font-size: 0.78rem; color: var(--muted); }
.sz-flow__source-meta {
  margin-top: 0.2rem;
  padding-top: 0.45rem;
  border-top: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  font-size: 0.76rem;
  color: var(--muted);
}
.sz-flow__source-meta strong { color: var(--text); font-weight: 600; }
.sz-flow__source-actions {
  margin-top: 0.3rem;
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
}
.sz-flow__source-actions form { display: inline; margin: 0; }
.sz-flow__right {
  flex: 1 1 50%;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}
.sz-flow__group {
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 0.55rem 0.65rem 0.65rem;
  background: rgba(127,127,127,0.04);
}
.sz-flow__group--empty {
  color: var(--muted);
  font-style: italic;
  font-size: 0.85rem;
}
.sz-flow__group-badge {
  font-size: 0.7rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--muted);
  margin-bottom: 0.4rem;
}
.sz-flow__group-badge code { font-size: inherit; font-weight: 700; text-transform: none; letter-spacing: 0; }
.sz-flow__group-inner { display: flex; flex-direction: column; gap: 0.4rem; }
.sz-flow__lane {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
  min-width: 0;
}
.sz-flow__arrow {
  flex: 0 0 clamp(2.25rem, 12vw, 4.5rem);
  height: 4px;
  border-radius: 2px;
  position: relative;
  margin-top: 0.55rem;
}
.sz-flow__arrow::after {
  content: "";
  position: absolute;
  right: -1px;
  top: 50%;
  transform: translateY(-50%);
  border: 5px solid transparent;
}
.sz-flow__arrow--synced { background: var(--flow-synced); }
.sz-flow__arrow--synced::after { border-left: 8px solid var(--flow-synced); }
.sz-flow__arrow--pending { background: var(--flow-pending); }
.sz-flow__arrow--pending::after { border-left: 8px solid var(--flow-pending); }
.sz-flow__arrow--drift { background: var(--flow-drift); }
.sz-flow__arrow--drift::after { border-left: 8px solid var(--flow-drift); }
.sz-flow__dest-wrap {
  flex: 1 1 auto;
  min-width: 0;
  padding: 0.4rem 0.6rem;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: var(--surface);
}
.sz-flow__dest-text {
  font-size: 0.82rem;
  word-break: break-word;
  margin: 0;
}
.sz-lane-details {
  margin: 0.4rem 0 0;
  padding: 0;
  list-style: none;
  font-size: 0.76rem;
  color: var(--muted);
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}
.sz-lane-details li {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 0.35rem;
  line-height: 1.35;
}
.sz-lane-details .sz-lane-details__k {
  font-weight: 600;
  color: var(--text);
  flex: 0 0 auto;
}
.sz-lane-details code {
  font-size: 0.74rem;
  word-break: break-word;
  color: var(--text);
}
.sz-lane-force {
  margin: 0.45rem 0 0;
}
.sz-lane-force .btn-sm { font-size: 0.72rem; padding: 0.22rem 0.45rem; }
.sz-ai {
  margin-top: 0.35rem;
  padding-top: 0.45rem;
  border-top: 1px solid var(--border);
  font-size: 0.78rem;
  line-height: 1.45;
}
.sz-ai summary {
  cursor: pointer;
  font-weight: 600;
  color: var(--accent);
  list-style: none;
}
.sz-ai summary::-webkit-details-marker { display: none; }
.sz-ai summary::before { content: "▸ "; display: inline; }
.sz-ai[open] summary::before { content: "▾ "; }
.sz-ai__summary { margin-bottom: 0.35rem; }
.sz-ai p { margin: 0.35rem 0 0; color: var(--text); }
.sz-ai .sz-ai__prereq {
  margin: 0.45rem 0 0;
  padding-left: 1.1rem;
  color: var(--muted);
}
.sz-ai ol.sz-ai__steps {
  margin: 0.4rem 0 0;
  padding-left: 1.15rem;
}
.sz-ai ol.sz-ai__steps li { margin-bottom: 0.45rem; }
.sz-ai .sz-ai__step-title { font-weight: 600; color: var(--text); }
.sz-ai .sz-ai__muted { color: var(--muted); font-size: 0.92em; margin-top: 0.15rem; }
.sz-ai .sz-ai__extras { margin-top: 0.45rem; font-size: 0.74rem; color: var(--muted); }
.sz-ai a { color: var(--accent); }
@media (max-width: 720px) {
  .sz-flow__top { flex-direction: column; align-items: stretch; }
  .sz-flow__source { max-width: none; }
}
.notice-ok {
  padding: 0.65rem 1rem;
  border-radius: 8px;
  margin-bottom: 1rem;
  border: 1px solid #198754;
  background: rgba(25, 135, 84, 0.12);
  color: var(--text);
  font-size: 0.9rem;
}
.card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 1.75rem;
  box-shadow: var(--shadow);
}
h1 {
  font-size: 1.35rem;
  font-weight: 600;
  margin: 0 0 0.5rem;
  letter-spacing: -0.02em;
}
p.lead { color: var(--muted); font-size: 0.95rem; margin: 0 0 1.25rem; }
label {
  display: block;
  font-size: 0.875rem;
  font-weight: 500;
  margin-top: 1rem;
  margin-bottom: 0.35rem;
}
input[type="password"], input[type="text"] {
  width: 100%;
  padding: 0.6rem 0.75rem;
  font: inherit;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface);
  color: var(--text);
}
input:focus {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}
/* Full-width primary CTA for simple forms only (login, legacy submit). Dashboard/toolbar
   buttons use .btn / .btn-sm; without :not(.btn), this rule's specificity beats .btn-sm and
   made Sync larger and blue while Set value / Rotate stayed outline style. */
button[type="submit"]:not(.btn) {
  margin-top: 1.5rem;
  width: 100%;
  padding: 0.65rem 1rem;
  font: inherit;
  font-weight: 600;
  color: #fff;
  background: var(--accent);
  border: none;
  border-radius: 8px;
  cursor: pointer;
}
button[type="submit"]:not(.btn):hover { background: var(--accent-hover); }
.alert {
  padding: 0.75rem 1rem;
  border-radius: 8px;
  font-size: 0.9rem;
  margin-bottom: 1rem;
  border: 1px solid var(--border);
  background: rgba(176, 42, 55, 0.08);
  color: var(--danger);
}
footer { margin-top: 2rem; font-size: 0.8rem; color: var(--muted); text-align: center; }
"""

TEMPLATES = {
    "base.html": """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>{{ title }}</title>
  <style>"""
    + _BASE_STYLE
    + """</style>
</head>
<body>
  <main>
    <div class="card">
      {% block body %}{% endblock %}
    </div>
  </main>
  <footer>SecretZero · values stay in this process · not logged</footer>
</body>
</html>
""",
    "login.html": """
{% extends "base.html" %}
{% block body %}
  <h1>{{ title }}</h1>
  <p class="lead">Enter the one-time access token from the operator to open the dashboard.</p>
  {% if auth_error %}
  <div class="alert" role="alert">{{ auth_error }}</div>
  {% endif %}
  {% if bootstrap_consumed %}
  <div class="alert" role="alert">The access link was already used. Run <code>secretzero web</code> again for a new token.</div>
  {% else %}
  <form method="post" action="/auth" autocomplete="off">
    <label for="access_token">Access token</label>
    <input id="access_token" name="access_token" type="password" required autocomplete="off"/>
    <button type="submit">Continue</button>
  </form>
  {% endif %}
{% endblock %}
""",
    "form.html": """
{% extends "base.html" %}
{% block body %}
  <h1>{{ title }}</h1>
  {% if secret_names %}
  <p class="lead">Submit values for pending secrets. They are sent only to this CLI process.</p>
  {% else %}
  <p class="lead">No secrets currently require manual values. Submit to run sync with the current manifest.</p>
  {% endif %}
  {% if error_message %}
  <div class="alert" role="alert">{{ error_message }}</div>
  {% endif %}
  <form method="post" action="/submit" autocomplete="off">
    <input type="hidden" name="csrf_token" value="{{ csrf_token }}"/>
    {% for name in secret_names %}
    <label for="f-{{ name }}">{{ name }}</label>
    <input id="f-{{ name }}" name="{{ name }}" type="password" required autocomplete="off"/>
    {% endfor %}
    <button type="submit">{% if secret_names %}Submit and sync{% else %}Run sync{% endif %}</button>
  </form>
{% endblock %}
""",
    "success.html": """
{% extends "base.html" %}
{% block body %}
  <h1>{{ title }}</h1>
  <p class="lead">{% if dry_run %}Dry run complete. No changes were written.{% else %}Secrets were applied and the server is shutting down. You can close this tab.{% endif %}</p>
{% endblock %}
""",
    "error.html": """
{% extends "base.html" %}
{% block body %}
  <h1>{{ title }}</h1>
  <div class="alert" role="alert">{{ message }}</div>
  <p class="lead"><a href="/">Return to access</a></p>
{% endblock %}
""",
    "agent_instructions_partial.html": """
{% if agent_instructions %}
<details class="sz-ai">
  <summary class="sz-ai__summary">Agent instructions</summary>
  <p>{{ agent_instructions.summary }}</p>
  {% if agent_instructions.prerequisites %}
  <ul class="sz-ai__prereq">
    {% for p in agent_instructions.prerequisites %}
    <li>{{ p }}</li>
    {% endfor %}
  </ul>
  {% endif %}
  <ol class="sz-ai__steps">
    {% for step in agent_instructions.steps %}
    <li>
      <div class="sz-ai__step-title">{{ step.action }}</div>
      <div class="sz-ai__muted">{{ step.description }}</div>
    </li>
    {% endfor %}
  </ol>
  <div class="sz-ai__extras">
    {% if agent_instructions.estimated_time %}<div>Est. time: {{ agent_instructions.estimated_time }}</div>{% endif %}
    {% if agent_instructions.automation_hint %}<div>Automation: {{ agent_instructions.automation_hint }}</div>{% endif %}
    {% if agent_instructions.fallback %}<div>Fallback: {{ agent_instructions.fallback }}</div>{% endif %}
    {% if agent_instructions.required_tools %}<div>Tools: {{ agent_instructions.required_tools | join(", ") }}</div>{% endif %}
    {% if agent_instructions.documentation_url %}<div><a href="{{ agent_instructions.documentation_url }}" rel="noopener noreferrer" target="_blank">Documentation</a></div>{% endif %}
  </div>
</details>
{% endif %}
""",
    "dashboard.html": """
{% extends "base.html" %}
{% block body %}
  <h1>{{ title }}</h1>
  <p class="lead">Manifest, lockfile metadata, and per-secret sync. Values are not logged by SecretZero.</p>
  {% if dry_run %}
  <div class="alert" role="alert">Dry-run mode: actions simulate only; lockfile is not written.</div>
  {% endif %}
  {% if notice %}
  <div class="notice-ok" role="status">{{ notice }}</div>
  {% endif %}
  {% if error %}
  <div class="alert" role="alert">{{ error }}</div>
  {% endif %}
  <nav class="tabbar" aria-label="Dashboard views">
    <a href="/dashboard?filter={{ list_filter }}&tab=dashboard&graph_view={{ graph_view }}&graph_type={{ graph_type }}{% if selected_environment %}&environment={{ selected_environment | uquote }}{% endif %}" class="btn btn-sm{% if current_tab == 'dashboard' %} btn-primary{% endif %}">Dashboard</a>
    <a href="/dashboard?filter={{ list_filter }}&tab=secretfile&graph_view={{ graph_view }}&graph_type={{ graph_type }}{% if selected_environment %}&environment={{ selected_environment | uquote }}{% endif %}" class="btn btn-sm{% if current_tab == 'secretfile' %} btn-primary{% endif %}">Secretfile (source)</a>
    <a href="/dashboard?filter={{ list_filter }}&tab=interpolated&graph_view={{ graph_view }}&graph_type={{ graph_type }}{% if selected_environment %}&environment={{ selected_environment | uquote }}{% endif %}" class="btn btn-sm{% if current_tab == 'interpolated' %} btn-primary{% endif %}">Manifest (interpolated)</a>
    <a href="/dashboard?filter={{ list_filter }}&tab=graph&graph_view={{ graph_view }}&graph_type={{ graph_type }}{% if selected_environment %}&environment={{ selected_environment | uquote }}{% endif %}" class="btn btn-sm{% if current_tab == 'graph' %} btn-primary{% endif %}">Graph</a>
  </nav>
  {% if current_tab == "dashboard" %}
  <div class="manifest-meta">
    <div><strong>Secretfile</strong> {{ manifest.secretfile_display }}</div>
    <div><strong>Lockfile synced</strong> {{ manifest.synced_at }}</div>
    <div><strong>Manifest hash (lock)</strong> {{ manifest.secretfile_hash }}</div>
    <div><strong>Var files</strong> {{ manifest.var_files }}</div>
    <div><strong>Environment</strong> {{ manifest.selected_environment }}</div>
    <div><strong>Resolved var files</strong> {{ manifest.resolved_var_files }}</div>
    <div><strong>Target profile</strong> {{ manifest.resolved_target_profile }}</div>
  </div>
  {% if manifest.provider_rows %}
  <div class="manifest-meta" style="margin-top:0.5rem;">
    <div><strong>Provider identity</strong> <span style="font-weight:400;">— who your configured credentials resolve to (no secret values shown)</span></div>
    <div class="table-wrap" style="margin-top:0.5rem;">
      <table class="sz" role="table" aria-label="Provider authentication identity">
        <thead><tr><th>Provider</th><th>Kind</th><th>Status</th><th>Identity</th></tr></thead>
        <tbody>
          {% for p in manifest.provider_rows %}
          <tr>
            <td><strong>{{ p.alias }}</strong></td>
            <td><code>{{ p.kind }}</code></td>
            <td><span class="pi-status pi-status--{{ p.status }}">{{ p.status }}</span></td>
            <td class="pi-ident">{{ p.primary }}{% if p.secondary %}<br/><span style="font-size:0.92em;opacity:0.9;">{{ p.secondary }}</span>{% endif %}</td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
    </div>
  </div>
  {% endif %}
  {% elif current_tab == "secretfile" %}
  <section class="tab-panel" aria-label="Secretfile source">
    <p class="lead" style="margin-bottom:0.6rem;">Raw <code>Secretfile.yml</code> on disk for this session (placeholders such as <code>${VAR}</code> or <code>{{ '{{' }} var.* }}</code> are not expanded here).</p>
    <pre class="sz-tool-pre">{{ secretfile_text }}</pre>
  </section>
  {% elif current_tab == "interpolated" %}
  <section class="tab-panel" aria-label="Interpolated manifest">
    <p class="lead" style="margin-bottom:0.6rem;">
      Same output semantics as <code>secretzero render</code> for the selected environment: merged <code>variables:</code> from <code>Secretfile.yml</code> plus resolved <code>.szvar</code> files (see <strong>Resolved var files</strong> on the Dashboard), then <code>${VAR}</code> and Jinja-style <code>{{ '{{' }} var.* }}</code> interpolation everywhere except <code>agent_instructions</code> (those templates still use <code>{{ '{{' }} secret_name }}</code> / <code>target</code> and are expanded per secret at sync time).
    </p>
    <div class="alert" role="note" style="margin-bottom:0.75rem;">
      This view can include literal static values from your manifest and var files. Treat it like source code containing secrets; avoid screenshots or shared links when the server is reachable beyond your machine.
    </div>
    <pre class="sz-tool-pre">{{ interpolated_manifest_yaml }}</pre>
  </section>
  {% elif current_tab == "graph" %}
  <section class="tab-panel" aria-label="Generated graph view">
    <div class="graph-controls">
      <a href="/dashboard?filter={{ list_filter }}&tab=graph&graph_view=mermaid&graph_type={{ graph_type }}{% if selected_environment %}&environment={{ selected_environment | uquote }}{% endif %}" class="btn btn-sm{% if graph_view == 'mermaid' %} btn-primary{% endif %}">Mermaid</a>
      <a href="/dashboard?filter={{ list_filter }}&tab=graph&graph_view=json&graph_type={{ graph_type }}{% if selected_environment %}&environment={{ selected_environment | uquote }}{% endif %}" class="btn btn-sm{% if graph_view == 'json' %} btn-primary{% endif %}">Generated graph (JSON)</a>
      {% if graph_view == "mermaid" %}
      <a href="/dashboard?filter={{ list_filter }}&tab=graph&graph_view=mermaid&graph_type=flow{% if selected_environment %}&environment={{ selected_environment | uquote }}{% endif %}" class="btn btn-sm{% if graph_type == 'flow' %} btn-primary{% endif %}">Flow</a>
      <a href="/dashboard?filter={{ list_filter }}&tab=graph&graph_view=mermaid&graph_type=detailed{% if selected_environment %}&environment={{ selected_environment | uquote }}{% endif %}" class="btn btn-sm{% if graph_type == 'detailed' %} btn-primary{% endif %}">Detailed</a>
      <a href="/dashboard?filter={{ list_filter }}&tab=graph&graph_view=mermaid&graph_type=architecture{% if selected_environment %}&environment={{ selected_environment | uquote }}{% endif %}" class="btn btn-sm{% if graph_type == 'architecture' %} btn-primary{% endif %}">Architecture</a>
      <a href="/dashboard?filter={{ list_filter }}&tab=graph&graph_view=mermaid&graph_type=destination{% if selected_environment %}&environment={{ selected_environment | uquote }}{% endif %}" class="btn btn-sm{% if graph_type == 'destination' %} btn-primary{% endif %}">Destination</a>
      {% endif %}
    </div>
    {% if graph_view == "mermaid" %}
    <div class="graph-render">
      {% if mermaid_source %}
      <pre class="mermaid">{{ mermaid_source }}</pre>
      {% else %}
      <pre class="sz-tool-pre">Mermaid output unavailable (Secretfile path is required).</pre>
      {% endif %}
    </div>
    <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
    <script>
      if (window.mermaid) {
        window.mermaid.initialize({ startOnLoad: true, securityLevel: "loose" });
      }
    </script>
    {% else %}
    <pre class="sz-tool-pre">{{ graph_json }}</pre>
    {% endif %}
  </section>
  {% endif %}
  {% if current_tab == "dashboard" %}
  {% if manifest.identity_preflight and manifest.identity_preflight.has_policies and (manifest.identity_preflight.preflight_error or not manifest.identity_preflight.all_ok) %}
  <div class="manifest-meta identity-preflight-wrap" style="margin-top:0.5rem;">
    <div><strong>Authentication vs identity policies</strong>
      <span style="font-weight:400;"> — live check using each provider’s <code>get_actor_info()</code> (same rules as sync)</span>
    </div>
    <div class="identity-preflight {% if manifest.identity_preflight.preflight_error %}identity-preflight--bad{% elif manifest.identity_preflight.has_policies %}{% if manifest.identity_preflight.all_ok %}identity-preflight--ok{% else %}identity-preflight--bad{% endif %}{% else %}identity-preflight--neutral{% endif %}" role="status">
      {{ manifest.identity_preflight.headline }}
    </div>
    {% if manifest.identity_preflight.rows %}
    <div class="table-wrap" style="margin-top:0.5rem;">
      <table class="sz" role="table" aria-label="Provider identity policy check results">
        <thead><tr><th>Policy</th><th>Provider</th><th>Result</th><th>Detail</th></tr></thead>
        <tbody>
          {% for it in manifest.identity_preflight.rows %}
          <tr>
            <td><code>{{ it.policy_name }}</code></td>
            <td><code>{{ it.provider_alias }}</code></td>
            <td><span class="pi-pf-status pi-pf-status--{{ it.status }}">{{ it.status }}</span></td>
            <td class="pi-pf-detail">{% if it.detail %}{{ it.detail }}{% else %}—{% endif %}</td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
    </div>
    {% endif %}
  </div>
  {% endif %}
  <div class="toolbar">
    {% if environment_profiles %}
    <form method="get" action="/dashboard">
      <input type="hidden" name="filter" value="{{ list_filter }}"/>
      <input type="hidden" name="tab" value="{{ current_tab }}"/>
      <input type="hidden" name="graph_view" value="{{ graph_view }}"/>
      <input type="hidden" name="graph_type" value="{{ graph_type }}"/>
      <label for="environment" style="font-size:0.85rem;color:var(--muted);">Environment</label>
      <select id="environment" name="environment" onchange="this.form.submit()">
        <option value="">(default)</option>
        {% for env_name in environment_profiles %}
        <option value="{{ env_name }}" {% if selected_environment == env_name %}selected{% endif %}>{{ env_name }}</option>
        {% endfor %}
      </select>
    </form>
    {% endif %}
    <form method="post" action="/action/sync-all">
      <input type="hidden" name="csrf_token" value="{{ csrf_token }}"/>
      <input type="hidden" name="list_filter" value="{{ list_filter }}"/>
      <input type="hidden" name="environment" value="{{ selected_environment }}"/>
      <button type="submit" class="btn btn-primary btn-sm">Sync all secrets</button>
    </form>
    <form method="post" action="/logout">
      <input type="hidden" name="csrf_token" value="{{ csrf_token }}"/>
      <button type="submit" class="btn btn-sm">Log out</button>
    </form>
    <form method="post" action="/shutdown" onsubmit="return confirm('Shut down the web server? Unsaved work is already written when actions succeed.');">
      <input type="hidden" name="csrf_token" value="{{ csrf_token }}"/>
      <input type="hidden" name="list_filter" value="{{ list_filter }}"/>
      <input type="hidden" name="environment" value="{{ selected_environment }}"/>
      <button type="submit" class="btn btn-danger btn-sm">Shut down server</button>
    </form>
  </div>
  <div class="toolbar toolbar--secondary toolbar--filters">
    <span style="font-size:0.85rem;color:var(--muted);">Show</span>
    <a href="/dashboard?filter=all&tab={{ current_tab }}&graph_view={{ graph_view }}&graph_type={{ graph_type }}{% if selected_environment %}&environment={{ selected_environment | uquote }}{% endif %}" class="btn btn-sm{% if list_filter == 'all' %} btn-primary{% endif %}">All ({{ row_total }})</a>
    <a href="/dashboard?filter=unsynced&tab={{ current_tab }}&graph_view={{ graph_view }}&graph_type={{ graph_type }}{% if selected_environment %}&environment={{ selected_environment | uquote }}{% endif %}" class="btn btn-sm{% if list_filter == 'unsynced' %} btn-primary{% endif %}">Unsynced only ({{ unsynced_count }})</a>
  </div>
  <div class="toolbar toolbar--secondary">
    <span style="font-size:0.85rem;color:var(--muted);">Tools</span>
    {% if tools_available %}
    <form method="post" action="/action/validate-manifest">
      <input type="hidden" name="csrf_token" value="{{ csrf_token }}"/>
      <input type="hidden" name="list_filter" value="{{ list_filter }}"/>
      <input type="hidden" name="environment" value="{{ selected_environment }}"/>
      <button type="submit" class="btn btn-sm">Validate manifest</button>
    </form>
    <form method="post" action="/action/import-all">
      <input type="hidden" name="csrf_token" value="{{ csrf_token }}"/>
      <input type="hidden" name="list_filter" value="{{ list_filter }}"/>
      <input type="hidden" name="environment" value="{{ selected_environment }}"/>
      <button type="submit" class="btn btn-sm">Refresh</button>
    </form>
    {% else %}
    <span style="font-size:0.85rem;color:var(--muted);">Validate / Refresh need the Secretfile path (normal CLI <code>secretzero web</code>).</span>
    {% endif %}
  </div>
  <p class="sync-legend" role="note" aria-label="Per-target arrow colors">
    <span><span class="sync-legend__i sync-legend__i--synced" aria-hidden="true"></span> Synced</span>
    <span><span class="sync-legend__i sync-legend__i--pending" aria-hidden="true"></span> Pending</span>
    <span><span class="sync-legend__i sync-legend__i--drift" aria-hidden="true"></span> Drift</span>
  </p>
  <div class="flow-list" role="list" aria-label="Secrets and deployment targets">
    {% for row in rows %}
    <article class="sz-flow" role="listitem">
      <div class="sz-flow__top">
        <div class="sz-flow__source">
          <div class="sz-flow__name">{{ row.name }}</div>
          <div class="sz-flow__kind"><code>{{ row.kind }}</code></div>
          <div class="sz-flow__source-meta">
            <span><strong>Value hash</strong> <code>{{ row.hash_preview }}</code></span>
            <span><strong>Updated</strong> {{ row.updated_at }}</span>
            <div class="sz-flow__source-actions">
              {% if row.can_set_value %}
              <a class="btn btn-sm" href="/secret/{{ row.name | uquote }}/edit?filter={{ list_filter }}{% if selected_environment %}&environment={{ selected_environment | uquote }}{% endif %}">Update</a>
              {% endif %}
              <form method="post" action="/action/sync-secret">
                <input type="hidden" name="csrf_token" value="{{ csrf_token }}"/>
                <input type="hidden" name="list_filter" value="{{ list_filter }}"/>
                <input type="hidden" name="environment" value="{{ selected_environment }}"/>
                <input type="hidden" name="secret_name" value="{{ row.name }}"/>
                <button type="submit" class="btn btn-sm">Sync</button>
              </form>
              <form method="post" action="/action/import-secret">
                <input type="hidden" name="csrf_token" value="{{ csrf_token }}"/>
                <input type="hidden" name="list_filter" value="{{ list_filter }}"/>
                <input type="hidden" name="environment" value="{{ selected_environment }}"/>
                <input type="hidden" name="secret_name" value="{{ row.name }}"/>
                <button type="submit" class="btn btn-sm">Refresh</button>
              </form>
              {% if row.can_web_rotate %}
                {% if row.can_set_value %}
              <a class="btn btn-sm" href="/secret/{{ row.name | uquote }}/edit?filter={{ list_filter }}{% if selected_environment %}&environment={{ selected_environment | uquote }}{% endif %}">Rotate</a>
                {% else %}
              <form method="post" action="/action/rotate-secret">
                <input type="hidden" name="csrf_token" value="{{ csrf_token }}"/>
                <input type="hidden" name="list_filter" value="{{ list_filter }}"/>
                <input type="hidden" name="environment" value="{{ selected_environment }}"/>
                <input type="hidden" name="secret_name" value="{{ row.name }}"/>
                <button type="submit" class="btn btn-sm">Rotate</button>
              </form>
                {% endif %}
              {% endif %}
            </div>
          </div>
          {% with agent_instructions=row.agent_instructions %}
          {% include "agent_instructions_partial.html" %}
          {% endwith %}
        </div>
        <div class="sz-flow__right" aria-label="Targets for {{ row.name }}">
          {% if row.has_targets %}
          {% for group in row.target_groups %}
          <div class="sz-flow__group">
            <div class="sz-flow__group-badge"><span class="sz-flow__group-provider">{{ group.provider }}</span> · <code>{{ group.kind }}</code></div>
            <div class="sz-flow__group-inner">
              {% for item in group.lanes %}
              <div class="sz-flow__lane">
                <div class="sz-flow__arrow sz-flow__arrow--{{ item.sync_state }}" role="img" title="{{ item.arrow_title }}"></div>
                <div class="sz-flow__dest-wrap">
                  <p class="sz-flow__dest-text"><code>{{ item.dest }}</code></p>
                  {% if item.details %}
                  <ul class="sz-lane-details" aria-label="Storage details">
                    {% for d in item.details %}
                    <li><span class="sz-lane-details__k">{{ d.label }}</span> <code>{{ d.value }}</code></li>
                    {% endfor %}
                  </ul>
                  {% endif %}
                  {% if item.can_force_resync %}
                  <form class="sz-lane-force" method="post" action="/action/force-sync-target">
                    <input type="hidden" name="csrf_token" value="{{ csrf_token }}"/>
                    <input type="hidden" name="list_filter" value="{{ list_filter }}"/>
                    <input type="hidden" name="environment" value="{{ selected_environment }}"/>
                    <input type="hidden" name="secret_name" value="{{ row.name }}"/>
                    <input type="hidden" name="target_id" value="{{ item.target_id }}"/>
                    <button type="submit" class="btn btn-sm" title="Write the current secret value to this target again">Force to target</button>
                  </form>
                  {% endif %}
                </div>
              </div>
              {% endfor %}
            </div>
          </div>
          {% endfor %}
          {% else %}
          <div class="sz-flow__group sz-flow__group--empty" role="presentation">No targets — sync will only update lock metadata.</div>
          {% endif %}
        </div>
      </div>
    </article>
    {% endfor %}
  </div>
  {% if not rows and row_total > 0 %}
  <p class="lead">No secrets match this filter. Try <a href="/dashboard?filter=all&tab={{ current_tab }}&graph_view={{ graph_view }}&graph_type={{ graph_type }}{% if selected_environment %}&environment={{ selected_environment | uquote }}{% endif %}">show all</a>.</p>
  {% elif not rows %}
  <p class="lead">No secrets are defined in this Secretfile.</p>
  {% endif %}
  {% if debug %}
  <section class="sz-debug-pane" style="margin-top:2rem;border-top:1px solid var(--border);padding-top:1rem;" aria-label="Debug log">
    <details open>
      <summary style="cursor:pointer;font-weight:600;">Debug log</summary>
      <p style="font-size:0.85rem;color:var(--muted);margin:0.5rem 0 0;">Structured sync output (targets, skip reasons, errors). Secret values are never included.</p>
      <pre class="sz-tool-pre" role="region" style="max-height:28rem;overflow:auto;">{{ debug_log_text or "(Run a sync action to populate this log.)" }}</pre>
    </details>
  </section>
  {% endif %}
  {% endif %}
{% endblock %}
""",
    "tool_result.html": """
{% extends "base.html" %}
{% block body %}
  <h1>{{ title }}</h1>
  <p class="lead"><a class="btn btn-sm" href="{{ back_href }}">← {{ back_label }}</a></p>
  <pre class="sz-tool-pre" role="region" aria-label="Command output">{{ tool_body }}</pre>
{% endblock %}
""",
    "secret_edit.html": """
{% extends "base.html" %}
{% block body %}
  <h1>{{ title }}</h1>
  <p class="lead">New value is merged as a static secret and synced to targets for <code>{{ secret_name }}</code>.</p>
  {{ operator_banner_html | safe }}
  {% if error_message %}
  <div class="alert" role="alert">{{ error_message }}</div>
  {% endif %}
  {% with agent_instructions=agent_instructions %}
  {% include "agent_instructions_partial.html" %}
  {% endwith %}
  <form method="post" action="/secret/{{ secret_name | uquote }}/apply" autocomplete="off" id="sz-static-edit-form">
    <input type="hidden" name="csrf_token" value="{{ csrf_token }}"/>
    <input type="hidden" name="list_filter" value="{{ list_filter }}"/>
    {% if structured %}
    <fieldset style="border:1px solid var(--border);padding:1rem;border-radius:6px;margin-top:1rem;">
      <legend style="font-weight:600;">Structured fields</legend>
      <p style="font-size:0.9rem;color:var(--muted);margin:0 0 0.75rem;">Enter each missing field (same order as <code>secretzero sync</code>), or paste a full JSON object below.</p>
      {% for row in dict_leaves %}
      <label for="sz-leaf-{{ loop.index0 }}"><strong>{{ secret_name }}</strong> — {{ row.label }}</label>
      <input id="sz-leaf-{{ loop.index0 }}" name="{{ row.field_name }}" type="password" autocomplete="off" required/>
      {% endfor %}
    </fieldset>
    <details style="margin-top:1rem;">
      <summary style="cursor:pointer;font-weight:600;">Paste full JSON instead</summary>
      <label for="sz-json-bulk" style="display:block;margin-top:0.75rem;">JSON object</label>
      <textarea id="sz-json-bulk" name="{{ json_field_name }}" rows="8" style="width:100%;font-family:ui-monospace,monospace;" placeholder="{}"></textarea>
      <p style="font-size:0.85rem;color:var(--muted);">If you provide JSON, per-field inputs can be left empty.</p>
    </details>
    <script>
    (function () {
      var form = document.getElementById("sz-static-edit-form");
      if (!form) return;
      form.addEventListener("submit", function () {
        var ta = form.querySelector("textarea[name='{{ json_field_name }}']");
        if (ta && ta.value && String(ta.value).trim() !== "") {
          form.querySelectorAll("fieldset input[type=password]").forEach(function (inp) {
            inp.removeAttribute("required");
          });
        }
      });
    })();
    </script>
    {% else %}
    <label for="value">New value</label>
    <input id="value" name="value" type="password" required autocomplete="off"/>
    {% endif %}
    <button type="submit" class="btn btn-primary" style="margin-top:1rem;width:auto;">Apply and sync</button>
  </form>
  <p style="margin-top:1.25rem;"><a href="/dashboard?filter={{ list_filter }}">← Back to manifest</a></p>
{% endblock %}
""",
    "stopped.html": """
{% extends "base.html" %}
{% block body %}
  <h1>{{ title }}</h1>
  <p class="lead">The web server has stopped. {% if dry_run %}No lockfile changes were persisted.{% else %}The lockfile was saved.{% endif %} You can close this tab.</p>
  <p class="lead"><a href="/">Sign in again</a> requires restarting <code>secretzero web</code> from the CLI.</p>
{% endblock %}
""",
}
