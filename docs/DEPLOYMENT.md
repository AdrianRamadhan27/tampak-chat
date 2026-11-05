# VPS deployment

Production URL: https://chat.tampak.my.id. The production deployment requires an administrator login; anonymous sessions are disabled. Local development keeps its temporary guest mode unless `TAMPAK_AUTH_REQUIRED=true` is set.

## GitHub Actions

The repository's `Verify and deploy Tampak-Chat` workflow runs on `main`, pull requests and manual dispatch. Pull requests run verification only. Main runs verify TypeScript, lint, formatting, Python tests against a disposable PostgreSQL database and deployment-script syntax, then build Linux AMD64 web/backend images in GitHub Container Registry. Production uses image digests rather than mutable tags.

Actions uses repository variables `DEPLOY_HOST` and `DEPLOY_USER`, plus secrets `DEPLOY_SSH_KEY` and `DEPLOY_KNOWN_HOSTS`. The dedicated SSH key is restricted on the host to a forced deployment command. It cannot open an interactive shell, forward ports or execute arbitrary commands. Each deployment receives an ephemeral registry token; its temporary Docker login is removed afterward. Application and model credentials stay on the VPS, outside Git and Actions logs.

The host command accepts only a main-branch commit and two SHA-256 image digests, serializes deployments with `flock`, runs migrations and idempotent seeding, waits for healthy services, then checks public HTTPS. Successful releases record their image digests and previous release. Existing database contents and uploaded artifacts persist across releases.

## Host layout and networking

- `/opt/tampak-chat/source`: public repository checkout used to resolve release commits.
- `/opt/tampak-chat/releases/<commit>`: immutable release source.
- `/opt/tampak-chat/current`: most recently verified release.
- `/opt/tampak-chat/shared/.env`: private production database, encryption and initial administrator secrets.
- `/opt/tampak-chat/shared/runtime`: persistent document originals, extraction, source previews and model cache.
- `/opt/tampak-chat/shared/current.env` and `previous.env`: image references and release IDs.
- `/opt/tampak-chat/backups`: private database snapshots created before upgrades.

Tampak uses a separate Compose project and database volume. It publishes no application or database host ports. The existing Caddy proxy joins the dedicated `tampak-edge` network; its existing Applicient routes are preserved. The Caddy fragment routes `/api/*` directly to the private API with immediate SSE flushing and other requests to the web container. HTTPS certificates renew through Caddy.

The API trusts forwarded client headers only from the dedicated edge subnet, `172.31.221.0/28`. Production uses Secure HttpOnly cookies, the exact HTTPS origin and disabled local-provider URLs. Containers have bounded memory/CPU/process counts, dropped capabilities and no-new-privileges; application roots are read-only. PostgreSQL stays on an internal network. Only the setup container receives migration credentials.

## Administrator access

Production credentials are generated separately from the local app. A private `runtime/deploy/recruiter-credentials.txt` file on the owner's computer contains only the URL, username and password to share with recruiters. It is excluded from Git. Model provider profiles are transferred through SSH and encrypted under the production master key. Local conversations and temporary guest data are not transferred.

Use **Sign out** to revoke the current session and return to the login gate. A password change uses the existing owner CLI and revokes all administrator sessions. Preserve the production encryption key with backups so saved provider keys remain usable.

## Health, upgrades and rollback

```sh
ssh applicient-vps
cd /opt/tampak-chat
docker compose --project-name tampak-chat \
  --env-file shared/.env --env-file shared/current.env \
  -f current/deploy/compose.production.yaml ps
curl --fail https://chat.tampak.my.id/api/v1/health
```

Push a reviewed change to `main` to deploy it through Actions. Do not edit a release's source in place. Before rolling back, review whether the new migrations remain compatible with the previous application. The previous release's image references are kept in `shared/previous.env`; database snapshots are retained separately. A rollback does not automatically rewind database migrations or replay potentially billed model calls.

Host-local snapshots do not provide off-host disaster recovery. Off-host backup storage, a scheduled retention policy and a full restore drill remain separate operations. The container bounds reduce parser exposure; they are not a complete sandbox for hostile public uploads. This release is restricted to the authenticated owner and invited reviewers.
