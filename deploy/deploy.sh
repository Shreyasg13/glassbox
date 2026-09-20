#!/usr/bin/env bash
# Deploy a CI-built image tag on the server -- pull, swap, wait for health, and
# roll back automatically if the new version doesn't come up healthy.
#
#   cd ~/glassbox && deploy/deploy.sh <tag>      # <tag> = short commit SHA, or "latest"
#   deploy/deploy.sh --rollback                  # go back to the previous tag
#   deploy/deploy.sh --status                    # what is running
#
# The tag lives in .env (IMAGE_TAG=...), so every later `docker compose` command
# agrees with what is deployed. Nothing is built here: the VM only pulls finished
# images from Artifact Registry (built and tested by .github/workflows/images.yml),
# which is what removed the memory spikes that used to freeze the server.
set -euo pipefail
cd "$(dirname "$0")/.."

REGISTRY_HOST=us-central1-docker.pkg.dev
SERVICES="backend frontend"

current_tag() { grep -E '^IMAGE_TAG=' .env 2>/dev/null | tail -1 | cut -d= -f2 || true; }
set_tag() {
  touch .env
  sed -i -e '/^IMAGE_TAG=/d' -e '$a\' .env
  echo "IMAGE_TAG=$1" >> .env
}
app_domain() { grep -E '^APP_DOMAIN=' .env | tail -1 | cut -d= -f2; }

registry_login() {
  # The VM authenticates with its own service account -- no key file exists anywhere.
  local token
  token=$(curl -sf -H "Metadata-Flavor: Google" \
    http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token \
    | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')
  echo "$token" | docker login -u oauth2accesstoken --password-stdin "$REGISTRY_HOST" >/dev/null
}

rollout() {  # $1 = tag; returns non-zero if the new containers don't become healthy in time
  set_tag "$1"
  docker compose pull $SERVICES
  docker compose up -d --no-deps --wait --wait-timeout 150 $SERVICES
}

case "${1:-}" in
  --status)
    echo "tag in .env: $(current_tag)"; docker compose ps; exit 0 ;;
  --rollback)
    PREV=$(cat .deploy_previous 2>/dev/null || true)
    [ -n "$PREV" ] || { echo "no previous tag recorded"; exit 1; }
    set -- "$PREV" ;;
  ""|-h|--help)
    sed -n '2,12p' "$0"; exit 1 ;;
esac

NEW="$1"
OLD=$(current_tag)
echo "==> deploying '$NEW' (currently '${OLD:-none}')"
registry_login

if rollout "$NEW"; then
  [ -n "$OLD" ] && [ "$OLD" != "$NEW" ] && echo "$OLD" > .deploy_previous
  echo "==> healthy. checking the public site..."
  DOMAIN=$(app_domain)
  for i in 1 2 3 4 5 6; do
    if curl -sf --max-time 10 "https://$DOMAIN/health" >/dev/null; then echo "==> https://$DOMAIN/health OK"; break; fi
    [ "$i" = 6 ] && { echo "!! public health check failed"; exit 1; }
    sleep 4
  done
  docker image prune -f >/dev/null            # dangling layers only
  docker compose ps --format '   {{.Name}}  {{.Status}}'
  echo "==> done. roll back with: deploy/deploy.sh --rollback   (previous: ${OLD:-none})"
else
  echo "!! '$NEW' did not become healthy."
  if [ -n "$OLD" ] && [ "$OLD" != "$NEW" ]; then
    echo "==> rolling back to '$OLD'"
    rollout "$OLD" && echo "==> rolled back; site is on '$OLD'" || echo "!! rollback failed too -- check: docker compose logs"
  fi
  exit 1
fi
