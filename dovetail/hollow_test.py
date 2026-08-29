"""Hollow-test detection for the PreToolUse author-time cue.

Pure, stdlib-only, body-scoped: every check runs only INSIDE an extracted
`def test_...` (py) or `it(`/`test(` (ts/js) body, never over the whole diff.
Body-scoping is what lets conftest.py / fixtures / test-utility files stay
silent with no basename denylist — they define no test bodies to scan, so
`has_hollow_test` returns False by construction. The trade-off (accepted,
false-negative-safe): an Edit fragment that touches only the INSIDE of an
existing test body, without the `def`/`it(` line itself in the diff, yields
no extractable body and is missed. A missed cue costs nothing; a noisy one
erodes trust in every dovetail cue.
"""

import re

_TEST_DIR = re.compile(r"(?:^|/)(?:tests?|__tests__)/", re.I)

_JS_EXTS = {"ts", "tsx", "js", "jsx", "mjs", "cjs"}


def _basename(file_path: str) -> str:
    return file_path.replace("\\", "/").rsplit("/", 1)[-1]


def _ext(file_path: str) -> str:
    basename = _basename(file_path)
    return basename.rsplit(".", 1)[-1].lower() if "." in basename else ""


def _is_test_file(file_path: str) -> bool:
    """Path contains a tests?/__tests__ dir, or the basename carries a test
    marker — *.test.*, *_test.*, *.spec.*, or test_*.py (spec trigger)."""
    normalized = file_path.replace("\\", "/")
    if _TEST_DIR.search(normalized):
        return True
    basename = _basename(normalized)
    return (
        ".test." in basename
        or "_test." in basename
        or ".spec." in basename
        or (basename.startswith("test_") and basename.endswith(".py"))
    )


# ---- python ----

_PY_TEST_DEF_LINE = re.compile(r"^(?P<indent>[ \t]*)(?:async\s+)?def\s+test_\w*\s*\(")

# Mock-assertion family (unittest.mock / AsyncMock): calling these alone is
# checking that a call happened, never what the system under test actually
# produced — excluded from "real assertion" so shape 1 (no real assertion)
# also catches the mock-only case without a separate check.
_MOCK_ASSERT_NAMES = (
    r"called|called_once|called_with|called_once_with|any_call|has_calls|"
    r"not_called|awaited|awaited_once|awaited_with|awaited_once_with|"
    r"any_await|has_awaits|not_awaited"
)

# A real python assertion: the bare `assert` keyword, a unittest `self.assertX(`
# call, a pytest/bare `raises(` (exception-path assertion), or an `assert_*`
# helper call that is NOT one of the mock-only names above — covers
# pandas/numpy-style `assert_frame_equal`/`assert_allclose` and custom
# `assert_valid_x` helpers, which are real assertions delegated to a function.
_PY_REAL_ASSERTION = re.compile(
    r"\bassert\b"
    r"|\bassert[A-Z]\w*\s*\("
    rf"|\bassert_(?!(?:{_MOCK_ASSERT_NAMES})\b)\w*\s*\("
    r"|\braises\s*\("
)

_PY_ASSERT_TRUE_LITERAL = re.compile(
    r"^\s*assert\s+True\s*(?:,.*)?$" r"|\bassertTrue\s*\(\s*True\s*\)",
    re.M,
)

_PY_ASSERT_EQ_LINE = re.compile(r"^\s*assert\s+(.+?)\s*==\s*(.+?)\s*(?:,.*)?$", re.M)


_TRIPLE_QUOTE = re.compile(r'"""|\'\'\'')


def _python_test_bodies(text: str) -> "list[str]":
    """Indentation-scoped body for each `def test_...` found in `text`. Best
    effort over a possibly-partial diff fragment: a def line with no visible
    body in this fragment simply yields an empty body (no shape matches it).

    Tracks triple-quoted-string state across lines (odd/even count of
    triple-quote delimiters per line) so column-0 content inside a multiline
    string — a SQL block, an expected-output template — doesn't read as
    dedented-past-the-body and truncate the scan early."""
    lines = text.splitlines()
    bodies = []
    i = 0
    while i < len(lines):
        m = _PY_TEST_DEF_LINE.match(lines[i])
        if not m:
            i += 1
            continue
        indent = len(m.group("indent").expandtabs())
        body = []
        # A one-liner def keeps its whole suite on the def line
        # (`def test_x(): assert f() == 42`) — seed the body with it, or the
        # only real assertion is invisible and the test falsely reads hollow.
        _, sep, inline = lines[i].partition("):")
        if sep and inline.strip():
            body.append(inline.strip())
        in_string = False
        j = i + 1
        while j < len(lines):
            line = lines[j]
            if in_string:
                body.append(line)
                if len(_TRIPLE_QUOTE.findall(line)) % 2 == 1:
                    in_string = False
                j += 1
                continue
            if line.strip() == "":
                body.append(line)
                j += 1
                continue
            cur_indent = len(line[: len(line) - len(line.lstrip())].expandtabs())
            if cur_indent <= indent:
                break
            body.append(line)
            if len(_TRIPLE_QUOTE.findall(line)) % 2 == 1:
                in_string = True
            j += 1
        bodies.append("\n".join(body))
        i = j
    return bodies


def _has_self_equality(body: str) -> bool:
    for m in _PY_ASSERT_EQ_LINE.finditer(body):
        lhs, rhs = m.group(1).strip(), m.group(2).strip()
        if lhs and lhs == rhs:
            return True
    return False


def _has_hollow_python_test(added_text: str) -> bool:
    for body in _python_test_bodies(added_text):
        if not _PY_REAL_ASSERTION.search(body):
            return True
        if _PY_ASSERT_TRUE_LITERAL.search(body):
            return True
        if _has_self_equality(body):
            return True
    return False


# ---- js / ts ----

# `it(`/`test(` with a name string (any quote style, via backreference so an
# apostrophe inside the name doesn't terminate the match early) and a
# function/arrow callback, up to its opening `{`. The matching `}` is found by
# a balanced-brace scan below — regex alone can't nest.
_JS_TEST_CALL = re.compile(
    r"\b(?:it|test)\s*\(\s*(?P<q>['\"`]).*?(?P=q)\s*,\s*"
    r"(?:async\s*)?(?:function\s*\([^)]*\)|\([^)]*\)\s*=>|\w+\s*=>)\s*\{"
)

_JS_EXPECT_START = re.compile(r"\bexpect\s*\(")
# The LAST `.name(` in the chain is the matcher; `.not`/`.resolves`/`.rejects`
# (and any other bare `.word` link) may sit in front of it — capture whichever
# segment is immediately followed by a call, via backtracking over the
# zero-or-more non-call segments first.
_JS_MATCHER_NAME = re.compile(r"\s*(?:\.\s*\w+\s*)*\.\s*(\w+)\s*\(")

_JS_EXPECT_TRUE_TAUTOLOGY = re.compile(r"expect\s*\(\s*true\s*\)\s*\.\s*toBe\s*\(\s*true\s*\)")


def _matched_paren(text: str, open_idx: int) -> "int | None":
    """Index of the ')' matching the '(' at text[open_idx], or None if the
    fragment is cut off before it closes (partial-diff safe direction)."""
    depth = 1
    i = open_idx + 1
    n = len(text)
    while i < n and depth > 0:
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
        i += 1
    return i - 1 if depth == 0 else None


def _js_matchers(body: str) -> "list[str]":
    """Matcher name following each `expect(...)` call in `body`. Finds the
    close paren with a balanced scan (not `[^)]*`) so an argument that itself
    contains parens — `expect(render().title)` — doesn't truncate early."""
    matchers = []
    for m in _JS_EXPECT_START.finditer(body):
        open_idx = m.end() - 1
        close_idx = _matched_paren(body, open_idx)
        if close_idx is None:
            continue
        name_match = _JS_MATCHER_NAME.match(body, close_idx + 1)
        if name_match:
            matchers.append(name_match.group(1))
    return matchers


def _js_test_bodies(text: str) -> "list[str]":
    """Balanced-brace body for each `it(`/`test(` call found in `text`. An
    unbalanced fragment (diff cuts off mid-block) yields no body for that
    call — safe direction, matches the python side's partial-fragment miss."""
    bodies = []
    for m in _JS_TEST_CALL.finditer(text):
        start = m.end()
        depth = 1
        i = start
        n = len(text)
        while i < n and depth > 0:
            c = text[i]
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
            i += 1
        if depth == 0:
            bodies.append(text[start : i - 1])
    return bodies


def _has_real_js_assertion(body: str) -> bool:
    """True when at least one `expect(...)` matcher in `body` is NOT a
    toHaveBeen*-family mock matcher (toHaveBeenCalled, ...CalledWith,
    ...LastCalledWith, ...NthCalledWith, ...)."""
    matchers = _js_matchers(body)
    return any(not m.startswith("toHaveBeen") for m in matchers)


def _has_hollow_js_test(added_text: str) -> bool:
    for body in _js_test_bodies(added_text):
        if not _has_real_js_assertion(body):
            return True
        if _JS_EXPECT_TRUE_TAUTOLOGY.search(body):
            return True
    return False


def has_hollow_test(added_text: str, file_path: str) -> bool:
    """True when `added_text` (already scoped to a test-path file) contains a
    hollow test shape: no real assertion, an assert-only-on-mock body, a
    literal `assert True`/`assertTrue(True)`/`expect(true).toBe(true)`
    tautology, or a byte-identical `assert X == X`. False for any file whose
    path doesn't look like a test, any file with no extractable test body
    (helper/fixture files), and any extension outside py/ts/js."""
    if not _is_test_file(file_path):
        return False
    ext = _ext(file_path)
    if ext == "py":
        return _has_hollow_python_test(added_text)
    if ext in _JS_EXTS:
        return _has_hollow_js_test(added_text)
    return False
