# Project Plans

This folder collects the higher-level vision and planning documents that guide the major systems in this repository.

## Included Documents

- `blackbook_vision.md` - founder vision and system blueprint for BlackBook as Pantheon's financial command center for Apollo
- `blackbook_build_plan.md` - staged roadmap for migrating the live Streamlit BlackBook into a Pantheon-native system without losing financial truth
- `maridian_vision.md` - founder vision for Maridian as Pantheon's reflective memory engine, owned locally and mirrored into Obsidian
- `maridian_build_plan.md` - staged roadmap for making Maridian Pantheon-native, moving journaling out of BlackBook, and feeding Apollo processed personal memory
- `maridian_storage_paths.md` - locked local path decision for the Maridian app, canonical vault, and direct Obsidian access
- `maridian_repo_policy.md` - Git/local boundary and planning-first execution policy for Maridian before deeper implementation begins
- `maridian_privacy_boundary.md` - file-level Git-vs-local policy for the Maridian vault so private memory stays local while system logic stays trackable
- `source_of_truth_policy.md` - repo-wide founder policy defining local runtime truth versus GitHub coordination/history across the whole monorepo
- `pantheon_consolidation_plan.md` - architecture-first plan for resolving Pantheon's split roots, subsystem duplication, and the Phase 7/8 consolidation blockers
- `repo_vision.md` - strategic blueprint for how external repos strengthen the Olympus ecosystem
- `repo_status_tracker.md` - master tracker for canonical paths, current classifications, missing docs, and next milestones across the repo
- `source_of_truth_framework.md` - rule set for deciding canonical paths, labeling split systems, and auditing unresolved source-of-truth conflicts
- `pantheon/Pantheon Vision.pdf` - vision document for Pantheon
- `olympus/olympus_master_plan.md` - Olympus master blueprint
- `olympus/olympus_build_plan.md` - Olympus phase-by-phase build plan
- `apollo/Master_Plan_v2.md` - Apollo master plan v2
- `apollo/Build_Plan_v2.md` - Apollo build plan v2

## Why This Lives At The Repo Level

These documents span multiple systems and describe product direction, architecture intent, and sequencing. Keeping them at the repo level makes them easier to find than burying them inside one individual app folder.
