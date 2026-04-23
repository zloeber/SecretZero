# Workflow Visuals

This page captures common SecretZero workflow views from the web graph/dashboard experience.

Use these visuals as a quick orientation before diving into command-level docs.

## Secret Graph Overview

![Secret graph overview](../inc/sz-graph-1.png)

This view shows the top-level relationship between generated/resolved secrets and their targets.

## Sync State Across Targets

![Sync state graph](../inc/sz-graph-2.png)

Edges reflect target sync state so you can quickly identify what is already synced versus pending/drifted.

## Destination-Centric View

![Destination-centric graph](../inc/sz-graph-3.png)

This view groups writes by destination so operators can confirm where each secret instance lands.

## Related Docs

- [How sync works](../user-guide/cli/sync.md)
- [Agent-guided sync](../user-guide/agent-sync.md)
- [Graph command reference](../user-guide/cli/graph.md)
