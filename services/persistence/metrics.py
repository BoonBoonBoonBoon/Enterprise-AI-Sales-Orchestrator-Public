"""Lightweight in-process metrics collectors for persistence layer.

Purpose: Provide a no-dependency mechanism to accumulate basic counters and
latency aggregates until a full metrics backend (Prometheus/OpenTelemetry)
is wired. Designed to be threadsafe-light (GIL reliance) and inexpensive.
"""
from __future__ import annotations
import time
from typing import Dict, Tuple

_counter: Dict[Tuple[str, str], int] = {}
_latency: Dict[Tuple[str, str], Dict[str, float]] = {}


def inc(op: str, table: str):  # increment operation counter
    key = (op, table)
    _counter[key] = _counter.get(key, 0) + 1


def observe(op: str, table: str, ms: float):  # record latency stats (min/max/count/total)
    key = (op, table)
    bucket = _latency.setdefault(key, {"count": 0, "total": 0.0, "min": ms, "max": ms})
    bucket["count"] += 1
    bucket["total"] += ms
    if ms < bucket["min"]:
        bucket["min"] = ms
    if ms > bucket["max"]:
        bucket["max"] = ms


def snapshot():  # produce a read-only view
    out = []
    for (op, table), c in _counter.items():
        lat = _latency.get((op, table))
        if lat:
            avg = lat["total"] / lat["count"] if lat["count"] else 0.0
            out.append({
                "op": op,
                "table": table,
                "count": c,
                "lat_min_ms": round(lat["min"], 2),
                "lat_max_ms": round(lat["max"], 2),
                "lat_avg_ms": round(avg, 2),
            })
        else:
            out.append({"op": op, "table": table, "count": c})
    return sorted(out, key=lambda r: (r["op"], r["table"]))

__all__ = ["inc", "observe", "snapshot"]
