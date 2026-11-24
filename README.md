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
python experiment.py              # full experiment, about 1-2 minutes, writes results.json
```
Only the Python standard library is needed (Python >= 3.9).
In Google Colab: https://colab.research.google.com/github/Euc1d/hintguard/blob/main/demo.ipynb → *Runtime → Run all*.

## Files
`core.py`: the guard (code extraction, execution check, structural check) · `variants.py`: generation of the seven tutor-response types · `experiment.py`: the simulated study · `demo.py`: demo used in the video · `demo.ipynb`: Colab notebook · `mbpp.jsonl`: MBPP dataset · `results.json`, `scores_test.csv`, `run_log.txt`: results.

## Experiment (simulated study, TRL 4)
* Data: MBPP (Austin et al., 2021, CC BY 4.0), 499 test exercises (tasks 11–510) and 90 validation exercises (tasks 511–600) whose reference solution passes its own tests.
* For every exercise seven tutor-response types are generated: **leaks**: full solution, disguised solution (all identifiers renamed, reformatted, no code fence), partial solution (first half of the lines); **safe help**: text hint, hint + unrelated code example, skeleton with comments, full solution of a *different* exercise.
* Policy (strict): no solution code, complete or partial. 3,463 test responses. The run is deterministic (fixed seeds, 10 s test time limit).

| Method | Precision | Recall | F1 | False positive rate |
|---|---|---|---|---|
| B1 code-presence rule (>=3 code lines) | 0.585 | 0.978 | 0.733 | 0.509 |
| B2 text similarity (tau=0.50) | 0.945 | 0.870 | 0.906 | 0.038 |
| HG-a execution check only | 0.998 | 0.678 | 0.807 | 0.001 |
| HG-b structural similarity only (tau=0.35) | 0.978 | 0.984 | 0.981 | 0.017 |
| HintGuard: execution OR structure (tau=0.40) | 0.991 | 0.982 | 0.986 | 0.007 |

Median latency of HintGuard: 60 ms per response (p95 137 ms); 18 responses with slow code took more than 4 s (limit 10 s).

## Known limitations (v0.1)
* Responses are generated from benchmark solutions, not collected from real LLM tutors; the next step (TRL 5) is a corpus of real tutor answers.
* 6 of the 13 false positives come from very short reference solutions (1–3 lines); 2 are solutions of another sorting exercise that also pass the target exercise's tests.
* Unfenced code with blank lines inside a function is split by the extractor (3 missed disguised leaks); fixed extraction is planned for v0.2.
* The execution check runs untrusted code: in production it must run in an isolated sandbox (container without network).

## Licence
Code: MIT. MBPP data: CC BY 4.0 (Google Research).
