#!/usr/bin/env bash
# Installed as a forced SSH command, not a general-purpose remote shell.
set -euo pipefail
umask 077

root=/opt/tampak-chat
command_pattern='^deploy ([0-9a-f]{40}) (sha256:[0-9a-f]{64}) (sha256:[0-9a-f]{64})$'
if [[ ! ${SSH_ORIGINAL_COMMAND:-} =~ $command_pattern ]]; then
  printf 'Only a validated Tampak deployment is allowed.\n' >&2
  exit 64
fi
revision=${BASH_REMATCH[1]}
backend_digest=${BASH_REMATCH[2]}
web_digest=${BASH_REMATCH[3]}

exec 9>"$root/deploy.lock"
flock -w 900 9
IFS= read -r registry_token
export DOCKER_CONFIG
DOCKER_CONFIG=$(mktemp -d)
trap 'rm -rf "$DOCKER_CONFIG"' EXIT
printf '%s' "$registry_token" | docker login ghcr.io -u AdrianRamadhan27 --password-stdin
unset registry_token

git -C "$root/source" fetch --quiet origin main
git -C "$root/source" merge-base --is-ancestor "$revision" origin/main
release="$root/releases/$revision"
mkdir -p "$release"
git -C "$root/source" archive "$revision" | tar -x -C "$release"
export TAMPAK_BACKEND_IMAGE="ghcr.io/adrianramadhan27/tampak-backend@$backend_digest"
export TAMPAK_WEB_IMAGE="ghcr.io/adrianramadhan27/tampak-web@$web_digest"
compose=(docker compose --project-name tampak-chat --env-file "$root/shared/.env" -f "$release/deploy/compose.production.yaml")

"${compose[@]}" config --quiet
"${compose[@]}" pull --quiet
"${compose[@]}" up -d --wait --wait-timeout 150 postgres
if [[ -f "$root/shared/current.env" ]]; then
  backup="$root/backups/$(date -u +%Y%m%dT%H%M%SZ)-before-$revision.dump"
  "${compose[@]}" exec -T postgres pg_dump -U tampak_owner -d tampak -Fc > "$backup"
fi
"${compose[@]}" run --rm --no-deps setup
"${compose[@]}" up -d --wait --wait-timeout 180 api chat-worker ingest-worker web
curl --fail --silent --show-error --retry 12 --retry-delay 5 --retry-all-errors https://chat.tampak.my.id/api/v1/health

if [[ -f "$root/shared/current.env" ]]; then
  cp "$root/shared/current.env" "$root/shared/previous.env"
fi
printf 'TAMPAK_BACKEND_IMAGE=%s\nTAMPAK_WEB_IMAGE=%s\nTAMPAK_RELEASE=%s\n' \
  "$TAMPAK_BACKEND_IMAGE" "$TAMPAK_WEB_IMAGE" "$revision" > "$root/shared/current.env"
ln -sfn "$release" "$root/current"
printf '\nDeployed Tampak release %s\n' "$revision"
