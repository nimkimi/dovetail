"""Trigger detection for the PreToolUse author-time cue.

Pure, stdlib-only. Given the text a change ADDS plus its file path, decide which
dovetail cue triggers fire. Each trigger maps to one cue key the hook will surface.
"""


import re

# Actual loop syntax (not the bare word "for"/"while", which appears in prose,
# strings, and identifiers). Covers C/JS `for(`/`while(`, python/JS for-in/of,
# and python `while …:`.
_LOOP = re.compile(
    r"\bfor\s*\("
    r"|\bfor\s+\w[\w,\s]*\s+(?:in|of)\b"
    r"|\bwhile\s*\("
    r"|^[ \t]*while\s+.+:\s*$",
    re.M,
)

# A fallible call (I/O, network, parse, subprocess) or a caught exception —
# the context where "handle vs propagate / never echo secrets / validate
# untrusted input / release on the error path" is worth surfacing.
_FAILURE_PATH = re.compile(
    r"\bopen\s*\("
    r"|\b(?:requests|httpx|urllib|axios|fetch)\b\s*[.(]"
    r"|\bjson\.loads\s*\(|\bJSON\.parse\s*\("
    r"|\bsubprocess\.\w+\s*\(|\bos\.system\s*\("
    r"|^\s*except\b|\}\s*catch\s*\(|\.catch\s*\(",
    re.M,
)

# A package.json value that looks like a dependency version range (vs. a plain
# metadata string). Reserved scalar keys (name/version/…) are excluded so a
# version bump or rename does not masquerade as a new dependency.
_PKG_JSON_DEP = re.compile(
    r'"(?!(?:name|version|description|main|module|types|typings|license|'
    r'author|homepage|repository|bugs|keywords|private|type|sideEffects|'
    r'engines|packageManager)")'
    r'[^"]+"\s*:\s*"(?:[\^~><=*]|\d|v\d|latest|git|https?:|file:|workspace:|npm:|github:)'
)


def _is_new_dependency(basename: str, added_text: str) -> bool:
    """True when `added_text` adds a dependency line to a known manifest."""
    if basename == "package.json":
        return bool(_PKG_JSON_DEP.search(added_text))
    if basename == "requirements.txt":
        return bool(re.search(r"^\s*[A-Za-z][\w.\-]*\s*(==|>=|<=|~=|!=|>|<)", added_text, re.M))
    if basename == "pyproject.toml":
        return bool(re.search(r"^\s*[A-Za-z][\w.\-]*\s*=\s*[\"'][\^~><=*\d]", added_text, re.M))
    if basename == "go.mod":
        return bool(re.search(r"^\s*[\w.\-/]+\s+v\d", added_text, re.M))
    return False


_COMMENT_LINE = ("#", "//", "--", "/*")

# File types dovetail's code-quality lane covers. Manifests are watched by
# basename (so a non-code .json like package.json still counts); everything else
# is sized by extension. Anything outside both is out of lane → trivial/silent.
_CODE_EXTS = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".go", ".rs", ".java",
    ".rb", ".php", ".c", ".h", ".hpp", ".cpp", ".cc", ".cs", ".m", ".mm",
    ".swift", ".kt", ".kts", ".scala", ".sql", ".sh", ".bash", ".zsh", ".lua",
    ".ex", ".exs", ".pl", ".vue", ".svelte", ".dart",
}
_WATCHED_MANIFESTS = {
    "package.json", "requirements.txt", "pyproject.toml", "go.mod",
    "cargo.toml", "gemfile", "build.gradle", "pom.xml",
}

# Below this many non-whitespace code chars (after dropping comments/blanks) a
# change is cosmetic — the always-on cue would just be noise. High-signal
# triggers still surface separately, so a tiny-but-dangerous edit is not lost.
_TRIVIAL_CODE_CHARS = 10


def is_watched_file(file_path: str) -> bool:
    """True when the file is in dovetail's code-quality lane: a known manifest
    (by basename) or a recognised code extension. Everything else (docs, data,
    lockfiles) is out of lane — the hook must stay silent regardless of content,
    so a trigger pattern appearing in prose never fires a cue."""
    basename = file_path.replace("\\", "/").rsplit("/", 1)[-1].lower()
    ext = "." + basename.rsplit(".", 1)[-1] if "." in basename else ""
    return basename in _WATCHED_MANIFESTS or ext in _CODE_EXTS


def is_trivial(added_text: str, file_path: str) -> bool:
    """True when a PreToolUse change is too small or out-of-lane to cue on:
    a non-code/non-manifest file, or a whitespace/comment-only/cosmetic edit."""
    if not is_watched_file(file_path):
        return True
    code = _strip_full_line_comments(added_text)
    return len(re.sub(r"\s+", "", code)) < _TRIVIAL_CODE_CHARS


def _strip_full_line_comments(text: str) -> str:
    """Drop lines that are entirely a comment, so prose mentioning code-like
    tokens (e.g. `# delete from cache`) does not trip a trigger. Conservative:
    only whole-line comments are removed; inline trailing comments and code are
    left intact (missing a cue is safer than a false one)."""
    return "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith(_COMMENT_LINE)
    )


def _is_breaking_surface(added_text: str) -> bool:
    """True when `added_text` touches a public contract: exported TS type, DB
    schema DDL, an env-var dependency, or a CLI-flag definition. Deliberately
    NOT bare `export const/function` — that is ordinary additive code and would
    fire on nearly every TS edit (reuse/idiom already cover it)."""
    return bool(
        re.search(r"\bexport\s+(?:interface|type|enum)\b", added_text)
        or re.search(r"\b(?:create|alter|drop)\s+table\b", added_text, re.I)
        or re.search(r"\bprocess\.env\.\w+|\bos\.environ\b|\b(?:os\.)?getenv\s*\(", added_text)
        or re.search(
            r"\.add_argument\s*\(|\.option\s*\(|\bflag\.(?:String|Bool|Int|Var)\s*\(",
            added_text,
        )
    )


def _is_high_blast(added_text: str, file_path: str) -> bool:
    """True for a high-blast-radius change: a destructive op, a file living in a
    migrations directory, or a retried effect. (Shared-mutable-state detection is
    deferred for v1 — too false-positive-prone to be proportional.)"""
    if re.search(r"(^|/)migrations?/", file_path.replace("\\", "/")):
        return True
    return bool(
        re.search(r"\b(?:drop|truncate)\s+table\b|\bdelete\s+from\b", added_text, re.I)
        or re.search(
            r"\brm\s+-[a-z]*[rf]|\bshutil\.rmtree\b|\bos\.(?:remove|unlink|rmdir)\b"
            r"|\bfs\.(?:rm|unlink|rmSync|rmdirSync)\b",
            added_text,
        )
        or re.search(r"\bretr(?:y|ies|ied)\b", added_text, re.I)
    )


# A new module / boundary / data-shape — for the Stop hook's one-line
# structural-decision declaration. Detected from the added text (NOT disk state:
# at Stop-time a newly-written file already exists). Plain functions are not
# structural; new classes / exported types / new tables are.
_STRUCTURAL = re.compile(
    r"\bexport\s+(?:interface|type|enum|class|abstract\s+class)\b"
    r"|^\s*(?:export\s+)?(?:default\s+)?class\s+\w"
    r"|^\s*@dataclass\b"
    r"|\bcreate\s+table\b",
    re.M | re.I,
)


def is_structural(added_text: str) -> bool:
    """True when `added_text` introduces a new module / boundary / data shape."""
    return bool(_STRUCTURAL.search(_strip_full_line_comments(added_text)))


def detect_triggers(added_text: str, file_path: str) -> list[str]:
    """Return the cue keys whose trigger pattern appears in `added_text`."""
    triggers: list[str] = []
    added_text = _strip_full_line_comments(added_text)
    if _LOOP.search(added_text):
        triggers.append("runtime-cost")
    if (
        re.search(r"^\s*import\s+\S", added_text, re.M)
        or re.search(r"^\s*from\s+\S+\s+import\s", added_text, re.M)
        or re.search(r"\brequire\s*\(", added_text)
    ):
        triggers.append("reuse")
    basename = file_path.replace("\\", "/").rsplit("/", 1)[-1]
    if _is_new_dependency(basename, added_text):
        triggers.append("dep-vet")
    if _is_breaking_surface(added_text):
        triggers.append("breaking-change")
    if _is_high_blast(added_text, file_path):
        triggers.append("blast-radius")
    if _FAILURE_PATH.search(added_text):
        triggers.append("failure-path")
    return triggers
