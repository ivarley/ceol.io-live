#!/usr/bin/env bash
# Full backup of a Postgres database with pg_dump, custom format (-Fc).
#
# Unlike scripts/backup_database.py (data-only INSERT statements), this captures
# the whole database: schema, functions, indexes, sequences and data, in a
# compressed file that pg_restore can load into an empty database, or
# selectively. Use it before anything irreversible, such as a major-version
# upgrade.
#
# Usage:
#   scripts/pg_backup.sh                 # prompts for the connection URL
#   DATABASE_URL=postgres://... scripts/pg_backup.sh
#
# The URL is read with echo off and never printed. Backups land in
# data/backup/ (gitignored). The script then lists the archive's contents
# to prove the file is readable.
set -euo pipefail

cd "$(dirname "$0")/.."
mkdir -p data/backup

if [ -z "${DATABASE_URL:-}" ]; then
    read -r -s -p "Postgres connection URL (external, from the Render dashboard): " DATABASE_URL
    echo
fi

if [ -z "$DATABASE_URL" ]; then
    echo "No connection URL given." >&2
    exit 1
fi

dbname="$(printf '%s' "$DATABASE_URL" | sed -E 's#.*/([^/?]+)(\?.*)?$#\1#')"
stamp="$(date +%Y-%m-%d_%H-%M-%S)"
out="data/backup/${dbname}_${stamp}.dump"

echo "Server:  $(psql "$DATABASE_URL" -qAtc 'select version()' | cut -d, -f1)"
echo "Size:    $(psql "$DATABASE_URL" -qAtc 'select pg_size_pretty(pg_database_size(current_database()))')"
echo "Writing: $out"

pg_dump "$DATABASE_URL" --format=custom --compress=6 --no-owner --no-privileges --file "$out"

echo
echo "Wrote $(du -h "$out" | cut -f1)"
echo "Archive contents: $(pg_restore --list "$out" | grep -c '^[0-9]') entries, including:"
pg_restore --list "$out" | grep -E '^[0-9]+; [0-9]+ [0-9]+ (TABLE DATA|FUNCTION|INDEX) ' \
    | awk '{ print ($5 == "DATA") ? $4 " " $5 : $4 }' | sort | uniq -c | sed 's/^/  /'
echo
echo "Restore into an empty database with:"
echo "  pg_restore --no-owner --no-privileges -d <target-url> $out"
