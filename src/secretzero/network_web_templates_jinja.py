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
  max-width: 52rem;
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
.toolbar { display: flex; flex-wrap: wrap; gap: 0.5rem; margin-bottom: 1rem; align-items: center; }
.toolbar form { display: inline; margin: 0; }
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
button[type="submit"] {
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
button[type="submit"]:hover { background: var(--accent-hover); }
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
  <div class="manifest-meta">
    <div><strong>Secretfile</strong> {{ manifest.secretfile_display }}</div>
    <div><strong>Lockfile synced</strong> {{ manifest.synced_at }}</div>
    <div><strong>Manifest hash (lock)</strong> {{ manifest.secretfile_hash }}</div>
    <div><strong>Var files</strong> {{ manifest.var_files }}</div>
  </div>
  <div class="toolbar">
    <form method="post" action="/action/sync-all">
      <input type="hidden" name="csrf_token" value="{{ csrf_token }}"/>
      <button type="submit" class="btn btn-primary btn-sm">Sync all secrets</button>
    </form>
    <form method="post" action="/logout">
      <input type="hidden" name="csrf_token" value="{{ csrf_token }}"/>
      <button type="submit" class="btn btn-sm">Log out</button>
    </form>
    <form method="post" action="/shutdown" onsubmit="return confirm('Shut down the web server? Unsaved work is already written when actions succeed.');">
      <input type="hidden" name="csrf_token" value="{{ csrf_token }}"/>
      <button type="submit" class="btn btn-danger btn-sm">Shut down server</button>
    </form>
  </div>
  <div class="table-wrap">
    <table class="sz" aria-describedby="manifest-heading">
      <thead>
        <tr>
          <th>Secret</th>
          <th>Kind</th>
          <th>Targets</th>
          <th>Value hash</th>
          <th>Updated</th>
          <th>Last rotated</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        {% for row in rows %}
        <tr>
          <td><strong>{{ row.name }}</strong></td>
          <td><code>{{ row.kind }}</code></td>
          <td class="targets">{% for t in row.targets %}{{ t }}{% if not loop.last %}<br/>{% endif %}{% endfor %}</td>
          <td><code>{{ row.hash_preview }}</code></td>
          <td>{{ row.updated_at }}</td>
          <td>{{ row.last_rotated }}{% if row.rotation_count %} (×{{ row.rotation_count }}){% endif %}</td>
          <td class="actions">
            {% if row.can_set_value %}
            <a class="btn btn-sm" href="/secret/{{ row.name | uquote }}/edit">Set value</a>
            {% endif %}
            <form method="post" action="/action/sync-secret">
              <input type="hidden" name="csrf_token" value="{{ csrf_token }}"/>
              <input type="hidden" name="secret_name" value="{{ row.name }}"/>
              <button type="submit" class="btn btn-sm">Sync</button>
            </form>
            <form method="post" action="/action/rotate-secret">
              <input type="hidden" name="csrf_token" value="{{ csrf_token }}"/>
              <input type="hidden" name="secret_name" value="{{ row.name }}"/>
              <button type="submit" class="btn btn-sm">Rotate</button>
            </form>
          </td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
  {% if not rows %}
  <p class="lead">No secrets are defined in this Secretfile.</p>
  {% endif %}
{% endblock %}
""",
    "secret_edit.html": """
{% extends "base.html" %}
{% block body %}
  <h1>{{ title }}</h1>
  <p class="lead">New value is merged as a static secret and synced to targets for <code>{{ secret_name }}</code>.</p>
  {% if error_message %}
  <div class="alert" role="alert">{{ error_message }}</div>
  {% endif %}
  <form method="post" action="/secret/{{ secret_name | uquote }}/apply" autocomplete="off">
    <input type="hidden" name="csrf_token" value="{{ csrf_token }}"/>
    <label for="value">New value</label>
    <input id="value" name="value" type="password" required autocomplete="off"/>
    <button type="submit" class="btn btn-primary" style="margin-top:1rem;width:auto;">Apply and sync</button>
  </form>
  <p style="margin-top:1.25rem;"><a href="/dashboard">← Back to manifest</a></p>
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
