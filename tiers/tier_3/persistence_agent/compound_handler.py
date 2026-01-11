"""Compound multi-table operations with FK resolution, conditions, rollback."""

from __future__ import annotations

import logging
import os
import re
import uuid
from typing import Any, Dict, List, Optional, Tuple, Union

from core.schemas.persistence import (
    TableStep,
    StepOperation,
    CompoundPayload,
    CompoundResult,
    StepResult,
    ConditionalCheck,
)
from services.persistence.adapters.supabase_adapter import SupabaseAdapter

logger = logging.getLogger(__name__)

# Allow nested field paths: $ref:step.field.subfield
REF_PATTERN = re.compile(r"\$ref:([a-zA-Z_][a-zA-Z0-9_]*)\.([a-zA-Z_][a-zA-Z0-9_.]*)")


def _filter_known_columns(table: str, data: Any, known_columns: Optional[List[str]]) -> Any:
    """Drop unknown columns when the adapter exposes table schema."""
    if not known_columns:
        return data

    if isinstance(data, dict):
        return {k: v for k, v in data.items() if k in known_columns}
    if isinstance(data, list):
        return [_filter_known_columns(table, item, known_columns) for item in data]
    return data


def _normalized_on_conflict(on_conflict: Optional[List[str]], known_columns: Optional[List[str]]) -> Optional[List[str]]:
    if not on_conflict:
        return on_conflict
    if not known_columns:
        return on_conflict
    filtered = [c for c in on_conflict if c in known_columns]
    if filtered:
        return filtered
    # Fallback to id if available; otherwise keep original to avoid silent mismatches
    if "id" in known_columns:
        return ["id"]
    return on_conflict


def resolve_value(value: Any, outputs: Dict[str, Any]) -> Any:
    """Resolve a single value that may contain a $ref reference."""
    if not isinstance(value, str) or not value.startswith("$ref:"):
        return value

    match = REF_PATTERN.match(value)
    if not match:
        raise ValueError(f"Invalid reference format: {value}")

    step_name, field_path = match.groups()

    if step_name not in outputs:
        raise ValueError(f"Reference to unknown step '{step_name}'")

    current = outputs[step_name]
    for part in field_path.split('.'):
        if isinstance(current, dict):
            if part not in current:
                raise ValueError(f"Field '{part}' not found in step '{step_name}' output")
            current = current[part]
        elif isinstance(current, list) and part.isdigit():
            idx = int(part)
            if idx >= len(current):
                raise ValueError(f"Index {idx} out of range for list in step '{step_name}'")
            current = current[idx]
        else:
            raise ValueError(f"Cannot resolve path segment '{part}' in reference {value}")
    return current


def resolve_references(data: Any, outputs: Dict[str, Any]) -> Any:
    """Recursively resolve $ref tokens in arbitrary data structures."""
    if isinstance(data, str):
        return resolve_value(data, outputs)
    if isinstance(data, dict):
        return {k: resolve_references(v, outputs) for k, v in data.items()}
    if isinstance(data, list):
        return [resolve_references(item, outputs) for item in data]
    return data


def evaluate_condition(condition: ConditionalCheck, outputs: Dict[str, Any]) -> Tuple[bool, str]:
    """Evaluate a conditional gate for a step."""
    try:
        field_value = resolve_value(condition.field, outputs) if condition.field.startswith("$ref:") else condition.field
    except Exception as exc:
        if condition.operator == "not_exists":
            return True, ""
        return False, f"Could not resolve condition field: {exc}"

    op = condition.operator
    val = condition.value

    if op == "exists":
        return field_value is not None, "" if field_value is not None else "Field missing"
    if op == "not_exists":
        return field_value is None, "" if field_value is None else "Field present"
    if op == "equals":
        return field_value == val, "" if field_value == val else f"{field_value} != {val}"
    if op == "not_equals":
        return field_value != val, "" if field_value != val else f"{field_value} == {val}"
    if op == "gt":
        return field_value > val, "" if field_value > val else f"{field_value} <= {val}"
    if op == "gte":
        return field_value >= val, "" if field_value >= val else f"{field_value} < {val}"
    if op == "lt":
        return field_value < val, "" if field_value < val else f"{field_value} >= {val}"
    if op == "lte":
        return field_value <= val, "" if field_value <= val else f"{field_value} > {val}"
    if op == "in":
        return field_value in val, "" if field_value in val else f"{field_value} not in {val}"
    if op == "not_in":
        return field_value not in val, "" if field_value not in val else f"{field_value} in {val}"
    return False, f"Unknown operator: {op}"


def _normalize_result(result: Any) -> Any:
    if isinstance(result, list) and result:
        return result[0] if isinstance(result[0], dict) else result
    return result


def execute_step(step: TableStep, adapter: SupabaseAdapter, outputs: Dict[str, Any]) -> StepResult:
    """Execute a single step with reference resolution and optional condition."""

    # Condition check
    if step.condition:
        should_exec, skip_reason = evaluate_condition(step.condition, outputs)
        if not should_exec:
            return StepResult(
                step_name=step.step_name,
                table=step.table,
                operation=step.operation.value,
                status="skipped",
                skipped_reason=skip_reason or "Condition not met",
            )

    try:
        resolved_data = resolve_references(step.data, outputs) if step.data is not None else None
        resolved_where = resolve_references(step.where, outputs) if step.where is not None else None
        known_columns = None
        # Schema introspection is a READ and can fail under write-only/RLS JWTs.
        # Keep it opt-in for debugging/migrations.
        enable_schema_filtering = os.getenv("PERSISTENCE_ENABLE_SCHEMA_FILTERING", "0").lower() in (
            "1",
            "true",
            "yes",
        )
        if enable_schema_filtering:
            try:
                known_columns = adapter.get_columns(step.table)  # type: ignore[attr-defined]
            except Exception:
                known_columns = None

        filtered_data = _filter_known_columns(step.table, resolved_data, known_columns)

        # Surface silent drops when schema mismatch occurs so we can fix upstream payloads.
        if known_columns:
            dropped: List[str] = []
            if isinstance(resolved_data, dict):
                dropped = [k for k in resolved_data.keys() if k not in known_columns]
            elif isinstance(resolved_data, list):
                for item in resolved_data:
                    if isinstance(item, dict):
                        for k in item.keys():
                            if k not in known_columns and k not in dropped:
                                dropped.append(k)
            if dropped:
                logger.warning(
                    "Dropping unknown columns for table %s: %s",
                    step.table,
                    ",".join(sorted(dropped)),
                )

        logger.info("Executing step %s: %s on %s", step.step_name, step.operation.value, step.table)
        logger.debug("  data=%s", resolved_data)
        logger.debug("  where=%s", resolved_where)

        records_affected = 0
        output: Optional[Any] = None

        if step.operation == StepOperation.CREATE:
            if isinstance(filtered_data, list):
                output = adapter.batch_write(step.table, filtered_data)
                records_affected = len(output) if output else 0
            else:
                output = adapter.write(step.table, filtered_data or {})
                output = _normalize_result(output)
                records_affected = 1 if output else 0

        elif step.operation == StepOperation.UPDATE:
            if not resolved_where:
                raise ValueError("UPDATE requires 'where'")
            # If id provided, direct update; else query then update
            record_id = resolved_where.get("id") if isinstance(resolved_where, dict) else None
            if record_id:
                payload = filtered_data or {}
                payload = payload if isinstance(payload, dict) else {}
                payload = {**payload, "id": record_id}
                res = adapter.upsert(step.table, payload, on_conflict=["id"])
                output = _normalize_result(res)
                records_affected = 1 if output else 0
            else:
                matches = adapter.query(step.table, resolved_where, limit=1000)
                if isinstance(matches, dict):
                    matches = matches.get("data", [])
                if matches:
                    updated_ids: List[Any] = []
                    for m in matches:
                        m_id = m.get("id") if isinstance(m, dict) else None
                        if not m_id:
                            continue
                        payload = filtered_data or {}
                        payload = payload if isinstance(payload, dict) else {}
                        payload = {**payload, "id": m_id}
                        adapter.upsert(step.table, payload, on_conflict=["id"])
                        updated_ids.append(m_id)
                    records_affected = len(updated_ids)
                    output = {"updated_ids": updated_ids}

        elif step.operation == StepOperation.UPSERT:
            on_conflict = _normalized_on_conflict(step.match_on or ["id"], known_columns)
            if isinstance(filtered_data, list):
                collected = []
                for item in filtered_data:
                    res = adapter.upsert(step.table, item, on_conflict=on_conflict)
                    collected.append(_normalize_result(res))
                output = collected
                records_affected = len(collected)
            else:
                res = adapter.upsert(step.table, filtered_data or {}, on_conflict=on_conflict)
                output = _normalize_result(res)
                records_affected = 1 if output else 0

        elif step.operation == StepOperation.DELETE:
            if not resolved_where:
                raise ValueError("DELETE requires 'where'")
            record_id = resolved_where.get("id") if isinstance(resolved_where, dict) else None
            if record_id:
                adapter.delete(step.table, record_id)
                output = {"deleted_id": record_id}
                records_affected = 1
            else:
                matches = adapter.query(step.table, resolved_where, limit=1000)
                if matches:
                    for m in matches:
                        adapter.delete(step.table, m.get("id"))
                    output = {"deleted_ids": [m.get("id") for m in matches]}
                    records_affected = len(matches)

        return StepResult(
            step_name=step.step_name,
            table=step.table,
            operation=step.operation.value,
            status="success",
            records_affected=records_affected,
            output=output,
        )

    except Exception as exc:
        logger.error("Step '%s' failed: %s", step.step_name, exc)
        return StepResult(
            step_name=step.step_name,
            table=step.table,
            operation=step.operation.value,
            status="failed",
            error=str(exc),
        )


def rollback_step(result: StepResult, adapter: SupabaseAdapter) -> StepResult:
    """Rollback a successful create/upsert step by deleting created records."""
    if result.status != "success":
        return result
    if result.operation not in ("create", "upsert"):
        return StepResult(
            step_name=result.step_name,
            table=result.table,
            operation="rollback",
            status="skipped",
            skipped_reason="Rollback unsupported for this operation",
        )

    try:
        output = result.output
        if isinstance(output, list):
            for item in output:
                if isinstance(item, dict) and item.get("id"):
                    adapter.delete(result.table, item["id"])
        elif isinstance(output, dict) and output.get("id"):
            adapter.delete(result.table, output["id"])
        return StepResult(
            step_name=result.step_name,
            table=result.table,
            operation="rollback",
            status="success",
            records_affected=result.records_affected,
        )
    except Exception as exc:
        return StepResult(
            step_name=result.step_name,
            table=result.table,
            operation="rollback",
            status="failed",
            error=str(exc),
        )


def execute_compound(payload: CompoundPayload, adapter: SupabaseAdapter) -> CompoundResult:
    """Execute an ordered compound operation with conditions and rollback."""

    txid = payload.transaction_id or str(uuid.uuid4())[:8]
    outputs: Dict[str, Any] = {}
    step_results: List[StepResult] = []
    completed = 0
    skipped = 0

    logger.info("[%s] Compound start: %s steps", txid, len(payload.steps))

    for idx, step in enumerate(payload.steps):
        logger.info("[%s] Step %s/%s: %s", txid, idx + 1, len(payload.steps), step.step_name)

        result = execute_step(step, adapter, outputs)
        step_results.append(result)

        if result.status == "success":
            completed += 1
            if result.output is not None:
                outputs[step.step_name] = result.output

        elif result.status == "skipped":
            skipped += 1
            if not payload.continue_on_skip:
                break

        elif result.status == "failed":
            if step.on_error == "fail":
                # rollback if required
                rollback_results: List[StepResult] = []
                if payload.rollback_on_failure:
                    for prior in reversed(step_results[:-1]):
                        rb = rollback_step(prior, adapter)
                        rollback_results.append(rb)

                return CompoundResult(
                    success=False,
                    transaction_id=txid,
                    total_steps=len(payload.steps),
                    completed_steps=completed,
                    skipped_steps=skipped,
                    failed_step=step.step_name,
                    error=result.error,
                    step_results=step_results,
                    outputs=outputs,
                    rollback_performed=payload.rollback_on_failure,
                    rollback_results=rollback_results,
                )
            elif step.on_error in ("skip", "warn"):
                skipped += 1
                if step.on_error == "warn":
                    logger.warning("[%s] Step %s failed (warn): %s", txid, step.step_name, result.error)
                continue

    logger.info("[%s] Compound completed: %s success, %s skipped", txid, completed, skipped)

    return CompoundResult(
        success=True,
        transaction_id=txid,
        total_steps=len(payload.steps),
        completed_steps=completed,
        skipped_steps=skipped,
        step_results=step_results,
        outputs=outputs,
    )


# Convenience builder for inbound email flows
def build_inbound_email_compound(
    email_event: Dict[str, Any],
    lead_data: Optional[Dict[str, Any]] = None,
    cleanup_staging: bool = False,
) -> CompoundPayload:
    lead_data = lead_data or {}
    sender_email = email_event.get("from", "")

    steps: List[TableStep] = [
        TableStep(
            step_name="lead",
            table="leads",
            operation=StepOperation.UPSERT,
            data={"email": sender_email, **lead_data},
            match_on=["email"],
        ),
        TableStep(
            step_name="conversation",
            table="conversations",
            operation=StepOperation.UPSERT,
            data={
                "lead_id": "$ref:lead.id",
                "thread_id": email_event.get("thread_id"),
                "subject": email_event.get("subject", ""),
                "channel": "email",
                "metadata": {},
            },
            match_on=["lead_id", "thread_id"] if email_event.get("thread_id") else ["lead_id", "subject"],
        ),
        TableStep(
            step_name="message",
            table="messages",
            operation=StepOperation.CREATE,
            data={
                "conversation_id": "$ref:conversation.id",
                "direction": "inbound",
                "content": email_event.get("body", ""),
                "message_id": email_event.get("message_id"),
                "metadata": email_event.get("metadata", {}),
            },
        ),
        TableStep(
            step_name="update_stage",
            table="leads",
            operation=StepOperation.UPDATE,
            where={"id": "$ref:lead.id"},
            data={"stage": "engaged"},
            on_error="warn",
        ),
    ]

    if cleanup_staging and sender_email:
        steps.append(
            TableStep(
                step_name="cleanup_staging",
                table="staging_leads",
                operation=StepOperation.DELETE,
                where={"email": sender_email},
                on_error="skip",
            )
        )

    return CompoundPayload(steps=steps)


def build_lead_lifecycle_compound(
    lead_id: str,
    new_stage: str,
    note: Optional[str] = None,
    archive_if_closed: bool = True,
) -> CompoundPayload:
    steps: List[TableStep] = [
        TableStep(
            step_name="update_lead",
            table="leads",
            operation=StepOperation.UPDATE,
            where={"id": lead_id},
            data={"stage": new_stage},
        ),
    ]

    if note:
        steps.append(
            TableStep(
                step_name="add_note",
                table="messages",
                operation=StepOperation.CREATE,
                data={
                    "lead_id": lead_id,
                    "direction": "system",
                    "content": note,
                    "metadata": {"type": "stage_change_note"},
                },
                on_error="warn",
            )
        )

    if archive_if_closed and new_stage in ("closed_won", "closed_lost", "archived"):
        steps.append(
            TableStep(
                step_name="archive",
                table="leads",
                operation=StepOperation.UPDATE,
                where={"id": lead_id},
                data={"archived_at": "NOW()"},
                condition=ConditionalCheck(
                    field="$ref:update_lead.stage",
                    operator="in",
                    value=["closed_won", "closed_lost", "archived"],
                ),
            )
        )

    return CompoundPayload(steps=steps)