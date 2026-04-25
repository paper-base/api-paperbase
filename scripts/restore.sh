#!/usr/bin/env bash
set -euo pipefail

# PITR restore helper for Paperbase PostgreSQL BASE+WAL architecture.
# Usage:
#   ./scripts/restore.sh <DATABASE_URL> --type base --pg-data-dir /var/lib/postgresql/data
#   ./scripts/restore.sh <DATABASE_URL> --type pitr --target-time "YYYY-MM-DD HH:MM:SS" --pg-data-dir /var/lib/postgresql/data
# Optional overrides:
#   --s3-uri s3://bucket/path/to/base_*.tar.gz
#   --service-name postgresql
#   --dry-run

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=/dev/null
. "$ROOT/backup/lib.sh"

usage() {
  cat <<'EOF'
Usage:
  scripts/restore.sh <DATABASE_URL> --type base|pitr --pg-data-dir /path/to/pgdata [--target-time "YYYY-MM-DD HH:MM:SS"] [--s3-uri s3://bucket/path/base_*.tar.gz] [--service-name postgresql] [--dry-run]

Env: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_S3_ENDPOINT_URL.
For latest pointer resolution: also BACKUP_S3_BUCKET.
WAL restore prefix: BACKUP_PREFIX_WAL (default backups/wal).
EOF
  exit "${1:-0}"
}

if [[ $# -lt 1 ]]; then
  paperbase_log "ERROR: You must provide a database URL"
  usage 1
fi
if [[ "$1" == "-h" || "$1" == "--help" ]]; then
  usage 0
fi

target_url="$1"
shift

dry_run=0
restore_type="base"
s3_uri=""
target_time=""
pg_data_dir=""
service_name="postgresql"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --type)
      if [[ -z "${2:-}" ]]; then
        paperbase_log "ERROR: --type requires a value: base or pitr"
        exit 1
      fi
      restore_type="$2"
      shift 2
      ;;
    --target-time)
      if [[ -z "${2:-}" ]]; then
        paperbase_log "ERROR: --target-time requires a value"
        exit 1
      fi
      target_time="$2"
      shift 2
      ;;
    --pg-data-dir)
      if [[ -z "${2:-}" ]]; then
        paperbase_log "ERROR: --pg-data-dir requires a value"
        exit 1
      fi
      pg_data_dir="$2"
      shift 2
      ;;
    --service-name)
      if [[ -z "${2:-}" ]]; then
        paperbase_log "ERROR: --service-name requires a value"
        exit 1
      fi
      service_name="$2"
      shift 2
      ;;
    --s3-uri)
      if [[ -z "${2:-}" ]]; then
        paperbase_log "ERROR: --s3-uri requires a value"
        exit 1
      fi
      s3_uri="$2"
      shift 2
      ;;
    --dry-run)
      dry_run=1
      shift
      ;;
    -h | --help) usage 0 ;;
    *)
      paperbase_log "ERROR: unknown option: $1"
      usage 1
      ;;
  esac
done

if [[ "$restore_type" != "base" && "$restore_type" != "pitr" ]]; then
  paperbase_log "ERROR: --type must be one of: base, pitr"
  exit 1
fi
if [[ -z "$pg_data_dir" ]]; then
  paperbase_log "ERROR: --pg-data-dir is required for host-level restore"
  exit 1
fi
if [[ "$restore_type" == "pitr" && -z "$target_time" ]]; then
  paperbase_log "ERROR: --target-time is required for --type pitr"
  exit 1
fi

paperbase_require_env AWS_ACCESS_KEY_ID || exit 1
paperbase_require_env AWS_SECRET_ACCESS_KEY || exit 1
paperbase_require_env AWS_S3_ENDPOINT_URL || exit 1

bucket="$(paperbase_backup_bucket)"
if [[ -z "$s3_uri" && -z "$bucket" ]]; then
  paperbase_log "ERROR: set BACKUP_S3_BUCKET (or AWS_STORAGE_BUCKET_NAME fallback) when --s3-uri is not provided"
  exit 1
fi
if [[ "$restore_type" == "pitr" && -z "$bucket" ]]; then
  paperbase_log "ERROR: PITR mode requires BACKUP_S3_BUCKET (or AWS_STORAGE_BUCKET_NAME) for WAL restore_command"
  exit 1
fi
if [[ "$restore_type" == "pitr" ]]; then
  if ! date -d "$target_time" +"%Y-%m-%d %H:%M:%S" >/dev/null 2>&1; then
    paperbase_log "ERROR: --target-time must parse as 'YYYY-MM-DD HH:MM:SS'"
    exit 1
  fi
fi

if [[ -z "$target_url" ]]; then
  paperbase_log "ERROR: You must provide a database URL"
  exit 1
fi

tmp_root="$(mktemp -d "${TMPDIR:-/tmp}/paperbase-restore.XXXXXX")"
cleanup() {
  rm -rf "$tmp_root"
}
trap cleanup EXIT INT TERM

resolve_uri_from_latest_json() {
  local latest_file="${tmp_root}/latest.json"
  local pointer_value=""

  if ! paperbase_try_read_latest_json "$bucket" "$latest_file"; then
    paperbase_log "ERROR: failed to fetch latest pointer s3://${bucket}/$(paperbase_latest_json_key)"
    exit 1
  fi

  pointer_value="$(paperbase_json_get_field "$latest_file" latest_base || true)"

  if [[ -z "$pointer_value" ]]; then
    paperbase_log "ERROR: latest_base pointer is empty in latest.json"
    exit 1
  fi

  if [[ "$pointer_value" == s3://* ]]; then
    printf '%s' "$pointer_value"
    return
  fi
  printf 's3://%s/%s' "$bucket" "${pointer_value#/}"
}

if [[ -n "$s3_uri" ]]; then
  uri="$s3_uri"
else
  uri="$(resolve_uri_from_latest_json)"
fi
paperbase_log "Resolved object: $uri"

fname="${uri##*/}"
local_path="${tmp_root}/${fname}"

if ((dry_run)); then
  paperbase_log "DRY-RUN: would download $uri -> $local_path and extract to $pg_data_dir"
  paperbase_log "DRY-RUN: would stop/start service=$service_name mode=$restore_type"
  exit 0
fi

paperbase_log "Downloading..."
paperbase_aws_s3_download_with_retry "$uri" "$local_path"

if [[ "$fname" != *.tar.gz ]]; then
  paperbase_log "ERROR: unsupported file type for BASE restore (expected .tar.gz)"
  exit 1
fi

paperbase_log "restore_start type=${restore_type} service=${service_name} data_dir=${pg_data_dir}"
sudo systemctl stop "$service_name"
sudo rm -rf "$pg_data_dir"
sudo mkdir -p "$pg_data_dir"
sudo tar -xzf "$local_path" -C "$pg_data_dir"
sudo chown -R postgres:postgres "$pg_data_dir"
sudo chmod 700 "$pg_data_dir"

if [[ "$restore_type" == "pitr" ]]; then
  wal_prefix="${BACKUP_PREFIX_WAL:-backups/wal}"
  wal_prefix="${wal_prefix#/}"
  wal_prefix="${wal_prefix%/}"
  restore_command="aws s3 cp s3://${bucket}/${wal_prefix}/%f.gz - --endpoint-url=${AWS_S3_ENDPOINT_URL} --region $(paperbase_aws_region) | gunzip -c > %p"
  sudo tee -a "${pg_data_dir}/postgresql.auto.conf" >/dev/null <<EOF
restore_command = '${restore_command}'
recovery_target_time = '${target_time}'
EOF
  sudo touch "${pg_data_dir}/recovery.signal"
else
  sudo sed -i '/^restore_command = /d;/^recovery_target_time = /d' "${pg_data_dir}/postgresql.auto.conf" 2>/dev/null || true
  sudo rm -f "${pg_data_dir}/recovery.signal"
fi

sudo systemctl start "$service_name"
paperbase_log "restore_end type=${restore_type} status=ok target_db=${target_url}"
