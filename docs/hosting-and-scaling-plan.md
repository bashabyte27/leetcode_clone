# BashaByte: Hosting, Services and Scaling Plan

_Written November 2026. Prices come from 2026 sources and change often, so check each provider's pricing page before paying. Conversions use roughly ₹88 = $1._

---

## 1. Where the app stands today

| Area | Current state | Problem |
|---|---|---|
| Code judging | Public Judge0 server (`JUDGE0_URL=https://ce.judge0.com`) | Shared with everyone and rate-limited. One submission took about 50 s |
| Judging flow | `submissions/views.py` calls `judge_submission()` inside the web request | The web worker is blocked for the whole judging time |
| Polling | `submissions/judge0.py` → `execute_batch` checks each test token with its own request (18 requests per round) | Slow. Judge0 can return all statuses in one request |
| Cache | None | Every page queries the database again |
| Sessions | Stored in the database | One extra database read per request |
| Media uploads | Saved to `MEDIA_ROOT` on the server's own disk | Render's disk is wiped on every redeploy, and extra app copies can't see the files |
| `DEBUG` | Turns on by default if the `DEBUG` environment variable is unset | Security and performance risk in production |
| Background jobs | None | Exports, emails and leaderboard recalculation all run inside requests |

### What happens when 50 students submit together
- 50 × 18 = 900 code runs hit the public Judge0 at once, so expect rate limits, a long queue and "Internal Error (timeout)" results (`JUDGE0_TIMEOUT=15`).
- The web workers get stuck waiting, so other students can't load pages.
- Worst case with one worker: 50 × 50 s ≈ 40 minutes for the last student.

---

## 2. Recommended services

| Need | Pick | Approx. cost | Notes |
|---|---|---|---|
| Domain (.com) | **Cloudflare Registrar** | ~$10.46/yr (~₹920), same price on renewal | Sold at cost, free WHOIS privacy |
| Domain (.in) | **NameSilo** / **Namemart** | ~$7–10/yr | Look at the renewal price, not the first-year price |
| DNS, SSL, CDN, DDoS protection | **Cloudflare Free** | ₹0 | Put it in front of everything |
| Django app | **Render** (Singapore region) | Starter $7 → Standard $25/mo | Easy to run. Move to a Mumbai server later if latency matters |
| PostgreSQL | **Render Postgres** | Basic-256MB $6 → Basic-1GB $19/mo | Don't use the free plan: it expires after 30 days |
| Redis (cache and job queue) | **Render Key Value** | Starter $10/mo | Needed for caching and background judging |
| Code judge | **Self-hosted Judge0 on a Hostinger KVM VPS (Mumbai)** | KVM 2 ₹799 / KVM 4 ₹1,099 per month intro (+18% GST, renews higher) | Needs a full Linux server; Render can't run it |
| Images, PDFs, uploads | **Cloudflare R2** | 10 GB free, then $0.015/GB, no charge for downloads | Use `django-storages` with the S3 interface |
| Course videos | **Bunny Stream** | Storage ~$0.01/GB, delivery ~$0.03/GB in Asia, free encoding | Adaptive quality, built-in player, signed links |
| Email | **Resend** (already integrated) | Free tier, then low cost | Keep it |
| Payments | **Razorpay** | About 2% + GST per payment (confirm on Razorpay's site) | UPI, cards, net banking |
| Error and uptime alerts | **Sentry** free + **UptimeRobot** free | ₹0 | |

### Considered and not chosen (for now)
- **Hetzner**: two price rises in 2026 and new servers restricted, so it's unreliable to plan around.
- **Cloudflare Stream**: $5 per 1,000 minutes stored and $1 per 1,000 minutes watched. Cost grows quickly with watch time: 1,000 students × 10 h ≈ $600/mo, against about $200 on Bunny.
- **AWS Lightsail Mumbai**: Mumbai plans include only half the usual bandwidth.
- **DigitalOcean managed Postgres**: from about $15/mo; Bangalore availability not confirmed. Good for later.

---

## 3. Course module: media plan
- **Videos:** upload to Bunny Stream and store only the video ID on the `Lesson` model. Bunny's player picks the right quality (360p, 720p or 1080p) for each student's connection.
- **Protection:** use signed (token) URLs and lock playback to your domain. DRM is $99/mo extra; only consider it for paid premium courses.
- **Images, animations (GIF, Lottie, short MP4 clips) and PDFs:** store on Cloudflare R2 and serve through the domain via Cloudflare.
- **Keep video costs down:** use 720p as the default quality. Video delivery is usually the biggest monthly bill.

---

## 4. Scaling roadmap

### Phase 1: code fixes (no extra cost, 1–2 days)
1. Poll Judge0 with one batch-status request per round instead of one request per test token. Save results with `bulk_create`.
2. Make `DEBUG` default to `False`.
3. Add database indexes and remove repeated queries on the dashboard, leaderboard and problem list.
4. Run gunicorn with multiple workers and threads (for example `--workers 3 --threads 4 --timeout 60`).

### Phase 2: Redis and background jobs (~₹1–2k/month)
5. Add Redis: Django cache and cache-backed sessions.
6. Add Celery or Django-RQ. Judging runs in a worker, and the browser checks status about every second.
7. Move exports and leaderboard recalculation to background jobs.

### Phase 3: own judge (~₹3–8k/month)
8. Self-host Judge0 on a 4–8 core server and tune the worker count. Add servers in exam season.

### Phase 4: ready for growth (~₹5–15k/month total)
9. Run 2+ app copies, put Cloudflare in front, and move media to R2.
10. Upgrade the database plan and add a connection pooler (PgBouncer).
11. Add Sentry, load-test with Locust (for example 500 simulated students submitting together), and fix what it finds.

### Monthly cost by stage

| Stage | What runs | ₹ / month |
|---|---|---|
| Launch (a few hundred users) | Render Starter app + Basic PG, 1 Hostinger VPS (Judge0), Cloudflare, R2 free tier, Bunny pay-as-you-go | 2,500–3,500 |
| Colleges onboard (exams with 200–300 students at once) | Render Standard + worker + Redis + 1 GB PG, 2 judge servers, more video delivery | 10,000–18,000 |
| Multi-college (thousands of users) | Several app copies behind a load balancer (AWS Mumbai or DigitalOcean), managed PG with a read copy, judge servers added on exam days | 30,000–80,000+ |

### What to expect
- After Phases 1–2: typically hundreds of page requests per second on modest plans.
- With Phase 3: a hall of 200–300 students submitting together should get results in seconds to about a minute. Load-test before exam day to confirm.
- "Thousands of requests per second" means more app copies and more caching later, paid for only when real traffic arrives.

---

## 5. How this compares with Amazon

| Amazon-scale building block | BashaByte equivalent |
|---|---|
| CDN in front of everything | Cloudflare |
| Many identical app servers behind a load balancer | Render instances or cloud servers. The app must keep no files or state on its own server |
| Caches | Redis |
| Job queues | Celery or RQ |
| Separate fleet for heavy work | Judge0 / judge workers |
| Object storage | Cloudflare R2 / S3 |
| Monitoring and load testing | Sentry, UptimeRobot, Locust |

---

## 6. Launch checklist (in order)
1. [ ] Buy the domain on Cloudflare Registrar and turn on Cloudflare for it.
2. [ ] Move media uploads to Cloudflare R2 (`django-storages`).
3. [ ] Rent a Hostinger Mumbai server and self-host Judge0 (see `docs/judge-engine-plan.md`).
4. [ ] Fix Judge0 polling (one batch request per round) and use `bulk_create` for results.
5. [ ] Make `DEBUG` default to False and set production environment variables on Render.
6. [ ] Add Redis, then move judging to a background worker.
7. [ ] Build the course module on Bunny Stream and R2.
8. [ ] Add Sentry and UptimeRobot, and run a Locust load test before the first exam.

---

## Sources
- Domains: [TheGuideX 2026 registrars](https://theguidex.com/domain-registrars), [TinyTools registrar comparison](https://tinytools-smoky.vercel.app/domain-generator/blog/domain-registrar-comparison-namecheap-cloudflare-porkbun-godaddy-2026/), [DEV: registrars for indie hackers](https://dev.to/devtoolpicks/best-domain-registrars-for-indie-hackers-in-2026-cloudflare-vs-porkbun-vs-namecheap-2ebm), [.IN price comparison](https://domainoffer.net/tld/in)
- Render: [Render pricing](https://render.com/pricing), [Render pricing 2026 review](https://temps.sh/blog/render-pricing-2026)
- VPS and cloud: [Hostinger VPS India price](https://zoutons.com/news/hostinger-vps-hosting-price-india-2026), [Valebyte India VPS](https://valebyte.com/en/vps/india/?city=Mumbai), [Hetzner June 2026 increase](https://wz-it.com/en/blog/hetzner-price-increase-june-2026-cpx-ccx-alternatives/), [Lightsail pricing guide](https://cloudburn.io/blog/amazon-lightsail-pricing), [DigitalOcean Postgres pricing](https://docs.digitalocean.com/products/databases/postgresql/details/pricing/)
- Storage and video: [Cloudflare R2 pricing explained](https://mecanik.dev/en/posts/cloudflare-r2-pricing-explained-real-costs-vs-s3-and-backblaze/), [Cloudflare Stream pricing](https://developers.cloudflare.com/stream/pricing), [Bunny Stream pricing](https://bunny.net/pricing/stream/), [Bunny Stream docs](https://docs.bunny.net/stream/pricing)
- Payments: [Razorpay UPI MDR explained](https://razorpay.com/blog/upi-mdr-for-merchants-in-payment-gateway-explained/)
