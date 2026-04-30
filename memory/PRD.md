# Autopilot — Passive Income OS (PRD)

## Original Problem Statement
"Build me passive income setup on auto pilot."

User confirmed "all of the above": full opportunity hub combining dashboard tracker + AI idea
generator + auto content/affiliate generator + crypto/stock DCA simulator + AI coach chat.
AI model: Claude Sonnet 4.5 (via EMERGENT_LLM_KEY / emergentintegrations). Auth: JWT
email/password. Design: distinctive deep-forest-green premium wealth-OS (no purple/Inter).

## Personas
- Aspiring builder with some skills and time, wanting first $1 of passive income.
- Existing side-hustler with multiple streams, wanting one cockpit to track and grow them.
- Long-term investor planning compound growth and a "freedom number".

## Core Requirements (static)
- Secure JWT auth (register, login, me).
- Track multiple income streams (10 categories), log income entries, see aggregate earnings.
- Dashboard with monthly income, all-time earned, invested, active streams, 6-month trend,
  category breakdown, goal progress, recent activity.
- AI Idea Engine (Claude Sonnet 4.5, 5 tailored ideas with action plans & tools).
- AI Content Generator (SEO blog post with affiliate placeholders, copy-ready markdown).
- DCA compound-growth simulator with area chart.
- AI Coach chat with persistent multi-turn sessions.
- Goals page: monthly target + freedom number.

## Architecture
- Backend: FastAPI + MongoDB (motor) + bcrypt + pyjwt + emergentintegrations (Claude Sonnet 4.5).
- Frontend: React 19 + react-router-dom v7 + axios + recharts + framer-motion + lucide-react.
- All API routes prefixed with `/api`. Frontend uses `REACT_APP_BACKEND_URL`.
- Theme: Deep Forest Green dark mode. Cormorant Garamond (serif) + Chivo (sans) + JetBrains Mono.

## Implemented (2026-04-30)
- Auth: register/login/me with JWT (14-day expiry) and bcrypt.
- Streams: CRUD + entries CRUD + total_earned aggregation.
- Dashboard summary endpoint (trend, breakdown, goal, recent).
- Goals upsert (single doc per user).
- AI Ideas (structured JSON via Claude Sonnet 4.5).
- AI Content (structured JSON).
- AI Coach chat (multi-turn with session persistence in MongoDB + LlmChat session_id memory).
- DCA Simulator (pure math, no auth required).
- Landing, Login, Register, AppLayout (sidebar), Dashboard, Streams, Ideas, Content,
  Simulator, Coach, Goals pages — all with `data-testid` coverage.
- Tested: Backend 26/26 (100% on retry), Frontend 8/8 critical flows.

## Backlog / Nice-to-haves
- P1: Silence Recharts `width/height` console warning with `min-h-[260px]` on chart wrappers.
- P1: Friendlier 502 retry UX on /api/ai/* endpoints (transient throttling).
- P1: Edit stream (currently only create/delete).
- P2: Export streams/entries to CSV.
- P2: Weekly action-plan email digest (SendGrid integration).
- P2: Stripe subscription for Pro (unlimited AI generations).
- P2: Google OAuth login (Emergent-managed).
- P2: Browser push reminders to log income weekly.

## Next Action Items
- Collect feedback from user on overall look and any specific flow to refine.
- Consider adding Stripe for a Pro tier (monetization pathway).
