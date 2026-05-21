# Resume Tailor — Autonomous 1-Page PDF Agent

A local Python CLI that takes your master resume and a target job description, uses an LLM to tailor the content, and guarantees the output is exactly **1 page** — with no manual tweaking.

## How it works

```
./run.sh
  │
  ├─ PASS 1 — LLM (gpt-5.5 or claude-3-5-sonnet)
  │    Extracts JD keywords → selects & rewrites bullets to match
  │    → compiles PDF via typst → checks page count (pypdf)
  │    → ✅ done if 1 page
  │
  ├─ PASS 2 — Geometry tightening  (no LLM calls)
  │    Iteratively lowers: font size (11 → 10 pt)
  │                        top/bottom margins (2 → 1.2 cm)
  │                        side margins (1.5 → 1.2 cm)
  │                        line spacing (1.15 → 1.0)
  │    Recompiles after each micro-step → ✅ done if 1 page
  │
  └─ PASS 3 — Semantic compaction  (LLM loop, up to 8 passes)
       "Shorten the 2–3 longest bullets, keep all metrics intact."
       Recompile → check → repeat until exactly 1 page
```

## Stack

| Layer | Tool |
|-------|------|
| LLM client | `instructor` + `openai` / `anthropic` (structured Pydantic outputs) |
| Typesetting | `typst` CLI — single-column, ATS-optimised template |
| PDF validation | `pypdf` — programmatic page-count guardrail |
| CLI | `typer` + `rich` |
| Schemas | `pydantic` v2 |

## Setup

**Prerequisites:** Python 3.11+, [`typst` CLI](https://github.com/typst/typst/releases) (`brew install typst` on macOS)

```bash
git clone https://github.com/<your-username>/resume-tailor
cd resume-tailor

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Add your OPENAI_API_KEY or ANTHROPIC_API_KEY to .env
```

## Usage

1. Fill in `data/master_resume.json` with your full resume (see `data/master_resume.example.json` for the schema).
2. Paste the target job description into `data/job_description.txt`.
3. Run:

```bash
./run.sh
```

Or with custom paths:

```bash
source .venv/bin/activate
python3 main.py \
  --master ./data/master_resume.json \
  --jd     ./data/job_description.txt \
  --output ./tailored_resume.pdf
```

The finished PDF opens automatically in your default viewer when done.

## File layout

```
resume-tailor/
├── main.py                        # Typer CLI entrypoint
├── models.py                      # Pydantic schemas (ContactInfo, WorkExperience, …)
├── engine.py                      # JD keyword extraction + LLM tailoring
├── agent.py                       # 3-pass 1-page optimization loop
├── template.typ                   # Typst resume template (geometry via --input flags)
├── run.sh                         # One-command launcher
├── requirements.txt
├── .env.example                   # Copy to .env and add your API key
└── data/
    ├── master_resume.example.json # Schema reference — fill in your own data
    └── job_description.txt        # Paste target JD here (gitignored when real)
```

## Configuration

All layout thresholds live in `agent.py` constants:

```python
FONT_DEFAULT = 11.0;  FONT_FLOOR = 10.0   # pt
TOP_DEFAULT  = 2.0;   TOP_FLOOR  = 1.2    # cm
SIDE_DEFAULT = 1.5;   SIDE_FLOOR = 1.2    # cm
LEADING_DEFAULT = 1.15; LEADING_FLOOR = 1.0
```

## Privacy

`data/master_resume.json`, `workspace/tailored_resume.json`, `tailored_resume.pdf`, and `.env` are all gitignored. Only the example schema and template are committed.
