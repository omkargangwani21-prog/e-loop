#!/usr/bin/env bash
# Creates the SSM SecureString that collector sign-in keys are derived from, then prints the key
# for each demo collector. Run once per stage, before the first deploy.
#
#   ./infra/seed_collector_secret.sh dev
set -euo pipefail

STAGE="${1:-dev}"
PARAM="/eloop/${STAGE}/collector-secret"
SECRET="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"

aws ssm put-parameter --name "$PARAM" --type SecureString --value "$SECRET" --no-overwrite >/dev/null
echo "Created $PARAM"
echo
echo "Collector keys (share each with the matching collection point):"
SECRET="$SECRET" PYTHONPATH="$(dirname "$0")/../backend/src" python3 - <<'PY'
import os
from eloop.auth import derive_key
from eloop.service import load_collectors

secret = os.environ["SECRET"]
for collector_id in sorted(load_collectors()):
    print(f"  {collector_id:<16} {derive_key(secret, collector_id)}")
PY
