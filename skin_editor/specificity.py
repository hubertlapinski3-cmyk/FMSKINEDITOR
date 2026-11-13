"""Raise appended selectors above vanilla competitors. Port of tools/specificity_pass.py, reading the
style index instead of the bundles and covering every sheet's appended rules."""
import math

from . import token_patch as tp

LICENSED = {"PremierLeague", "Bundesliga", "EFLChampionship", "UEFAChampionsLeague", "UEFAEuropa", "UEFASuperCup",
            "UEFAUWCL", "FIFAWC", "FIFAWC2026"}
STATES = {"disabled", "active", "focus", "checked", "hover"}


def subject(parts):
    return tuple(sorted((t, v) for t, v in parts if t != tp.P_PSEUDO))


def states(parts):
    return {v for t, v in parts if t == tp.P_PSEUDO} & STATES


def chain_text(chain):
    s = ""
    for rel, parts in chain:
        s += " > " if rel == 1 else " " if rel == 2 else ""
        s += "".join({tp.P_CLASS: "." + v, tp.P_ID: "#" + v, tp.P_PSEUDO: ":" + v, tp.P_WILDCARD: "*"}.get(t, v)
                     for t, v in parts)
    return s.strip()


def vanilla_table(index, renamed):
    """{subject compound: [competitor rows]} over every non-licensed vanilla rule."""
    key = frozenset(renamed)
    cache = index.__dict__.setdefault("_competitors", {})
    if key in cache:
        return cache[key]
    table = {}
    for sh in index.sheets:
        if sh["name"] in LICENSED:
            continue
        for r in sh["rules"]:
            props = {p[0] for p in r["p"]}
            for text in r["s"]:
                branches = tp.parse_selector(text)
                if not branches:
                    continue
                chain = branches[0]
                allparts = [pt for _rel, parts in chain for pt in parts]
                table.setdefault(subject(chain[-1][1]), []).append({
                    "sheet": sh["name"], "sel": text, "spec": tp.specificity(chain), "states": states(allparts),
                    "props": props, "dead": any(t == tp.P_CLASS and v in renamed for t, v in allparts)})
    cache[key] = table
    return table


def raise_spec(spec, index):
    """Rewrites spec['append_rules_by_sheet'] selectors in place; returns the log."""
    van = vanilla_table(index, set(spec.get("rename_classes", {})))
    log = []
    for rules in spec.get("append_rules_by_sheet", {}).values():
        for r in rules:
            if r["selector"].strip() == ":root":
                continue
            new_branches = []
            for chain in tp.parse_selector(r["selector"]):
                before = tp.specificity(chain)
                st = states([pt for _rel, parts in chain for pt in parts])
                comp, excluded = [], 0
                for v in van.get(subject(chain[-1][1]), []):
                    if not (v["props"] & set(r["props"])) or v["spec"] < before:
                        continue
                    if v["dead"] or (v["states"] - st):
                        excluded += 1
                        continue
                    comp.append(v)
                text = chain_text(chain)
                if comp:
                    top = max(comp, key=lambda v: v["spec"])
                    idx = next((i for i in range(len(chain) - 1, -1, -1)
                                if any(t == tp.P_CLASS for t, _ in chain[i][1])), None)
                    if idx is not None:
                        cls = next(v for t, v in chain[idx][1] if t == tp.P_CLASS)
                        n = math.floor((top["spec"] - before) / 10) + 1
                        chain[idx] = (chain[idx][0], list(chain[idx][1]) + [(tp.P_CLASS, cls)] * n)
                    else:
                        idx = next((i for i in range(len(chain) - 1, -1, -1)
                                    if any(t == tp.P_ID for t, _ in chain[i][1])), None)
                        if idx is None:
                            log.append({"branch": text, "raised_to": text, "before": before, "after": before,
                                        "competitors": len(comp), "strongest": "%s: %s (%d)" % (top["sheet"], top["sel"], top["spec"]),
                                        "excluded_state_or_dead": excluded, "cannot_raise": True})
                            new_branches.append(text)
                            continue
                        iid = next(v for t, v in chain[idx][1] if t == tp.P_ID)
                        n = math.floor((top["spec"] - before) / 100) + 1
                        chain[idx] = (chain[idx][0], list(chain[idx][1]) + [(tp.P_ID, iid)] * n)
                    after = tp.specificity(chain)
                    log.append({"branch": text, "raised_to": chain_text(chain), "before": before, "after": after,
                                "competitors": len(comp), "strongest": "%s: %s (%d)" % (top["sheet"], top["sel"], top["spec"]),
                                "excluded_state_or_dead": excluded})
                    text = chain_text(chain)
                elif excluded:
                    log.append({"branch": text, "raised_to": text, "before": before, "after": before, "competitors": 0,
                                "strongest": "-", "excluded_state_or_dead": excluded})
                new_branches.append(text)
            r["selector"] = ", ".join(new_branches)
    return log
