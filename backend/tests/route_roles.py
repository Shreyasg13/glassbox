"""Enumerates every route in the app and the role each one declares (see app.auth.require_role).

    python -m tests.route_roles --write     # regenerate tests/route_role_allowlist.txt (only ever do this to REMOVE lines)
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, Set

ALLOWLIST = Path(__file__).with_name("route_role_allowlist.txt")


def _walk(dep, out: Set[str]) -> None:
    role = getattr(getattr(dep, "call", None), "declared_role", None)
    if role:
        out.add(role)
    for d in dep.dependencies:
        _walk(d, out)


def _iter_routes(routes, prefix: str = "", extra_deps: tuple = ()):
    """Flattens the app's routes. Newer FastAPI keeps each included router as a wrapper, so unwrap it, carrying the prefix
    and any include-level dependencies down to the concrete routes."""
    for r in routes:
        if type(r).__name__ == "_IncludedRouter":
            ctx = r.include_context
            yield from _iter_routes(r.original_router.routes, prefix + (ctx.prefix or ""), extra_deps + tuple(ctx.dependencies or ()))
        else:
            yield r, prefix, extra_deps


def route_roles() -> Dict[str, Set[str]]:
    """{ "GET /api/x": {"admin"} } for every route; an empty set means the route declares no role."""
    from app.main import app

    found: Dict[str, Set[str]] = {}
    for r, prefix, extra in _iter_routes(app.routes):
        path = prefix + r.path
        dependant = getattr(r, "dependant", None)
        methods = getattr(r, "methods", None)
        key = f"{','.join(sorted(m for m in methods if m != 'HEAD'))} {path}" if methods else f"{'WS' if dependant is not None else 'ROUTE'} {path}"
        roles: Set[str] = set()
        if dependant is not None:
            _walk(dependant, roles)
        for d in extra:
            role = getattr(getattr(d, "dependency", None), "declared_role", None)
            if role:
                roles.add(role)
        found[key] = roles
    return found


def undeclared() -> list[str]:
    return sorted(k for k, v in route_roles().items() if not v)


if __name__ == "__main__":
    if "--write" in sys.argv:
        ALLOWLIST.write_text("\n".join(undeclared()) + "\n", encoding="utf-8")
        print(f"wrote {len(undeclared())} entries to {ALLOWLIST}")
    else:
        print("\n".join(undeclared()))
