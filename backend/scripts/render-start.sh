#!/bin/sh
# Render's free tier has no Pre-Deploy Command (that's paid-only — confirmed),
# and its Docker Command field doesn't reliably pass a quoted `sh -c "a && b"`
# string through an actual shell (it was tokenizing the whole thing as one
# literal, unfindable command). Putting the logic in a real script file
# sidesteps that entirely — Render's Docker Command just needs to be
# `sh scripts/render-start.sh`, too simple to mis-parse.
set -e

alembic upgrade head

# There is no sign-up page and no Shell tab on the free tier, so this is the
# only way an admin account can come into existence on Render. Idempotent:
# creates the account, or resets its password to match the env var. Unset
# ADMIN_EMAIL once you're in and it's skipped entirely — the account stays.
# `|| echo`, not bare: set -e is on, and a rejected password (too short) or a
# typo'd email must not stop uvicorn from booting. Students losing the chatbot
# because an admin credential was wrong is the worse failure of the two — the
# error lands in Render's logs and the service still serves.
if [ -n "$ADMIN_EMAIL" ]; then
    python scripts/create_admin.py --email "$ADMIN_EMAIL" \
        || echo "!!! admin bootstrap failed (see error above) — starting anyway"
fi
# Single worker, deliberately: Render free tier is 512Mi RAM total, and this
# app imports paddlepaddle/paddleocr, which are heavy enough that 4 workers
# (4 full copies of the process) OOM-killed a real deploy. Render itself
# suggests 1 ("Setting WEB_CONCURRENCY=1... based on available CPUs") for an
# instance this size — the previous --workers 4 here overrode that. This also
# happens to be required for core/rate_limit.py's in-memory limiter, which
# only counts correctly with exactly one process.
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --workers 1
