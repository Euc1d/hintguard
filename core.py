"""HintGuard core: detect whether an AI tutor response leaks the solution of a programming exercise.

The guard is model-agnostic. It only needs (1) the tutor's response text and (2) what the
instructor already has for every exercise: a reference solution and the unit tests.

Two independent signals are combined:
  * execution check  - code found in the response is run against the hidden unit tests;
                       every function in the response is tried under the expected name,
                       so renaming the function does not hide a working solution;
  * structural check - share of the reference solution's token 5-grams that appear in the
                       response after identifiers, numbers and strings are normalised.
"""
import ast
import io
import keyword
import os
import re
import subprocess
import sys
import tempfile
import tokenize
import builtins
import difflib

BUILTINS = set(dir(builtins))
FENCE = re.compile(r"```(?:python|py)?\s*\n(.*?)```", re.S)


# ----------------------------------------------------------------------------- code extraction
def extract_code(response: str) -> str:
    """Return the Python code contained in a tutor response (fenced or unfenced)."""
    blocks = FENCE.findall(response)
    if blocks:
        return "\n".join(b.strip("\n") for b in blocks)
    # no fences: keep paragraphs that parse as Python and are not plain prose
    keep = []
    for chunk in re.split(r"\n\s*\n", response):
        lines = chunk.strip("\n")
        if not lines.strip():
            continue
        try:
            tree = ast.parse(lines)
        except SyntaxError:
            continue
        # a lone expression such as a word is not code
        if all(isinstance(n, ast.Expr) and isinstance(n.value, (ast.Name, ast.Constant)) for n in tree.body):
            continue
        keep.append(lines)
    return "\n".join(keep)


# ----------------------------------------------------------------------------- structural similarity
def norm_tokens(code: str):
    out = []
    try:
        toks = list(tokenize.generate_tokens(io.StringIO(code + "\n").readline))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        toks = []
        for line in code.splitlines():  # fall back to a rough split
            toks += [tokenize.TokenInfo(tokenize.NAME if w.isidentifier() else tokenize.OP, w, 0, 0, "")
                     for w in re.findall(r"[A-Za-z_]\w*|\d+|\S", line)]
    for t in toks:
        if t.type in (tokenize.COMMENT, tokenize.NL, tokenize.ENCODING, tokenize.ENDMARKER):
            continue
        if t.type == tokenize.NAME:
            out.append(t.string if (keyword.iskeyword(t.string) or t.string in BUILTINS) else "ID")
        elif t.type == tokenize.NUMBER:
            out.append("NUM")
        elif t.type == tokenize.STRING:
            out.append("STR")
        elif t.type == tokenize.NEWLINE:
            out.append(";")
        elif t.type == tokenize.INDENT:
            out.append("{")
        elif t.type == tokenize.DEDENT:
            out.append("}")
        else:
            out.append(t.string)
    return out


def ngrams(tokens, k=5):
    return {tuple(tokens[i:i + k]) for i in range(max(0, len(tokens) - k + 1))}


def structural_similarity(response_code: str, reference: str, k: int = 5) -> float:
    """Share of the reference's normalised k-grams that also occur in the response (0..1)."""
    ref = ngrams(norm_tokens(reference), k)
    if not ref or not response_code.strip():
        return 0.0
    return len(ref & ngrams(norm_tokens(response_code), k)) / len(ref)


def text_similarity(response_code: str, reference: str) -> float:
    """Baseline: raw character-level similarity (difflib)."""
    if not response_code.strip():
        return 0.0
    return difflib.SequenceMatcher(None, response_code, reference).ratio()


# ----------------------------------------------------------------------------- execution check
def _top_functions(code: str):
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []
    return [n.name for n in tree.body if isinstance(n, ast.FunctionDef)]


def expected_name(tests):
    for t in tests:
        m = re.search(r"assert\s+(?:not\s+)?\(?\s*([A-Za-z_]\w*)\s*\(", t)
        if m and m.group(1) not in BUILTINS:
            return m.group(1)
    return None


def _run(src: str, timeout: float = 10.0) -> bool:
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(src)
        path = f.name
    try:
        r = subprocess.run([sys.executable, "-I", path], capture_output=True, timeout=timeout,
                           cwd=tempfile.gettempdir())
        return r.returncode == 0
    except subprocess.TimeoutExpired:
        return False
    finally:
        os.unlink(path)


def passes_tests(code: str, tests, setup: str = "") -> bool:
    """True if some function in `code`, bound to the expected name, passes all unit tests."""
    funcs = _top_functions(code)
    if not funcs:
        return False
    target = expected_name(tests)
    body = "\n".join(tests)
    for fn in ([target] if target in funcs else []) + [f for f in funcs if f != target]:
        alias = f"\n{target} = {fn}\n" if target and fn != target else "\n"
        if _run(setup + "\n" + code + alias + body + "\n"):
            return True
    return False


# ----------------------------------------------------------------------------- the guard
DEFAULT_TAU = 0.40  # tuned on the MBPP validation split, see experiment.py


def check(response: str, reference: str, tests, setup: str = "", tau: float = DEFAULT_TAU):
    """Decide whether a tutor response leaks the solution. Returns a dict with the evidence."""
    code = extract_code(response)
    sim = structural_similarity(code, reference)
    runs = passes_tests(code, tests, setup) if code else False
    leak = runs or sim >= tau
    reason = ("response code passes the hidden tests" if runs else
              f"{sim:.0%} of the reference solution's structure is revealed" if leak else
              "no working solution and low structural overlap")
    return {"leak": leak, "passes_tests": runs, "structural_similarity": round(sim, 3),
            "code_lines": len([l for l in code.splitlines() if l.strip()]), "reason": reason}
