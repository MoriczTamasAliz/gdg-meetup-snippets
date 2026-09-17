---
name: release
description: Release and rollback process for the ledger service — cut, approvals, migration safety, canary steps and rollback. Load when preparing a release, writing a migration, or responding to a bad deploy.
---

# Release

Deploys go out Tuesday and Thursday at 10:00 CET. Never Friday. The release
branch is cut Monday afternoon and needs two approvals, one from the on-call
engineer.

## Migrations

Run a dry-run against a production snapshot first. Migrations stay backwards
compatible for one release: never drop a column in the same release that stops
writing to it. Check the query plan for anything touching `postings`.

## Canary

5% for 30 minutes, then 50% for 30 minutes, then full. Post in `#ledger-deploys`
before and after.

## Rollback

`make rollback VERSION=<previous>`. Never hand-edit. The runbook is in Confluence
under Ledger / Operations / Runbook.

## Feature flags

Default off, removed within two releases. CI enforces the second part.
