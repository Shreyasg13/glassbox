# Deploying with CI-built images

Images are **built and tested in GitHub Actions** and **pulled** by the VM. The server
never builds anything, which is what used to freeze it (a `next build` alone exhausted
its 4 GB of RAM) and bloated the Docker daemon.

```
git push main ─► GitHub Actions: test ─► build backend + frontend ─► push to Artifact Registry
                                                                              │
VM:  deploy/deploy.sh <tag>  ─► pull ─► swap containers ─► wait until healthy ─► (rollback if not)
```

## Day to day

1. Push to `main`. Actions runs the tests, builds both images and pushes them, tagged with
   the short commit SHA and `latest`. The run's summary prints the exact deploy command.
2. On the VM:
   ```bash
   cd ~/glassbox && deploy/deploy.sh <tag>      # e.g. deploy/deploy.sh 919e7b2
   ```
   It logs in with the VM's own service account (no key file), pulls, restarts only the
   backend and frontend, **waits for their healthchecks**, checks the public `/health`, and
   **rolls back automatically** if the new version doesn't become healthy in time.
3. Other commands: `deploy/deploy.sh --status`, `deploy/deploy.sh --rollback` (previous tag).

The deployed tag is stored in `~/glassbox/.env` (`IMAGE_TAG=`), so every later
`docker compose` command agrees with what is running.

## Files that are still copied by hand

Only when they change (rare): `docker-compose.yml`, `deploy/Caddyfile`, `deploy/deploy.sh`.
`scp` them to `~/glassbox/`. A changed `Caddyfile` needs
`docker compose up -d --force-recreate --no-deps caddy` (single-file bind mounts go stale).

## What exists in Google Cloud (created once)

| Thing | Name |
|---|---|
| Docker repository | `us-central1-docker.pkg.dev/project-f015cf71-9e01-4a2a-8f5/glassbox` (cleanup policy: keep the 6 newest versions, delete anything older than 7 days) |
| Identity for CI | `github-deployer@…` — may only **push** to that repository |
| Keyless trust | Workload Identity pool `github`, provider `glassbox`: accepts tokens only from repo `Shreyasg13/glassbox-trading-agents` on branch `main` |
| VM access | the VM's default service account has **reader** on the repository (its built-in credentials already work) |

There is no long-lived Google key in GitHub or on the server.

## Notes

- `NEXT_PUBLIC_*` URLs are baked into the frontend image at build time (see `images.yml`).
  If the public domain changes, update `PUBLIC_URL` / `PUBLIC_WS_URL` there and rebuild.
- The VM's `.env` still holds all runtime secrets; images contain none.
- Rolling back is a pull, not a rebuild, so it takes seconds.
- Cost: Artifact Registry storage is billed per GB-month above a small free amount; the
  cleanup policy keeps it to a few pennies.
- Local development is unchanged: `docker compose build` still works (`build:` is kept).
