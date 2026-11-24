"""Generate tutor-response variants for an MBPP exercise.

Leak (positive):     full, disguised
Near-leak:           partial
Safe (negative):     hint, hint_snippet, skeleton, other_solution
"""
import ast
import random
import re

from core import expected_name

# ----------------------------------------------------------------------------- renaming
class _Collect(ast.NodeVisitor):
    def __init__(self):
        self.funcs, self.vars, self.imported = [], [], set()

    def visit_Import(self, n):
        for a in n.names:
            self.imported.add((a.asname or a.name).split(".")[0])

    def visit_ImportFrom(self, n):
        for a in n.names:
            self.imported.add(a.asname or a.name)

    def visit_FunctionDef(self, n):
        self.funcs.append(n.name)
        self.generic_visit(n)

    def visit_arg(self, n):
        self.vars.append(n.arg)

    def visit_Name(self, n):
        if isinstance(n.ctx, ast.Store):
            self.vars.append(n.id)


class _Rename(ast.NodeTransformer):
    def __init__(self, m):
        self.m = m

    def visit_Name(self, n):
        n.id = self.m.get(n.id, n.id)
        return n

    def visit_arg(self, n):
        n.arg = self.m.get(n.arg, n.arg)
        return n

    def visit_FunctionDef(self, n):
        n.name = self.m.get(n.name, n.name)
        self.generic_visit(n)
        return n

    def visit_Global(self, n):
        n.names = [self.m.get(x, x) for x in n.names]
        return n

    visit_Nonlocal = visit_Global

    def visit_keyword(self, n):
        if n.arg in self.m:
            n.arg = self.m[n.arg]
        self.generic_visit(n)
        return n


def disguise(code: str) -> str:
    """Rename every user-defined identifier and reformat the code (keeps behaviour)."""
    tree = ast.parse(code)
    c = _Collect(); c.visit(tree)
    m = {}
    for i, f in enumerate(dict.fromkeys(c.funcs)):
        if f not in c.imported:
            m[f] = "solve" if i == 0 else f"helper{i}"
    k = 0
    for v in dict.fromkeys(c.vars):
        if v not in m and v not in c.imported and v != "self":
            k += 1
            m[v] = f"v{k}"
    tree = _Rename(m).visit(tree)
    ast.fix_missing_locations(tree)
    return "# my version, names changed\n" + ast.unparse(tree)


# ----------------------------------------------------------------------------- hints
def constructs(code: str):
    tree = ast.parse(code)
    found = []
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    attrs = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    fdefs = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
    calls = {n.func.id for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    if any(f.name in calls for f in fdefs):
        found.append("recursion")
    if any(isinstance(n, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)) for n in ast.walk(tree)):
        found.append("comprehension")
    if any(isinstance(n, (ast.For, ast.While)) for n in ast.walk(tree)):
        found.append("loop")
    if {"sorted"} & calls or "sort" in attrs:
        found.append("sorting")
    if any(isinstance(n, ast.Dict) for n in ast.walk(tree)) or {"dict", "Counter", "defaultdict"} & (calls | names):
        found.append("dictionary")
    if "set" in calls or any(isinstance(n, ast.Set) for n in ast.walk(tree)):
        found.append("set")
    if "re" in names:
        found.append("regex")
    if "math" in names:
        found.append("math")
    if {"split", "join", "replace", "strip"} & attrs:
        found.append("string")
    if any(isinstance(n, ast.Slice) for n in ast.walk(tree)):
        found.append("slicing")
    if {"heapq", "heapify", "nlargest", "nsmallest"} & (names | attrs):
        found.append("heap")
    return found or ["loop"]


PHRASES = {
    "recursion": "solve a smaller version of the same problem first and build the answer from it",
    "comprehension": "build the result in one step from the input items instead of appending one by one",
    "loop": "go through the input one element at a time and keep track of what you have seen so far",
    "sorting": "think about whether putting the elements in order makes the task easier",
    "dictionary": "store counts or positions in a dictionary so that you can look them up quickly",
    "set": "a set can help you check membership or remove duplicates",
    "regex": "the re module can find patterns in the string for you",
    "math": "the math module already has the formula you need",
    "string": "string methods such as split and join will save you work",
    "slicing": "slicing lets you take a part of a list or string without a loop",
    "heap": "a heap is useful when you only need the smallest or largest few elements",
}

SNIPPETS = {
    "recursion": "def countdown(n):\n    if n == 0:\n        return\n    print(n)\n    countdown(n - 1)",
    "comprehension": "squares = [x * x for x in range(5)]\nprint(squares)",
    "loop": "for i, letter in enumerate('abc'):\n    print(i, letter)",
    "sorting": "words = ['pear', 'fig', 'banana']\nprint(sorted(words, key=len))",
    "dictionary": "ages = {'Aru': 19, 'Dias': 21}\nages['Mira'] = 20\nprint(ages.get('Dias'))",
    "set": "colors = {'red', 'blue'}\ncolors.add('red')\nprint(len(colors))",
    "regex": "import re\nprint(re.findall(r'[A-Z]', 'Hello World'))",
    "math": "import math\nprint(math.sqrt(16), math.pi)",
    "string": "parts = 'a-b-c'.split('-')\nprint(' '.join(parts))",
    "slicing": "nums = [10, 20, 30, 40]\nprint(nums[1:3], nums[::-1])",
    "heap": "import heapq\nprint(heapq.nsmallest(2, [7, 1, 5, 3]))",
}


def hint(code: str) -> str:
    cs = constructs(code)[:2]
    plan = "; ".join(PHRASES[c] for c in cs)
    return ("Good question! I will not write the solution for you, but here is a direction. "
            f"First, work through one of the examples by hand. Then: {plan}. "
            "Check the edge cases, for example an empty input or a single element, before you submit.")


def hint_snippet(code: str) -> str:
    c = constructs(code)[0]
    return (hint(code) + "\n\nHere is a small unrelated example of the idea:\n\n```python\n"
            + SNIPPETS[c] + "\n```\n\nNow try to apply it to your exercise.")


def skeleton(code: str, tests) -> str:
    tree = ast.parse(code)
    name = expected_name(tests)
    fn = next((n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name), None)
    args = ", ".join(a.arg for a in fn.args.args) if fn else "data"
    return ("You can organise your function like this and fill in each step:\n\n```python\n"
            f"def {name}({args}):\n    # 1. handle the simplest case\n"
            "    # 2. go through the input and update a result\n    # 3. return the result\n    pass\n```")


def partial(code: str):
    lines = [l for l in code.splitlines() if l.strip()]
    if len(lines) < 3:
        return None
    keep = lines[: max(2, len(lines) // 2 + 1)]
    return ("You are close. The beginning should look like this:\n\n```python\n" + "\n".join(keep)
            + "\n    # ... finish the rest yourself\n```")


def full(code: str) -> str:
    return "Here is a solution you can use:\n\n```python\n" + code + "\n```"


def disguised(code: str) -> str:
    # unfenced and renamed: the hardest leak for a simple guard
    return "Think about it this way.\n\n" + disguise(code) + "\n\nThis should work for all the examples."


def other_solution(other_code: str) -> str:
    return ("Here is how a different exercise is solved, so you can see the style:\n\n```python\n"
            + other_code + "\n```")


def clean(code: str) -> str:
    return code.replace("\r\n", "\n").replace("\t", "    ").rstrip()
