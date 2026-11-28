# Pome

A minimal Next.js + TypeScript web app scaffold with a local development workflow,
a multi-stage production container, and Docker Compose files for both dev and prod.

## Contents

- [POME decision app (Streamlit)](#pome-decision-app-streamlit)
- [Overview](#overview)
- [Tech stack](#tech-stack)
- [Prerequisites](#prerequisites)
- [Project structure](#project-structure)
- [Local development](#local-development)
- [npm scripts](#npm-scripts)
- [Environment variables](#environment-variables)
- [Docker](#docker)
- [Health check](#health-check)
- [Git](#git)
- [Agent skills](#agent-skills)
- [Troubleshooting](#troubleshooting)

## POME decision app (Streamlit)

The Python app in `pome/` is separate from the Next.js scaffold below. It replays
recorded results from `runs/records`, so it needs no API key and makes no live calls.

```bash
uv sync
uv run python -m streamlit run pome/app/home.py
```

Open http://localhost:8501. Use `python -m streamlit`, not `streamlit run` on its own:
the plain command does not put the repo root on the import path and fails with
`ModuleNotFoundError: No module named 'pome'`.

What the page shows (2026-11-23): the question "Which model and hosting plan should you use?",
an answer box with the recommended model, hosting plan and monthly cost (INR), and tabs for
Gates, Baselines, Cost, Evidence, Deployment variants and Configurations. Baselines shows
what simpler benchmark and cost rules would pick instead, with the cost difference and the gates each one fails. The sidebar sets tickets per
month, max monthly spend, max error rate, hosting scope and infrastructure costs. It has a Tweak mode toggle per
gate. In the Gates tab, threshold sliders update a separate what-if result.
Opt-in compliance filters apply to the main recommendation. See [Compliance screening](docs/compliance.md)
for the India and zero-retention preset, evidence, and buyer review setup. See [Hosting distinction](docs/distinction.md) for cost and deployment details.

In a container: `docker compose -f compose.pome.yaml up --build`, then open the same address
(start Docker Desktop first on Windows; verified on the owner's PC 2026-11-23).
Tests: `uv run pytest -q`. Lint: `uv run ruff check .`.
Secrets scan: `gitleaks git . --redact --no-banner` (history scan; `.gitleaksignore` lists 15
verified false positives, all config IDs containing "api"). Use `git`, not `dir`: `dir` also
reads the gitignored `.env`.

Status 2026-11-23: 427 tests pass; the same inputs give decision hash `e9ad4c71d6a2` every
run. With the default settings (1,00,000 tickets a month, max spend ₹1,39,195, max error rate
1.0%) the app recommends gpt-5.4-nano on the OpenAI API (global endpoint) at ₹3,433 a month,
from published vendor data (cost MODELED); 3 of 20 configurations pass every gate. Evidence
sources and the full results table: `docs/research/evidence-plan.md` ("Status 2026-11-23").
Gate thresholds and rules: `CONSTRAINTS.md`. Product and wording rules: `PRODUCT.md`.

## Overview

Pome is a starting point for a web app, not a finished application. It ships with a
starter page, a health endpoint, and container definitions so the same code can run
locally without Docker or in a small, non-root production image.

The production container uses Next.js's `standalone` output: `next build` emits a
self-contained `server.js` plus only the dependencies it needs, which is copied into
a bare `node:24-alpine` runtime image.

## Tech stack

| Component | Version / choice |
| --- | --- |
| Framework | Next.js 16 (App Router, Turbopack builds) |
| UI | React 19 |
| Language | TypeScript 5.9 (strict mode) |
| Runtime | Node.js >= 20.9 locally; Node 24 Alpine in containers |
| Container orchestration | Docker Compose v2 (`docker compose`) |
| Package manager | npm, with a committed `package-lock.json` |

## Prerequisites

- Node.js 20.9 or newer and npm (for local development)
- Docker Engine with the Compose plugin, e.g. Docker Desktop (for containers)
- Git (the repository is already initialized)

Check your tools:

```bash
node --version
npm --version
docker compose version
git --version
```

## Project structure

```text
.
├── app/                        # Next.js App Router
│   ├── api/health/route.ts     # GET /api/health, used by the Docker healthcheck
│   ├── globals.css             # Global styles
│   ├── layout.tsx              # Root layout and page metadata
│   └── page.tsx                # Starter page at /
├── public/                     # Static assets served at the site root
├── .opencode/skills/           # Local-only agent skills (git-ignored)
│   ├── cli-serve/
│   └── omni-auth/
├── .dockerignore               # Files excluded from the Docker build context
├── .env.example                # Template for environment variables
├── .gitignore                  # Ignored files, including .opencode/skills/
├── Dockerfile                  # Multi-stage production image
├── Dockerfile.dev              # Development image with hot reload
├── compose.yaml                # Production Compose stack
├── compose.dev.yaml            # Development Compose stack
├── next.config.ts              # Enables the standalone build output
├── package.json                # Dependencies and scripts
├── package-lock.json           # Locked dependency tree (used by npm ci)
├── README.md                   # This file
└── tsconfig.json               # TypeScript configuration
```

Generated and ignored by Git: `node_modules/`, `.next/`, `*.tsbuildinfo`,
`next-env.d.ts`, and `.env*` (except `.env.example`).

## Local development

No Docker required:

```bash
npm install       # once, or after changing package.json
npm run dev       # http://localhost:3000
```

The dev server supports hot reload: edit `app/page.tsx` or `app/globals.css` and the
browser updates automatically. To serve on another port:

```bash
npm run dev -- -p 3001
```

### npm scripts

| Command | What it does |
| --- | --- |
| `npm run dev` | Start the Next.js development server on port 3000 |
| `npm run build` | Create the optimized production build (`.next/standalone`) |
| `npm start` | Serve an existing production build (`npm run build` first) |
| `npm run typecheck` | Run `tsc --noEmit` without producing files |

A typical verification pass before committing:

```bash
npm run typecheck
npm run build
```

## Environment variables

- Copy `.env.example` to `.env.local` for local Next.js variables. `NEXT_PUBLIC_*`
  variables are exposed to the browser; keep secrets server-side and unprefixed.
- For Compose, create a `.env` file next to `compose.yaml`, then uncomment the
  `env_file` block in `compose.yaml`.
- `.env`, `.env.*`, and `.env.local` are git-ignored. Only `.env.example` is tracked.
  Never commit real keys or passwords.

## Docker

The images use `node:24-alpine`. To use a different Node base image, override the
build argument:

```bash
docker compose -f compose.dev.yaml build --build-arg NODE_VERSION=22-alpine
```

### Development

Builds `Dockerfile.dev`, runs `next dev` bound to `0.0.0.0`, and bind-mounts the
source directory for hot reload. Anonymous volumes keep container-owned
`node_modules` and `.next` from being overwritten by the host mount.

```bash
docker compose -f compose.dev.yaml up --build     # foreground
docker compose -f compose.dev.yaml up --build -d  # background
docker compose -f compose.dev.yaml logs -f web
docker compose -f compose.dev.yaml down
```

### Production

Builds `Dockerfile` in three stages (`deps` → `builder` → `runner`). The final image
contains the standalone server and static assets, runs as the unprivileged `nextjs`
user, listens on port 3000, and has a healthcheck.

```bash
docker compose -f compose.yaml up --build -d
docker compose -f compose.yaml ps
docker compose -f compose.yaml logs -f web
docker compose -f compose.yaml down
```

In both cases the app is available at <http://localhost:3000>. To change the host
port, edit the `ports` entry in the corresponding Compose file.

## Health check

`GET /api/health` returns a JSON body such as:

```json
{ "status": "ok", "timestamp": "2026-11-22T12:00:00.000Z" }
```

It is marked dynamic so it is evaluated per request, and the production container
polls it with `wget` every 30 seconds.

## Git

The repository is initialized on `main` with an initial commit. Ignore rules cover
`node_modules/`, `.next/`, local env files, build artifacts, and local agent skills.

The remote is https://github.com/bleng0/Chatbot-Recommendations (branch `main`). Commits are
authored as bleng0 and carry no AI attribution lines. Run the secrets scan above before pushing. Day-to-day workflow:

```bash
git status                       # see what changed
git add .                        # stage changes
git commit -m "describe change"
git push                         # push to the upstream branch
```

## Agent skills

Two project-local OpenCode skills are installed on this machine but intentionally
**not tracked by Git** (see `.opencode/skills/` in `.gitignore`):

| Skill | Purpose |
| --- | --- |
| `omni-auth` | Authentication and session-token endpoints of the OmniRoute API |
| `cli-serve` | Starting, stopping, and configuring the OmniRoute CLI/server |

They come from `cheaper-inference/OmniRoute` and are available to agents working in
this directory. To recreate them on another machine:

```bash
mkdir -p .opencode/skills/omni-auth .opencode/skills/cli-serve
curl -L -o .opencode/skills/omni-auth/SKILL.md \
  https://raw.githubusercontent.com/cheaper-inference/OmniRoute/release/v3.8.55/skills/omni-auth/SKILL.md
curl -L -o .opencode/skills/cli-serve/SKILL.md \
  https://raw.githubusercontent.com/cheaper-inference/OmniRoute/release/v3.8.55/skills/cli-serve/SKILL.md
```

## Troubleshooting

| Problem | Fix |
| --- | --- |
| `EADDRINUSE` / port 3000 already in use | Stop the other process or change the port (`npm run dev -- -p 3001`, or the `ports` value in Compose) |
| `docker: command not found` | Install Docker Desktop and confirm with `docker compose version` |
| Dev container has stale dependencies | `docker compose -f compose.dev.yaml down -v` then `up --build` |
| Container is unhealthy | Check `docker compose logs web` and `curl http://localhost:3000/api/health` |
| Type or build errors after a dependency update | Delete `.next` and `node_modules`, run `npm install`, then `npm run typecheck && npm run build` |
| Node version too old | Install Node 20.9+ locally, or override `NODE_VERSION` in the Docker build |
