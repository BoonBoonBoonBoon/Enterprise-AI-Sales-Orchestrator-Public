import os
import json
import contextvars
from pathlib import Path
import time
import pytest  # noqa

# --- .env loader -----------------------------------------------------------

def _load_env_file(filename: str = '.env'):
    """Lightweight .env loader (no external dependency)."""
    root = Path(__file__).resolve().parent.parent
    env_path = root / filename
    if not env_path.exists():
        return
    try:
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            k, v = line.split('=', 1)
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            if k and k not in os.environ:
                os.environ[k] = v
    except Exception:
        pass

_load_env_file()

# Provide a simple marker skip for live network calls if user explicitly disables them.
LIVE_NETWORK_DISABLED = os.environ.get('DISABLE_LIVE_INTEGRATION') in ('1', 'true', 'TRUE')

def pytest_runtest_setup(item):
    if LIVE_NETWORK_DISABLED and 'live_integration' in item.keywords:
        pytest.skip('Live integration tests disabled by DISABLE_LIVE_INTEGRATION env flag')

# --- CLI options to control RAG debug/capture ------------------------------

def pytest_addoption(parser):  # noqa
    parser.addoption(
        "--rag-verbose",
        action="store_true",
        default=False,
        help="Print RAG input/output during tests (disables silent behavior when combined with -s)",
    )
    parser.addoption(
        "--rag-capture-tools",
        action="store_true",
        default=False,
        help="Capture and summarize RAG tool calls (query_leads_tool) in final summary",
    )
    parser.addoption(
        "--rag-print-records",
        action="store_true",
        default=False,
        help="Print a preview of returned records for each RAGAgent.run when return_json=True",
    )
    parser.addoption(
        "--rag-records-n",
        action="store",
        default=None,
        help="How many records to preview when printing (default 3, or env RAG_PRINT_RECORDS_N)",
    )
    parser.addoption(
        "--rag-record-fields",
        action="store",
        default=None,
        help="Comma-separated field names to print (default: email,company_name,id; or env RAG_RECORD_FIELDS)",
    )
    parser.addoption(
        "--rag-deep-debug",
        action="store_true",
        default=False,
        help="Enable deep step-by-step tracing (RAG_DEEP_DEBUG=1) across agent and persistence",
    )
    parser.addoption(
        "--rag-print-records-full",
        action="store_true",
        default=False,
        help="Print full JSON rows for record previews (overrides selected fields)",
    )

# --- RAG run capture / summary ---------------------------------------------

_current_test = contextvars.ContextVar('rag_current_test', default=None)
_captured_runs: list[dict] = []  # every run (intermediate + final)
_captured_tools: list[dict] = []  # tool-level IO traces (input filters + envelope)

# Config via env
RAG_SUMMARY_JSON = os.environ.get('RAG_SUMMARY_JSON', 'rag_summary.json')
RAG_SUMMARY_DISABLE_FILE = os.environ.get('RAG_SUMMARY_DISABLE_FILE') in ('1','true','TRUE')
RAG_SUMMARY_COLOR = os.environ.get('RAG_SUMMARY_COLOR', '1') not in ('0','false','FALSE')
RAG_SUMMARY_SHOW_INTERMEDIATE = os.environ.get('RAG_SUMMARY_INTERMEDIATE', '1') not in ('0','false','FALSE')
RAG_SUMMARY_INCLUDE_RECORDS = os.environ.get('RAG_SUMMARY_INCLUDE_RECORDS', '1') in ('1','true','TRUE')
RAG_SUMMARY_RECORDS_N = int(os.environ.get('RAG_SUMMARY_RECORDS_N', os.environ.get('RAG_PRINT_RECORDS_N') or 3))
RAG_SUMMARY_FULL_ROWS = os.environ.get('RAG_SUMMARY_FULL_ROWS', os.environ.get('RAG_PRINT_RECORDS_FULL') or '0') in ('1','true','TRUE')
RAG_SUMMARY_RECORD_FIELDS = [f.strip() for f in (os.environ.get('RAG_SUMMARY_RECORD_FIELDS') or os.environ.get('RAG_RECORD_FIELDS') or 'email,company_name,id').split(',') if f.strip()]

def _color(code: str, text: str) -> str:
    if not RAG_SUMMARY_COLOR:
        return text
    return f"\033[{code}m{text}\033[0m"

def _fmt_fallback(fb):
    if fb == 'agent':
        return _color('35', str(fb))  # magenta
    if fb == 'reformulation':
        return _color('34', str(fb))  # blue
    if fb == 'suppressed':
        return _color('33', str(fb))  # yellow
    if fb:
        return _color('36', str(fb))
    return _color('32', 'none')  # green

def _extract_ident(filters: dict | None) -> str | None:
    if not isinstance(filters, dict):
        return None
    if 'id' in filters:
        return f"id={filters.get('id')}"
    if 'email' in filters:
        return f"email={filters.get('email')}"
    if 'company_name' in filters:
        return f"company={filters.get('company_name')}"
    if 'company' in filters:
        return f"company={filters.get('company')}"
    return None

def _preview_rows(rows: list[dict] | None, n: int, full: bool, fields: list[str]) -> list:
    if not rows:
        return []
    out = []
    for row in rows[: max(0, n)]:
        if not isinstance(row, dict):
            out.append(row)
            continue
        if full:
            out.append(dict(row))
        else:
            sel = {}
            for f in fields:
                if f in row:
                    sel[f] = row.get(f)
            out.append(sel or dict(row))
    return out

@pytest.fixture(autouse=True)
def _rag_test_context(request, monkeypatch):
    """Autouse fixture to capture RAGAgent.run JSON envelopes for summary.

    We monkeypatch RAGAgent.run once (first use) to wrap and collect the final envelope
    whenever return_json=True. Multiple invocations in one test all get recorded.
    """
    token = _current_test.set(request.node.nodeid)
    cfg = request.config
    rag_verbose = bool(cfg.getoption("--rag-verbose"))
    rag_capture_tools = bool(cfg.getoption("--rag-capture-tools")) or os.environ.get('RAG_CAPTURE_TOOLS') in ('1','true','TRUE')
    rag_print_records = bool(cfg.getoption("--rag-print-records")) or os.environ.get('RAG_PRINT_RECORDS') in ('1','true','TRUE')
    rag_print_records_full = bool(cfg.getoption("--rag-print-records-full")) or os.environ.get('RAG_PRINT_RECORDS_FULL') in ('1','true','TRUE')
    rag_deep_debug = bool(cfg.getoption("--rag-deep-debug")) or os.environ.get('RAG_DEEP_DEBUG') in ('1','true','TRUE')
    try:
        _n_opt = cfg.getoption("--rag-records-n")
    except Exception:
        _n_opt = None
    try:
        _fields_opt = cfg.getoption("--rag-record-fields")
    except Exception:
        _fields_opt = None
    preview_n = int((_n_opt or os.environ.get('RAG_PRINT_RECORDS_N') or 3))
    fields_raw = (_fields_opt or os.environ.get('RAG_RECORD_FIELDS') or 'email,company_name,id')
    record_fields = [f.strip() for f in fields_raw.split(',') if f.strip()]

    # Propagate env toggles for in-agent color logs when requested
    if rag_verbose:
        os.environ.setdefault('RAG_DEBUG_IO', '1')
    # Propagate capture intent for any early session-level patches
    if rag_capture_tools:
        os.environ.setdefault('RAG_CAPTURE_TOOLS', '1')
    if rag_deep_debug:
        os.environ.setdefault('RAG_DEEP_DEBUG', '1')
    # Only patch once per session
    from agent.operational_agents.rag_agent import rag_agent as rag_module
    RAGAgent = getattr(rag_module, 'RAGAgent')

    if not getattr(RAGAgent, '_rag_run_patched', False):
        original_run = RAGAgent.run

        def wrapped(self, *a, **k):  # type: ignore
            started = time.time()
            result = original_run(self, *a, **k)
            elapsed_ms = (time.time() - started) * 1000.0
            try:
                if isinstance(result, dict) and 'metadata' in result and 'records' in result:
                    total = result['metadata'].get('total_count')
                    status = 'success' if isinstance(total, int) and total > 0 else 'fail'
                    filters_meta = result['metadata'].get('query_filters')
                    ident_detail = _extract_ident(filters_meta)
                    records_preview = _preview_rows(result.get('records'), RAG_SUMMARY_RECORDS_N, RAG_SUMMARY_FULL_ROWS, RAG_SUMMARY_RECORD_FIELDS) if RAG_SUMMARY_INCLUDE_RECORDS else []
                    agent_preview = None
                    if status == 'fail':
                        # try to surface agent response preview if any
                        try:
                            for r in (result.get('records') or []):
                                if isinstance(r, dict) and 'response' in r:
                                    agent_preview = str(r.get('response'))[:400]
                                    break
                        except Exception:
                            pass
                    rec = {
                        'test': _current_test.get(),
                        't_ms': round(elapsed_ms, 2),
                        'total_count': total,
                        'fallback': result['metadata'].get('fallback'),
                        'truncated': result['metadata'].get('truncated'),
                        'summary_present': 'summary' in result['metadata'],
                        'filters': filters_meta,
                        'attempts': result['metadata'].get('reformulation_attempts'),
                        'kind': 'run',
                        'status': status,
                        'ident': ident_detail,
                        'records_preview': records_preview,
                        'agent_response_preview': agent_preview,
                    }
                    _captured_runs.append(rec)
                    if RAG_SUMMARY_SHOW_INTERMEDIATE:
                        print(_color('90', f"[RAG RUN] {rec['test']} count={rec['total_count']} fb={rec['fallback']} ms={rec['t_ms']} filters={rec['filters']}"))
                        # Colorized identification failure when zero results
                        if rag_verbose and (rec['total_count'] in (0, None)):
                            f = rec.get('filters') or {}
                            ident = None
                            if isinstance(f, dict):
                                if 'id' in f:
                                    ident = f"id={f.get('id')}"
                                elif 'email' in f:
                                    ident = f"email={f.get('email')}"
                                elif 'company_name' in f:
                                    ident = f"company={f.get('company_name')}"
                                elif 'company' in f:
                                    ident = f"company={f.get('company')}"
                            detail = ident or (f"filters={f}" if f else "no filters")
                            print(_color('31', f"[IDENT FAIL] failed identification ({detail})"))
                        # Colorized identification success marker when rows found
                        if rag_verbose and isinstance(rec.get('total_count'), int) and rec['total_count'] > 0:
                            f = rec.get('filters') or {}
                            ident = None
                            if isinstance(f, dict):
                                if 'id' in f:
                                    ident = f"id={f.get('id')}"
                                elif 'email' in f:
                                    ident = f"email={f.get('email')}"
                                elif 'company_name' in f:
                                    ident = f"company={f.get('company_name')}"
                                elif 'company' in f:
                                    ident = f"company={f.get('company')}"
                            detail = ident or (f"filters={f}" if f else "no filters")
                            print(_color('32', f"[IDENT OK] identification succeeded ({detail}); rows={rec['total_count']}"))
                    # Optional record preview for quick visual of outputs
                    if rag_print_records and rag_verbose:
                        try:
                            rows = result.get('records') or []
                            for i, row in enumerate(rows[:preview_n]):
                                if rag_print_records_full:
                                    try:
                                        import json as _json
                                        txt = _json.dumps(row, default=str)
                                    except Exception:
                                        txt = str(row)
                                    if len(txt) > 8000:
                                        txt = txt[:8000] + '...<truncated>'
                                    print(_color('92', f"[RAG OUT FULL {i+1}] {txt}"))
                                else:
                                    pieces = []
                                    for f in record_fields:
                                        if f in row:
                                            pieces.append(f"{f}={row.get(f)}")
                                    print(_color('92', f"[RAG OUT {i+1}] " + (', '.join(pieces) if pieces else str(row)[:200])))
                        except Exception:
                            pass
            except Exception:  # pragma: no cover - defensive
                pass
            return result

        monkeypatch.setattr(RAGAgent, 'run', wrapped, raising=True)
        setattr(RAGAgent, '_rag_run_patched', True)

    # Optionally patch query_leads_tool to capture inputs/outputs (if not already session-patched)
    if rag_capture_tools and (not getattr(RAGAgent, '_rag_tools_patched', False)) and (not getattr(RAGAgent, '_rag_tools_patched_early', False)):
        try:
            original_tool = RAGAgent.query_leads_tool
        except Exception:
            original_tool = None

        if original_tool is not None:
            def tool_wrapped(self, args):  # type: ignore
                started = time.time()
                filters = None
                try:
                    if isinstance(args, dict) and isinstance(args.get('filters'), dict):
                        filters = dict(args.get('filters'))
                except Exception:
                    filters = None
                res = original_tool(self, args)
                elapsed_ms = (time.time() - started) * 1000.0
                try:
                    if isinstance(res, dict) and 'metadata' in res and 'records' in res:
                        total = res['metadata'].get('total_count')
                        status = 'success' if isinstance(total, int) and total > 0 else 'fail'
                        filters_meta = res['metadata'].get('query_filters') or filters
                        ident_detail = _extract_ident(filters_meta)
                        records_preview = _preview_rows(res.get('records'), RAG_SUMMARY_RECORDS_N, RAG_SUMMARY_FULL_ROWS, RAG_SUMMARY_RECORD_FIELDS) if RAG_SUMMARY_INCLUDE_RECORDS else []
                        rec = {
                            'test': _current_test.get(),
                            't_ms': round(elapsed_ms, 2),
                            'total_count': total,
                            'filters': filters_meta,
                            'kind': 'tool.query_leads',
                            'status': status,
                            'ident': ident_detail,
                            'records_preview': records_preview,
                        }
                        _captured_tools.append(rec)
                        if rag_verbose:
                            print(_color('36', f"[RAG TOOL SEND] filters={filters}"))
                            print(_color('32', f"[RAG TOOL RECV] count={rec['total_count']}"))
                            if rec['total_count'] in (0, None):
                                f2 = rec.get('filters') or filters or {}
                                ident = None
                                if isinstance(f2, dict):
                                    if 'id' in f2:
                                        ident = f"id={f2.get('id')}"
                                    elif 'email' in f2:
                                        ident = f"email={f2.get('email')}"
                                    elif 'company_name' in f2:
                                        ident = f"company={f2.get('company_name')}"
                                    elif 'company' in f2:
                                        ident = f"company={f2.get('company')}"
                                detail = ident or (f"filters={f2}" if f2 else "no filters")
                                print(_color('31', f"[IDENT FAIL] failed identification ({detail})"))
                            else:
                                # Success marker for tool path
                                f2 = rec.get('filters') or filters or {}
                                ident = None
                                if isinstance(f2, dict):
                                    if 'id' in f2:
                                        ident = f"id={f2.get('id')}"
                                    elif 'email' in f2:
                                        ident = f"email={f2.get('email')}"
                                    elif 'company_name' in f2:
                                        ident = f"company={f2.get('company_name')}"
                                    elif 'company' in f2:
                                        ident = f"company={f2.get('company')}"
                                detail = ident or (f"filters={f2}" if f2 else "no filters")
                                print(_color('32', f"[IDENT OK] identification succeeded ({detail}); rows={rec['total_count']}"))
                            if rag_print_records:
                                try:
                                    rows = res.get('records') or []
                                    for i, row in enumerate(rows[:preview_n]):
                                        if rag_print_records_full:
                                            try:
                                                import json as _json
                                                txt = _json.dumps(row, default=str)
                                            except Exception:
                                                txt = str(row)
                                            if len(txt) > 8000:
                                                txt = txt[:8000] + '...<truncated>'
                                            print(_color('92', f"[RAG TOOL OUT FULL {i+1}] {txt}"))
                                        else:
                                            pieces = []
                                            for f in record_fields:
                                                if f in row:
                                                    pieces.append(f"{f}={row.get(f)}")
                                            print(_color('92', f"[RAG TOOL OUT {i+1}] " + (', '.join(pieces) if pieces else str(row)[:200])))
                                except Exception:
                                    pass
                except Exception:  # pragma: no cover
                    pass
                return res

            monkeypatch.setattr(RAGAgent, 'query_leads_tool', tool_wrapped, raising=True)
            setattr(RAGAgent, '_rag_tools_patched', True)

    yield
    _current_test.reset(token)

@pytest.fixture(autouse=True, scope='session')
def _rag_patch_tools_early():
    """Patch the RAGAgent.query_leads_tool once at session start.

    This ensures tool-level I/O capture is active even if agent instances are
    constructed in class-scoped fixtures before per-test fixtures run.
    Printing respects env toggles RAG_DEBUG_IO and RAG_CAPTURE_TOOLS.
    """
    try:
        from agent.operational_agents.rag_agent import rag_agent as rag_module
        RAGAgent = getattr(rag_module, 'RAGAgent')
    except Exception:
        return

    if getattr(RAGAgent, '_rag_tools_patched_early', False):
        return

    original_tool = getattr(RAGAgent, 'query_leads_tool', None)
    if original_tool is None:
        return

    def tool_wrapped(self, args):  # type: ignore
        started = time.time()
        filters = None
        try:
            if isinstance(args, dict) and isinstance(args.get('filters'), dict):
                filters = dict(args.get('filters'))
        except Exception:
            filters = None
        res = original_tool(self, args)
        elapsed_ms = (time.time() - started) * 1000.0
        try:
            if isinstance(res, dict) and 'metadata' in res and 'records' in res:
                total = res['metadata'].get('total_count')
                status = 'success' if isinstance(total, int) and total > 0 else 'fail'
                filters_meta = res['metadata'].get('query_filters') or filters
                ident_detail = _extract_ident(filters_meta)
                records_preview = _preview_rows(res.get('records'), RAG_SUMMARY_RECORDS_N, RAG_SUMMARY_FULL_ROWS, RAG_SUMMARY_RECORD_FIELDS) if RAG_SUMMARY_INCLUDE_RECORDS else []
                rec = {
                    'test': _current_test.get(),
                    't_ms': round(elapsed_ms, 2),
                    'total_count': total,
                    'filters': filters_meta,
                    'kind': 'tool.query_leads',
                    'status': status,
                    'ident': ident_detail,
                    'records_preview': records_preview,
                }
                _captured_tools.append(rec)
                # Print only when tool capture requested and debug IO enabled
                if os.environ.get('RAG_CAPTURE_TOOLS') in ('1','true','TRUE') and os.environ.get('RAG_DEBUG_IO') in ('1','true','TRUE'):
                    print(_color('36', f"[RAG TOOL SEND] filters={filters}"))
                    print(_color('32', f"[RAG TOOL RECV] count={rec['total_count']}"))
                    if rec['total_count'] in (0, None):
                        f2 = rec.get('filters') or filters or {}
                        ident = None
                        if isinstance(f2, dict):
                            if 'id' in f2:
                                ident = f"id={f2.get('id')}"
                            elif 'email' in f2:
                                ident = f"email={f2.get('email')}"
                            elif 'company_name' in f2:
                                ident = f"company={f2.get('company_name')}"
                            elif 'company' in f2:
                                ident = f"company={f2.get('company')}"
                        detail = ident or (f"filters={f2}" if f2 else "no filters")
                        print(_color('31', f"[IDENT FAIL] failed identification ({detail})"))
                    else:
                        # Success marker for tool path (early patch variant)
                        f2 = rec.get('filters') or filters or {}
                        ident = None
                        if isinstance(f2, dict):
                            if 'id' in f2:
                                ident = f"id={f2.get('id')}"
                            elif 'email' in f2:
                                ident = f"email={f2.get('email')}"
                            elif 'company_name' in f2:
                                ident = f"company={f2.get('company_name')}"
                            elif 'company' in f2:
                                ident = f"company={f2.get('company')}"
                        detail = ident or (f"filters={f2}" if f2 else "no filters")
                        print(_color('32', f"[IDENT OK] identification succeeded ({detail}); rows={rec['total_count']}"))
                    if os.environ.get('RAG_PRINT_RECORDS') in ('1','true','TRUE'):
                        try:
                            rows = res.get('records') or []
                            n = int(os.environ.get('RAG_PRINT_RECORDS_N') or 3)
                            full = os.environ.get('RAG_PRINT_RECORDS_FULL') in ('1','true','TRUE')
                            fields = [f.strip() for f in (os.environ.get('RAG_RECORD_FIELDS') or 'email,company_name,id').split(',') if f.strip()]
                            for i, row in enumerate(rows[:n]):
                                if full:
                                    try:
                                        import json as _json
                                        txt = _json.dumps(row, default=str)
                                    except Exception:
                                        txt = str(row)
                                    if len(txt) > 8000:
                                        txt = txt[:8000] + '...<truncated>'
                                    print(_color('92', f"[RAG TOOL OUT FULL {i+1}] {txt}"))
                                else:
                                    pieces = []
                                    for f in fields:
                                        if f in row:
                                            pieces.append(f"{f}={row.get(f)}")
                                    print(_color('92', f"[RAG TOOL OUT {i+1}] " + (', '.join(pieces) if pieces else str(row)[:200])))
                        except Exception:
                            pass
        except Exception:  # pragma: no cover
            pass
        return res

    setattr(RAGAgent, 'query_leads_tool', tool_wrapped)
    setattr(RAGAgent, '_rag_tools_patched_early', True)
    # Also mark as patched for per-test logic to avoid double wrapping
    setattr(RAGAgent, '_rag_tools_patched', True)

def pytest_sessionfinish(session, exitstatus):  # noqa
    if not _captured_runs and not _captured_tools:
        print(_color('31', '\n[RAG SUMMARY] No RAGAgent JSON runs or tool calls captured.'))
        return
    # Aggregate last snapshot per test
    latest_by_test = {}
    for rec in _captured_runs:
        latest_by_test[rec['test']] = rec
    latest_tools_by_test = {}
    for rec in _captured_tools:
        latest_tools_by_test[rec['test']] = rec
    # Build textual lines
    print(_color('36', '\n[RAG SUMMARY] Final snapshot per test:'))
    for test, rec in sorted(latest_by_test.items()):
        fb = _fmt_fallback(rec['fallback'])
        trunc = _color('33', 'trunc') if rec['truncated'] else ''
        summ = _color('35', 'summary') if rec['summary_present'] else ''
        status = rec.get('status') or ('success' if (isinstance(rec.get('total_count'), int) and rec['total_count'] > 0) else 'fail')
        status_col = _color('32', 'success') if status == 'success' else _color('31', 'fail')
        print(f"{_color('37', '[RAG]')} {test} count={rec['total_count']} fb={fb} ms={rec['t_ms']} {trunc} {summ} status={status_col} ident={rec.get('ident')} filters={rec['filters']}")
    if latest_tools_by_test:
        print(_color('36', '\n[RAG SUMMARY] Final tool snapshot per test:'))
        for test, rec in sorted(latest_tools_by_test.items()):
            status = rec.get('status') or ('success' if (isinstance(rec.get('total_count'), int) and rec['total_count'] > 0) else 'fail')
            status_col = _color('32', 'success') if status == 'success' else _color('31', 'fail')
            print(f"{_color('37', '[RAG TOOL]')} {test} count={rec['total_count']} ms={rec['t_ms']} status={status_col} ident={rec.get('ident')} filters={rec['filters']}")
    print(_color('36', f"[RAG SUMMARY] Total tests with captured runs: {len(latest_by_test)} (intermediate runs: {len(_captured_runs)})"))
    if latest_tools_by_test:
        print(_color('36', f"[RAG SUMMARY] Total tests with captured tools: {len(latest_tools_by_test)} (tool calls: {len(_captured_tools)})"))

    if not RAG_SUMMARY_DISABLE_FILE:
        try:
            payload = {
                'tests_final': latest_by_test,
                'all_runs': _captured_runs,
                'tools_final': latest_tools_by_test,
                'all_tools': _captured_tools,
                'generated_at': time.time(),
            }
            with open(RAG_SUMMARY_JSON, 'w', encoding='utf-8') as f:
                json.dump(payload, f, indent=2, default=str)
            print(_color('32', f"[RAG SUMMARY] JSON written to {RAG_SUMMARY_JSON}"))
        except Exception as e:  # pragma: no cover
            print(_color('31', f"[RAG SUMMARY] Failed to write summary file: {e}"))
