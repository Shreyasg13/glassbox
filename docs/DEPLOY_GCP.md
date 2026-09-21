# Deploying GlassBox to GCP (no AWS, open-source stack)

Single small Compute Engine VM running Docker Compose: FastAPI + Next.js +
Caddy (auto-HTTPS) + optional self-hosted Ollama. Everything in the stack —
Caddy, Docker, FastAPI, Next.js, SQLite, Ollama — is open source; GCP is just
where the containers run, not a dependency you're locked into.

Single domain, path-based routing (`deploy/Caddyfile`) — the backend's
`/admin` and `/reports` API routers live under `/api/admin` and
`/api/reports` specifically so they don't collide with the frontend's own
`/admin/*` and `/reports/*` pages at those exact paths. Everything under
`/api/*`, `/auth/*`, `/health`, or `/ws/*` goes to the backend; everything
else goes to the frontend. (An earlier version of this deploy used two
subdomains — `app.` / `api.` — to sidestep the collision instead; that's
no longer necessary now that the colliding backend prefixes were renamed.)

## 0. Prerequisites

- A GCP project with billing enabled, `gcloud` CLI installed and authenticated
  (`gcloud auth login`).
- A domain you control, so you can point two A records at the VM's IP.
- This repo pushed somewhere the VM can `git clone`/`git pull` from (a
  private GitHub repo is fine — set up a deploy key or use `gh` auth on the VM).

## 1. Provision the VM

```bash
gcloud config set project YOUR_PROJECT_ID

# e2-small is the safe default (2 vCPU burst, 2GB). e2-micro (free-tier
# eligible) can work since the frontend runs Next's standalone build, but
# it's tight under load — start on e2-small and downsize later if idle.
gcloud compute instances create glassbox-vm \
  --zone=us-central1-a \
  --machine-type=e2-small \
  --image-family=debian-12 \
  --image-project=debian-cloud \
  --boot-disk-size=30GB \
  --tags=http-server,https-server

# Firewall: open 80/443 (skip if your project already has these tags rigged up)
gcloud compute firewall-rules create allow-http \
  --allow=tcp:80 --target-tags=http-server
gcloud compute firewall-rules create allow-https \
  --allow=tcp:443 --target-tags=https-server

# Grab the external IP and point your DNS at it
gcloud compute instances describe glassbox-vm --zone=us-central1-a \
  --format='get(networkInterfaces[0].accessConfigs[0].natIP)'
```

Create one DNS A record (`yourdomain.com`) pointing at that IP before
starting Caddy — it needs to resolve to issue a TLS cert. (Any registrar
works, including free dynamic-DNS style ones like DuckDNS as long as the
VM's IP is static, which a GCP Compute Engine external IP is by default.)

## 2. Install Docker on the VM

```bash
gcloud compute ssh glassbox-vm --zone=us-central1-a
```

Then on the VM:

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
newgrp docker
```

## 3. Clone and configure

```bash
git clone <this-repo-url> glassbox   # or however you're hosting it
cd glassbox
git clone https://github.com/Shreyasg13/multi-agent-trading-system backend-source
cp .env.example .env
nano .env   # fill in APP_DOMAIN, PUBLIC_API_URL, PUBLIC_WS_URL, any provider keys,
            # and the auth secrets generated below
```

Generate the auth secrets (prints lines to paste into `.env`; nothing is stored):

```bash
docker compose run --rm backend python -m app.scripts.gen_secrets --admin
# -> GLASSBOX_JWT_SECRET=...  and  GLASSBOX_ADMIN_PASSWORD_HASH='$2b$12$...'
```

The admin login is username `admin` plus the password you type at that prompt.
There is no built-in default admin, and the backend refuses to start in
production without a real `GLASSBOX_JWT_SECRET`. Keep the single quotes around
the hash (it contains `$` characters, which compose would otherwise expand).

`backend-source` must sit inside the `glassbox` repo directory, alongside
`backend/` and `frontend/` (the compose file mounts `./backend-source` —
adjust the `volumes:` path in `docker-compose.yml` if your layout differs).
`TRADING_STORAGE_PATH` almost
certainly won't exist on the VM (it's a Windows dev-machine path) — leave it
unset in `.env`; `data_source.py` falls back to reading `reports/` and still
serves real data, just without the live parquet-derived detail.

## 4. Bring it up

```bash
docker compose up -d --build
# add local Ollama too:
docker compose --profile local-llm up -d --build
```

Caddy will request a Let's Encrypt cert for the domain automatically on
first boot — check `docker compose logs caddy -f` if a cert doesn't issue
(usually a DNS propagation delay).

## 5. Verify

```bash
curl -s https://yourdomain.com/health
# {"status":"ok"}
```

Then open `https://yourdomain.com` in a browser.

## 6. Updating

> **Preferred (current) flow: CI-built images, pulled by the VM -- see docs/DEPLOY_IMAGES.md**
> (`deploy/deploy.sh <tag>`). The build-on-the-VM commands below still work but are what
> used to exhaust the VM's memory.


```bash
cd glassbox && git pull
docker compose up -d --build
```

No registry, no CI needed for this — add GitHub Actions later (build +
`gcloud compute ssh ... -- 'cd glassbox && git pull && docker compose up -d --build'`)
once the manual flow is stable and you want push-to-deploy.

## 6b. Daily market-data refresh (cron)

`./trading-storage` is bind-mounted read-write into the backend container
at `/data/trading-storage`. A host crontab entry runs the refresh script
inside that container once per weekday, after US market close:

```
0 22 * * 1-5 cd /home/shrey/glassbox && /usr/bin/docker compose exec -T backend python -m app.scripts.update_daily_data >> /home/shrey/glassbox/logs/daily_sync.log 2>&1
```

(`22:00 UTC` = 5pm ET; weekdays only. Registered via `crontab -e` / the
append pattern `(crontab -l 2>/dev/null; echo '<line>') | crontab -` so an
existing crontab isn't clobbered.)

What it does: for each of the 15 tracked symbols, fetches the last ~10 days
from yfinance, merges into the existing full-history parquet file by date
(existing history is never dropped — the script refuses to write if the
merged row count would be lower or the earliest date would shift), recomputes
`RSI`/`MA_10..200`/`Volatility`/`Volume_MA` over the full series, and writes
back atomically (temp file + `os.replace`).

- **Check it ran**: `ssh ... 'tail -50 ~/glassbox/logs/daily_sync.log'` or
  `crontab -l` to confirm the entry is still registered.
- **Run it manually**: `docker compose exec -T backend python -m app.scripts.update_daily_data`
- **Schema note**: the parquet files this reads/writes use a different
  column set than `backend-source/live_trading/LIVE_DATA_CONNECTOR.py`
  produces (that script's `DataStorageManager` writes to a different,
  nested path entirely) — `update_daily_data.py` targets the exact schema
  the running backend (`app/data_source.py`) actually reads, verified
  directly against the live parquet files rather than assumed from the
  legacy script.

## 6c. Paper-trading cycle (cron)

Runs the simulated portfolios forward one day (see docs/PROJECT_STATUS.md,
"Phase 1"). Once, to create the accounts and backfill history:

```bash
docker compose exec -T backend python -m app.scripts.run_paper_cycle --bootstrap
```

Then daily, AFTER the committee review (which starts at 22:15 -- see 6d; the committee's calls feed the
"Committee on all symbols" account, and the script waits for a review still in progress) (`crontab -e`):

```
45 22 * * 1-5 cd /home/shrey/glassbox && /usr/bin/docker compose exec -T backend python -m app.scripts.run_paper_cycle >> /home/shrey/glassbox/logs/paper_cycle.log 2>&1
```

- **Check it ran**: `tail -30 ~/glassbox/logs/paper_cycle.log`, or Admin -> Paper Trading.
- **Idempotent**: running it twice on the same data does nothing the second time.
- **Dry run**: add `--dry-run` to compute and print without saving.
- Optional env: `PAPER_LLM_NARRATIVES=1` (adds an AI note to reports, best-effort),
  `PAPER_BACKTEST_START`, `PAPER_COMMISSION_BPS`.

## 6d. Daily Investment Committee review (cron)

Runs the 10-agent Investment Committee on a few symbols each trading day and saves every
decision (Admin -> Paper Trading -> "Investment Committee"; a daily report lands in Admin ->
Reports). Schedule it AFTER the data sync (22:00) and BEFORE the paper cycle (22:45): the
committee's calls feed the "Committee on all symbols" paper account, so they must exist when the
cycle runs. 22:15 UTC = 6:15 pm US Eastern (5:15 pm in winter), after the 4 pm close in both
seasons; a full review takes 2-6 minutes, well inside the 30-minute gap:

```
15 22 * * 1-5 cd /home/shrey/glassbox && /usr/bin/docker compose exec -T backend python -m app.scripts.run_committee_daily >> /home/shrey/glassbox/logs/committee_daily.log 2>&1
```

- **Which symbols**: BUY/SELL signals and signals that just changed (up to `COMMITTEE_MAX_SYMBOLS`),
  topped up to `COMMITTEE_MIN_SYMBOLS` with the biggest 5-day movers -- typically 2-3 symbols,
  14-21 model calls a day, which fits the free tiers (Gemini, then the failover providers).
- **Idempotent**: one decision per date+symbol. A holiday (no new price bar) or a second run does nothing.
- **Try it**: `docker compose exec -T backend python -m app.scripts.run_committee_daily --dry-run`
  shows today's picks without calling a model; `--force` re-reviews; `--symbols AAPL,NVDA` overrides.
- **Check it ran**: `tail -30 ~/glassbox/logs/committee_daily.log`. Exit code 1 = it could not run
  (stale prices) or every model call failed.

## 7. Claude via Vertex AI instead of the direct Anthropic API (optional)

If you'd rather keep LLM billing entirely inside your GCP project: GCP's
Vertex AI hosts Claude models through the `AnthropicVertex` client (GCP
credentials, no separate Anthropic API key). This needs a small change to
`backend/app/providers/claude.py` to support a Vertex auth mode — flag it if
you want this wired in; it's not done by default since it requires enabling
Claude in your project's Vertex AI Model Garden first.

## Notes on the "open source to maintain" constraint

- Nothing here is GCP-proprietary except the VM itself and (optionally)
  Vertex AI for Claude routing. Swap the VM for any other host — Hetzner,
  a bare-metal box, another cloud — and the `docker compose up -d` step is
  identical.
- SQLite is fine for one VM. If you outgrow it, swap in a Postgres
  container (`postgres:16-alpine` image, update `DATABASE_URL` in
  `backend/app/db.py`) rather than a managed Cloud SQL instance, to keep the
  stack self-hostable.
- Caddy was chosen over nginx specifically for its zero-config automatic
  HTTPS — one less thing to hand-maintain certs for.
