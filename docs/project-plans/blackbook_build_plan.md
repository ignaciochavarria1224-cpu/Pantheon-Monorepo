# BlackBook Build Plan

This document turns the BlackBook vision into a practical build and migration roadmap.

It assumes the current Streamlit BlackBook at `active/BlackBook` is the live source of truth today, while `active/Pantheon/apps/blackbook` is the long-term destination inside Pantheon.

## Planning Inputs

This plan is based on:

- the BlackBook vision document
- the current live Streamlit BlackBook app
- the current Pantheon consolidation plan
- the current repo status tracker

Those sources agree on one important point:

- BlackBook must end up native inside Pantheon
- but the working Streamlit app is still the real product truth today

The plan therefore follows a staged migration strategy rather than a forced rewrite.

## Core Build Thesis

BlackBook should be built in two realities at once:

1. protect the working Streamlit system so financial truth is never degraded
2. migrate its domain logic and user experience into Pantheon until the standalone app is no longer needed

The mistake to avoid is declaring Pantheon BlackBook "done" before it reaches functional parity with the current app.

## Current State

Today, BlackBook is:

- a working Streamlit financial operating system
- backed by PostgreSQL through `DATABASE_URL`
- effectively Neon-backed in the current live setup
- already carrying real product logic for:
  - transactions
  - accounts
  - holdings
  - allocations
  - reports
  - agenda
  - reconciliation
  - journal
  - advisor
  - Meridian question integration

At the same time:

- the Pantheon BlackBook location exists
- the Pantheon UI direction is correct
- but the Pantheon copy is not yet the full canonical product truth

## Non-Negotiable Rules

- `active/BlackBook` remains canonical until Pantheon reaches explicit feature parity
- no migration step should reduce financial data trust
- the database schema and live data access must stay stable during UI migration
- Pantheon should inherit BlackBook's truth, not replace it with a weaker duplicate
- Apollo integration should sit on top of BlackBook truth, not bypass it

## Target End-State

The end-state is:

- one BlackBook domain system
- one trusted financial database layer
- one Pantheon-native BlackBook experience
- Apollo as the easiest way to log, ask about, and act on financial events
- the standalone Streamlit app removable without losing capability

## Build Strategy

The migration should happen in six phases.

## Phase 1 - Stabilize The Canonical Streamlit System

Goal:
protect the current working app and make its ownership explicit before deeper migration begins.

Required outcomes:

- add a true free local-database fallback so BlackBook does not depend on paid or quota-limited cloud compute to keep working
- keep `active/BlackBook` as the live canonical app
- preserve the archived Reflex copy only for reference
- document runtime requirements clearly:
  - `DATABASE_URL`
  - `GROQ_API_KEY`
  - Streamlit secrets
- confirm the current canonical app is Neon/Postgres based
- treat Supabase as historical context unless a real runtime dependency appears later

Immediate infrastructure priority inside this phase:

1. make BlackBook run locally without Neon by supporting a real fallback path when `DATABASE_URL` is unavailable
2. keep Neon optional rather than required
3. only return to cloud hosting later if it can remain free and non-fragile

Exit criteria:

- the repo path for canonical BlackBook is stable
- the app launches locally from `active/BlackBook`
- the app can keep running without Neon compute availability
- documentation clearly distinguishes canonical app, Pantheon destination, and legacy archive

## Phase 2 - Extract BlackBook Domain Boundaries

Goal:
separate durable financial logic from Streamlit-only presentation so Pantheon can reuse the real system instead of re-implementing it badly.

Work in this phase:

- identify the durable domain areas inside the Streamlit app:
  - accounts and balances
  - transactions
  - holdings and price refresh
  - allocations
  - reports and snapshots
  - reconciliation
  - journal
  - advisor memory and conversations
  - Meridian questions bridge
- define what belongs to:
  - database schema
  - business logic
  - AI/advisor logic
  - UI-only rendering
- extract or mirror reusable query/service functions into Pantheon-owned modules where appropriate
- avoid coupling new Pantheon services to Streamlit session-state assumptions

Important rule:
the goal is not to rewrite everything immediately. The goal is to define the real BlackBook domain contract.

Exit criteria:

- BlackBook's major capabilities are mapped into domain modules and service responsibilities
- the Pantheon side has a clear list of reusable functions and required endpoints
- no important financial workflow is still conceptually hidden inside UI code

## Phase 3 - Build Pantheon Service Parity

Goal:
make Pantheon capable of serving BlackBook's core data and actions from the same underlying truth.

Work in this phase:

- create or finish Pantheon-side service modules for:
  - transactions CRUD
  - holdings CRUD and refresh
  - allocation snapshots
  - reports access
  - account reconciliation
  - journal CRUD
  - advisor request handling
  - settings and financial rules
- standardize database access around the same Postgres truth the Streamlit app uses
- migrate any remaining old BlackBook import paths into Pantheon-local service ownership
- keep naming and payloads stable enough that UI work can move faster afterward

This phase should also preserve the Phase 8 direction already defined in Pantheon:

- old legacy app imports should disappear over time
- Pantheon should own the service layer before the old standalone implementation is retired

Exit criteria:

- Pantheon can read and mutate the same BlackBook truth reliably
- critical endpoints exist for all major BlackBook surfaces
- no essential Pantheon service depends on the archived Reflex app

## Phase 4 - Rebuild BlackBook Inside Pantheon With Feature Parity

Goal:
make `active/Pantheon/apps/blackbook` a real daily-use interface, not just a placeholder.

This phase should follow the already-defined Pantheon Phase 7 UI direction.

Required surface parity:

- `dashboard`
- `transactions`
- `investments`
- `allocation`
- `reports`
- `journal`
- `reconcile`
- `agenda`
- `advisor`
- `meridian`
- `settings`

Pantheon BlackBook should preserve the current BlackBook strengths:

- immediate financial visibility
- action-oriented workflows
- advisor usefulness
- trust and auditability
- low-friction navigation

Mobile parity matters here too:

- tables need mobile-safe fallbacks
- forms need touch-safe controls
- subpages need to remain usable on phone

Exit criteria:

- every major Streamlit BlackBook surface has a Pantheon equivalent
- all major CRUD flows round-trip successfully through Pantheon
- the Pantheon version is usable enough for real daily BlackBook work

## Phase 5 - Apollo Integration And Friction Reduction

Goal:
make Apollo the natural interface layer over BlackBook without weakening BlackBook's data ownership.

Work in this phase:

- allow Apollo to log financial events into BlackBook
- allow Apollo to query balances, transactions, allocations, and reports
- support conversational advisor-style follow-ups against BlackBook truth
- route financial actions through Pantheon so Apollo never becomes a shadow financial database
- use Maridian context only as enrichment, not as replacement for BlackBook facts

Examples of target flows:

- "Log a $23 Uber to food"
- "How much did I spend eating out this week?"
- "What should I do with my next paycheck?"
- "Show me what changed since my last report"

Exit criteria:

- Apollo can perform useful BlackBook actions against the real system
- conversational logging reduces manual friction
- financial truth still resolves back to BlackBook services and database state

## Phase 6 - Canonical Switch And Standalone Retirement

Goal:
change canonical status only after Pantheon proves it deserves it.

Pantheon BlackBook should only become canonical when:

- feature parity is complete
- real workflows are stable in Pantheon
- the advisor flow works acceptably
- data trust is unchanged or improved
- phone and desktop use are both acceptable
- the standalone app is no longer needed for normal operation

Only then should you:

- switch canonical status from standalone BlackBook to Pantheon BlackBook
- demote `active/BlackBook` to legacy/reference or maintenance-only
- keep the archived Reflex copy as historical reference only

Exit criteria:

- Pantheon BlackBook is the real daily financial command center
- the standalone Streamlit app can be retired without capability loss

## Functional Parity Checklist

The Pantheon migration is not complete until it preserves these capabilities from the current app:

- account and balance visibility
- transaction logging and deletion
- transfer handling
- holdings tracking and refresh
- paycheck allocation logic
- report generation and inspection
- reconciliation workflows
- journal workflows
- advisor memory and conversation history
- financial advisor tool access
- Meridian question/bridge behavior
- exports and operational settings

## Data And Infrastructure Notes

- current live database model is Postgres through `DATABASE_URL`
- current working deployment context is Neon-backed
- no active Supabase runtime dependency is assumed unless a real integration surfaces later
- any future account-linking or automation should be layered onto this truth carefully

## Immediate Next Steps

1. Add the free local-database fallback so BlackBook can run without Neon.
2. Write down the BlackBook domain map from the current Streamlit app.
3. Inventory the current Pantheon BlackBook services and endpoints against that map.
4. Mark which BlackBook surfaces already have Pantheon parity and which do not.
5. Turn the biggest missing surfaces into implementation milestones under Pantheon Phase 7.
6. Keep the standalone app canonical until those milestones are complete.

## Final Position

BlackBook should not stay split forever.

But the path to unification is not "move everything now and hope."

The right path is:

- protect the working Streamlit truth
- extract the real financial domain carefully
- rebuild the experience inside Pantheon with parity
- switch canonical status only when Pantheon has earned it

That is how BlackBook becomes fully native to Pantheon without losing the thing that matters most: trusted financial truth.
