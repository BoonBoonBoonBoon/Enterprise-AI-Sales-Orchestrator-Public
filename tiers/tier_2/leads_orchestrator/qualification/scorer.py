"""Lead Qualification Scorer - Hybrid Rules + LLM.

Computes a qualification score (0-100) for leads based on:
1. Email classification signals (from ClassifierAgent)
2. Conversation signals (keywords, engagement patterns)
3. Lead profile signals (company, title, domain)
4. LLM fallback for ambiguous cases (score 40-69)

Usage:
    from tiers.tier_2.leads_orchestrator.qualification import QualificationScorer
    
    scorer = QualificationScorer()
    result = scorer.score(
        lead_data={"email": "...", "company_name": "...", ...},
        conversation_history=[{"content": "...", "direction": "inbound"}, ...],
        email_classification={"category": "business_inquiry", "confidence": 0.9},
        lead_source="staging_leads"  # or "leads", "new"
    )
    
    # result = QualificationResult(
    #     score=75,
    #     decision="qualified",  # "qualified" | "nurture" | "disqualified" | "fast_track"
    #     promote=True,
    #     fast_track=False,
    #     signals=["email_category:business_inquiry:+25", "has_company:+10", ...],
    #     reasoning="High intent business inquiry from known company",
    #     llm_used=False
    # )
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

logger = logging.getLogger(__name__)


@dataclass
class QualificationResult:
    """Result of lead qualification scoring."""
    
    score: int  # 0-100
    decision: str  # "qualified", "nurture", "disqualified", "fast_track"
    promote: bool  # Should move from staging to leads
    fast_track: bool  # Should skip staging entirely (new lead → leads)
    signals: List[str]  # Contributing signals with points
    reasoning: str  # Human-readable explanation
    llm_used: bool = False  # Whether LLM fallback was used
    llm_adjustment: int = 0  # Score adjustment from LLM
    confidence: float = 1.0  # Confidence in decision


@dataclass
class QualificationConfig:
    """Loaded qualification configuration."""
    
    thresholds: Dict[str, int] = field(default_factory=dict)
    signals: Dict[str, Dict[str, int]] = field(default_factory=dict)
    fast_track_rules: List[Dict[str, Any]] = field(default_factory=list)
    llm_fallback: Dict[str, Any] = field(default_factory=dict)
    decision_maker_titles: List[str] = field(default_factory=list)
    freemail_domains: List[str] = field(default_factory=list)
    keyword_patterns: Dict[str, List[str]] = field(default_factory=dict)


class QualificationScorer:
    """Hybrid rules + LLM lead qualification scorer."""
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize scorer with configuration.
        
        Args:
            config_path: Path to qualification.yaml. If None, uses default location.
        """
        self.config = self._load_config(config_path)
        self._llm = None  # Lazy-loaded
        
    def _load_config(self, config_path: Optional[str] = None) -> QualificationConfig:
        """Load configuration from YAML file."""
        if config_path is None:
            # Default to config/manager/qualification.yaml
            base_dir = Path(__file__).parent.parent.parent.parent.parent
            config_path = base_dir / "config" / "manager" / "qualification.yaml"
        else:
            config_path = Path(config_path)
            
        if not config_path.exists():
            logger.warning(f"Qualification config not found at {config_path}, using defaults")
            return QualificationConfig(
                thresholds={"auto_promote": 70, "fast_track": 85, "disqualify": 20},
                signals={},
                fast_track_rules=[],
                llm_fallback={"enabled": False},
                decision_maker_titles=[],
                freemail_domains=[],
                keyword_patterns={},
            )
            
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            
        return QualificationConfig(
            thresholds=data.get("thresholds", {}),
            signals=data.get("signals", {}),
            fast_track_rules=data.get("fast_track_rules", []),
            llm_fallback=data.get("llm_fallback", {}),
            decision_maker_titles=[t.lower() for t in data.get("decision_maker_titles", [])],
            freemail_domains=[d.lower() for d in data.get("freemail_domains", [])],
            keyword_patterns=data.get("keyword_patterns", {}),
        )
    
    def score(
        self,
        lead_data: Dict[str, Any],
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        email_classification: Optional[Dict[str, Any]] = None,
        lead_source: str = "new",  # "leads", "staging_leads", "new"
        email_direction: str = "inbound",  # "inbound", "outbound"
    ) -> QualificationResult:
        """Compute qualification score for a lead.
        
        Args:
            lead_data: Lead profile data (email, company_name, job_title, etc.)
            conversation_history: List of messages [{content, direction, sender}, ...]
            email_classification: Classification result {category, confidence, action}
            lead_source: Where lead was found ("leads", "staging_leads", "new")
            email_direction: Direction of triggering email
            
        Returns:
            QualificationResult with score, decision, and signals
        """
        # --- Input normalization & defensive handling ---
        lead_data = self._normalize_lead_data(lead_data)
        conversation_history = self._normalize_conversation_history(conversation_history)
        email_classification = email_classification if isinstance(email_classification, dict) else {}
        lead_source = str(lead_source or "new").lower()
        email_direction = str(email_direction or "inbound").lower()
        
        signals: List[str] = []
        total_score = 0
        
        # --- 1. Email Classification Signals ---
        category_score, category_signals = self._score_email_category(email_classification)
        total_score += category_score
        signals.extend(category_signals)
        
        # --- 2. Conversation Signals ---
        conv_score, conv_signals = self._score_conversation(
            conversation_history, 
            lead_source,
            email_direction
        )
        total_score += conv_score
        signals.extend(conv_signals)
        
        # --- 3. Lead Profile Signals ---
        profile_score, profile_signals = self._score_profile(lead_data)
        total_score += profile_score
        signals.extend(profile_signals)
        
        # --- 4. Engagement Signals ---
        engagement_score, engagement_signals = self._score_engagement(
            lead_source,
            email_direction,
            conversation_history
        )
        total_score += engagement_score
        signals.extend(engagement_signals)
        
        # --- 5. Negative Signals ---
        negative_score, negative_signals = self._score_negative(conversation_history)
        total_score += negative_score
        signals.extend(negative_signals)
        
        # Clamp score to 0-100
        total_score = max(0, min(100, total_score))
        
        # --- 6. Check Fast-Track Rules ---
        fast_track, fast_track_reason = self._check_fast_track_rules(
            lead_source=lead_source,
            email_direction=email_direction,
            score=total_score,
            signals=signals
        )
        
        # --- 7. LLM Fallback for Ambiguous Cases ---
        llm_used = False
        llm_adjustment = 0
        llm_reasoning = ""
        
        if not fast_track and self._is_ambiguous(total_score):
            llm_result = self._llm_evaluate(
                lead_data=lead_data,
                conversation_history=conversation_history,
                email_classification=email_classification,
                current_score=total_score
            )
            if llm_result:
                llm_used = True
                llm_adjustment = llm_result.get("score_adjustment", 0)
                total_score = max(0, min(100, total_score + llm_adjustment))
                llm_reasoning = llm_result.get("reasoning", "")
                signals.append(f"llm_adjustment:{llm_adjustment:+d}")
        
        # --- 8. Make Final Decision ---
        decision, promote = self._make_decision(total_score, fast_track)
        
        # Build reasoning
        if fast_track:
            reasoning = f"Fast-track: {fast_track_reason}"
        elif llm_used and llm_reasoning:
            reasoning = f"LLM: {llm_reasoning}"
        else:
            reasoning = self._build_reasoning(signals, decision)
        
        return QualificationResult(
            score=total_score,
            decision=decision,
            promote=promote,
            fast_track=fast_track,
            signals=signals,
            reasoning=reasoning,
            llm_used=llm_used,
            llm_adjustment=llm_adjustment,
            confidence=1.0 if not llm_used else 0.8,
        )
    
    def _normalize_lead_data(self, lead_data: Any) -> Dict[str, Any]:
        """Normalize lead data to ensure consistent structure."""
        if not isinstance(lead_data, dict):
            return {}
        
        normalized = {}
        for key, value in lead_data.items():
            if value is None:
                continue
            # Convert to string for text fields, preserve others
            if key in ("email", "company_name", "company", "job_title", "title", 
                       "first_name", "last_name", "phone_number", "phone",
                       "linkedin_url", "linkedin"):
                normalized[key] = str(value).strip() if value else ""
            else:
                normalized[key] = value
        return normalized
    
    def _normalize_conversation_history(
        self, 
        history: Optional[List[Dict[str, Any]]]
    ) -> List[Dict[str, Any]]:
        """Normalize conversation history to ensure consistent structure."""
        if not history or not isinstance(history, list):
            return []
        
        normalized = []
        for msg in history:
            if not isinstance(msg, dict):
                continue
            content = msg.get("content") or msg.get("text_content") or ""
            if not isinstance(content, str):
                content = str(content) if content else ""
            normalized.append({
                "content": content,
                "direction": str(msg.get("direction", "unknown")).lower(),
                "sender": str(msg.get("sender", "")) if msg.get("sender") else "",
            })
        return normalized

    def _score_email_category(
        self, 
        classification: Dict[str, Any]
    ) -> Tuple[int, List[str]]:
        """Score based on email classification category."""
        signals = []
        score = 0
        
        # Defensive: handle None or non-string category
        raw_category = classification.get("category")
        category = str(raw_category).lower() if raw_category else ""
        category_weights = self.config.signals.get("email_category", {})
        
        if category in category_weights:
            points = category_weights[category]
            score += points
            signals.append(f"email_category:{category}:{points:+d}")
        
        # Bonus for high-confidence classification
        # Defensive: handle string or non-numeric confidence
        raw_confidence = classification.get("confidence", 0)
        try:
            confidence = float(raw_confidence) if raw_confidence is not None else 0.0
        except (ValueError, TypeError):
            confidence = 0.0
        
        if confidence >= 0.9 and category in ["business_inquiry", "personal"]:
            score += 5
            signals.append(f"high_confidence:{confidence:.2f}:+5")
        
        return score, signals
    
    def _score_conversation(
        self,
        messages: List[Dict[str, Any]],
        lead_source: str,
        email_direction: str
    ) -> Tuple[int, List[str]]:
        """Score based on conversation history."""
        signals = []
        score = 0
        conv_weights = self.config.signals.get("conversation", {})
        
        if not messages:
            return score, signals
        
        # Combine all message content for keyword analysis
        all_content = " ".join(
            (m.get("content") or m.get("text_content") or "").lower()
            for m in messages
        )
        
        # Has reply (they responded to us)
        inbound_count = sum(1 for m in messages if m.get("direction") == "inbound")
        if inbound_count > 0 and lead_source in ["leads", "staging_leads"]:
            points = conv_weights.get("has_reply", 15)
            score += points
            signals.append(f"has_reply:+{points}")
        
        # Multiple messages (engagement depth)
        if len(messages) >= 3:
            points = conv_weights.get("multiple_messages", 10)
            score += points
            signals.append(f"multiple_messages:{len(messages)}:+{points}")
        
        # Asked question
        if "?" in all_content:
            points = conv_weights.get("asked_question", 10)
            score += points
            signals.append(f"asked_question:+{points}")
        
        # Budget/pricing keywords
        budget_keywords = self.config.keyword_patterns.get("budget_keywords", [])
        if any(kw in all_content for kw in budget_keywords):
            points = conv_weights.get("mentioned_budget", 15)
            score += points
            signals.append(f"mentioned_budget:+{points}")
        
        # Timeline keywords
        timeline_keywords = self.config.keyword_patterns.get("timeline_keywords", [])
        if any(kw in all_content for kw in timeline_keywords):
            points = conv_weights.get("mentioned_timeline", 10)
            score += points
            signals.append(f"mentioned_timeline:+{points}")
        
        # Meeting/demo request keywords
        meeting_keywords = self.config.keyword_patterns.get("meeting_keywords", [])
        if any(kw in all_content for kw in meeting_keywords):
            points = conv_weights.get("requested_meeting", 20)
            score += points
            signals.append(f"requested_meeting:+{points}")
        
        return score, signals
    
    def _score_profile(self, lead_data: Dict[str, Any]) -> Tuple[int, List[str]]:
        """Score based on lead profile data."""
        signals = []
        score = 0
        profile_weights = self.config.signals.get("profile", {})
        
        # Has company
        if lead_data.get("company_name") or lead_data.get("company"):
            points = profile_weights.get("has_company", 10)
            score += points
            signals.append(f"has_company:+{points}")
        
        # Has title
        title = (lead_data.get("job_title") or lead_data.get("title") or "").lower()
        if title:
            points = profile_weights.get("has_title", 5)
            score += points
            signals.append(f"has_title:+{points}")
            
            # Decision maker title bonus
            if any(dm in title for dm in self.config.decision_maker_titles):
                points = profile_weights.get("decision_maker_title", 15)
                score += points
                signals.append(f"decision_maker_title:{title}:+{points}")
        
        # Has phone
        if lead_data.get("phone_number") or lead_data.get("phone"):
            points = profile_weights.get("has_phone", 5)
            score += points
            signals.append(f"has_phone:+{points}")
        
        # Has LinkedIn
        if lead_data.get("linkedin_url") or lead_data.get("linkedin"):
            points = profile_weights.get("has_linkedin", 5)
            score += points
            signals.append(f"has_linkedin:+{points}")
        
        # Known domain (not freemail)
        email = lead_data.get("email", "")
        if "@" in email:
            domain = email.split("@")[1].lower()
            if domain not in self.config.freemail_domains:
                points = profile_weights.get("known_domain", 10)
                score += points
                signals.append(f"known_domain:{domain}:+{points}")
        
        return score, signals
    
    def _score_engagement(
        self,
        lead_source: str,
        email_direction: str,
        messages: List[Dict[str, Any]]
    ) -> Tuple[int, List[str]]:
        """Score based on engagement signals."""
        signals = []
        score = 0
        engagement_weights = self.config.signals.get("engagement", {})
        
        # First contact inbound (they reached out)
        if lead_source == "new" and email_direction == "inbound":
            points = engagement_weights.get("first_contact_inbound", 10)
            score += points
            signals.append(f"first_contact_inbound:+{points}")
        
        # Campaign reply (they replied to our outreach)
        if lead_source == "leads" and email_direction == "inbound":
            points = engagement_weights.get("campaign_reply", 25)
            score += points
            signals.append(f"campaign_reply:+{points}")
        
        return score, signals
    
    def _score_negative(
        self, 
        messages: List[Dict[str, Any]]
    ) -> Tuple[int, List[str]]:
        """Score negative signals (subtracts points)."""
        signals = []
        score = 0
        negative_weights = self.config.signals.get("negative", {})
        
        if not messages:
            return score, signals
        
        all_content = " ".join(
            (m.get("content") or m.get("text_content") or "").lower()
            for m in messages
        )
        
        # Not interested keywords
        not_interested = self.config.keyword_patterns.get("not_interested_keywords", [])
        for kw in not_interested:
            if kw in all_content:
                if "unsubscribe" in kw or "remove" in kw or "stop" in kw:
                    points = negative_weights.get("unsubscribe_request", -30)
                    signals.append(f"unsubscribe_request:{points}")
                elif "not interested" in kw or "no thanks" in kw:
                    points = negative_weights.get("not_interested", -25)
                    signals.append(f"not_interested:{points}")
                elif "wrong" in kw or "not the right" in kw:
                    points = negative_weights.get("wrong_contact", -20)
                    signals.append(f"wrong_contact:{points}")
                elif "competitor" in kw:
                    points = negative_weights.get("competitor", -15)
                    signals.append(f"competitor:{points}")
                else:
                    points = -10
                    signals.append(f"negative_keyword:{kw}:{points}")
                score += points
                break  # Only count one negative signal
        
        return score, signals
    
    def _check_fast_track_rules(
        self,
        lead_source: str,
        email_direction: str,
        score: int,
        signals: List[str]
    ) -> Tuple[bool, str]:
        """Check if any fast-track rule matches."""
        for rule in self.config.fast_track_rules:
            rule_name = rule.get("name", "")
            min_score = rule.get("min_score", 0)
            conditions = rule.get("conditions", [])
            signals_required = rule.get("signals_required", [])
            
            if score < min_score:
                continue
            
            # Check conditions
            conditions_met = True
            for cond in conditions:
                if "lead_source" in cond and cond["lead_source"] != lead_source:
                    conditions_met = False
                    break
                if "email_direction" in cond and cond["email_direction"] != email_direction:
                    conditions_met = False
                    break
            
            if not conditions_met:
                continue
            
            # Check required signals
            if signals_required:
                signal_names = [s.split(":")[0] for s in signals]
                if not any(req in signal_names for req in signals_required):
                    continue
            
            # Rule matched!
            return True, rule.get("description", rule_name)
        
        # Also check if score exceeds fast_track threshold
        if score >= self.config.thresholds.get("fast_track", 85):
            return True, f"Score {score} exceeds fast-track threshold"
        
        return False, ""
    
    def _is_ambiguous(self, score: int) -> bool:
        """Check if score is in ambiguous range requiring LLM."""
        if not self.config.llm_fallback.get("enabled", False):
            return False
        
        ambiguous = self.config.llm_fallback.get("ambiguous_range", {})
        min_score = ambiguous.get("min", 40)
        max_score = ambiguous.get("max", 69)
        
        return min_score <= score <= max_score
    
    def _llm_evaluate(
        self,
        lead_data: Dict[str, Any],
        conversation_history: List[Dict[str, Any]],
        email_classification: Dict[str, Any],
        current_score: int
    ) -> Optional[Dict[str, Any]]:
        """Use LLM to evaluate ambiguous cases."""
        if not self.config.llm_fallback.get("enabled", False):
            return None
        
        try:
            from langchain_openai import ChatOpenAI
            import json
            
            if self._llm is None:
                model = self.config.llm_fallback.get("model", "gpt-4o-mini")
                temperature = self.config.llm_fallback.get("temperature", 0.1)
                max_tokens = self.config.llm_fallback.get("max_tokens")
                if max_tokens is not None:
                    self._llm = ChatOpenAI(model=model, temperature=temperature, max_tokens=max_tokens)
                else:
                    self._llm = ChatOpenAI(model=model, temperature=temperature)
            
            # Build prompt
            prompt_template = self.config.llm_fallback.get("prompt_template", "")
            
            lead_profile = "\n".join(
                f"- {k}: {v}" for k, v in lead_data.items() 
                if v and k not in ["metadata", "enrichment_data"]
            )
            
            conv_lines = []
            for msg in conversation_history[-5:]:  # Last 5 messages
                direction = msg.get("direction", "unknown")
                content = (msg.get("content") or msg.get("text_content") or "")[:500]
                conv_lines.append(f"[{direction.upper()}] {content}")
            conversation_text = "\n".join(conv_lines) or "No conversation history"
            
            classification_text = "\n".join(
                f"- {k}: {v}" for k, v in email_classification.items() if v
            ) or "No classification available"
            
            prompt = prompt_template.format(
                lead_profile=lead_profile,
                conversation_history=conversation_text,
                email_classification=classification_text,
                current_score=current_score
            )
            
            response = self._llm.invoke(prompt)
            content = response.content
            
            # Parse JSON response
            # Try to extract JSON from the response
            json_match = re.search(r'\{[^}]+\}', content, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                return {
                    "decision": result.get("decision", "nurture"),
                    "score_adjustment": int(result.get("score_adjustment", 0)),
                    "reasoning": result.get("reasoning", ""),
                    "confidence": float(result.get("confidence", 0.7))
                }
            
        except Exception as e:
            logger.warning(f"LLM evaluation failed: {e}")
        
        return None
    
    def _make_decision(self, score: int, fast_track: bool) -> Tuple[str, bool]:
        """Make final qualification decision based on score."""
        thresholds = self.config.thresholds
        
        if fast_track:
            return "fast_track", True
        
        if score >= thresholds.get("auto_promote", 70):
            return "qualified", True
        
        if score <= thresholds.get("disqualify", 20):
            return "disqualified", False
        
        return "nurture", False
    
    def _build_reasoning(self, signals: List[str], decision: str) -> str:
        """Build human-readable reasoning from signals."""
        if decision == "qualified":
            positive = [s for s in signals if "+" in s]
            if positive:
                top_signals = positive[:3]
                return f"Qualified based on: {', '.join(s.split(':')[0] for s in top_signals)}"
            return "Score exceeds qualification threshold"
        
        if decision == "disqualified":
            negative = [s for s in signals if "-" in s]
            if negative:
                return f"Disqualified due to: {', '.join(s.split(':')[0] for s in negative)}"
            return "Score below minimum threshold"
        
        return "Needs more engagement before qualification decision"


# Convenience function for sync contexts
def score_lead_sync(
    lead_data: Dict[str, Any],
    conversation_history: Optional[List[Dict[str, Any]]] = None,
    email_classification: Optional[Dict[str, Any]] = None,
    lead_source: str = "new",
    email_direction: str = "inbound",
    config_path: Optional[str] = None
) -> QualificationResult:
    """Synchronous wrapper for lead scoring.

    Safe to call from within an already-running event loop.

    Notes:
    - This wrapper forces rules-only scoring (no LLM) to keep it deterministic and
      side-effect free inside orchestrator runtime paths.
    """
    scorer = QualificationScorer(config_path=config_path)
    
    # Disable LLM for sync version
    scorer.config.llm_fallback["enabled"] = False

    return scorer.score(
        lead_data=lead_data,
        conversation_history=conversation_history,
        email_classification=email_classification,
        lead_source=lead_source,
        email_direction=email_direction,
    )
