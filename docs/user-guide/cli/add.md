# secretzero add

Create or edit one secret's generator, optional value source, and targets.

`secretzero new` is an alias of `secretzero add`.

## Synopsis

```bash
secretzero add [NAME] [OPTIONS]
secretzero new [NAME] [OPTIONS]
```

## Description

`add` updates `Secretfile.yml` in place. On a terminal, omitting `--kind` and `--target` walks through:

1. The secrets already in the file.
2. Add a new secret or edit an existing one.
3. Generator kind (how the value is produced).
4. Optional value source (`source:` — file, env, secret_ref, or provider_read).
5. One or more targets (local file, cloud, or encrypted-in-git).

The command does not ask for secret values. Static-like generators (`static`, `azure_app_reg`, and other kinds that prompt like static) accept only `null` or a `${VAR}` placeholder. Enter the value later with `secretzero web` or `secretzero sync`.

Comments already in the Secretfile are kept. If the file does not exist, `add` creates it and adds a provider stub for each new target alias.

## Options

| Option | Description |
|--------|-------------|
| `NAME` | Secret name. Required unless you use `--interactive` or a terminal. |
| `--file`, `-f` | Secretfile path (default: `Secretfile.yml`) |
| `--kind`, `-k` | Generator kind |
| `--generator-config`, `-G` | `KEY=VALUE` generator option. Repeatable. |
| `--target`, `-t` | `provider=<alias>,kind=<kind>,<key>=<value>`. Repeatable. |
| `--source-kind` | `file`, `env`, `secret_ref`, `provider_read`, or `none` to clear a source |
| `--source-config` | `KEY=VALUE` source option. Repeatable. |
| `--source-optional` | Source may fail without failing sync |
| `--create` | Fail if the name already exists |
| `--edit` | Fail if the name is missing |
| `--replace-targets` | Replace targets when editing. Default appends new targets. |
| `--interactive` | Prompt even when stdin is not a terminal |
| `--yes`, `-y` | Skip the confirmation prompt |
| `--dry-run` | Validate and print JSON/text without writing |
| `--format` | `text` (default) or `json` |

JSON output lists the secret name, generator kind, source kind, and targets. It does not include generator config.

## Examples

### Interactive

```bash
secretzero add
secretzero new -f Secretfile.yml
```

### Create a generated password in a local env file

```bash
secretzero add db_password \
  --kind random_password \
  --generator-config length=32 \
  --target provider=local,kind=file,path=.env.local,format=dotenv,merge=true
```

### Edit a secret and append an AWS target

```bash
secretzero add db_password --edit \
  --kind random_password \
  --target provider=aws,kind=ssm_parameter,name=/app/db/password,type=SecureString
```

Missing provider aliases are added as ambient stubs (`providers.aws.kind: aws`).

### Static secret with an env placeholder

```bash
secretzero add api_key \
  --kind static \
  --generator-config 'value=${API_KEY}' \
  --source-kind env \
  --source-config name=API_KEY \
  --target provider=local,kind=file,path=.env,format=dotenv
```

### API

`POST /secrets` accepts the same fields (`name`, `kind`, `config`, `targets`, `source`, `mode`, `replace_targets`, `dry_run`). Plaintext static values return HTTP 400.

## Related commands

- [`create`](create.md) — starter Secretfile from a template
- [`validate`](validate.md) — check the file after editing
- [`sync`](sync.md) — generate values and write targets
- `secretzero catalog` — list generator and target kinds
