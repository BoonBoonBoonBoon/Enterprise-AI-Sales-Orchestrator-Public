#!/usr/bin/env python3
"""
Redis Health Check API

Comprehensive health monitoring endpoint that returns JSON with all health metrics.
Can be used for programmatic monitoring, alerting, and dashboards.

Usage:
    # JSON output (default)
    python scripts/health_check.py

    # Pretty-printed JSON
    python scripts/health_check.py --pretty

    # Exit with non-zero code if unhealthy
    python scripts/health_check.py --fail-on-unhealthy

    # Custom alert thresholds
    python scripts/health_check.py --max-pending 500 --max-dlq 50 --max-idle-sec 120

Returns:
    JSON object with structure:
    {
        "status": "healthy" | "degraded" | "unhealthy",
        "timestamp": "2025-01-26T10:30:00Z",
        "namespace": "agentic-dev",
        "connection": {"status": "ok", "url": "redis://<REDACTED_REDIS_URL>"},
        "streams": {
            "rag:tasks": {"length": 3, "pending": 0, "consumers": 1, ...},
            ...
        },
        "heartbeats": {"rag": 1, "persist": 1, "copy": 0, "orchestrator": 0},
        "workflow_state": {"active_workflows": 1},
        "dlq": {"rag": 0, "persist": 2, "copy": 0},
        "alerts": [{"severity": "warning", "message": "..."}],
        "metrics": {
            "total_streams": 11,
            "total_pending": 0,
            "total_dlq_messages": 2,
            "active_consumers": 4
        }
    }
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any

from dotenv import load_dotenv

# Load .env BEFORE importing config
load_dotenv()

import redis


def _tenant_prefix() -> str:
    return os.getenv("TENANT_ID", "agentic-dev")


def _full_key(name: str) -> str:
    tenant_id = _tenant_prefix()
    return f"{tenant_id}:{name}" if tenant_id else name


class HealthChecker:
    """Comprehensive Redis health checker with configurable thresholds."""

    def __init__(
        self,
        max_pending: int = 1000,
        max_dlq: int = 100,
        max_consumer_idle_sec: int = 300,
        fail_on_unhealthy: bool = False,
    ):
        self.max_pending = max_pending
        self.max_dlq = max_dlq
        self.max_consumer_idle_ms = max_consumer_idle_sec * 1000
        self.fail_on_unhealthy = fail_on_unhealthy
        self.alerts = []
        self.metrics = {
            "total_streams": 0,
            "total_pending": 0,
            "total_dlq_messages": 0,
            "active_consumers": 0,
        }

    def _add_alert(self, severity: str, message: str) -> None:
        """Add an alert to the collection."""
        self.alerts.append({"severity": severity, "message": message})

    def _get_stream_info(self, client, stream_key: str) -> dict[str, Any] | None:
        """Get stream metadata (length, last-generated-id)."""
        try:
            info = client.xinfo_stream(stream_key)
            return {
                "length": int(info.get("length", 0)),
                "last_generated_id": str(info.get("last-generated-id", "")),
                "exists": True,
            }
        except Exception:
            return {"length": 0, "exists": False}

    def _get_group_info(
        self, client, stream_key: str, group: str
    ) -> dict[str, Any]:
        """Get consumer group info (consumers, pending, lag)."""
        try:
            groups = client.xinfo_groups(stream_key)
            for g in groups:
                if g.get("name") == group:
                    # Calculate consumer lag
                    lag = self._calculate_consumer_lag(client, stream_key, str(g.get("last-delivered-id", "0-0")))
                    
                    return {
                        "consumers": int(g.get("consumers", 0)),
                        "pending": int(g.get("pending", 0)),
                        "last_delivered_id": str(g.get("last-delivered-id", "")),
                        "lag": lag,  # Number of messages between last-delivered and stream end
                    }
        except Exception:
            pass
        return {"consumers": 0, "pending": 0, "last_delivered_id": "", "lag": 0}
    
    def _calculate_consumer_lag(self, client, stream_key: str, last_delivered_id: str) -> int:
        """Calculate lag: number of messages between last-delivered-id and stream end.
        
        Returns:
            Number of messages not yet delivered to consumers (consumer lag)
        """
        try:
            # Get all messages after last-delivered-id
            if last_delivered_id == "0-0" or not last_delivered_id:
                # Group hasn't delivered anything yet, count all messages
                info = client.xinfo_stream(stream_key)
                return int(info.get("length", 0))
            
            # Count messages from (last-delivered-id, stream-end]
            # Use XLEN to get total length, then subtract processed
            total_length = int(client.xinfo_stream(stream_key).get("length", 0))
            
            # Count messages up to and including last-delivered-id
            processed = len(client.xrange(stream_key, "-", last_delivered_id))
            
            lag = total_length - processed
            return max(0, lag)  # Ensure non-negative
        except Exception:
            return 0

    def _get_consumer_details(
        self, client, stream_key: str, group: str
    ) -> list[dict[str, Any]]:
        """Get details about individual consumers."""
        try:
            consumers = client.xinfo_consumers(stream_key, group)
            result = []
            for c in consumers:
                idle_ms = int(c.get("idle", 0))
                result.append(
                    {
                        "name": str(c.get("name", "")),
                        "pending": int(c.get("pending", 0)),
                        "idle_ms": idle_ms,
                        "idle_sec": idle_ms / 1000,
                    }
                )
                # Alert on consumers that are stale *and* holding pending work.
                pending = int(c.get("pending", 0))
                if pending > 0 and idle_ms > self.max_consumer_idle_ms:
                    self._add_alert(
                        "warning",
                        f"Stale consumer: {group}/{c.get('name')} idle for {idle_ms/1000:.0f}s",
                    )
            return result
        except Exception:
            return []

    def _check_stream(
        self, client, stream_name: str, group_name: str | None = None
    ) -> dict[str, Any]:
        """Check a single stream and optionally its consumer group."""
        stream_key = _full_key(stream_name)
        info = self._get_stream_info(client, stream_key)

        if not info or not info.get("exists"):
            return {"exists": False, "length": 0, "pending": 0}

        self.metrics["total_streams"] += 1

        result = {
            "exists": True,
            "length": info["length"],
            "last_generated_id": info["last_generated_id"],
        }

        if group_name:
            group_info = self._get_group_info(client, stream_key, group_name)
            consumers = self._get_consumer_details(client, stream_key, group_name)

            result.update(
                {
                    "group": group_name,
                    "consumers": group_info["consumers"],
                    "pending": group_info["pending"],
                    "last_delivered_id": group_info["last_delivered_id"],
                    "lag": group_info["lag"],
                    "consumer_details": consumers,
                }
            )

            self.metrics["total_pending"] += group_info["pending"]
            self.metrics["active_consumers"] += group_info["consumers"]

            # Alert on high pending
            if group_info["pending"] > self.max_pending:
                self._add_alert(
                    "critical",
                    f"High pending count: {group_name} has {group_info['pending']} pending (threshold: {self.max_pending})",
                )
            
            # Alert on high consumer lag
            if group_info["lag"] > self.max_pending:  # Use same threshold
                self._add_alert(
                    "warning",
                    f"High consumer lag: {group_name} has {group_info['lag']} undelivered messages",
                )

        return result

    def _check_heartbeats(self, client) -> dict[str, int]:
        """Count heartbeat keys by service."""
        services = [
            "manager",
            "leads",
            "outbound",
            "rag",
            "persistence",
            "copywriter",
            "booking",
            "sequencing",
        ]
        counts = {}
        for service in services:
            pattern = _full_key(f"ops:hb:{service}:*")
            count = sum(1 for _ in client.scan_iter(match=pattern, count=10))
            counts[service] = count

        # Only warn about missing heartbeats if heartbeats appear to be enabled at all.
        if sum(counts.values()) > 0:
            for service, count in counts.items():
                if count == 0:
                    self._add_alert(
                        "warning",
                        f"No active {service} workers detected (no heartbeats)",
                    )
        return counts

    def _check_workflow_state(self, client) -> dict[str, Any]:
        """Count and sample workflow state keys."""
        pattern = _full_key("workflow:state:*")
        total = 0
        samples = []
        try:
            for key in client.scan_iter(match=pattern, count=100):
                total += 1
                if len(samples) < 5:
                    try:
                        data = client.hgetall(key)
                        ttl = client.ttl(key)
                        correlation_id = str(key).split(":")[-1]
                        samples.append(
                            {
                                "correlation_id": correlation_id,
                                "status": data.get("status", "unknown"),
                                "task_count": int(data.get("task_count", 0)),
                                "completed_count": int(data.get("completed_count", 0)),
                                "ttl": ttl,
                            }
                        )
                    except Exception:
                        pass
        except Exception as e:
            self._add_alert("warning", f"Workflow state check failed: {e}")

        return {"active_workflows": total, "samples": samples}

    def _check_dlq(self, client) -> dict[str, int]:
        """Check DLQ stream lengths."""
        dlqs = {
            "rag": _full_key("agents:rag:dlq"),
            "persistence": _full_key("agents:persistence:dlq"),
            "copywriter": _full_key("agents:copywriter:dlq"),
            "booking": _full_key("agents:booking:dlq"),
            "sequencing": _full_key("agents:sequencing:dlq"),
            "leads": _full_key("orchestrators:leads:dlq"),
            "outbound": _full_key("orchestrators:outbound:dlq"),
            "manager": _full_key("manager:dlq"),
        }

        counts = {}
        for name, key in dlqs.items():
            info = self._get_stream_info(client, key)
            length = info["length"] if info else 0
            counts[name] = length
            self.metrics["total_dlq_messages"] += length

            # Alert on DLQ growth
            if length > self.max_dlq:
                self._add_alert(
                    "warning",
                    f"DLQ growth: {name}:dlq has {length} messages (threshold: {self.max_dlq})",
                )

        return counts

    def check_health(self) -> dict[str, Any]:
        """Perform comprehensive health check and return results."""
        result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "namespace": _tenant_prefix(),
        }

        try:
            client = redis.Redis.from_url(
                os.getenv("REDIS_URL", "redis://localhost:6379/0"),
                decode_responses=True,
                socket_connect_timeout=2,
            )

            # Connection check
            client.ping()
            result["connection"] = {
                "status": "ok",
                "url": os.getenv("REDIS_URL", "(not set)"),
            }

            # Check all streams
            result["streams"] = {
                "manager:tasks": self._check_stream(
                    client,
                    "manager:tasks",
                    "manager-workers",
                ),
                "manager:results": self._check_stream(client, "manager:results"),
                "orchestrators:leads:tasks": self._check_stream(
                    client,
                    "orchestrators:leads:tasks",
                    "leads-workers",
                ),
                "orchestrators:leads:results": self._check_stream(
                    client,
                    "orchestrators:leads:results",
                ),
                "orchestrators:outbound:tasks": self._check_stream(
                    client,
                    "orchestrators:outbound:tasks",
                    "outbound-workers",
                ),
                "orchestrators:outbound:results": self._check_stream(
                    client,
                    "orchestrators:outbound:results",
                ),
                "agents:rag:tasks": self._check_stream(
                    client,
                    "agents:rag:tasks",
                    "rag-workers",
                ),
                "agents:rag:results": self._check_stream(client, "agents:rag:results"),
                "agents:persistence:tasks": self._check_stream(
                    client,
                    "agents:persistence:tasks",
                    "persistence-workers",
                ),
                "agents:persistence:results": self._check_stream(
                    client,
                    "agents:persistence:results",
                ),
                "agents:copywriter:tasks": self._check_stream(
                    client,
                    "agents:copywriter:tasks",
                    "copywriter-workers",
                ),
                "agents:copywriter:results": self._check_stream(
                    client,
                    "agents:copywriter:results",
                ),
                "agents:booking:tasks": self._check_stream(
                    client,
                    "agents:booking:tasks",
                    "booking-workers",
                ),
                "agents:booking:results": self._check_stream(
                    client,
                    "agents:booking:results",
                ),
                "agents:sequencing:tasks": self._check_stream(
                    client,
                    "agents:sequencing:tasks",
                    "sequencing-workers",
                ),
                "agents:sequencing:results": self._check_stream(
                    client,
                    "agents:sequencing:results",
                ),
            }

            # Heartbeats
            result["heartbeats"] = self._check_heartbeats(client)

            # Workflow state
            result["workflow_state"] = self._check_workflow_state(client)

            # DLQ
            result["dlq"] = self._check_dlq(client)

            # Metrics
            result["metrics"] = self.metrics

            # Alerts
            result["alerts"] = self.alerts

            # Overall status
            if any(a["severity"] == "critical" for a in self.alerts):
                result["status"] = "unhealthy"
            elif self.alerts:
                result["status"] = "degraded"
            else:
                result["status"] = "healthy"

        except Exception as e:
            result["status"] = "unhealthy"
            result["connection"] = {"status": "error", "error": str(e)}
            self._add_alert("critical", f"Connection failed: {e}")
            result["alerts"] = self.alerts

        return result


def main():
    parser = argparse.ArgumentParser(
        description="Redis Health Check - Comprehensive health monitoring with JSON output"
    )
    parser.add_argument(
        "--pretty", action="store_true", help="Pretty-print JSON output"
    )
    parser.add_argument(
        "--fail-on-unhealthy",
        action="store_true",
        help="Exit with code 1 if status is unhealthy",
    )
    parser.add_argument(
        "--max-pending",
        type=int,
        default=1000,
        help="Max pending messages threshold (default: 1000)",
    )
    parser.add_argument(
        "--max-dlq", type=int, default=100, help="Max DLQ messages threshold (default: 100)"
    )
    parser.add_argument(
        "--max-idle-sec",
        type=int,
        default=300,
        help="Max consumer idle time in seconds (default: 300)",
    )

    args = parser.parse_args()

    checker = HealthChecker(
        max_pending=args.max_pending,
        max_dlq=args.max_dlq,
        max_consumer_idle_sec=args.max_idle_sec,
        fail_on_unhealthy=args.fail_on_unhealthy,
    )

    health = checker.check_health()

    # Output JSON
    if args.pretty:
        print(json.dumps(health, indent=2))
    else:
        print(json.dumps(health))

    # Exit code
    if args.fail_on_unhealthy and health["status"] == "unhealthy":
        sys.exit(1)


if __name__ == "__main__":
    main()

