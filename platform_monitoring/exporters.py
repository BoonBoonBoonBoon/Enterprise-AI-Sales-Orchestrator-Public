from typing import Dict, Any, Union
import logging
import re

_SECRET_KEY_RE = re.compile(r"(?i)(key|token|secret|authorization|apikey|api_key|password|passwd|bearer)")
_SECRET_VAL_RE = re.compile(r"(?i)^(?:sk|ghp|hf|xox|ya29|eyJ|pk_|rk_)[A-Za-z0-9\-\._]{8,}$")


def _mask_value(v: Any) -> Any:
    try:
        if isinstance(v, str):
            # mask long token-like strings
            if _SECRET_VAL_RE.search(v.strip()):
                return "***REDACTED***"
            # redact bearer tokens in headers-like strings
            if v.lower().startswith("bearer "):
                return "Bearer ***REDACTED***"
        return v
    except Exception:
        return v


def _sanitize(obj: Any) -> Any:
    try:
        if isinstance(obj, dict):
            out: Dict[str, Any] = {}
            for k, v in obj.items():
                if _SECRET_KEY_RE.search(str(k)):
                    out[k] = "***REDACTED***"
                else:
                    out[k] = _sanitize(v)
            return out
        if isinstance(obj, list):
            return [_sanitize(x) for x in obj]
        return _mask_value(obj)
    except Exception:
        return obj

logger = logging.getLogger('platform_monitoring')


def log_event(event: Union[str, Dict[str, Any]], payload: Dict[str, Any] | None = None):
    """Log a monitoring event to the central logger.

    Flexible signature supports:
      - log_event({'event': 'name', ...}) (legacy)
      - log_event('name', {...}) (preferred)
    """
    if isinstance(event, str):
        record = {'event': event, **(payload or {})}
    else:
        record = event
    logger.info('MONITOR_EVENT %s', _sanitize(record))


def prometheus_metric(name: str, value: float, labels: Dict[str, str] | None = None):
    # placeholder for prometheus client integration
    logger.info('PROM_METRIC %s=%s labels=%s', name, value, labels)
