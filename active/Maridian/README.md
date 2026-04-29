# Meridian

Your second brain. Reads your journals. Returns your thinking at full potential.

## Quick Start

```bash
# 1. Fill in your Neon connection string
# Edit .env -> NEON_DATABASE_URL=postgresql://...

# 2. Initialize Neon tables
python -c "from db.neon_bridge import init_tables; init_tables()"

# 3. Run first cycle
python evolve.py evolve

# 4. Check status
python evolve.py status

# 5. Open control panel
streamlit run control.py
```

## Commands

```
python evolve.py evolve         # Process new entries + generate questions
python evolve.py status         # Check stats
python evolve.py write <id>     # Write framework (local only)
python evolve.py push <id>      # Write framework + push to Black Book
streamlit run control.py        # Open control panel
```

## Neon Tables

- `meridian_questions`  — adaptive daily questions (Black Book reads this)
- `meridian_outputs`    — published frameworks (Black Book reads this)
- `meridian_insights`   — monthly pattern reports

## Prerequisites

- Ollama running locally with `llama3.2` and `phi3` models pulled
- Neon PostgreSQL with `journal_entries` table (id, entry_date, tag, body)

## Security

- `.env` (Neon credentials) — NEVER committed
- `vault_embeddings.json` — NEVER committed (your thought vectors)
- `voice_profile.json` — NEVER committed
- All raw journal text stays in Neon — never written to vault notes or Git

## Optional: Nightly Cron (Linux/Mac)

```
crontab -e
0 2 * * * cd ~/Meridian && python evolve.py evolve >> meridian.log 2>&1
```

## Optional: Windows Task Scheduler

Create a Basic Task running daily at 2am:
  Action: `python C:\Users\Ignac\Dropbox\Maridian\evolve.py evolve`
