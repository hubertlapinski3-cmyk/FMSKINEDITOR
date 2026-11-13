"""JSON-RPC 2.0 dispatch over the method table. Transport-free: handle(engine, text) -> text (or None for a notification).

Error codes: -32700 parse error, -32600 invalid request, -32601 method not found, -32602 invalid params (data.problems);
application errors: -32004 not found, -32010 placement refused (data: blocks, warnings, collisions, requires_confirm),
-32011 layout dump refused (data.errors), -32020 install refused, -32000 anything else (data.type)."""
import base64
import binascii
import json

from .methods import call, methods
from .schema import SchemaError


class MethodNotFound(Exception):
    """Not a LookupError on purpose: a KeyError raised inside a method must stay an application error."""


def _error(code, message, data=None):
    e = {"code": code, "message": message}
    if data is not None:
        e["data"] = data
    return e


def error_of(ex):
    """An exception from the engine as a JSON-RPC error object."""
    from .. import install, layout_dump
    from ..engine import PlacementRefused
    if isinstance(ex, SchemaError):
        return _error(-32602, "invalid params: " + str(ex), {"problems": ex.problems})
    if isinstance(ex, PlacementRefused):
        return _error(-32010, str(ex), {"blocks": ex.err.blocks, "warnings": ex.err.warnings, "collisions": ex.err.collisions,
                                        "requires_confirm": ex.err.requires_confirm})
    if isinstance(ex, layout_dump.LayoutError):
        return _error(-32011, str(ex), {"errors": ex.errors, "total_errors": ex.total})
    if isinstance(ex, install.InstallError):
        return _error(-32020, str(ex), {"type": "InstallError"})
    if isinstance(ex, (KeyError, FileNotFoundError)):
        return _error(-32004, "not found: %s" % (ex.args[0] if ex.args else ex), {"type": type(ex).__name__})
    return _error(-32000, "%s: %s" % (type(ex).__name__, ex), {"type": type(ex).__name__})


def invoke(engine, name, params):
    """Run one method by name with JSON params ('data' as base64 for byte parameters). Raises on failure."""
    m = methods().get(name)
    if m is None:
        raise MethodNotFound(name)
    params = dict(params or {})
    if m.schema.get("data") == "bytes" and isinstance(params.get("data"), str):
        try:
            params["data"] = base64.b64decode(params["data"], validate=True)
        except (binascii.Error, ValueError):
            raise SchemaError(["data must be base64"])
    return call(engine, m, params)


def _one(engine, req):
    if not isinstance(req, dict) or req.get("jsonrpc") != "2.0" or not isinstance(req.get("method"), str):
        return {"jsonrpc": "2.0", "id": req.get("id") if isinstance(req, dict) else None, "error": _error(-32600, "invalid request")}
    rid, notify = req.get("id"), "id" not in req
    params = req.get("params", {})
    if not isinstance(params, dict):
        out = {"error": _error(-32602, "invalid params: params must be an object (named parameters)")}
    else:
        try:
            out = {"result": invoke(engine, req["method"], params)}
        except MethodNotFound as ex:
            out = {"error": _error(-32601, "method not found: %s" % ex.args[0])}
        except Exception as ex:
            out = {"error": error_of(ex)}
    return None if notify else dict({"jsonrpc": "2.0", "id": rid}, **out)


def handle(engine, text):
    """One JSON-RPC message (a request or a batch) in, the response text out; None when nothing is to be sent."""
    try:
        req = json.loads(text)
    except (ValueError, UnicodeDecodeError):
        return json.dumps({"jsonrpc": "2.0", "id": None, "error": _error(-32700, "parse error")})
    if isinstance(req, list):
        if not req:
            return json.dumps({"jsonrpc": "2.0", "id": None, "error": _error(-32600, "invalid request")})
        res = [r for r in (_one(engine, x) for x in req) if r is not None]
        return json.dumps(res, default=str) if res else None
    res = _one(engine, req)
    return json.dumps(res, default=str) if res is not None else None
