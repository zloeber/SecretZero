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
  max-width: 28rem;
  margin: 0 auto;
  padding: clamp(1.5rem, 4vw, 3rem) 1.25rem;
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
  <p class="lead">Enter the one-time access token from the operator to open the secure form.</p>
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
  <p class="lead">Submit values for pending secrets. They are sent only to this CLI process.</p>
  {% if error_message %}
  <div class="alert" role="alert">{{ error_message }}</div>
  {% endif %}
  <form method="post" action="/submit" autocomplete="off">
    <input type="hidden" name="csrf_token" value="{{ csrf_token }}"/>
    {% for name in secret_names %}
    <label for="f-{{ name }}">{{ name }}</label>
    <input id="f-{{ name }}" name="{{ name }}" type="password" required autocomplete="off"/>
    {% endfor %}
    <button type="submit">Submit and sync</button>
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
}
