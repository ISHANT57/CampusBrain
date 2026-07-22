#!/bin/sh
# Render's free tier has no Pre-Deploy Command (that's paid-only — confirmed),
# and its Docker Command field doesn't reliably pass a quoted `sh -c "a && b"`
# string through an actual shell (it was tokenizing the whole thing as one
# literal, unfindable command). Putting the logic in a real script file
# sidesteps that entirely — Render's Docker Command just needs to be
# `sh scripts/render-start.sh`, too simple to mis-parse.
set -e

alembic upgrade head
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --workers 4
