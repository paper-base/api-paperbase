#!/usr/bin/env bash
set -euo pipefail

# Restore helper for Paperbase pg_dump backups.
# Usage:
#   ./scripts/restore.sh <DATABASE_URL>
#   ./scripts/restore.sh <DATABASE_URL> --s3-uri s3://bucket/path/to/base_*.dump
# Optional overrides:
#   --clean (drop existing schema objects before restore)
#   --dry-run

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=/dev/null
. "$ROOT/backup/lib.sh"

usage() {
  cat <<'EOF'
Usage:
  scripts/restore.sh <DATABASE_URL> [--s3-uri s3://bucket/path/base_*.dump] [--clean] [--dry-run]

Env:
  AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_S3_ENDPOINT_URL.
  For latest pointer resolution: also BACKUP_S3_BUCKET (or AWS_STORAGE_BUCKET_NAME).
Notes:
  - Restores a pg_dump custom-format archive with pg_restore.
  - --clean passes --clean --if-exists to pg_restore (destructive).
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
s3_uri=""
restore_clean=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --s3-uri)
      if [[ -z "${2:-}" ]]; then
        paperbase_log "ERROR: --s3-uri requires a value"
        exit 1
      fi
      s3_uri="$2"
      shift 2
      ;;
    --clean)
      restore_clean=1
      shift
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

paperbase_require_env AWS_ACCESS_KEY_ID || exit 1
paperbase_require_env AWS_SECRET_ACCESS_KEY || exit 1
paperbase_require_env AWS_S3_ENDPOINT_URL || exit 1

bucket="$(paperbase_backup_bucket)"
if [[ -z "$s3_uri" && -z "$bucket" ]]; then
  paperbase_log "ERROR: set BACKUP_S3_BUCKET (or AWS_STORAGE_BUCKET_NAME fallback) when --s3-uri is not provided"
  exit 1
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
  paperbase_log "DRY-RUN: would download $uri -> $local_path"
  if ((restore_clean)); then
    paperbase_log "DRY-RUN: would run pg_restore --clean --if-exists to ${target_url}"
  else
    paperbase_log "DRY-RUN: would run pg_restore to ${target_url}"
  fi
  exit 0
fi

paperbase_log "Downloading..."
paperbase_aws_s3_download_with_retry "$uri" "$local_path"

if [[ "$fname" != *.dump ]]; then
  paperbase_log "ERROR: unsupported file type for restore (expected .dump)"
  exit 1
fi

paperbase_log "restore_start type=pg_dump target_db=${target_url}"

pg_restore_args=(
  --no-password
  --verbose
  --dbname="$target_url"
)
if ((restore_clean)); then
  pg_restore_args+=(--clean --if-exists)
fi

pg_restore "${pg_restore_args[@]}" "$local_path"

paperbase_log "restore_end type=pg_dump status=ok target_db=${target_url}"
