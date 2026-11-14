"""M8: the node cap and lazy expansion of a render tree.

A few layouts are huge (`DetailedPreferencesBlock` 5,487 elements, a 27 MB payload at full detail). The cap keeps the first `cap` nodes in breadth-first order and replaces what is
left by stubs: a node whose children do not fit has `children = []` and `collapsed = {"children": n, "descendants": m}`; the browser shows a "show" button on it, which asks again with
that node's path in `open`. Rules, so that nothing moves under the user's hands:

- every top node is kept; a node's children are kept all or none (so a path "0/2/1" means the same in the capped and the full tree);
- the nodes under an opened node are "extra": they never use the shared budget, so opening one branch does not collapse another; their own children stay collapsed until opened too;
- the cap applies after the layout patches and before the cascade, so the cascade only computes what is shown (that is where the time goes: about 0.1 ms per node)."""
from collections import deque


def count(nodes):
    """Number of nodes in a list of subtrees (iterative: the trees are deep)."""
    n, stack = 0, list(nodes)
    while stack:
        x = stack.pop()
        n += 1
        stack.extend(x.get("children") or ())
    return n


def cap_tree(top, cap, open_paths=()):
    """Cut `top` (a list of render nodes, in place) to about `cap` nodes. Returns None when nothing was cut, else
    {"total", "shown", "cap", "collapsed": number of stubs, "opened": number of opened paths that applied}."""
    total = count(top)
    if not cap or cap <= 0 or total <= cap and not open_paths:
        return None
    opened = set(open_paths or ())
    included = len(top)
    queue = deque((n, str(i), False) for i, n in enumerate(top))
    stubs, applied = 0, 0
    while queue:
        n, p, extra = queue.popleft()
        kids = n.get("children") or []
        if not kids:
            continue
        if p in opened:
            applied += 1
            keep = True
            child_extra = True
        elif extra:
            keep, child_extra = False, True
        elif included + len(kids) <= cap:
            keep, child_extra = True, False
            included += len(kids)
        else:
            keep, child_extra = False, False
        if keep:
            queue.extend((c, "%s/%d" % (p, i), child_extra) for i, c in enumerate(kids))
        else:
            n["collapsed"] = {"children": len(kids), "descendants": count(kids)}
            n["children"] = []
            stubs += 1
    if stubs == 0 and not applied:
        return None
    return {"total": total, "shown": count(top), "cap": cap, "collapsed": stubs, "opened": applied}
