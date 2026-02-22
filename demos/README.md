# SecretZero CLI Demo Recordings

This directory contains the script and tooling to record CLI demos and convert them to SVG format for embedding in documentation.

## Quick Start

```bash
# Record all demos (only needs Python 3)
mise run demo:record

# Or run directly
bash scripts/record-demos.sh
```

## What Gets Created

The script creates SVG files in `docs/inc/` for embedding in documentation:

- `demo-help.svg` - Help command output
- `demo-validate.svg` - Validating a Secretfile
- `demo-status.svg` - Checking secret status
- `demo-providers.svg` - Listing available providers
- `demo-secret-types.svg` - Listing secret generator types
- `demo-test.svg` - Testing provider connections
- `demo-graph.svg` - Visualization graph
- `demo-init.svg` - Initialization (dry-run)

## Using in Documentation

Include SVGs in your markdown files:

```markdown
![SecretZero Help](inc/demo-help.svg)
```

Or with HTML for more control:

```html
<img src="inc/demo-help.svg" alt="SecretZero Help" width="100%">
```

## How It Works

1. Captures CLI command output as text (with `$ command` prompt)
2. Strips ANSI color codes for clean rendering
3. Generates static SVG with terminal-like styling
4. No animation, no external dependencies beyond Python 3

## Requirements

- **Python 3** - For SVG generation (already included via mise tools)
- **secretzero** - Installed in development mode

## Manual Recording

To manually record and convert a single demo:

```bash
cd /path/to/SecretZero

# Capture output
{
    echo "$ secretzero --help"
    secretzero --help 2>&1
} > demos/mycommand.txt

# Convert to SVG using the record script's Python code
python3 - demos/mycommand.txt docs/inc/mycommand.svg << 'PYEOF'
import html, re, sys

output_file = sys.argv[1]
svg_file = sys.argv[2]

with open(output_file, 'r') as f:
    output = f.read()

ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
output_clean = ansi_escape.sub('', output)
lines = output_clean.split('\n')

max_len = max((len(line) for line in lines), default=80)
num_lines = len(lines)
char_w, char_h, pad = 8.5, 18, 30
svg_w = max(max_len * char_w + pad * 2, 600)
svg_h = num_lines * char_h + pad * 2

svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {svg_w} {svg_h}" width="{int(svg_w)}" height="{int(svg_h)}">
<defs><style>
.term {{ font-family: Monaco, monospace; font-size: 14px; line-height: {char_h}px; }}
.prompt {{ fill: #50fa7b; font-weight: bold; }}
.output {{ fill: #f8f8f2; }}
</style></defs>
<rect width="100%" height="100%" fill="#282a36" rx="8"/>
<g class="term">
'''

y = pad + 14
for line in lines:
    esc = html.escape(line)
    cls = 'prompt' if line.startswith('$') else 'output'
    svg += f'<text x="{pad}" y="{y}" class="{cls}">{esc}</text>\n'
    y += char_h

svg += '</g></svg>'

with open(svg_file, 'w') as f:
    f.write(svg)
PYEOF
```

## Configuration

Edit `scripts/record-demos.sh` to:
- Add new demos
- Adjust SVG dimensions (char_w, char_h, padding)
- Change color scheme (CSS in SVG template)

## Troubleshooting

**secretzero not found:**
```bash
pip install -e .
# or
uv sync --all-extras
```

**Python not found:**
```bash
mise install python
```

## Integration with CI/CD

Add to your CI pipeline to regenerate demos on changes:

```yaml
- name: Record demos
  run: |
    pip install -e .
    bash scripts/record-demos.sh
```
