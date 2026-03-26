#!/usr/bin/env python3
"""
Evaluate SKILL.md quality against a fixed rubric.

This is the ground truth evaluator — analogous to prepare.py + evaluate_bpb()
in autoresearch.

Evaluation backends (tried in order):
  1. Anthropic SDK (pip install anthropic)
  2. claude CLI in print mode
  3. curl with ANTHROPIC_API_KEY

Usage:
    python evaluate.py              # evaluate SKILL.md in same directory
    python evaluate.py > run.log    # redirect for agent parsing

Output:
    quality_score:            X.XXXXXX   (0-10 scale, computed from dimension scores)
    structural_completeness:  N          (1-50 scale)
    instruction_clarity:      N          (1-50 scale)
    actionability:            N          (1-50 scale)
    example_quality:          N          (1-50 scale)
    conciseness:              N          (1-50 scale)
    adaptability:             N          (1-50 scale)
    test_first_fidelity:      N          (1-50 scale)
    grounding:                N          (1-50 scale)
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
MODEL = os.environ.get("EVAL_MODEL", "claude-haiku-4-5-20251001")


def read_file(path: Path) -> str:
    return path.read_text()


def build_prompt(skill: str, rubric: str, scenarios: str) -> str:
    return f"""You are an impartial skill quality evaluator. Your job is to score a Claude Code skill file against a detailed rubric.

Be rigorous and honest. Do not inflate scores. Scores are on a range of 1-50.
- 1 is a score worse than what we started with.
- 2 is a score representative of the quality at the start of the trial
- A score of 3-48 means an incremental improvement over the base
- A score of 49-50 means "exceptional, hard to improve."

<rubric>
{rubric}
</rubric>

<skill>
{skill}
</skill>

<scenarios>
{scenarios}
</scenarios>

## Your task

1. Read the skill carefully.
2. For each rubric dimension, mentally simulate applying the skill to each test scenario.
3. For each dimension, identify specific strengths and weaknesses.
4. Score each dimension 1-50 based strictly on the rubric criteria. Use the FULL range:
   - 2 is about where we started. Scores from 3 to 50 are noticeable improvements over the original. 
   - Treat the scores as if on a logarithmic scale. Make sure there are lots of scores to represent improvement.
   - Do NOT cluster all scores in a narrow band. Differentiate between dimensions.
   - Use the specific score bands in the rubric to determine sub-scores within each band.
5. Do NOT compute quality_score — the script will compute it.

Output ONLY the dimension scores in this exact format (no other text, no explanation).

structural_completeness:  N
instruction_clarity:      N
actionability:            N
example_quality:          N
conciseness:              N
adaptability:             N
test_first_fidelity:      N
grounding:                N"""


def evaluate_with_sdk(prompt: str) -> str | None:
    """Try the Anthropic Python SDK."""
    try:
        import anthropic

        client = anthropic.Anthropic()
        response = client.messages.create(
            model=MODEL,
            max_tokens=256,
            temperature=0,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()
    except ImportError:
        print("  [evaluate] anthropic SDK not installed, trying next backend...", file=sys.stderr)
        return None
    except Exception as e:
        print(f"  [evaluate] SDK error: {e}, trying next backend...", file=sys.stderr)
        return None


def evaluate_with_claude_cli(prompt: str) -> str | None:
    """Try the claude CLI in print mode."""
    try:
        result = subprocess.run(
            ["claude", "-p", "--model", "", prompt],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        print(f"  [evaluate] claude CLI returned {result.returncode}, trying next backend...", file=sys.stderr)
        return None
    except FileNotFoundError:
        print("  [evaluate] claude CLI not found, trying next backend...", file=sys.stderr)
        return None
    except subprocess.TimeoutExpired:
        print("  [evaluate] claude CLI timed out, trying next backend...", file=sys.stderr)
        return None
    except Exception as e:
        print(f"  [evaluate] claude CLI error: {e}, trying next backend...", file=sys.stderr)
        return None


def evaluate_with_curl(prompt: str) -> str | None:
    """Try curl with ANTHROPIC_API_KEY."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("  [evaluate] ANTHROPIC_API_KEY not set, trying next backend...", file=sys.stderr)
        return None

    payload = json.dumps(
        {
            "model": MODEL,
            "max_tokens": 256,
            "temperature": 0,
            "messages": [{"role": "user", "content": prompt}],
        }
    )

    try:
        result = subprocess.run(
            [
                "curl",
                "-s",
                "https://api.anthropic.com/v1/messages",
                "-H", f"x-api-key: {api_key}",
                "-H", "anthropic-version: 2023-06-01",
                "-H", "content-type: application/json",
                "-d", payload,
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0:
            resp = json.loads(result.stdout)
            if "content" in resp and resp["content"]:
                return resp["content"][0]["text"].strip()
        print(f"  [evaluate] curl request failed, no more backends available.", file=sys.stderr)
        return None
    except Exception as e:
        print(f"  [evaluate] curl error: {e}", file=sys.stderr)
        return None


WEIGHTS = {
    "structural_completeness": 1.0,
    "instruction_clarity": 1.5,
    "actionability": 1.5,
    "example_quality": 1.0,
    "conciseness": 0.5,
    "adaptability": 1.0,
    "test_first_fidelity": 1.0,
    "grounding": 1.0,
}
MAX_WEIGHTED_SUM = 50 * sum(WEIGHTS.values())  # 425.0


def parse_dimension_scores(output: str) -> dict[str, int] | None:
    """Parse dimension scores from LLM output. Returns None if any are missing."""
    scores = {}
    for dim in WEIGHTS:
        match = re.search(rf"{dim}:\s*(\d+)", output)
        if match:
            scores[dim] = int(match.group(1))
        else:
            return None
    return scores


def compute_quality_score(dimensions: dict[str, int]) -> float:
    """Compute the weighted composite quality score (1-50 scale)."""
    weighted_sum = sum(dimensions[dim] * WEIGHTS[dim] for dim in WEIGHTS)
    return weighted_sum / MAX_WEIGHTED_SUM


def main() -> int:
    skill_path = SCRIPT_DIR / "SKILL.md"
    rubric_path = SCRIPT_DIR / "rubric.md"
    scenarios_path = SCRIPT_DIR / "scenarios.md"

    for path in [skill_path, rubric_path, scenarios_path]:
        if not path.exists():
            print(f"ERROR: {path} not found", file=sys.stderr)
            return 1

    skill = read_file(skill_path)
    rubric = read_file(rubric_path)
    scenarios = read_file(scenarios_path)

    prompt = build_prompt(skill, rubric, scenarios)

    # Try each evaluation backend in order
    output = (
        evaluate_with_sdk(prompt)
        or evaluate_with_claude_cli(prompt)
        or evaluate_with_curl(prompt)
    )

    if output is None:
        print("ERROR: No evaluation backend available.", file=sys.stderr)
        print("Install one of:", file=sys.stderr)
        print("  1. pip install anthropic  (and set ANTHROPIC_API_KEY)", file=sys.stderr)
        print("  2. Install claude CLI", file=sys.stderr)
        print("  3. Set ANTHROPIC_API_KEY for curl fallback", file=sys.stderr)
        return 1

    # Parse dimension scores from LLM output
    dimensions = parse_dimension_scores(output)
    if dimensions is None:
        print(output)
        print("\nERROR: Could not parse all dimension scores from evaluator output", file=sys.stderr)
        return 1

    # Compute quality_score ourselves (don't trust LLM arithmetic)
    quality = compute_quality_score(dimensions)

    # Print final output in canonical format
    print(f"quality_score:            {quality:.6f}")
    for dim, score in dimensions.items():
        print(f"{dim + ':':26s}{score}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
