"""HintGuard demo (used in the video).

    python demo.py                 # four example tutor answers for MBPP task 66
    python demo.py --task 66 --paste   # paste your own tutor answer, finish with an empty line + Ctrl-D
"""
import argparse
import json
import sys

from hintguard import core

EXAMPLES = {
    "A. Hint only": (
        "Good question! Go through the list one number at a time and keep a counter. "
        "Increase the counter only when the number is not negative, and return it at the end."),
    "B. Full solution, written in a different style": (
        "Sure, this one-liner does it:\n\n```python\n"
        "def count_non_negative(values):\n    return sum(1 for v in values if v >= 0)\n```"),
    "C. Half of the reference solution": (
        "You are close, start like this:\n\n```python\n"
        "def pos_count(list):\n  pos_count= 0\n  for num in list:\n    if num >= 0:\n"
        "    # ... finish the rest yourself\n```"),
    "D. Unrelated example code": (
        "Here is how a loop with a condition works in general:\n\n```python\n"
        "for word in ['apple', 'kiwi', 'banana']:\n    if len(word) > 4:\n        print(word)\n```"),
}


def load(task_id):
    for line in open("data/mbpp.jsonl", encoding="utf-8"):
        r = json.loads(line)
        if r["task_id"] == task_id:
            return r
    raise SystemExit(f"task {task_id} not found")


def show(title, text, r):
    res = core.check(text, r["code"].replace("\r\n", "\n"), r["test_list"], r["test_setup_code"])
    verdict = "LEAK  -> block" if res["leak"] else "OK    -> deliver"
    print(f"\n{title}\n{'-' * len(title)}")
    print(f"  passes hidden tests : {res['passes_tests']}")
    print(f"  structural overlap  : {res['structural_similarity']:.2f} (threshold {core.DEFAULT_TAU})")
    print(f"  decision            : {verdict}   ({res['reason']})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", type=int, default=66)
    ap.add_argument("--paste", action="store_true")
    a = ap.parse_args()
    r = load(a.task)
    print(f"Exercise {a.task}: {r['text']}")
    if a.paste:
        print("Paste the tutor answer, then Ctrl-D (Ctrl-Z + Enter on Windows):")
        show("Your answer", sys.stdin.read(), r)
    else:
        for title, text in EXAMPLES.items():
            show(title, text, r)


if __name__ == "__main__":
    main()
