# CloudWeaver PRD

## Original problem statement
Build a production-ready, highly responsive web application named CloudWeaver: Intelligent Multi-Cloud Cost Optimization & Workload Migration System with JWT/email authentication and Google login, persistent workload history, exact AWS/Azure/GCP INR cost comparisons, recommendation and savings analytics, migration planning, settings, and an AI assistant.

## Architecture decisions
- React frontend with responsive CSS, Recharts, and Lucide icons.
- FastAPI backend with MongoDB via the existing `MONGO_URL` and `DB_NAME` environment values.
- JWT access/refresh cookies for email/password authentication.
- Exact provider rate calculations run server-side and analysis snapshots persist per user.
- Gemini 3 Flash is wired through the Emergent LLM integration for the assistant.

## User personas
- Cloud engineers comparing providers for a workload.
- Engineering managers evaluating monthly and annual infrastructure savings.
- Platform teams planning portable, staged workload migrations.

## Core requirements (static)
- Secure account access, guarded workspace, logout, and user profile.
- Workload inputs for CPU, memory, storage, hours, and region.
- AWS/Azure/GCP comparison, recommendation, savings, chart, and history.
- Migration workflow and assistant drawer.
- Responsive navigation and mobile sidebar.

## What's implemented
- 2026-10-07: Built CloudWeaver workspace, auth, dashboard, analysis API, history, planner, settings, and assistant.
- 2026-10-07: Fixed auth form label layout so each field renders line by line at desktop and mobile widths.
- 2026-10-07: Verified frontend build and live auth visual state; full end-to-end testing completed in iteration 1.

## Prioritized backlog
- P0: Configure Google OAuth client credentials and replace the configuration-ready 501 endpoint with verified OAuth exchange.
- P1: Add five-attempt login lockout and existing-admin password rotation from environment credentials.
- P1: Add workload deletion/export and richer migration plan persistence.
- P2: Add team workspaces, cost alerts, and provider pricing refresh jobs.

## Next tasks
- Implement auth hardening and retest security flows.
- Configure and test Google OAuth end to end.
- Add richer workload detail views and migration checklist persistence.