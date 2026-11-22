"""HintGuard proof-of-concept experiment on MBPP (Austin et al., 2021).

Validation split (tasks 511-600) -> tune thresholds.  Test split (tasks 11-510) -> report.
Run:  python experiment.py            (about 2-4 minutes on a laptop)
"""
import json
import random
import statistics
import time
from multiprocessing import Pool

from hintguard import core, variants as V

random.seed(42)
POS = {"full", "disguised", "partial"}   # strict policy: no solution code, complete or partial
POS_LENIENT = {"full", "disguised"}
NEG = {"hint", "hint_snippet", "skeleton", "other_solution"}
CATS = ["full", "disguised", "partial", "hint", "hint_snippet", "skeleton", "other_solution"]


def load():
    rows = [json.loads(l) for l in open("data/mbpp.jsonl", encoding="utf-8")]
    return {r["task_id"]: r for r in rows}


def prepare(r):
    """Return a usable reference (passes its own tests) or None."""
    raw = r["code"].replace("\r\n", "\n").rstrip()
    for code in (V.clean(r["code"]), raw):
        try:
            compile(code, "<ref>", "exec")
        except SyntaxError:
            continue
        if core.passes_tests(code, r["test_list"], r["test_setup_code"]):
            return code
    return None


def build_items(tasks, ids):
    refs = {}
    with Pool(8) as p:
        out = p.map(prepare, [tasks[i] for i in ids])
    for i, code in zip(ids, out):
        if code:
            refs[i] = code
    items = []
    keys = list(refs)
    for i in keys:
        r, code = tasks[i], refs[i]
        other = refs[random.choice([k for k in keys if k != i])]
        texts = {"full": V.full(code), "hint": V.hint(code), "hint_snippet": V.hint_snippet(code),
                 "skeleton": V.skeleton(code, r["test_list"]), "other_solution": V.other_solution(other)}
        try:
            texts["disguised"] = V.disguised(code)
        except Exception:
            pass
        p_ = V.partial(code)
        if p_:
            texts["partial"] = p_
        for cat, t in texts.items():
            items.append({"task": i, "cat": cat, "text": t, "ref": code,
                          "tests": r["test_list"], "setup": r["test_setup_code"]})
    return items, len(ids), len(refs)


def score(it):
    t0 = time.perf_counter()
    code = core.extract_code(it["text"])
    s = core.structural_similarity(code, it["ref"])
    ex = core.passes_tests(code, it["tests"], it["setup"]) if code else False
    ms = (time.perf_counter() - t0) * 1000
    return {**{k: it[k] for k in ("task", "cat")},
            "lines": len([l for l in code.splitlines() if l.strip()]),
            "text_sim": core.text_similarity(code, it["ref"]), "struct_sim": s, "exec": ex, "ms": ms}


def metrics(rows, pred, pos=None):
    pos = pos or POS
    rows = [r for r in rows if r["cat"] in pos | NEG]
    tp = sum(1 for r in rows if r["cat"] in pos and pred(r))
    fn = sum(1 for r in rows if r["cat"] in pos and not pred(r))
    fp = sum(1 for r in rows if r["cat"] in NEG and pred(r))
    tn = sum(1 for r in rows if r["cat"] in NEG and not pred(r))
    prec = tp / (tp + fp) if tp + fp else 0
    rec = tp / (tp + fn) if tp + fn else 0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0
    acc = (tp + tn) / len(rows)
    return {"TP": tp, "FN": fn, "FP": fp, "TN": tn, "precision": prec, "recall": rec, "F1": f1,
            "FPR": fp / (fp + tn), "accuracy": acc}


def tune(rows, key):
    best = max((metrics(rows, lambda r, t=t: r[key] >= t)["F1"], t) for t in [x / 100 for x in range(5, 100, 5)])
    return best[1]


def main():
    tasks = load()
    val_items, nv, okv = build_items(tasks, list(range(511, 601)))
    test_items, nt, okt = build_items(tasks, list(range(11, 511)))
    with Pool(8) as p:
        val = p.map(score, val_items)
        test = p.map(score, test_items)

    tau_text = tune(val, "text_sim")
    # tune HintGuard threshold with the execution signal switched on
    best = max((metrics(val, lambda r, t=t: r["exec"] or r["struct_sim"] >= t)["F1"], t)
               for t in [x / 100 for x in range(5, 100, 5)])
    tau_hg = best[1]
    tau_struct_only = tune(val, "struct_sim")

    methods = {
        "B1 code-presence rule (>=3 code lines)": lambda r: r["lines"] >= 3,
        f"B2 text similarity (tau={tau_text:.2f})": lambda r: r["text_sim"] >= tau_text,
        "HG-a execution check only": lambda r: r["exec"],
        f"HG-b structural similarity only (tau={tau_struct_only:.2f})": lambda r: r["struct_sim"] >= tau_struct_only,
        f"HintGuard: execution OR structure (tau={tau_hg:.2f})": lambda r: r["exec"] or r["struct_sim"] >= tau_hg,
    }
    res = {"splits": {"validation_tasks": nv, "validation_usable": okv, "test_tasks": nt, "test_usable": okt},
           "n_test_responses": len(test), "thresholds": {"text": tau_text, "hg": tau_hg, "struct_only": tau_struct_only},
           "methods": {}, "flag_rate_by_category": {}}
    res["methods_lenient_policy"] = {}
    for name, f in methods.items():
        res["methods"][name] = metrics(test, f)
        res["methods_lenient_policy"][name] = metrics(test, f, POS_LENIENT)
        res["flag_rate_by_category"][name] = {
            c: sum(1 for r in test if r["cat"] == c and f(r)) / max(1, sum(1 for r in test if r["cat"] == c)) for c in CATS}
    res["count_by_category"] = {c: sum(1 for r in test if r["cat"] == c) for c in CATS}
    ms = [r["ms"] for r in test]
    res["latency_ms"] = {"median": statistics.median(ms), "p95": sorted(ms)[int(0.95 * len(ms))], "max": max(ms)}
    json.dump(res, open("results/results.json", "w"), indent=2)
    with open("results/scores_test.csv", "w") as f:
        f.write("task,category,code_lines,text_sim,struct_sim,passes_tests,ms\n")
        for r in test:
            f.write(f"{r['task']},{r['cat']},{r['lines']},{r['text_sim']:.4f},{r['struct_sim']:.4f},{int(r['exec'])},{r['ms']:.1f}\n")
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
