"""Project change notifications for the offline render (M5; docs/PHASE9-PLAN.md section 6).

Every place a project can change calls `record(project, reason, scope)`. The RPC dispatcher wraps each call in `batch()`, so one API call raises ONE `render.invalidate` event per
project however many files it touched: `{project, reason, reasons, scope}`. Outside a batch (the CLI, internal code) a record is emitted at once. A page repaints only what the
reason can affect: `tokens | rules | layout-patch | tile-move | table-edit | font | image | file | options`.

`diff_reasons(old, new)` names what a saved model changed; an identical save records nothing."""
import threading
from contextlib import contextmanager

REASONS = ("tokens", "rules", "layout-patch", "tile-move", "table-edit", "font", "image", "file", "options")
_sink = None
_local = threading.local()

# project model key -> reason (the keys not listed, such as name and schema, change nothing visible)
KEY_REASON = {"token_overrides": "tokens", "literal_swaps": "tokens", "reverts": "tokens", "contrast_pairs": "options",
              "scoped_rules": "rules", "rename_classes": "rules", "native_sheets": "rules",
              "layout_patches": "layout-patch", "table_patches": "table-edit", "font_swaps": "font", "image_swaps": "image",
              "tile_placement": "tile-move", "options": "options", "native_support": "file", "native_name": "options"}


def set_sink(fn):
    """The function every event goes to (the engine publishes it on its event bus). None silences notifications."""
    global _sink
    _sink = fn


def diff_reasons(old, new):
    """[(reason, scope)] for what differs between two project models, in a stable order; [] when nothing visible differs."""
    out = []
    for key, reason in KEY_REASON.items():
        a, b = (old or {}).get(key), (new or {}).get(key)
        if (a or None) != (b or None):               # None, [] and {} are the same "nothing"
            scope = None
            if key == "layout_patches":
                scope = _changed(a, b, lambda d: d["layout"]["name"])
            elif key == "table_patches":
                scope = _changed(a, b, lambda d: d["view"]["name"])
            out.append((reason, scope))
    merged, seen = [], {}
    for reason, scope in out:                      # one entry per reason (several keys map to "tokens", "rules", ...)
        if reason in seen:
            if scope:
                merged[seen[reason]] = (reason, sorted(set(merged[seen[reason]][1] or []) | set(scope)))
            continue
        seen[reason] = len(merged)
        merged.append((reason, scope))
    return merged


def _changed(a, b, name):
    """Names of the patch documents that are in one list and not the other, or differ between them."""
    key = lambda d: __import__("json").dumps(d, sort_keys=True)
    sa, sb = {key(d): name(d) for d in a or [] if isinstance(d, dict)}, {key(d): name(d) for d in b or [] if isinstance(d, dict)}
    return sorted({sa[k] for k in set(sa) - set(sb)} | {sb[k] for k in set(sb) - set(sa)})


def record(project, reason, scope=None):
    """Note that `project` changed for `reason`. Inside a batch it is held for the single event; otherwise it is emitted now."""
    assert reason in REASONS, reason
    stack = getattr(_local, "stack", None)
    if stack:
        stack[-1].append((project, reason, scope))
    else:
        _emit([(project, reason, scope)])


@contextmanager
def batch():
    """Collect every record made inside; on leaving the OUTERMOST batch emit one event per project. A batch that ends in an exception still emits what changed before it."""
    stack = getattr(_local, "stack", None)
    if stack is None:
        stack = _local.stack = []
    stack.append([])
    try:
        yield
    finally:
        items = stack.pop()
        if stack:
            stack[-1].extend(items)
        elif items:
            _emit(items)


def _emit(items):
    if _sink is None:
        return
    by = {}
    for project, reason, scope in items:
        e = by.setdefault(project, {"project": project, "reasons": [], "scope": []})
        if reason not in e["reasons"]:
            e["reasons"].append(reason)
        for s in (scope if isinstance(scope, (list, tuple)) else [scope] if scope else []):
            if s not in e["scope"]:
                e["scope"].append(s)
    for e in by.values():
        e["reason"] = e["reasons"][0] if len(e["reasons"]) == 1 else "multiple"
        _sink(e)
