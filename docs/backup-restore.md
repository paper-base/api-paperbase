# Backup and Restore Runbook (pg_dump + S3)

This runbook documents the current backup architecture:

- Daily logical backups via `pg_dump` (custom format, compressed)
- Upload to S3-compatible storage (Cloudflare R2/S3)
- Latest pointer stored at `meta/latest.json`
- Restore via `pg_restore`

WAL archiving and PITR are not part of this flow.

## Required Environment Variables

- `DIRECT_DATABASE_URL` (backup source DB connection)
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_S3_ENDPOINT_URL`
- `BACKUP_S3_BUCKET` (or `AWS_STORAGE_BUCKET_NAME`)

Optional:

- `AWS_DEFAULT_REGION` / `AWS_S3_REGION_NAME` (defaults to `auto`)
- `BACKUP_PREFIX_BASE` (default `backups/base`)
- `BACKUP_TMP_DIR` (default `/tmp/paperbase-backup`)
- `BACKUP_AWS_MAX_ATTEMPTS` (default `3`)

Runtime requirements:

- `pg_dump`, `pg_restore`, `psql` tooling available in runtime
- `aws` CLI available in runtime
- Celery worker consuming the `backup` queue (for scheduled backups)

## Storage Layout

- Base backups: `backups/base/YYYY/MM/DD/base_<timestamp>.dump`
- Latest pointer: `meta/latest.json`

Example:

```json
{
  "latest_base": "backups/base/2026/04/26/base_20260426_042225.dump",
  "timestamp": "2026-04-26T04:22:59Z"
}
```

## Backup Flow

1. `engine.apps.backup.run_base_backup` starts on the `backup` queue.
2. Pre-backup prune runs (`engine.apps.backup.prune.prune_noncritical_tables`) to reduce high-churn data.
3. `backup/backup-base.sh` runs `pg_dump`:
   - `--format=custom`
   - `--compress=9`
   - `--exclude-table-data=...` for selected non-critical tables
4. Script validates:
   - dump file is non-empty
   - `pg_restore --list` can read the archive
5. Uploads to `s3://<bucket>/<prefix>/...base_<timestamp>.dump`
6. Updates `meta/latest.json` (`latest_base`)

## Excluded Table Data

Only table data is excluded (schema remains in dump) for these noisy/non-critical tables:

- `django_session`
- `django_admin_log`
- `core_activitylog`
- `emails_emaillog`
- `fraud_check_fraudchecklog`
- `marketing_integrations_storeeventlog`
- `notifications_notificationdismissal`
- `analytics_storedashboardstatssnapshot`
- `django_celery_beat_periodictask`
- `django_celery_beat_crontabschedule`
- `django_celery_beat_intervalschedule`
- `django_celery_beat_solarschedule`

## Manual Backup Command

```bash
bash backup/backup-base.sh
```

Success log ends with:

```text
backup_end type=pg_dump status=ok remote=s3://...
```

## Restore Flow

Use `scripts/restore.sh` to restore a `.dump` into a target database.

Latest-pointer restore:

```bash
scripts/restore.sh "<DATABASE_URL>"
```

Restore a specific object:

```bash
scripts/restore.sh "<DATABASE_URL>" --s3-uri "s3://bucket/backups/base/YYYY/MM/DD/base_*.dump"
```

Destructive restore (drops existing objects first):

```bash
scripts/restore.sh "<DATABASE_URL>" --clean
```

Dry-run:

```bash
scripts/restore.sh "<DATABASE_URL>" --dry-run
```

What the script does:

1. Resolves dump URI from `--s3-uri` or `meta/latest.json`
2. Downloads `.dump` from S3/R2
3. Runs `pg_restore` into target DB
4. With `--clean`, uses `--clean --if-exists`

## Reliability Controls

- `flock` in backup script prevents overlapping runs.
- S3 upload/download includes retries with exponential backoff.
- Required env vars are validated before backup/restore.
- Backup validates dump readability before upload.

## Retention Strategy

Use bucket lifecycle rules (do not hard-delete in scripts), e.g. keep base dumps for 7-30 days depending on RPO/RTO and storage budget.
