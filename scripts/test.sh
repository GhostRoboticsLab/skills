#!/usr/bin/env bash
# Run every test in the repo: check.py's own, then each skill's.
#
# A skill's tests are test_*.py files. Each folder that holds some runs as its
# own suite, with that folder first on the import path. One discover over
# skills/ would find nothing: unittest only walks folders that are Python
# packages, and kebab-case skill folders cannot be.
set -euo pipefail

repo="$(cd "$(dirname "$0")/.." && pwd)"
cd "$repo"
export PYTHONDONTWRITEBYTECODE=1

echo "-- scripts"
python3 scripts/test_check.py

find skills -name 'test_*.py' -not -path '*/__pycache__/*' -exec dirname {} \; | sort -u |
  while IFS= read -r dir; do
    echo "-- $dir"
    # </dev/null: a test that reads its input (ffmpeg does) would eat the rest of this list.
    python3 -m unittest discover -s "$dir" -p 'test_*.py' </dev/null
  done
