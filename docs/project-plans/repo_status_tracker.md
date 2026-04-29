# Repo Status Tracker

This document is the control tower for the repository cleanup.

It records what each major system is, where its current truth lives, what documents exist, what is missing, what stage it is in, and what problem must be solved next.

## Master Table

| System | Role In Ecosystem | Canonical Path | Current Classification | Current Implementation Location(s) | Docs Present | Missing Docs | Current Phase / Stage | Biggest Structural Risk | Next Milestone |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `Pantheon` | Parent operating-system root that holds Apollo, BlackBook, Maridian, and Pantheon-facing Olympus surfaces | `active/Pantheon` | `canonical` | `active/Pantheon`, duplicate tree at `active/Olympus-Trading/Pantheon` | root README, Pantheon Vision PDF, system overview docs | repo-level build/consolidation plan | structural root established, consolidation partial | duplicate working tree and incomplete consolidation rules | create Pantheon consolidation plan and duplicate-tree retirement path |
| `Apollo` | User-facing interface, voice/chat ingress, delivery shell, and Pantheon gateway | `active/Pantheon/apps/apollo` | `canonical` | canonical app under Pantheon plus legacy standalone at `active/Apollo` | app README, Apollo master/build plans | canonical decision record only if separated from tracker | transitional shell-over-Pantheon stage; active UI rebuild in progress | legacy standalone Apollo still contains historical backend/runtime surface | align Phase 7/8 with Apollo de-duplication and one-frontend end-state |
| `BlackBook` | Financial command center and financial source of truth for Pantheon/Apollo | `active/BlackBook` | `canonical` | canonical Streamlit app at `active/BlackBook`, Pantheon copy at `active/Pantheon/apps/blackbook`, archived Reflex copy at `archive/BlackBook_Reflex_Legacy_2026-04-29` | app README, repo-level BlackBook vision, BlackBook build plan | Pantheon migration execution milestones | live standalone Streamlit app; Pantheon-native surfacing is partial | Pantheon copy is still incomplete relative to the standalone truth | execute the staged migration plan toward Pantheon parity |
| `Maridian` | Reflective journal-processing and Obsidian-brain subsystem | `needs audit` | `needs audit` | standalone `active/Maridian`, Pantheon copy at `active/Pantheon/apps/maridian` | standalone README | repo-level vision doc, build/roadmap doc, source-of-truth decision record | working standalone subsystem, Pantheon-native status unclear | split truth and missing strategic documentation | run architecture-fit audit and define migration target/state |
| `Olympus` | Trading execution, ranking, memory, and reporting subsystem displayed through Pantheon | `active/Olympus-Trading/olympus` | `integrated external subsystem` | runtime at `active/Olympus-Trading/olympus`, Pantheon-facing surface at `active/Pantheon/apps/olympus` | Olympus README, Olympus master/build plans | optional Pantheon/Olympus integration decision note | Phases 1-5 live; debate/evolution/live gate not live yet | operational separation can be mistaken for architectural exclusion | keep Olympus explicit in Pantheon consolidation and UI roadmap |
| `MetaGPT` | Future multi-agent decision-engine import for Pantheon | none yet | `reference / future integration` | `active/MetaGPT` | upstream README, repo vision | integration decision record if promoted later | not integrated | can be mistaken for active subsystem work | keep classified as future integration until Pantheon agent architecture is ready |
| `deer-flow` | Future orchestration/import for agent pipelines and loops | none yet | `reference / future integration` | `active/deer-flow` | upstream README, repo vision | integration decision record if promoted later | not integrated | can be mistaken for active orchestration layer | keep classified as future integration until Pantheon orchestration work begins |
| `oh-my-claudecode` | Future prompt/agent-structure reference import | none yet | `reference / future integration` | `active/oh-my-claudecode` | upstream README, repo vision | integration decision record if promoted later | not integrated | can be mistaken for live system architecture | keep classified as future integration until prompt-structure adoption starts |

## Split-System Notes

### Pantheon

`active/Pantheon` is the intended root and should remain the canonical tree.

`active/Olympus-Trading/Pantheon` currently behaves like a duplicate working tree, not a second root. It points at the same remote/history family and should eventually be retired or archived after any useful deltas are reconciled intentionally.

### Apollo

Apollo has already crossed the threshold for a canonical decision.

`active/Pantheon/apps/apollo` should be treated as the active Apollo because the current visible product work is landing there, including the Pantheon-native UI direction and the unfinished Phase 7/8 work.

`active/Apollo` should be treated as:

- `legacy`
- `migration source`
- `reference`

It may still contain useful runtime pieces, but it should not remain a co-equal source of truth.

### BlackBook

BlackBook now has a current canonical ruling.

The most up-to-date application now lives in `active/BlackBook` as the imported Streamlit codebase.

That means:

- `active/BlackBook` is the current application truth
- `active/Pantheon/apps/blackbook` is the Pantheon migration target
- `archive/BlackBook_Reflex_Legacy_2026-04-29` is the preserved older `legacy / reference` copy

The remaining problem is no longer "which copy is canonical?" It is "how and when does the current Streamlit BlackBook migrate into Pantheon-native form without losing domain truth?"

### Maridian

Maridian also remains unresolved.

The audit must determine:

- whether the standalone implementation is still the real working truth
- whether the Pantheon Maridian copy is currently a destination scaffold or already meaningful
- what must move before a canonical Pantheon-native ruling is justified

Until then, classify it as `needs audit`.

## Current Missing Documentation

The highest-priority missing docs are:

1. Pantheon build/consolidation plan
2. Maridian vision doc
3. Maridian build/roadmap doc
4. optional audit decision records for Maridian if kept separate from this tracker

## Current Roadmap Order

1. source-of-truth framework
2. repo status tracker
3. Pantheon consolidation plan
4. Phase 7 and Phase 8 alignment inside that plan
5. BlackBook migration planning
6. Maridian audit
7. missing core docs
8. duplicate working-tree retirement plan
9. migration sequencing for legacy copies
10. future integration roadmap
