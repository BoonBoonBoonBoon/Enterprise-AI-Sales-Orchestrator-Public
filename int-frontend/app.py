import streamlit as st
import redis
import json
import uuid
import pandas as pd
import os
import time
import logging
import random
from datetime import datetime
from typing import Dict, Any, Tuple, Optional
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Template directory (file-based templates)
TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"

# Page Config
st.set_page_config(
    page_title="Agentic System - Internal Admin",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for professional styling
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 30px;
        border-radius: 10px;
        margin-bottom: 30px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .info-box {
        background-color: #e3f2fd;
        padding: 15px;
        border-left: 4px solid #2196f3;
        border-radius: 5px;
        margin: 10px 0;
    }
    .success-box {
        background-color: #d4edda;
        padding: 15px;
        border-left: 4px solid #28a745;
        border-radius: 5px;
        margin: 10px 0;
    }
    .error-box {
        background-color: #f8d7da;
        padding: 15px;
        border-left: 4px solid #dc3545;
        border-radius: 5px;
        margin: 10px 0;
    }
    .warning-box {
        background-color: #fff3cd;
        padding: 15px;
        border-left: 4px solid #ffc107;
        border-radius: 5px;
        margin: 10px 0;
    }
    .metric-card {
        background: white;
        padding: 20px;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .stButton>button {
        width: 100%;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        padding: 12px;
        border-radius: 6px;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

# Sidebar Configuration
st.sidebar.title("⚙️ System Configuration")
redis_url = st.sidebar.text_input(
    "Redis URL (optional)",
    value=os.getenv("REDIS_URL", ""),
    help="If set, the app connects via this URL (e.g. redis://localhost:6379/0). Overrides host/port.",
)
redis_host = st.sidebar.text_input("Redis Host", value=os.getenv("REDIS_HOST", "redis"))
redis_port = st.sidebar.number_input("Redis Port", value=int(os.getenv("REDIS_PORT", 6379)))
tenant_id = st.sidebar.text_input("Tenant ID", value=os.getenv("TENANT_ID", "agentic-dev"))

st.sidebar.divider()
# Debug Mode
debug_mode = st.sidebar.checkbox("🐛 Debug Mode", value=False)
show_raw_json = st.sidebar.checkbox("Show Raw JSON", value=False)

# Redis Connection
@st.cache_resource
def get_redis_client(redis_url: str, host: str, port: int) -> Optional[redis.Redis]:
    try:
        redis_url = (redis_url or "").strip()
        if redis_url:
            client = redis.Redis.from_url(redis_url, decode_responses=True)
        else:
            client = redis.Redis(host=host, port=port, decode_responses=True)
        client.ping()
        return client
    except Exception as e:
        return None

r = get_redis_client(redis_url, redis_host, int(redis_port))

# Mock Data Templates for Real-World Scenarios
MOCK_TEMPLATES = {
    "Lead Prospecting (Email)": {
        "goal": "Find 50 qualified B2B SaaS leads in San Francisco with annual revenue 1-50M",
        "context": {
            "source": "email_campaign",
            "campaign_id": f"camp_{datetime.now().year}_q4_saas",
            "filters": {
                "industry": ["SaaS", "Software Development"],
                "location": "San Francisco, CA",
                "revenue_min": 1000000,
                "revenue_max": 50000000,
                "employee_count": [50, 500]
            },
            "priority": "high",
            "enrichment_required": ["email", "phone", "linkedin_url", "tech_stack"]
        }
    },
    "CRM Contact Enrichment": {
        "goal": "Enrich 200 existing CRM contacts with missing email and phone data",
        "context": {
            "source": "crm_sync",
            "crm_system": "salesforce",
            "batch_id": f"batch_contacts_{random.randint(1000, 9999)}",
            "contacts_count": 200,
            "enrichment_fields": ["email", "phone", "company_website", "job_title"],
            "data_quality_threshold": 0.9
        }
    },
    "Outreach Campaign": {
        "goal": "Generate personalized outreach copy for 100 decision-makers",
        "context": {
            "source": "outreach_automation",
            "campaign_name": f"Q4 {datetime.now().year} Enterprise Push",
            "audience_segment": "VP Sales & Chief Revenue Officers",
            "company_size": "enterprise",
            "tone": "professional_consultative",
            "max_length": 150,
            "personalization_level": "high"
        }
    },
    "Market Research": {
        "goal": "Research competitive landscape for AI/ML vendors in financial services",
        "context": {
            "source": "market_research",
            "topic": "AI/ML solutions",
            "vertical": "financial_services",
            "competitors": ["DataRobot", "H2O.ai", "Scale AI"],
            "research_depth": "comprehensive",
            "include_pricing": True,
            "include_customer_reviews": True
        }
    },
    "Data Scraping Job": {
        "goal": "Scrape company contact information from 500 target websites",
        "context": {
            "source": "web_scraping",
            "target_count": 500,
            "data_points": ["company_name", "email", "phone", "address"],
            "compliance": "gdpr_compliant",
            "rate_limit": "10_requests_per_second"
        }
    },
    "Lead Scoring": {
        "goal": "Score 1000 leads based on engagement and firmographic data",
        "context": {
            "source": "lead_scoring_engine",
            "scoring_model": "ml_propensity_v2",
            "factors": ["email_opens", "website_visits", "company_size", "industry_fit"],
            "output_format": "csv_with_scores"
        }
    }
}

def generate_random_mock():
    """Generate a random realistic task"""
    cities = ["San Francisco", "New York", "Austin", "Seattle", "Boston", "Denver"]
    industries = ["SaaS", "FinTech", "HealthTech", "E-commerce", "AI/ML", "Cybersecurity"]
    counts = [25, 50, 100, 150, 200]
    
    template_choice = random.randint(1, 3)
    
    if template_choice == 1:
        return {
            "goal": f"Find {random.choice(counts)} qualified {random.choice(industries)} leads in {random.choice(cities)}",
            "context": {
                "source": "automated_prospecting",
                "industry": random.choice(industries),
                "location": random.choice(cities),
                "min_employees": random.choice([10, 50, 100]),
                "max_employees": random.choice([500, 1000, 5000]),
                "enrichment": True
            }
        }
    elif template_choice == 2:
        return {
            "goal": f"Enrich {random.choice(counts)} CRM contacts with missing data",
            "context": {
                "source": "crm_enrichment",
                "batch_id": f"auto_batch_{random.randint(10000, 99999)}",
                "fields_needed": random.sample(["email", "phone", "linkedin", "title", "company"], 3)
            }
        }
    else:
        return {
            "goal": f"Generate {random.choice([50, 100, 200])} personalized emails for outreach",
            "context": {
                "source": "copywriting_automation",
                "tone": random.choice(["professional", "casual", "consultative"]),
                "target_role": random.choice(["VP Sales", "CMO", "CTO", "CEO"]),
                "personalization": "high"
            }
        }
    
def load_file_templates(template_dir: Path) -> Dict[str, Dict[str, Any]]:
    """Load JSON templates from disk (if any)."""
    templates: Dict[str, Dict[str, Any]] = {}
    if not template_dir.exists():
        return templates

    for file in template_dir.glob("*.json"):
        try:
            with file.open("r", encoding="utf-8") as f:
                data = json.load(f)
            # store path so we can persist edits
            templates[file.stem] = {"__path": str(file), "data": data}
        except Exception as exc:
            logger.warning(f"Failed to load template {file}: {exc}")
            continue
    return templates


def save_file_template(path_str: str, data: Dict[str, Any]) -> None:
    path = Path(path_str)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def find_task_events(task_id: str, streams: list[str], client: redis.Redis, max_per_stream: int = 100) -> pd.DataFrame:
    """Scan recent entries across streams and return rows containing the task_id or related IDs.
    
    Manager delegations create NEW task_ids for child orchestrators, so a simple task_id match
    won't find the full flow. We use a two-pass approach:
    1. First pass: find messages matching the original task_id, collect correlation_ids and
       child task_ids from Manager's enqueued array.
    2. Second pass: find additional messages matching the discovered IDs.
    """
    def parse_message(fields: dict) -> tuple:
        """Parse message fields into (payload, metadata) regardless of format."""
        data_field = fields.get("data")
        if data_field:
            try:
                env = json.loads(data_field)
                return env.get("payload"), env.get("metadata")
            except Exception:
                pass
        # Legacy format
        payload = fields.get("payload")
        metadata = fields.get("metadata")
        try:
            parsed_payload = json.loads(payload) if payload else None
        except Exception:
            parsed_payload = payload
        try:
            parsed_metadata = json.loads(metadata) if metadata else None
        except Exception:
            parsed_metadata = metadata
        return parsed_payload, parsed_metadata

    def extract_related_ids(parsed_payload, parsed_metadata) -> set[str]:
        """Extract correlation_id and child task_ids from a parsed message."""
        ids = set()
        if isinstance(parsed_metadata, dict):
            cid = parsed_metadata.get("correlation_id")
            if cid:
                ids.add(cid)
            # Also grab the task_id from metadata for chaining
            tid = parsed_metadata.get("task_id")
            if tid:
                ids.add(tid)
        if isinstance(parsed_payload, dict):
            for item in parsed_payload.get("enqueued", []):
                if isinstance(item, dict) and item.get("task_id"):
                    ids.add(item["task_id"])
        return ids

    # Collect all messages from streams
    all_messages: list[tuple[str, str, dict]] = []  # (stream, msg_id, fields)
    for stream in streams:
        try:
            messages = client.xrevrange(stream, count=max_per_stream)
            for msg_id, fields in messages:
                all_messages.append((stream, msg_id, fields))
        except Exception as exc:
            logger.warning(f"Could not read stream {stream}: {exc}")

    # Pass 1: Find initial matches and collect related IDs
    related_ids: set[str] = {task_id} if task_id else set()
    matched_msg_ids: set[str] = set()

    for stream, msg_id, fields in all_messages:
        raw_str = str(fields)
        if task_id and task_id in raw_str:
            matched_msg_ids.add(msg_id)
            parsed_payload, parsed_metadata = parse_message(fields)
            related_ids.update(extract_related_ids(parsed_payload, parsed_metadata))

    # Pass 2: Find messages matching any of the related IDs
    for stream, msg_id, fields in all_messages:
        if msg_id in matched_msg_ids:
            continue
        raw_str = str(fields)
        if any(rid in raw_str for rid in related_ids):
            matched_msg_ids.add(msg_id)
            # Also extract from this message to follow chains further
            parsed_payload, parsed_metadata = parse_message(fields)
            related_ids.update(extract_related_ids(parsed_payload, parsed_metadata))

    # Build events from matched messages
    events = []
    for stream, msg_id, fields in all_messages:
        if msg_id not in matched_msg_ids:
            continue
        ts_ms = int(msg_id.split("-")[0]) if "-" in msg_id else 0
        ts = datetime.fromtimestamp(ts_ms / 1000) if ts_ms else None
        parsed_payload, parsed_metadata = parse_message(fields)

        events.append({
            "stream": stream,
            "message_id": msg_id,
            "time": ts.strftime("%Y-%m-%d %H:%M:%S") if ts else "",
            "source": (parsed_metadata or {}).get("source") if isinstance(parsed_metadata, dict) else "",
            "target": ((parsed_metadata or {}).get("destination") or (parsed_metadata or {}).get("target")) if isinstance(parsed_metadata, dict) else "",
            "payload": parsed_payload,
            "metadata": parsed_metadata,
        })

    if not events:
        return pd.DataFrame()

    df = pd.DataFrame(events)
    # Order newest first by message id timestamp
    df.sort_values(by=["message_id"], ascending=False, inplace=True)
    return df

# Main Interface
st.markdown("""
<div class="main-header">
    <h1>🤖 Agentic System - Internal Admin Dashboard</h1>
    <p style='margin:0; opacity:0.9;'>Task Orchestration • Stream Monitoring • Architecture Visualization • Debug Console</p>
</div>
""", unsafe_allow_html=True)

# Connection Status
col1, col2, col3, col4 = st.columns(4)
if r:
    with col1:
        st.metric("🔌 Redis", "Connected", delta="Ready", delta_color="normal")
    try:
        info = r.info()
        with col2:
            st.metric("📦 Version", info['redis_version'])
        with col3:
            st.metric("👥 Clients", info['connected_clients'])
        with col4:
            st.metric("💾 Memory", info['used_memory_human'])
    except:
        st.error("Could not fetch Redis info")
else:
    st.error("❌ Redis Connection Failed - Check configuration in sidebar")
    st.stop()

st.divider()

# Main Tabs
tab1, tab2, tab2b, tab3, tab4, tab5 = st.tabs([
    "📤 Submit Task", 
    "📊 Stream Monitor", 
    "🔄 Task Flow Trace", 
    "🏗️ Architecture", 
    "🐛 Debug Console", 
    "📚 Documentation"
])

# ============================================================================
# TAB 1: SUBMIT TASK
# ============================================================================
with tab1:
    st.header("📤 Task Submission Center")
    
    submission_mode = st.radio(
        "Select Submission Mode:", 
        ["🎯 Mock Template", "🎲 Random Mock", "✏️ Custom Envelope"], 
        horizontal=True
    )
    
    if submission_mode == "🎯 Mock Template":
        st.subheader("Use a Pre-Built or File-Based Template")

        file_templates = load_file_templates(TEMPLATE_DIR)
        template_source = st.radio(
            "Template source",
            ["Built-in", "File-based"],
            horizontal=True,
        )

        available_templates = (
            list(MOCK_TEMPLATES.keys()) if template_source == "Built-in" else list(file_templates.keys())
        )

        if not available_templates:
            st.info("No templates found. Built-in templates are always available; add JSON files to int-frontend/templates for file-based templates.")
            available_templates = list(MOCK_TEMPLATES.keys())
            template_source = "Built-in"

        col1, col2 = st.columns([1, 1])
        with col1:
            template_name = st.selectbox("Choose Scenario:", available_templates)
        with col2:
            allow_edit = st.checkbox("Allow Editing", value=True)
            save_edits = st.checkbox("Save edits (file templates)", value=False, help="Writes back to the JSON file if file-based")

        if template_source == "Built-in":
            template = MOCK_TEMPLATES[template_name].copy()
            template_path = None
        else:
            template_entry = file_templates.get(template_name, {"data": {}})
            template = template_entry.get("data", {}).copy()
            template_path = template_entry.get("__path")

        template["task_id"] = str(uuid.uuid4())
        template["timestamp"] = datetime.now().isoformat()
        
        st.markdown("### Template Preview")
        
        if allow_edit:
            if isinstance(template, dict):
                col1, col2 = st.columns([3, 2])
                with col1:
                    custom_goal = st.text_area("Goal:", value=template.get("goal", ""), height=100)
                    template["goal"] = custom_goal
                with col2:
                    custom_context = st.text_area(
                        "Context (JSON):", 
                        value=json.dumps(template.get("context", {}), indent=2), 
                        height=200
                    )
                    try:
                        template["context"] = json.loads(custom_context)
                    except Exception:
                        st.error("Invalid JSON in context")
            else:
                st.warning("Template is not a dict; showing raw JSON")
                template_raw = st.text_area("Template JSON", value=json.dumps(template, indent=2), height=240)
                try:
                    template = json.loads(template_raw)
                except Exception:
                    st.error("Invalid JSON")
        else:
            st.json(template)
        
        col1, col2, col3 = st.columns([2, 2, 1])
        with col1:
            if st.button("🚀 Submit Task", key="mock_submit", use_container_width=True):
                try:
                    envelope_obj = {
                        "metadata": {
                            "task_id": template["task_id"],
                            "source": "internal-frontend",
                            "destination": "manager",
                            "tenant_id": tenant_id,
                            "correlation_id": str(uuid.uuid4()),
                            "tags": {
                                "target": "manager",
                                "submission_type": "mock_template",
                                "template_name": str(template_name),
                            },
                        },
                        "payload": template,
                    }
                    
                    stream_name = f"{tenant_id}:manager:tasks"
                    msg_id = r.xadd(stream_name, {"data": json.dumps(envelope_obj)})

                    # Persist edits back to file-based template if requested
                    if template_path and save_edits:
                        try:
                            # Drop helper keys if they sneaked in
                            cleaned_template = {k: v for k, v in template.items() if k not in {"task_id", "timestamp"}}
                            save_file_template(template_path, cleaned_template)
                            st.info(f"Template saved to {template_path}")
                        except Exception as exc:
                            st.warning(f"Could not save template: {exc}")
                    
                    st.markdown(f"""
                    <div class="success-box">
                        <strong>✅ Task Submitted Successfully!</strong><br>
                        <strong>Task ID:</strong> <code>{template['task_id']}</code><br>
                        <strong>Message ID:</strong> <code>{msg_id}</code><br>
                        <strong>Stream:</strong> <code>{stream_name}</code>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    if debug_mode or show_raw_json:
                        st.json(envelope_obj)
                        
                except Exception as e:
                    st.markdown(f'<div class="error-box"><strong>❌ Error:</strong> {str(e)}</div>', unsafe_allow_html=True)
    
    elif submission_mode == "🎲 Random Mock":
        st.subheader("Generate & Send Random Realistic Task")
        
        st.markdown("""
        <div class="info-box">
            <strong>🎲 Random Generator:</strong> Creates realistic tasks with varied parameters including cities, industries, counts, and contexts.
        </div>
        """, unsafe_allow_html=True)
        
        col1, col2 = st.columns([3, 1])
        with col1:
            num_tasks = st.slider("Number of Tasks to Generate:", 1, 10, 1)
        with col2:
            st.write("")  # Spacing
        
        if st.button("🎲 Generate Random Task(s)", key="random_gen", use_container_width=True):
            for i in range(num_tasks):
                random_task = generate_random_mock()
                random_task["task_id"] = str(uuid.uuid4())
                random_task["timestamp"] = datetime.now().isoformat()
                
                st.markdown(f"### Generated Task #{i+1}")
                st.json(random_task)
                
                envelope_obj = {
                    "metadata": {
                        "task_id": random_task["task_id"],
                        "source": "internal-frontend",
                        "destination": "manager",
                        "tenant_id": tenant_id,
                        "correlation_id": str(uuid.uuid4()),
                        "tags": {
                            "target": "manager",
                            "submission_type": "random_mock",
                        },
                    },
                    "payload": random_task,
                }
                
                stream_name = f"{tenant_id}:manager:tasks"
                msg_id = r.xadd(stream_name, {"data": json.dumps(envelope_obj)})
                
                st.markdown(f"""
                <div class="success-box">
                    ✅ Task {i+1} submitted | ID: <code>{random_task['task_id'][:8]}...</code>
                </div>
                """, unsafe_allow_html=True)
    
    else:  # Custom Envelope
        st.subheader("✏️ Send Custom Envelope")
        
        st.markdown("""
        <div class="warning-box">
            <strong>⚠️ Advanced Mode:</strong> Use the typed envelope format expected by the Manager consumer:
            <code>{metadata:{task_id,source,tenant_id,...}, payload:{...}}</code>
        </div>
        """, unsafe_allow_html=True)
        
        # Example envelopes
        with st.expander("📖 View Example Envelopes", expanded=False):
            example_tab1, example_tab2, example_tab3, example_tab4, example_tab5 = st.tabs(
                ["Lead Generation", "Data Enrichment", "Custom Task", "Inbound Email", "Chained Outbound"]
            )
            
            with example_tab1:
                st.markdown("**Example: Lead Generation Request**")
                lead_example = {
                    "metadata": {
                        "task_id": "550e8400-e29b-41d4-a716-446655440000",
                        "source": "internal-frontend",
                        "destination": "manager",
                        "tenant_id": tenant_id,
                        "correlation_id": str(uuid.uuid4()),
                        "tags": {"priority": "high"},
                    },
                    "payload": {
                        "goal": "Find 100 B2B leads in the FinTech industry",
                        "context": {
                            "source": "api_request",
                            "industry": "FinTech",
                            "location": "New York, NY",
                            "employee_range": [50, 500],
                            "revenue_min": 5000000,
                            "enrichment": ["email", "phone", "linkedin"],
                        },
                        "timestamp": datetime.now().isoformat(),
                    },
                }
                st.code(json.dumps(lead_example, indent=2), language="json")
            
            with example_tab2:
                st.markdown("**Example: Data Enrichment Request**")
                enrich_example = {
                    "metadata": {
                        "task_id": "660f9511-f3ac-52e5-b827-557766551111",
                        "source": "internal-frontend",
                        "destination": "manager",
                        "tenant_id": tenant_id,
                        "correlation_id": str(uuid.uuid4()),
                        "tags": {"batch_id": "batch_001"},
                    },
                    "payload": {
                        "goal": "Enrich 500 CRM contacts with missing phone numbers",
                        "context": {
                            "source": "crm_export",
                            "crm_system": "hubspot",
                            "batch_size": 500,
                            "fields_to_enrich": ["phone", "job_title"],
                            "match_confidence": 0.85,
                        },
                        "timestamp": datetime.now().isoformat(),
                    },
                }
                st.code(json.dumps(enrich_example, indent=2), language="json")
            
            with example_tab3:
                st.markdown("**Example: Custom Analysis Task**")
                custom_example = {
                    "metadata": {
                        "task_id": str(uuid.uuid4()),
                        "source": "internal-frontend",
                        "destination": "manager",
                        "tenant_id": tenant_id,
                        "correlation_id": str(uuid.uuid4()),
                        "tags": {"custom_field": "custom_value"},
                    },
                    "payload": {
                        "goal": "Your custom goal here",
                        "context": {
                            "source": "manual_submission",
                            "custom_param_1": "value1",
                            "custom_param_2": "value2",
                        },
                        "timestamp": datetime.now().isoformat(),
                    },
                }
                st.code(json.dumps(custom_example, indent=2), language="json")

            with example_tab4:
                st.markdown("**Example: Inbound Email (Most Common)**")
                st.markdown(
                    "This is the envelope you submit to the **Manager**. "
                    "With the new behavior, the Manager routes **leads-first** and then (optionally) "
                    "creates a **separate outbound task** containing a `reply_packet` after Leads finishes."
                )
                inbound_email_example = {
                    "metadata": {
                        "task_id": str(uuid.uuid4()),
                        "source": "internal-frontend",
                        "destination": "manager",
                        "tenant_id": tenant_id,
                        "correlation_id": str(uuid.uuid4()),
                        "tags": {
                            "target": "manager",
                            "submission_type": "inbound_email",
                        },
                    },
                    "payload": {
                        "goal": "Inbound email received: draft a reply",
                        "context": {
                            "email_event": {
                                "from": "customer@example.com",
                                "to": "support@example.com",
                                "subject": "Question about pricing tiers",
                                "body": "Hi team, can you clarify the difference between Pro and Enterprise?",
                                "received_at": datetime.now().isoformat(),
                            },
                            "actions_allowed": ["store", "enrich", "reply"],
                        },
                        "timestamp": datetime.now().isoformat(),
                    },
                }
                st.code(json.dumps(inbound_email_example, indent=2), language="json")

            with example_tab5:
                st.markdown("**Example: Chained Outbound Task (Created by Manager)**")
                st.markdown(
                    "You normally **do not submit** this manually. "
                    "It is produced by the Manager after Leads returns a `reply_packet`. "
                    "This is what Outbound/Outreach consumes to deterministically delegate to Copywriter."
                )
                chained_outbound_example = {
                    "metadata": {
                        "task_id": "task_" + str(uuid.uuid4()),
                        "source": "manager_agent",
                        "destination": "outbound",
                        "tenant_id": tenant_id,
                        "correlation_id": str(uuid.uuid4()),
                        "tags": {
                            "chained": "true",
                            "chained_from": "leads",
                        },
                    },
                    "payload": {
                        "tenant_id": tenant_id,
                        "source": "manager",
                        "intent": "inbound",
                        "payload": {
                            "reply_packet": {
                                "inbound_email_event": {
                                    "from": "customer@example.com",
                                    "to": "support@example.com",
                                    "subject": "Question about pricing tiers",
                                    "body": "Hi team, can you clarify the difference between Pro and Enterprise?",
                                    "received_at": datetime.now().isoformat(),
                                },
                                "facts": {
                                    "intent": "pricing_question",
                                    "risk_flags": [],
                                },
                                "recommended_strategy": "craft personalized reply using retrieved history",
                                "next": {
                                    "delegate_to": ["outbound"],
                                    "reason": "reply_packet_ready_for_outreach",
                                },
                            },
                            "context_depth": "deep",
                            "upstream": {
                                "leads_task_ids": ["task_" + str(uuid.uuid4())],
                                "leads_result": {"success": True, "path": "deep_reply_packet"},
                            },
                        },
                    },
                }
                st.code(json.dumps(chained_outbound_example, indent=2), language="json")
        
        default_envelope = {
            "metadata": {
                "task_id": str(uuid.uuid4()),
                "source": "internal-frontend",
                "destination": "manager",
                "tenant_id": tenant_id,
                "correlation_id": str(uuid.uuid4()),
                "tags": {
                    "target": "manager",
                    "custom": "true",
                },
            },
            "payload": {
                "goal": "Your custom task goal here",
                "context": {
                    "source": "custom",
                    "param1": "value1",
                },
                "timestamp": datetime.now().isoformat(),
            },
        }

        # Important: give this widget a stable key.
        # Without an explicit key, Streamlit may regenerate widget IDs when the
        # "View Example Envelopes" expander/tabs render/unrender on reruns, causing
        # the textbox to reset to the default placeholder right before submit.
        if "custom_envelope_json" not in st.session_state:
            st.session_state["custom_envelope_json"] = json.dumps(default_envelope, indent=2)

        col_json, col_opts = st.columns([3, 1])

        with col_json:
            custom_envelope = st.text_area(
                "Envelope JSON:",
                key="custom_envelope_json",
                height=400,
            )

        with col_opts:
            st.markdown("**Envelope Options**")
            randomize_ids = st.checkbox(
                "Randomize IDs", value=True, help="Replace metadata.task_id and metadata.correlation_id with new UUIDs before sending."
            )
        
        if st.button("🚀 Send Custom Envelope", key="custom_submit", use_container_width=True):
            try:
                raw = json.loads(custom_envelope)

                # Accept either:
                # - Typed envelope dict: {metadata:{...}, payload:{...}}
                # - Legacy dict: {task_id, tenant_id, payload:<json str>, metadata:<json str>}
                envelope_obj = None
                tenant_for_stream = tenant_id

                if isinstance(raw, dict) and "metadata" in raw and "payload" in raw:
                    envelope_obj = raw
                    meta = envelope_obj.get("metadata") or {}
                    if randomize_ids and isinstance(meta, dict):
                        meta["task_id"] = str(uuid.uuid4())
                        meta["correlation_id"] = str(uuid.uuid4())
                    if isinstance(meta, dict) and meta.get("tenant_id"):
                        tenant_for_stream = meta.get("tenant_id")
                elif isinstance(raw, dict) and all(k in raw for k in ["task_id", "tenant_id", "payload", "metadata"]):
                    tenant_for_stream = raw.get("tenant_id")
                    try:
                        legacy_payload = raw.get("payload")
                        legacy_payload_dict = json.loads(legacy_payload) if isinstance(legacy_payload, str) else (legacy_payload or {})
                    except Exception:
                        legacy_payload_dict = {}
                    try:
                        legacy_metadata = raw.get("metadata")
                        legacy_metadata_dict = json.loads(legacy_metadata) if isinstance(legacy_metadata, str) else (legacy_metadata or {})
                    except Exception:
                        legacy_metadata_dict = {}

                    tags = {}
                    if isinstance(legacy_metadata_dict, dict):
                        for k, v in legacy_metadata_dict.items():
                            if v is None:
                                continue
                            tags[str(k)] = str(v)

                    envelope_obj = {
                        "metadata": {
                            "task_id": str(uuid.uuid4()) if randomize_ids else raw.get("task_id"),
                            "source": str((legacy_metadata_dict or {}).get("source") or "internal-frontend"),
                            "destination": str((legacy_metadata_dict or {}).get("target") or "manager"),
                            "tenant_id": raw.get("tenant_id"),
                            "correlation_id": str(uuid.uuid4()) if randomize_ids else str(uuid.uuid4()),
                            "tags": tags,
                        },
                        "payload": legacy_payload_dict,
                    }

                if not envelope_obj:
                    st.error("❌ Invalid envelope format. Provide either {metadata,payload} or the legacy {task_id,tenant_id,payload,metadata} format.")
                else:
                    stream_name = f"{tenant_for_stream}:manager:tasks"
                    msg_id = r.xadd(stream_name, {"data": json.dumps(envelope_obj)})
                    
                    st.markdown(f"""
                    <div class="success-box">
                        <strong>✅ Custom Envelope Sent!</strong><br>
                        <strong>Task ID:</strong> <code>{(envelope_obj.get('metadata') or {}).get('task_id')}</code><br>
                        <strong>Correlation ID:</strong> <code>{(envelope_obj.get('metadata') or {}).get('correlation_id')}</code><br>
                        <strong>Stream:</strong> <code>{stream_name}</code><br>
                        <strong>Message ID:</strong> <code>{msg_id}</code>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    if debug_mode or show_raw_json:
                        st.json(envelope_obj)
                        
            except json.JSONDecodeError as e:
                st.markdown(f'<div class="error-box"><strong>❌ Invalid JSON:</strong> {str(e)}</div>', unsafe_allow_html=True)
            except Exception as e:
                st.markdown(f'<div class="error-box"><strong>❌ Error:</strong> {str(e)}</div>', unsafe_allow_html=True)

# ============================================================================
# TAB 2: STREAM MONITOR
# ============================================================================
with tab2:
    st.header("📊 Real-Time Stream Monitor")
    
    col1, col2, col3 = st.columns([3, 1, 1])
    with col1:
        default_streams = [
            f"{tenant_id}:manager:tasks",
            f"{tenant_id}:manager:results",
            f"{tenant_id}:orchestrators:leads:tasks",
            f"{tenant_id}:orchestrators:leads:results",
            f"{tenant_id}:agents:persistence:tasks",
            f"{tenant_id}:agents:copywriter:tasks",
            f"{tenant_id}:agents:rag:tasks"
        ]
        selected_stream = st.selectbox("📡 Stream:", default_streams, index=1)
    with col2:
        refresh_rate = st.slider("⏱️ Refresh (s)", 1, 10, 2)
    with col3:
        auto_refresh = st.checkbox("🔄 Auto", value=False)

    try:
        messages = r.xrevrange(selected_stream, count=20)
        
        if not messages:
            st.info(f"📭 No messages in stream `{selected_stream}`")
        else:
            # Metrics
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("📦 Total in Stream", r.xlen(selected_stream))
            with col2:
                st.metric("👁️ Displaying", len(messages))
            with col3:
                st.metric("🕐 Latest", messages[0][0].split("-")[0] if messages else "N/A")
            
            st.divider()
            
            # Message table
            data = []
            for msg_id, fields in messages:
                timestamp_ms = int(msg_id.split("-")[0])
                dt = datetime.fromtimestamp(timestamp_ms / 1000)
                
                row = {
                    "📌 Message ID": msg_id,
                    "🕐 Time": dt.strftime("%Y-%m-%d %H:%M:%S"),
                    "📦 Fields": len(fields),
                    "🔑 Keys": ", ".join(list(fields.keys())[:3])
                }
                data.append(row)
            
            st.dataframe(pd.DataFrame(data), use_container_width=True, height=300)
            
            # Detailed inspector
            st.subheader("🔍 Message Inspector")
            selected_msg = st.selectbox("Select message to inspect:", [m[0] for m in messages])
            
            for msg_id, fields in messages:
                if msg_id == selected_msg:
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown("**Raw Fields:**")
                        st.json(fields)
                    
                    with col2:
                        # Parse either typed envelope (data) or legacy fields (payload/metadata)
                        if "data" in fields:
                            st.markdown("**📨 Parsed Envelope:**")
                            try:
                                env = json.loads(fields["data"])
                                st.markdown("**🏷️ Metadata:**")
                                st.json(env.get("metadata"))
                                st.markdown("**📋 Payload:**")
                                st.json(env.get("payload"))
                            except Exception:
                                st.code(fields["data"])
                        else:
                            if "payload" in fields:
                                st.markdown("**📋 Parsed Payload:**")
                                try:
                                    payload = json.loads(fields["payload"])
                                    st.json(payload)
                                except Exception:
                                    st.code(fields["payload"])

                            if "metadata" in fields:
                                st.markdown("**🏷️ Metadata:**")
                                try:
                                    metadata = json.loads(fields["metadata"])
                                    st.json(metadata)
                                except Exception:
                                    st.code(fields["metadata"])
                    break
                    
    except Exception as e:
        st.markdown(f'<div class="error-box"><strong>❌ Stream Error:</strong> {str(e)}</div>', unsafe_allow_html=True)
        
    if auto_refresh:
        time.sleep(refresh_rate)
        st.rerun()

# ============================================================================
# TAB 2B: TASK FLOW TRACE
# ============================================================================
with tab2b:
    st.header("🔄 Task Flow Trace")
    st.markdown("Trace a task across manager → orchestrators → agents by scanning recent messages for the task_id.")

    col1, col2 = st.columns([2, 1])
    with col1:
        trace_task_id = st.text_input("Task ID to trace", value="")
    with col2:
        max_per_stream = st.slider("Messages per stream", 20, 200, 100, step=20)

    default_trace_streams = [
        f"{tenant_id}:manager:tasks",
        f"{tenant_id}:manager:results",
        f"{tenant_id}:orchestrators:leads:tasks",
        f"{tenant_id}:orchestrators:leads:results",
        f"{tenant_id}:orchestrators:outbound:tasks",
        f"{tenant_id}:orchestrators:outbound:results",
        f"{tenant_id}:agents:rag:tasks",
        f"{tenant_id}:agents:rag:results",
        f"{tenant_id}:agents:persistence:tasks",
        f"{tenant_id}:agents:persistence:results",
        f"{tenant_id}:agents:copywriter:tasks",
        f"{tenant_id}:agents:copywriter:results",
        f"{tenant_id}:agents:sequencing:tasks",
        f"{tenant_id}:agents:sequencing:results",
    ]

    selected_streams = st.multiselect(
        "Streams to scan",
        options=default_trace_streams,
        default=default_trace_streams,
    )

    if st.button("🔍 Trace now", use_container_width=True) and trace_task_id:
        df = find_task_events(trace_task_id, selected_streams, r, max_per_stream=max_per_stream)
        if df.empty:
            st.info("No matching events found in the selected streams (recent messages).")
        else:
            st.dataframe(df[["time", "stream", "source", "target", "message_id"]], use_container_width=True)

            with st.expander("View details (payload + metadata)"):
                st.dataframe(df, use_container_width=True)

    elif trace_task_id:
        st.caption("Click 'Trace now' to fetch the latest events.")
    else:
        st.info("Enter a task_id to start tracing.")

# ============================================================================
# TAB 3: ARCHITECTURE
# ============================================================================
with tab3:
    st.header("🏗️ System Architecture")
    
    # Architecture diagram
    st.markdown("""
    <div class="info-box">
        <strong>3-Tier Event-Driven Architecture</strong> - Redis Streams orchestrate async communication between Manager, Orchestrators, and Agents
    </div>
    """, unsafe_allow_html=True)
    
    architecture_ascii = f"""
╔══════════════════════════════════════════════════════════════════╗
║                  INTERNAL ADMIN DASHBOARD                        ║
║                    (localhost:8501)                              ║
║  ✓ Task Submission  ✓ Monitor  ✓ Debug  ✓ Architecture          ║
╚═══════════════════════════╦══════════════════════════════════════╝
                            ║ HTTP/WebSocket
                            ▼
    ┌───────────────────────────────────────────────────────┐
    │              REDIS STREAMS (Message Broker)           │
    │  ┌─────────────────────────────────────────────────┐  │
    │  │  TIER 1: Strategic Layer                        │  │
    │  │  • {tenant_id}:manager:tasks                    │  │
    │  │  • {tenant_id}:manager:results                  │  │
    │  │  Role: Goal routing & high-level orchestration  │  │
    │  └─────────────────────────────────────────────────┘  │
    │                                                        │
    │  ┌─────────────────────────────────────────────────┐  │
    │  │  TIER 2: Orchestration Layer                    │  │
    │  │  • {tenant_id}:leads:tasks → LeadsOrch          │  │
    │  │  • {tenant_id}:outreach:tasks → OutreachOrch    │  │
    │  │  Role: Workflow decomposition & coordination    │  │
    │  └─────────────────────────────────────────────────┘  │
    │                                                        │
    │  ┌─────────────────────────────────────────────────┐  │
    │  │  TIER 3: Execution Layer (Agents)               │  │
    │  │  • {tenant_id}:agents:rag:tasks                 │  │
    │  │  • {tenant_id}:agents:persistence:tasks         │  │
    │  │  • {tenant_id}:agents:copywriter:tasks          │  │
    │  │  Role: Atomic operations (RAG, DB, LLM)         │  │
    │  └─────────────────────────────────────────────────┘  │
    └───────────────────────────────────────────────────────┘
                            │
                            ▼
    ┌───────────────────────────────────────────────────────┐
    │          PERSISTENCE LAYER (PostgreSQL/Supabase)      │
    │   • Leads DB  • Results Cache  • Audit Logs           │
    └───────────────────────────────────────────────────────┘
    """
    
    st.code(architecture_ascii, language="text")
    
    # Live Stream Status
    st.subheader("📡 Live Stream Status")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Manager Tier:**")
        manager_streams = [
            f"{tenant_id}:manager:tasks",
            f"{tenant_id}:manager:results"
        ]
        for stream in manager_streams:
            try:
                count = r.xlen(stream)
                st.markdown(f"✅ `{stream}` - **{count}** messages")
            except:
                st.markdown(f"❌ `{stream}` - unavailable")
    
    with col2:
        st.markdown("**Agent Tier:**")
        agent_streams = [
            f"{tenant_id}:agents:persistence:tasks",
            f"{tenant_id}:agents:copywriter:tasks",
            f"{tenant_id}:agents:rag:tasks"
        ]
        for stream in agent_streams:
            try:
                count = r.xlen(stream)
                st.markdown(f"✅ `{stream}` - **{count}** messages")
            except:
                st.markdown(f"⚠️ `{stream}` - not active")
    
    # All streams table
    st.divider()
    st.subheader("🗂️ All Active Streams")
    
    try:
        streams = list(r.scan_iter(match=f"{tenant_id}:*", _type="stream"))
        if streams:
            stream_data = []
            for stream in streams:
                length = r.xlen(stream)
                first_msg = r.xrange(stream, count=1)
                last_msg = r.xrevrange(stream, count=1)
                
                stream_data.append({
                    "Stream Name": stream,
                    "Messages": length,
                    "First ID": first_msg[0][0] if first_msg else "N/A",
                    "Last ID": last_msg[0][0] if last_msg else "N/A"
                })
            
            st.dataframe(pd.DataFrame(stream_data), use_container_width=True)
        else:
            st.info(f"No streams found for tenant `{tenant_id}`")
    except Exception as e:
        st.error(f"Error fetching streams: {e}")

# ============================================================================
# TAB 4: DEBUG CONSOLE
# ============================================================================
with tab4:
    st.header("🐛 Debug Console")
    
    debug_section = st.radio(
        "Debug Tool:", 
        ["🔧 Redis Info", "📊 Stream Analysis", "🔍 Message Inspector", "📝 Logs"],
        horizontal=True
    )
    
    if debug_section == "🔧 Redis Info":
        st.subheader("Redis Server Diagnostics")
        
        try:
            info = r.info()
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.markdown("**Server:**")
                st.json({
                    "version": info.get('redis_version'),
                    "uptime_days": info.get('uptime_in_days'),
                    "os": info.get('os')
                })
            
            with col2:
                st.markdown("**Clients:**")
                st.json({
                    "connected": info.get('connected_clients'),
                    "blocked": info.get('blocked_clients'),
                    "max_clients": info.get('maxclients')
                })
            
            with col3:
                st.markdown("**Memory:**")
                st.json({
                    "used": info.get('used_memory_human'),
                    "peak": info.get('used_memory_peak_human'),
                    "fragmentation": info.get('mem_fragmentation_ratio')
                })
            
            with st.expander("📋 Full Redis Info"):
                st.json(info)
                
        except Exception as e:
            st.error(f"Error: {e}")
    
    elif debug_section == "📊 Stream Analysis":
        st.subheader("Stream Depth & Age Analysis")
        
        stream_filter = st.text_input("Filter pattern:", value=f"{tenant_id}:*")
        
        try:
            streams = list(r.scan_iter(match=stream_filter, _type="stream"))
            
            if streams:
                analysis = []
                for stream in streams:
                    first_msg = r.xrange(stream, count=1)
                    last_msg = r.xrevrange(stream, count=1)
                    length = r.xlen(stream)
                    
                    first_ts = int(first_msg[0][0].split("-")[0]) if first_msg else 0
                    last_ts = int(last_msg[0][0].split("-")[0]) if last_msg else 0
                    
                    age_seconds = (last_ts - first_ts) / 1000 if first_ts and last_ts else 0
                    
                    analysis.append({
                        "Stream": stream,
                        "Count": length,
                        "Age (min)": round(age_seconds / 60, 1),
                        "First ID": first_msg[0][0] if first_msg else "N/A",
                        "Last ID": last_msg[0][0] if last_msg else "N/A"
                    })
                
                st.dataframe(pd.DataFrame(analysis), use_container_width=True)
            else:
                st.info("No streams match filter")
                
        except Exception as e:
            st.error(f"Error: {e}")
    
    elif debug_section == "🔍 Message Inspector":
        st.subheader("Raw Message Inspector")
        
        col1, col2 = st.columns([2, 1])
        with col1:
            inspect_stream = st.text_input("Stream:", value=f"{tenant_id}:manager:tasks")
        with col2:
            message_id = st.text_input("Message ID (optional):", value="")
        
        if st.button("🔍 Fetch & Inspect"):
            try:
                if message_id:
                    result = r.xrange(inspect_stream, min=message_id, max=message_id)
                else:
                    result = r.xrevrange(inspect_stream, count=1)
                
                if result:
                    msg_id, fields = result[0]
                    
                    st.success(f"✅ Found message: `{msg_id}`")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown("**Raw JSON:**")
                        st.code(json.dumps(fields, indent=2), language="json")
                    
                    with col2:
                        if "payload" in fields:
                            st.markdown("**Parsed Payload:**")
                            try:
                                st.json(json.loads(fields["payload"]))
                            except:
                                st.text("Cannot parse payload")
                else:
                    st.warning("Message not found")
                    
            except Exception as e:
                st.error(f"Error: {e}")
    
    else:  # Logs
        st.subheader("📝 Application Logs")
        
        st.markdown("""
        <div class="info-box">
            <strong>Frontend Session Info:</strong>
        </div>
        """, unsafe_allow_html=True)
        
        log_data = {
            "Redis Host": redis_host,
            "Redis Port": redis_port,
            "Tenant ID": tenant_id,
            "Debug Mode": debug_mode,
            "Show Raw JSON": show_raw_json,
            "Session Start": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        st.json(log_data)
        
        if debug_mode:
            st.markdown("**🐛 Debug Mode Active** - All submissions will show raw envelope data")

# ============================================================================
# TAB 5: DOCUMENTATION
# ============================================================================
with tab5:
    st.header("📚 Documentation & User Guide")
    
    doc_section = st.radio(
        "Section:",
        ["🚀 Quick Start", "📖 Task Submission", "🔧 Debugging", "🏗️ Architecture Details"],
        horizontal=True
    )
    
    if doc_section == "🚀 Quick Start":
        st.markdown("""
        ## Welcome to the Agentic System Dashboard
        
        ### What is this?
        This is an **internal admin tool** for developers and operators to:
        - Submit tasks to the agentic system
        - Monitor Redis streams in real-time
        - Debug message flow and inspect payloads
        - Visualize system architecture
        
        ### Quick Workflow
        1. Go to **📤 Submit Task**
        2. Choose a mock template or generate random
        3. Submit the task
        4. Go to **📊 Stream Monitor** 
        5. Watch your task in `{tenant}:manager:results`
        
        ### First Steps
        - ✅ Verify Redis connection (top metrics)
        - ✅ Check **🏗️ Architecture** tab to see stream layout
        - ✅ Try submitting a mock task
        - ✅ Enable **Debug Mode** in sidebar for detailed output
        """)
    
    elif doc_section == "📖 Task Submission":
        st.markdown("""
        ## Task Submission Modes
        
        ### 🎯 Mock Template
        Pre-built realistic scenarios:
        - **Lead Prospecting**: Find B2B leads with filters
        - **CRM Enrichment**: Add missing contact data
        - **Outreach Campaign**: Generate personalized emails
        - **Market Research**: Competitive intelligence
        - **Data Scraping**: Web scraping jobs
        - **Lead Scoring**: Score leads with ML
        
        ### 🎲 Random Mock
        Automatically generates realistic tasks with:
        - Random cities, industries, counts
        - Varied contexts and parameters
        - Great for load testing
        - Can generate 1-10 tasks at once
        
        ### ✏️ Custom Envelope
        Full control - send any JSON structure
        
        **Required fields:**
        ```json
        {
          "task_id": "uuid",
          "tenant_id": "agentic-dev",
          "payload": "JSON string",
          "metadata": "JSON string"
        }
        ```
        
        ### Payload Structure
        Inside the `payload` field:
        ```json
        {
          "goal": "What you want to accomplish",
          "context": {
            "source": "where this came from",
            "...": "any additional params"
          },
          "timestamp": "ISO-8601 datetime"
        }
        ```
        """)
    
    elif doc_section == "🔧 Debugging":
        st.markdown("""
        ## Debugging Tools
        
        ### 🐛 Debug Mode (Sidebar)
        - Shows raw envelope JSON after submission
        - Displays all message fields
        - Useful for troubleshooting
        
        ### Stream Monitor
        - View last 20 messages in any stream
        - Auto-refresh option
        - Parse payloads and metadata
        - See message timing
        
        ### Debug Console
        
        **Redis Info:**
        - Server version, uptime
        - Memory usage
        - Client connections
        
        **Stream Analysis:**
        - Message counts
        - Stream age
        - First/last message IDs
        
        **Message Inspector:**
        - Fetch specific message by ID
        - Or get latest message
        - View raw JSON
        
        ### Common Issues
        
        **No messages appearing?**
        - Check tenant ID matches
        - Verify Redis connection
        - Check stream name spelling
        
        **Task not processing?**
        - Check if consumers are running
        - Inspect message in Debug → Message Inspector
        - Verify payload JSON is valid
        """)
    
    else:  # Architecture Details
        st.markdown(f"""
        ## System Architecture Details
        
        ### Message Flow
        
        1. **Task Submitted** → `{{tenant}}:manager:tasks`
        2. **Manager Agent** reads task, routes to orchestrator
        3. **Orchestrator** (e.g., LeadsOrchestrator) decomposes task
        4. **Agents** (RAG, Persistence, Copywriter) execute atomic ops
        5. **Results** flow back → `{{tenant}}:manager:results`
        
        ### Stream Naming Convention
        
        **Tier 1 (Manager):**
        - `{{tenant}}:manager:tasks`
        - `{{tenant}}:manager:results`
        
        **Tier 2 (Orchestrators):**
        - `{{tenant}}:leads:tasks`
        - `{{tenant}}:outreach:tasks`
        
        **Tier 3 (Agents):**
        - `{{tenant}}:agents:rag:tasks`
        - `{{tenant}}:agents:persistence:tasks`
        - `{{tenant}}:agents:copywriter:tasks`
        
        ### Current Configuration
        - **Tenant ID:** `{tenant_id}`
        - **Redis Host:** `{redis_host}:{redis_port}`
        - **Manager Stream:** `{tenant_id}:manager:tasks`
        
        ### Persistence
        - Results are stored in PostgreSQL/Supabase
        - Audit logs track all task execution
        - Stream messages are kept for debugging
        
        ### Scaling
        - Each agent can scale independently
        - Redis consumer groups enable parallelization
        - Orchestrators coordinate distributed work
        """)
