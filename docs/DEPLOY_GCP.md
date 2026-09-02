# Deploying GlassBox to GCP (no AWS, open-source stack)

Single small Compute Engine VM running Docker Compose: FastAPI + Next.js +
Caddy (auto-HTTPS) + optional self-hosted Ollama. Everything in the stack —
Caddy, Docker, FastAPI, Next.js, SQLite, Ollama — is open source; GCP is just
where the containers run, not a dependency you're locked into.

Two subdomains (`app.yourdomain.com` for the UI, `api.yourdomain.com` for the
API) rather than path-based routing on one domain — the frontend's own
`/admin/*` pages collide with the backend's `/admin/*` API prefix otherwise.

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

Create two DNS A records (`app.yourdomain.com`, `api.yourdomain.com`) pointing
at that IP before starting Caddy — it needs both resolving to issue TLS certs.

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
nano .env   # fill in APP_DOMAIN, API_DOMAIN, PUBLIC_API_URL, PUBLIC_WS_URL,
            # GLASSBOX_JWT_SECRET (openssl rand -hex 32), any provider keys
```

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

Caddy will request Let's Encrypt certs for both domains automatically on
first boot — check `docker compose logs caddy -f` if a cert doesn't issue
(usually a DNS propagation delay).

## 5. Verify

```bash
curl -s https://api.yourdomain.com/health
# {"status":"ok"}
```

Then open `https://app.yourdomain.com` in a browser.

## 6. Updating

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
