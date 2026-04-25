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

Runtime requirement:
- Celery worker must consume the `backup` queue in production (base backup task).
- General Celery workers process the default queue for periodic maintenance (including steady-state table prune).

## Physical backups and table exclusion

Backups are **physical** only: `pg_basebackup` copies the entire PostgreSQL data directory (cluster files). WAL archiving captures **every** change in the cluster.

**You cannot exclude specific tables** from `pg_basebackup` or from WAL-based PITR. Table-level exclusion exists only in **logical** dumps (`pg_dump`), which this stack does **not** use for BASE backups (there is no `pg_dump` in the base backup path).

**Philosophy:** We do not exclude data at backup time. We control data volume **at the source** using retention policies and batched deletes on non-critical tables (see below).

## Storage Layout

- BASE backups: `backups/base/YYYY/MM/DD/base_<timestamp>.tar.gz`
- WAL archives: `backups/wal/<wal_file_name>.gz` (gzip-compressed 16 MiB segments; typical object size about 1–3 MiB)
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
2. Worker runs **pre-base prune** (`engine.apps.backup.prune.prune_noncritical_tables`): batched, time-based deletes on non-critical tables (see next section). Skipped entirely when `BACKUP_PRUNE_ENABLED=false`. If prune raises an unexpected error, the worker logs it and **still runs** `pg_basebackup` so the base backup is not blocked.
3. Worker runs `backup/backup-base.sh` (entrypoint for base backups).
4. Script runs `pg_basebackup -D - -Ft -z -X fetch` and writes `base_<timestamp>.tar.gz`.
5. Script validates backup integrity (`gzip -t` + `tar -tzf`).
6. Artifact is uploaded to R2.
7. `meta/latest.json` is updated with `latest_base`.

Default schedules:
- base backup: daily `0 2 * * *` (`BACKUP_CRON_BASE`)
- steady-state prune: `engine.apps.backup.run_backup_table_prune` every six hours at :30 (`30 */6 * * *`) on the **default** Celery queue (same retention rules as step 2; reduces heap and write churn between daily bases).

Related periodic tasks (not part of the base tarball script, but part of overall retention):

- `engine.apps.tracking.cleanup_old_event_logs` — `StoreEventLog` rows with `app="tracking"` older than `EVENT_LOG_RETENTION_HOURS` (default **72**).
- `engine.apps.orders.cleanup_expired_order_exports` — completed export files past `expires_at` (rows may remain `EXPIRED` until hard-pruned by backup prune).
- `engine.core.purge_expired_trash` — expired `TrashItem` rows.

## Non-critical tables and in-database retention

These tables are treated as **non-critical for long-term backup bulk** (operational logs, dismissals, cache-like snapshots, terminal export jobs, etc.). They remain inside PostgreSQL and inside physical backups until pruned; retention is controlled with `BACKUP_PRUNE_*` settings (see `.env.example`).

| Logical area | DB table | Prune behavior |
|--------------|----------|----------------|
| Marketing / tracking events | `marketing_integrations_storeeventlog` | Rows older than `BACKUP_PRUNE_STORE_EVENT_LOG_HOURS` (default 72), **all** `app` values; complements tracking’s `app="tracking"` cleaner. |
| Fraud cache log | `fraud_check_fraudchecklog` | Rows with `checked_at` older than `BACKUP_PRUNE_FRAUD_CHECK_LOG_DAYS`. |
| Email audit | `emails_emaillog` | Rows with `created_at` older than `BACKUP_PRUNE_EMAIL_LOG_DAYS`. |
| Admin UI activity | `core_activitylog` | Rows with `created_at` older than `BACKUP_PRUNE_ACTIVITY_LOG_DAYS`. |
| Django admin history | `django_admin_log` | `LogEntry` rows with `action_time` older than `BACKUP_PRUNE_ADMIN_LOG_DAYS`. |
| Django sessions | `django_session` | Rows with `expire_date` in the past (same idea as `clearsessions`). |
| Basic analytics snapshots | `analytics_storedashboardstatssnapshot` | Rows with `end_date` older than `BACKUP_PRUNE_DASHBOARD_SNAPSHOT_DAYS` (calendar days). |
| Notification dismissals | `notifications_notificationdismissal` | Rows with calendar `date` older than `BACKUP_PRUNE_NOTIFICATION_DISMISSAL_DAYS`. |
| Order CSV export jobs | `orders_orderexportjob` | `EXPIRED` or `FAILED` rows with `updated_at` older than `BACKUP_PRUNE_ORDER_EXPORT_JOB_DAYS`. |
| Soft-delete trash | `core_trashitem` | Not pruned here; use `engine.core.purge_expired_trash` (daily). |

Deletes run in configurable batches (`BACKUP_PRUNE_BATCH_SIZE`) under a system execution scope so tenant-scoped models can be pruned safely from Celery.

### WAL and base backup size

- **Base tarball:** Smaller heaps for the tables above yield smaller `pg_basebackup` archives once autovacuum reclaims space.
- **WAL:** Ongoing inserts to large log tables generate sustained WAL volume. Pruning **caps** table growth and limits future WAL from those tables. A large prune run still emits WAL for the `DELETE`s themselves; steady-state scheduling plus batching avoids a single huge spike right before `pg_basebackup` when possible.

Disable pruning only when necessary (e.g. forensic hold): set `BACKUP_PRUNE_ENABLED=false`.

## WAL Archiving (infra-managed PostgreSQL)

Enable on the PostgreSQL host/service. The repo ships `postgres-ssl/archive_wal.sh`, which **gzip-streams** each segment to R2/S3 as `%f.gz` (same env vars as other backup tooling: `BACKUP_S3_BUCKET`, optional `BACKUP_PREFIX_WAL`, `AWS_S3_ENDPOINT_URL`, `AWS_DEFAULT_REGION`, `BACKUP_AWS_MAX_ATTEMPTS`).

Example `postgresql.conf` fragment:

```conf
wal_level = replica
archive_mode = on
archive_command = '/usr/local/bin/archive_wal.sh %p %f'
```

Production notes:
- Prefer the provided wrapper (retries, endpoint/region flags, compression) over a bare `aws s3 cp %p …/%f`.
- If you ever stored **uncompressed** WAL as `%f` without `.gz`, PITR `restore_command` must match that layout (see restore script) or those objects must be migrated/renamed.

Validation checklist:
1. Force WAL switch (`SELECT pg_switch_wal();`).
2. Confirm a new object appears under `backups/wal/` with a `.gz` suffix matching the WAL file name.
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
   - `restore_command` (download `BACKUP_PREFIX_WAL/%f.gz` from S3/R2, decompress with `gunzip -c` into `%p`)
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
