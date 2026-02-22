# Including SecretZero CLI Demos in Documentation

This directory contains SVG recordings of SecretZero CLI usage. These animated SVGs can be embedded directly in Markdown documentation.

## Available Demo SVGs

### Basic Commands

**Help Command**
```markdown
![SecretZero Help](inc/demo-help.svg)
```

**Version Check**
```markdown
![SecretZero Version](inc/test-demo.svg)
```

### Configuration & Validation

**Validate Secretfile**
```markdown
![Validate Secretfile](inc/demo-validate.svg)
```

**View Status**
```markdown
![Check Status](inc/demo-status.svg)
```

### Discovery Commands

**List Providers**
```markdown
![List Providers](inc/demo-providers.svg)
```

**List Secret Types**
```markdown
![Secret Types](inc/demo-secret-types.svg)
```

### Operations

**Test Provider Connections**
```markdown
![Test Providers](inc/demo-test.svg)
```

**Visualize Graph**
```markdown
![Secret Graph](inc/demo-graph.svg)
```

**Initialize (Dry Run)**
```markdown
![Initialize](inc/demo-init.svg)
```

## Usage in MkDocs

For your MkDocs documentation, you can use:

```markdown
## Quick Start

See SecretZero in action:

![SecretZero Help](inc/demo-help.svg)

## Validating Your Configuration

Ensure your Secretfile is valid:

![Validate Configuration](inc/demo-validate.svg)
```

## Styling Options

### Full Width

```html
<div style="width: 100%;">
  <img src="inc/demo-help.svg" alt="SecretZero Help" style="width: 100%;">
</div>
```

### Centered

```html
<div align="center">
  <img src="inc/demo-help.svg" alt="SecretZero Help" width="800">
</div>
```

### With Caption

```html
<figure>
  <img src="inc/demo-validate.svg" alt="Validate Secretfile">
  <figcaption>Validating a Secretfile configuration</figcaption>
</figure>
```

## Regenerating Demos

To update all demos (e.g., after CLI changes):

```bash
# Via mise task
mise run demo:record

# Or directly
bash scripts/record-demos.sh
```

To regenerate a specific demo, edit `scripts/record-demos.sh` and call the specific function.

## File Locations

- **Scripts**: `scripts/record-demos.sh`
- **Demo Scripts**: `demos/*.sh` (generated during recording)
- **SVG Output**: `docs/inc/demo-*.svg`

## SVG Properties

- **Format**: Animated SVG
- **Terminal Size**: 100x30 characters
- **Theme**: window_frame template
- **Auto-play**: Yes (loops continuously)

## Tips

1. **File Size**: SVGs are optimized but still contain terminal data. Keep recordings brief.
2. **Timing**: Adjust sleep values in `scripts/record-demos.sh` to control playback speed.
3. **Terminal Size**: Modify `COLUMNS` and `LINES` exports to change dimensions.
4. **Theme**: Change `-t window_frame` to other termtosvg templates.

## Example Documentation Page

```markdown
# Getting Started with SecretZero

## Installation

```bash
pip install secretzero
```

## First Steps

Check the installation:

![Version Check](inc/test-demo.svg)

View available commands:

![Help Command](inc/demo-help.svg)

## Validating Your Secretfile

Create a `Secretfile.yml` and validate it:

![Validate](inc/demo-validate.svg)

## Listing Providers

Discover which secret providers are available:

![Providers](inc/demo-providers.svg)

## Checking Status

View the status of your secrets:

![Status](inc/demo-status.svg)
```

## CI/CD Integration

Add to your GitHub Actions workflow:

```yaml
- name: Generate CLI demos
  run: |
    mise install
    mise run demo:install
    mise run demo:record
    
- name: Commit updated demos
  run: |
    git config user.name "GitHub Actions"
    git config user.email "actions@github.com"
    git add docs/inc/demo-*.svg
    git diff --quiet && git diff --staged --quiet || git commit -m "Update CLI demos"
    git push
```
