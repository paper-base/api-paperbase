#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=/dev/null
if [[ -f "/usr/local/lib/paperbase-backup/lib.sh" ]]; then
  . /usr/local/lib/paperbase-backup/lib.sh
else
  . "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
fi

if [ -z "${DIRECT_DATABASE_URL:-}" ]; then
  echo "ERROR: DIRECT_DATABASE_URL is not set"
  exit 1
fi
paperbase_require_env AWS_ACCESS_KEY_ID || exit 1
paperbase_require_env AWS_SECRET_ACCESS_KEY || exit 1
paperbase_require_env AWS_S3_ENDPOINT_URL || exit 1

bucket="$(paperbase_backup_bucket)"
if [[ -z "$bucket" ]]; then
  paperbase_log "ERROR: set BACKUP_S3_BUCKET or AWS_STORAGE_BUCKET_NAME"
  exit 1
fi

prefix="${BACKUP_PREFIX_BASE:-backups/base}"
prefix="${prefix#/}"
prefix="${prefix%/}"

lock_dir="$(paperbase_tmpdir)"
mkdir -p "$lock_dir"
exec 200>"$lock_dir/base.lock"
if ! flock -n 200; then
  paperbase_log "SKIP: another base backup is running."
  exit 0
fi

paperbase_wait_for_postgres "$DIRECT_DATABASE_URL" || exit 1

stamp="$(date -u +"%Y%m%d_%H%M%S")"
path_date="$(date -u +"%Y/%m/%d")"
remote_key="${prefix}/${path_date}/base_${stamp}.tar.gz"

tmp_dir="$(mktemp -d "$(paperbase_tmpdir)/base.XXXXXX")"
cleanup() {
  rm -rf "$tmp_dir"
}
trap cleanup EXIT INT TERM

tmp_base_tar_gz="${tmp_dir}/base.tar.gz"
paperbase_log "backup_start type=base target=${tmp_base_tar_gz##*/}"

set -o pipefail
paperbase_run_nice pg_basebackup -D - -Ft -z -X fetch -d "$DIRECT_DATABASE_URL" >"$tmp_base_tar_gz"

paperbase_log "backup_validate type=base check=gzip"
gzip -t "$tmp_base_tar_gz"
paperbase_log "backup_validate type=base check=tar"
tar -tzf "$tmp_base_tar_gz" >/dev/null

paperbase_log "Uploading s3://${bucket}/${remote_key}"
paperbase_aws_s3_cp_with_retry "$tmp_base_tar_gz" "s3://${bucket}/${remote_key}"

paperbase_try_update_latest_pointer "$bucket" "$remote_key"
paperbase_log "backup_end type=base status=ok remote=s3://${bucket}/${remote_key}"
