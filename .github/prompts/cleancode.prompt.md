---
name: cleancode
description: Clean the codebase of unit test and lint issues
---
You are tasked with cleaning the codebase of unit test and lint issues. Follow these best practices to ensure a clean and maintainable codebase:

Run the following commands to address unit test and lint issues:

```bash
# Repeat unit tests until all pass
task test
# Automatically format and fix lint issues
task format lint:fix
# Check for remaining lint issues, resolve manually if needed
task lint
```

Run this command to ensure all code builds successfully:
```bash
task build
```
Run this command to check for and resolve any security issues:

```bash
task security:check
```

Run this command to update the root Secretfile.schema.json file:
```bash
task schema:update
```

Build the documentation to ensure there are no issues. Ensure you have resolved any issues or missing links:
```bash
# Check for documentation issues
task docs:build
```
