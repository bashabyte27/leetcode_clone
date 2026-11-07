# BashaByte: Code Judging Engine Plan

_Written November 2026._

## 1. What a judging engine does

```
Django (submit) ──► Job queue (Redis) ──► Judge workers (N servers)
                                              │
                                              ├─ 1. Compile (C/C++/Java/Go/Rust)
                                              ├─ 2. Run each test case inside a SANDBOX
                                              │      limits: CPU time, memory, processes, no network
                                              ├─ 3. Compare output with expected
                                              └─ 4. Push result back ──► Django saves, browser updates
```

### Parts you need
1. **Sandbox (the critical part).** Student code must not be able to read your files, open network connections, fork-bomb the server, or escape.
   - **isolate**: what Judge0 and the IOI olympiad use. Built on Linux namespaces and cgroups. Best choice.
   - **nsjail**: Google's sandbox. Strong, slightly more setup.
   - **gVisor or Firecracker**: stronger isolation through a separate kernel or a micro-VM.
   - **Never** run untrusted code with plain `subprocess` or plain Docker.
2. **Resource limits:** time per test (CPU and wall clock), memory cap, output size cap, process count cap, no network.
3. **Language runtimes:** gcc/g++, OpenJDK, Python, Node, Go and Rust at pinned versions (to match the `Language` table).
4. **Queue and workers:** Redis with RQ or Celery. One job per CPU core per worker. To scale, add workers or servers.
5. **Smart judging:** compile once, then run all test cases. Stop at the first failure. Compare output with `comparable_case_text`, which ignores leading and trailing whitespace on the whole output.
6. **Live results:** the worker writes `SubmissionResult` rows, and the browser checks the submission's status about every second, or results are pushed to it.

---

## 2. Option A: self-host Judge0 (recommended now)

### In plain words
Today the site uses **someone else's copy** of Judge0 (`ce.judge0.com`, the public shared server). Option A means installing **the same open-source Judge0 on your own rented server**. No shared queue, no rate limits, and student code stays private.

The website code barely changes:
```
JUDGE0_URL=https://ce.judge0.com        ← shared public server (today)
JUDGE0_URL=http://<your-server-ip>:2358 ← your own server (Option A)
```

### What runs on the Judge0 server
```
                Your Django website (on Render)
                          │  "run this code with this input"
                          ▼
┌──────────────── Your Judge0 server (e.g. 4 CPU, 8 GB) ────────────────┐
│  1. API server ─── receives the code, gives back a token (ticket no.)  │
│  2. Redis queue ── the line of jobs waiting to run                     │
│  3. Workers ────── run jobs inside "isolate" (time and memory limits,  │
│                    no internet or file access)                         │
│  4. PostgreSQL ─── stores each result until Django asks for it         │
└────────────────────────────────────────────────────────────────────────┘
```
The number of **workers** sets the speed: more CPU cores → more workers → faster results when many students submit together.

### Setup steps
1. Rent an Ubuntu server with 4 CPU cores and 8 GB RAM (Hostinger KVM 4 in Mumbai, or DigitalOcean/AWS).
2. Install Docker and Docker Compose.
3. Download the official Judge0 CE release (it includes `docker-compose.yml` and `judge0.conf`).
4. Edit `judge0.conf`:
   - Set strong database and Redis passwords.
   - Set `AUTHN_HEADER` / `AUTHN_TOKEN` so only your website can use it.
   - Set the worker count to match the CPU cores.
5. Run `docker compose up -d db redis`, wait a few seconds, then `docker compose up -d`.
6. Firewall: allow port 2358 **only** from the website's outbound IPs (Render's static outbound IPs), plus SSH.
7. On Render, set `JUDGE0_URL` and `JUDGE0_AUTH_TOKEN`.
8. Code fix in `submissions/judge0.py`:
   - Poll with `GET /submissions/batch?tokens=t1,t2,...&base64_encoded=false&fields=token,status,stdout,stderr,compile_output,time,memory`, one request per round instead of 18.
   - Save results with `bulk_create`.

### Cost
About ₹1,000–4,000 a month for the server. Judge0 is GPL-licensed, which is fine to self-host and use. Check the licence before redistributing Judge0 itself inside a product you sell.

### Expected result
A single submission should drop from about 50 s to a few seconds.

---

## 3. Option B: own engine built on isolate (later)

### Why
Features Judge0 lacks:
- compile once for all test cases
- special checkers (accept any valid answer)
- per-problem time limits
- exam-mode priority queues
- your own result format

It also gives a stronger product to pitch to colleges.

### How it fits the project
- **New Django app `judge/`:** turns a submission into a job on the Redis queue.
- **Separate `judge-worker` service:** a Python process on dedicated Linux servers.
  1. Pull a job and fetch its test cases.
  2. Compile once inside isolate.
  3. Run each test inside isolate with limits.
  4. Compare output and write the `SubmissionResult` rows.
- **Docker image:** pinned compilers, plus isolate with cgroups v2.
- **Frontend:** submit returns immediately with a submission ID, then the page checks status until it's done. The existing judge animation fits this.
- **Hardening:**
  - Separate server from the web app.
  - No network from the sandbox.
  - Read-only filesystem and a non-root user.
  - Output size caps.

### Effort and cost
- 3–6 weeks for one experienced developer, plus a security review. Hiring it out costs about ₹1.5–4 lakh.
- Capacity: one CPU core judges roughly 3–10 short Python submissions per second, fewer for Java and C++ because of compile time. 8 cores handle a 200-student exam rush comfortably.

### Server cost (₹/month)

| Scale | Setup | Cost |
|---|---|---|
| Practice, about 1 college | 1 judge server, 4 cores / 8 GB | 2,500–4,000 |
| Exam hall, 200–300 students at once | 2–3 judge servers, 8 cores each | 8,000–15,000 |
| Multi-college | Auto-scaling judge servers on AWS or GCP | 20,000+ |
| Redis queue (any scale) | Render or Upstash | 500–1,500 |

---

## 4. Option C: write your own sandbox
Not recommended: months of work, high security risk, and no benefit over isolate or nsjail.

---

## 5. Path
1. **Now:** Option A (self-host Judge0) plus the batch-polling fix.
2. **Next month:** background judging through a Redis queue, so the site never freezes.
3. **When pitching colleges:** Option B on isolate, with compile-once, exam priority queues and special checkers.
