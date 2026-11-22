# HintGuard: a solution-leak guard for AI programming tutors

Proof-of-concept prototype for the mini-R&D proposal *HintGuard* (Assignment 12, Research Tools and Methods, SDU University, 2026; author: Danial Kaltay).

AI tutors for programming courses are told by their prompts not to give students the full solution, but nothing checks whether they actually do. HintGuard checks every tutor response **before** the student sees it, using what the instructor already has for each graded exercise: a reference solution and unit tests.

1. **Execution check**: code found in the response (fenced or not) is run against the hidden unit tests. Every function is tried under the expected name, so renaming does not hide a working solution.
2. **Structural check**: share of the reference solution's token 5-grams (identifiers, numbers and strings normalised) that appear in the response. This catches partial solutions that do not run yet.

A response is a leak if (1) passes **or** (2) ≥ τ (τ = 0.40, tuned on the validation split).

## Quick start
```bash
python demo.py                    # four example tutor answers for MBPP task 66
python demo.py --task 66 --paste  # check your own answer
python experiment.py              # full experiment, about 1-2 minutes, writes results/
```
Only the Python standard library is needed (Python ≥ 3.9). `figs` in the report were made with matplotlib.
In Google Colab: open `demo.ipynb` from this repository and run all cells.

## Experiment (simulated study, TRL 4)
* Data: MBPP (Austin et al., 2021, CC BY 4.0), 499 test exercises (tasks 11–510) and 90 validation exercises (tasks 511–600) whose reference solution passes its own tests.
* For every exercise seven tutor-response types are generated: **leaks**: full solution, disguised solution (all identifiers renamed, reformatted, no code fence), partial solution (first half of the lines); **safe help**: text hint, hint + unrelated code example, skeleton with comments, full solution of a *different* exercise.
* Policy (strict): no solution code, complete or partial. 3463 test responses.

| Method | Precision | Recall | F1 | False positive rate |
|---|---|---|---|---|
| B1 code-presence rule (>=3 code lines) | 0.584 | 0.978 | 0.731 | 0.513 |
| B2 text similarity (tau=0.50) | 0.947 | 0.870 | 0.907 | 0.036 |
| HG-a execution check only | 1.000 | 0.678 | 0.808 | 0.000 |
| HG-b structural similarity only (tau=0.35) | 0.976 | 0.984 | 0.980 | 0.018 |
| HintGuard: execution OR structure (tau=0.40) | 0.989 | 0.982 | 0.985 | 0.008 |

Median latency of HintGuard: 65 ms per response (p95 169 ms; max 4.0 s when a response hits the 4 s test timeout).

All numbers: `results/results.json`; per-response scores: `results/scores_test.csv`.

## Known limitations (v0.1)
* Responses are generated from benchmark solutions, not collected from real LLM tutors; the next step (TRL 5) is a corpus of real tutor answers.
* Very short reference solutions (1–3 lines) cause most false positives, because generic code shares their structure.
* Unfenced code with blank lines inside a function is split by the extractor (3 missed disguised leaks); fixed extraction is planned for v0.2.
* The execution check runs untrusted code: in production it must run in an isolated sandbox (container without network).

## Licence
Code: MIT. MBPP data: CC BY 4.0 (Google Research).
