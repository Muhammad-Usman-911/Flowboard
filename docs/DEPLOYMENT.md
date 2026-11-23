# Publish Flowboard for free

Flowboard has four parts. Each one needs a home on the internet:

| Part | What it is | Needs |
|---|---|---|
| **Web** | The React app (static files after `npm run build`) | Any static host |
| **API** | FastAPI + WebSockets (`backend/`, has a `Dockerfile`) | A host that runs a Docker container and keeps WebSockets open |
| **Database** | PostgreSQL 16 | A hosted Postgres |
| **Redis** | Login rate limits + pub/sub for live updates | A Redis with a normal TCP URL (`redis://` or `rediss://`) |

There are two free ways to do it. Pick one.

| | **Option A: free managed services** | **Option B: one free VM** |
|---|---|---|
| Effort | ~30 minutes, no server to manage | ~1 hour, you manage a Linux server |
| Uses | Cloudflare Pages + Render + Neon + Upstash | Oracle Cloud "Always Free" VM + Docker Compose |
| Sleeps when idle? | Yes. The API sleeps after 15 min idle and takes up to a minute to wake up | No, always on |
| File attachments | Lost when the API restarts or sleeps | Kept (Docker volume) |
| Best for | Portfolio, demos, trying it out | A small team using it every day |

> Free plans change often. The limits below were checked in November 2026. Check each provider's
> pricing page before you depend on them.

---

## Option A: free managed services

```
 browser ──▶ Cloudflare Pages (web)  ──HTTPS + WSS──▶ Render (API container)
                                                        │            │
                                                   Neon Postgres  Upstash Redis
```

### 1. Database: Neon (free Postgres)

1. Sign up at [neon.com](https://neon.com) and create a project (pick the region closest to your API).
2. Open **Connect**. Turn **off** "Connection pooling" so you get the **direct** host
   (no `-pooler` in the name). The API uses asyncpg, which does not work well behind PgBouncer.
3. Copy the URL and change it to the asyncpg form. Replace the start and the SSL option:

   ```
   Neon gives you:  postgresql://USER:PASSWORD@ep-xxx.eu-central-1.aws.neon.tech/neondb?sslmode=require
   Flowboard needs: postgresql+asyncpg://USER:PASSWORD@ep-xxx.eu-central-1.aws.neon.tech/neondb?ssl=require
   ```

   That is your `DATABASE_URL`.

Why not Render's own free Postgres? It is deleted 30 days after you create it. Neon's free plan does not expire.
(Supabase also works, but it pauses free projects after a week without use.)

### 2. Redis: Upstash (free Redis)

1. Sign up at [upstash.com](https://upstash.com) → **Create database** → Redis, same region as the API.
2. On the database page, copy the **TCP** URL that starts with `rediss://` (not the REST URL).
   That is your `REDIS_URL`.

The free plan gives 256 MB and 500K commands per month, which is plenty for a small team.

### 3. API: Render (free web service)

1. Push Flowboard to GitHub (it already is: `Muhammad-Usman-911/Flowboard`).
2. Sign up at [render.com](https://render.com) → **New → Web Service** → connect the repo.
3. Settings:

   | Field | Value |
   |---|---|
   | Language / Runtime | **Docker** |
   | Root Directory | `backend` |
   | Instance type | **Free** |
   | Health Check Path | `/health` |

4. **Environment variables:**

   | Key | Value |
   |---|---|
   | `DATABASE_URL` | the Neon URL from step 1 |
   | `REDIS_URL` | the Upstash `rediss://` URL from step 2 |
   | `SECRET_KEY` | a long random string: `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
   | `CORS_ORIGINS` | your web URL from step 4, e.g. `https://flowboard.pages.dev` (no trailing slash) |
   | `ENVIRONMENT` | `production` |
   | `PORT` | `8000` (the port the container listens on) |
   | `SEED_DEMO_DATA` | `true` for a demo site with the demo accounts, `false` for real use |

5. **Create Web Service**. The container runs the database migrations on start
   (`backend/docker-entrypoint.sh`), then starts the API.
6. Check it: open `https://<your-service>.onrender.com/health`. You should see
   `{"status":"ok","database":"ok","redis":"ok"}`. Swagger is at `/docs`.

Free plan limits you should know:

- The service **sleeps after 15 minutes** with no traffic; the next request wakes it in up to a minute.
  To keep a demo awake, add a free monitor on [UptimeRobot](https://uptimerobot.com) that opens
  `/health` every 5 minutes. One service running all month uses ~744 of the 750 free hours.
- The disk is **not kept**: uploaded attachments disappear when the service restarts or sleeps.
  For real use, choose Option B, or a paid instance with a persistent disk.

### 4. Web: Cloudflare Pages (free static hosting)

1. Sign up at [pages.cloudflare.com](https://pages.cloudflare.com) → **Create → Pages → Connect to Git** → pick the repo.
2. Build settings:

   | Field | Value |
   |---|---|
   | Framework preset | Vite (or None) |
   | Root directory | `frontend` |
   | Build command | `npm run build` |
   | Build output directory | `dist` |

3. **Environment variables** (they are baked into the build, so redeploy after changing them):

   | Key | Value |
   |---|---|
   | `VITE_API_URL` | `https://<your-service>.onrender.com/api/v1` |
   | `VITE_WS_URL` | `wss://<your-service>.onrender.com` |
   | `NODE_VERSION` | `20` |

4. Deploy. You get `https://<project>.pages.dev`. Put that exact URL in the API's `CORS_ORIGINS`
   on Render and let Render redeploy.

Cloudflare Pages already sends unknown paths such as `/boards/3` to `index.html`, so React Router works.
The walkthrough video in `frontend/public/media/` is deployed with the site and plays at `/tour`.

**Netlify or Vercel instead of Cloudflare?** Same settings (base directory `frontend`, build
`npm run build`, output `dist`, same two `VITE_` variables). Add a single-page-app rewrite:

- Netlify: create `frontend/public/_redirects` with the line `/*  /index.html  200`
- Vercel: create `frontend/vercel.json` with
  `{ "rewrites": [{ "source": "/(.*)", "destination": "/index.html" }] }`

### 5. Test it

1. Open the web URL → **Watch the 90-second tour** link under the login card.
2. Log in (demo: `owner@flowboard.dev` / `Password123` if `SEED_DEMO_DATA=true`).
3. Open the same board in a private window as `member@flowboard.dev` and drag a card. The
   other window should update. If the board header does not say **Live**, check `VITE_WS_URL`
   (must start with `wss://`) and that the API is awake.

---

## Option B: one free VM (always on, keeps uploads)

Oracle Cloud's **Always Free** tier includes an Arm VM (up to 4 CPUs / 24 GB RAM) that never
expires. It needs a card for identity checks at sign-up, but Always Free resources are not charged.
Any other VPS works the same way.

### 1. Create the VM

1. Sign up at [oracle.com/cloud/free](https://www.oracle.com/cloud/free/).
2. **Compute → Instances → Create**: image **Ubuntu 24.04**, shape **VM.Standard.A1.Flex**
   (Ampere, Always Free eligible), e.g. 2 OCPU / 12 GB. Add your SSH key.
3. In the instance's **VCN → Security List**, add ingress rules for TCP ports **80** and **443**.
4. On the VM, open the same ports in the OS firewall (Oracle's Ubuntu image blocks them by default):

   ```bash
   sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
   sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT
   sudo netfilter-persistent save
   ```

### 2. Get a free domain name

Use [DuckDNS](https://www.duckdns.org): sign in, create e.g. `myflowboard.duckdns.org` and set it
to the VM's public IP. (If you own a domain, point an `A` record at the IP instead.)

### 3. Install Docker and start Flowboard

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER && newgrp docker

git clone https://github.com/Muhammad-Usman-911/Flowboard.git && cd Flowboard
cp .env.example .env
```

Edit `.env`:

```bash
SECRET_KEY=<long random string>
POSTGRES_PASSWORD=<strong password>
CORS_ORIGINS=https://myflowboard.duckdns.org
ENVIRONMENT=production
SEED_DEMO_DATA=false        # true if you want the demo accounts
WEB_PORT=8080               # Caddy (below) takes 80/443
```

```bash
docker compose up -d --build
```

The database, Redis and API ports are also published on the host by `docker-compose.yml`. They are
blocked from outside by the firewall rules above (only 80/443 are open); keep it that way.

### 4. Free HTTPS with Caddy

Caddy gets and renews a Let's Encrypt certificate on its own, and proxies WebSockets without extra setup.

```bash
sudo apt install -y caddy
echo 'myflowboard.duckdns.org {
    reverse_proxy localhost:8080
}' | sudo tee /etc/caddy/Caddyfile
sudo systemctl reload caddy
```

Open `https://myflowboard.duckdns.org`. The web container's nginx already forwards `/api` and `/ws`
to the API, so no `VITE_` variables are needed.

### 5. Updates and backups

```bash
git pull && docker compose up -d --build                    # deploy a new version
docker compose exec db pg_dump -U flowboard flowboard > backup-$(date +%F).sql   # back up the database
```

---

## Production checklist

- [ ] `SECRET_KEY` is a new random value (never the one from `.env.example`).
- [ ] `CORS_ORIGINS` is exactly your web URL (scheme + host, no trailing slash).
- [ ] `SEED_DEMO_DATA=false` unless the site is a public demo (the demo passwords are public).
- [ ] `/health` returns `ok` for both `database` and `redis`.
- [ ] The board shows **Live** in two browsers at once.
- [ ] Database backups: Neon keeps a short restore history on the free plan; on a VM, schedule `pg_dump`.
