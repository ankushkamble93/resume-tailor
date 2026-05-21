#!/usr/bin/env zsh
# Run the resume-tailor agent from anywhere.
# Usage: ./run.sh [--output path/to/output.pdf]

set -e

SCRIPT_DIR="${0:A:h}"
cd "$SCRIPT_DIR"

source .venv/bin/activate

python3 main.py \
  --master ./data/master_resume.json \
  --jd     ./data/job_description.txt \
  --output ./tailored_resume.pdf \
  "$@"

# Auto-open the finished PDF in macOS Preview
open "$SCRIPT_DIR/tailored_resume.pdf"
