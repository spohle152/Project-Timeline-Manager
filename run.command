#!/bin/bash
# Double-click this file in Finder to set up (first run only) and start
# Project Manager. Safe to run repeatedly — setup steps are skipped once done.
cd "$(dirname "$0")"

fail() {
  echo ""
  echo "Something went wrong: $1"
  read -n 1 -s -r -p "Press any key to close this window..."
  echo ""
  exit 1
}

command -v python3 >/dev/null 2>&1 \
  || fail "Python 3 isn't installed. Get it from https://www.python.org/downloads/ and run this again."

if [ ! -d ".venv" ]; then
  echo "First-time setup: creating a virtual environment..."
  python3 -m venv .venv || fail "Could not create a virtual environment."
fi

source .venv/bin/activate

echo "Checking dependencies..."
pip install -q -r requirements.txt || fail "Could not install dependencies."

python3 main.py
status=$?
if [ $status -ne 0 ]; then
  fail "Project Manager exited with an error (exit code $status)."
fi
