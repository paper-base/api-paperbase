# Backup and Restore Runbook (BASE + WAL PITR)

This runbook describes the production backup architecture for PostgreSQL using BASE backups plus WAL archiving (PITR) on S3-compatible storage (Cloudflare R2).

## Required Environment Variables

- `DIRECT_DATABASE_URL` (backup source, direct Postgres connection)
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_DEFAULT_REGION` (R2 commonly uses `auto`)
- `AWS_S3_ENDPOINT_URL`
- `BACKUP_S3_BUCKET`
- `BACKUP_PREFIX_BASE` (default: `backups/base`)
- `BACKUP_PREFIX_WAL` (default: `backups/wal`)
- `TZ` (optional process timezone hint)

Compatibility notes:
- `BACKUP_PREFIX_FULL` is accepted as fallback for `BACKUP_PREFIX_BASE` during migration.
- `BACKUP_CRON_FULL` is accepted as fallback for `BACKUP_CRON_BASE` during migration.

Runtime requirement:
- Celery worker must consume the `backup` queue in production.

## Storage Layout

- BASE backups: `backups/base/YYYY/MM/DD/base_<timestamp>.tar.gz`
- WAL archives: `backups/wal/<wal_file_name>`
- Latest pointer: `meta/latest.json`

Example `meta/latest.json`:

```json
{
  "latest_base": "backups/base/2026/04/24/base_20260424_020000.tar.gz",
  "timestamp": "2026-04-24T02:00:13Z"
}
```

## Backup Flow

1. Celery Beat enqueues the base backup task on the `backup` queue.
2. Celery Worker runs `backup/backup-full.sh` (kept as entrypoint, now performs base backups).
3. Script runs `pg_basebackup -D - -Ft -z -X fetch` and writes `base_<timestamp>.tar.gz`.
4. Script validates backup integrity (`gzip -t` + `tar -tzf`).
5. Artifact is uploaded to R2.
6. `meta/latest.json` is updated with `latest_base`.

Default schedule:
- base backup: daily `0 2 * * *` (`BACKUP_CRON_BASE`)

## WAL Archiving (infra-managed PostgreSQL)

Enable on the PostgreSQL host/service:

```conf
wal_level = replica
archive_mode = on
archive_command = 'aws s3 cp %p s3://$BACKUP_S3_BUCKET/backups/wal/%f --endpoint-url=$AWS_S3_ENDPOINT_URL'
```

Production recommendation:
- Wrap `archive_command` in a retry-capable shell wrapper that logs failures and returns non-zero on persistent error.

Validation checklist:
1. Force WAL switch (`SELECT pg_switch_wal();`).
2. Confirm new object appears under `backups/wal/`.
3. Check PostgreSQL logs for archive success/failure entries.

## Restore Flow

The restore script is host-level and assumes control of PostgreSQL service and data directory.

### Base-only restore

```bash
scripts/restore.sh "<DATABASE_URL>" --type base --pg-data-dir /var/lib/postgresql/data
```

### Point-in-time restore (PITR)

```bash
scripts/restore.sh "<DATABASE_URL>" --type pitr --target-time "2026-04-24 12:10:00" --pg-data-dir /var/lib/postgresql/data
```

Behavior:
1. Resolve base object from `meta/latest.json` (`latest_base`) unless `--s3-uri` is provided.
2. Stop PostgreSQL service.
3. Replace target `PGDATA` with extracted base backup.
4. For `--type pitr`, write:
   - `restore_command` (download WAL from `BACKUP_PREFIX_WAL`)
   - `recovery_target_time`
   - `recovery.signal`
5. Start PostgreSQL and allow automatic WAL replay.

## Reliability Controls

- `flock` prevents overlapping base backup jobs.
- S3 uploads/downloads retry with exponential backoff (`BACKUP_AWS_MAX_ATTEMPTS`, default 3).
- Scripts fail fast on missing critical env vars and invalid CLI arguments.
- Logs include backup start/end and validation checkpoints.

## Retention Strategy (R2 lifecycle policy)

Do not delete objects in scripts. Use bucket lifecycle rules:
- BASE backups: retain 7-30 days
- WAL archives: retain 3-7 days

## Migration Notes (from FULL+SNAPSHOT)

What changed:
- Removed logical snapshot backups (`backup-snapshot.sh` and snapshot scheduler/task paths).
- Replaced logical full dump with physical base backup (`pg_basebackup`).
- Pointer schema changed from `latest_full/latest_snapshot` to `latest_base`.
- Restore modes changed from `full|snapshot` to `base|pitr`.

Cutover sequence:
1. Deploy new backup code and env vars (`BACKUP_PREFIX_BASE`, `BACKUP_PREFIX_WAL`).
2. Enable PostgreSQL WAL archiving at infra level.
3. Run one base backup and verify `meta/latest.json` has `latest_base`.
4. Run a disposable PITR drill before declaring production-ready.
