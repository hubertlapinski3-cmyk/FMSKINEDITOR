"""Typed API over the engine: parameter schemas (schema.py), named methods (methods.py), JSON-RPC 2.0 dispatch (rpc.py) and a
job queue with an event bus (jobs.py). Transport-free: server.py exposes it over HTTP (/rpc, /events), __main__ over the CLI."""
