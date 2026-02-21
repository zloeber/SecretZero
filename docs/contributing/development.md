# Development Setup

## Requirements

- Python 3.12+
- Optional extras: `secretzero[all,dev]`

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[all,dev]"
```

## Common Tasks

- Run tests: `pytest`
- Format: `ruff format .` and `black .`
- Lint: `ruff check .`
