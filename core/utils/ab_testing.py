"""A/B Testing framework for variant assignment and conversion tracking.

Provides:
- Deterministic variant assignment based on lead ID and experiment key
- Bucketing strategies (traffic split, weighted, sequential)
- Conversion tracking and result aggregation
- Statistical significance calculation
- Experiment lifecycle management
"""
from __future__ import annotations

from typing import Any, Dict, Optional, List, Tuple
from pydantic import BaseModel, Field, validator
from enum import Enum
from datetime import datetime, timedelta
import hashlib
import json


class BucketStrategy(str, Enum):
    """Variant bucketing strategies"""
    TRAFFIC_SPLIT = "traffic_split"  # Even distribution
    WEIGHTED = "weighted"  # Custom weight per variant
    SEQUENTIAL = "sequential"  # Ramp up: 10% A, then 50%, then 100%


class ConversionEvent(str, Enum):
    """Types of conversion events to track"""
    SENT = "sent"  # Email sent
    OPENED = "opened"  # Email opened
    CLICKED = "clicked"  # Link clicked
    REPLIED = "replied"  # Lead replied
    MEETING = "meeting"  # Meeting booked
    CONVERTED = "converted"  # Purchase/signup
    UNSUBSCRIBED = "unsubscribed"  # Opted out
    BOUNCED = "bounced"  # Delivery failed


class ExperimentStatus(str, Enum):
    """Experiment lifecycle status"""
    DRAFT = "draft"  # Not yet started
    RUNNING = "running"  # Active
    PAUSED = "paused"  # Paused mid-experiment
    COMPLETED = "completed"  # Finished
    ARCHIVED = "archived"  # Historical


class VariantConfig(BaseModel):
    """Configuration for an experiment variant"""
    name: str = Field(..., description="Variant identifier (e.g., 'A', 'B', 'control')")
    weight: float = Field(default=1.0, ge=0.0, le=1.0, description="Traffic weight (0-1)")
    template: str = Field(..., description="Copy template for this variant")
    tone: str = Field(..., description="Copy tone for this variant")
    description: Optional[str] = Field(None, description="Variant description")
    
    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "name": "A",
                    "weight": 0.5,
                    "template": "cold_email",
                    "tone": "professional",
                    "description": "Standard professional tone"
                },
                {
                    "name": "B",
                    "weight": 0.5,
                    "template": "cold_email",
                    "tone": "casual",
                    "description": "Casual, friendly tone"
                }
            ]
        }


class ExperimentConfig(BaseModel):
    """Configuration for an A/B test experiment"""
    experiment_id: str = Field(..., description="Unique experiment identifier")
    name: str = Field(..., description="Human-readable experiment name")
    hypothesis: str = Field(..., description="Expected outcome/hypothesis")
    variants: List[VariantConfig] = Field(..., min_items=2, description="List of variants (min 2)")
    bucketing_strategy: BucketStrategy = Field(default=BucketStrategy.TRAFFIC_SPLIT)
    start_date: datetime = Field(..., description="Experiment start date")
    end_date: Optional[datetime] = Field(None, description="Planned end date")
    min_sample_size: int = Field(default=100, ge=10, description="Min samples per variant")
    significance_threshold: float = Field(default=0.95, ge=0.90, le=0.99, description="95% confidence")
    campaign_id: Optional[str] = Field(None, description="Associated campaign")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Custom metadata")
    
    @validator('variants')
    def validate_weights_sum(cls, v):
        """Ensure weights sum to approximately 1.0"""
        total_weight = sum(variant.weight for variant in v)
        if not (0.99 <= total_weight <= 1.01):
            raise ValueError(f"Variant weights must sum to 1.0 (got {total_weight})")
        return v
    
    @validator('end_date')
    def validate_end_after_start(cls, v, values):
        """Ensure end date is after start date"""
        if v and 'start_date' in values:
            if v <= values['start_date']:
                raise ValueError("end_date must be after start_date")
        return v
    
    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "experiment_id": "exp-tone-2024",
                    "name": "Professional vs Casual Tone Test",
                    "hypothesis": "Casual tone increases open rates by 15%",
                    "variants": [
                        {
                            "name": "A",
                            "weight": 0.5,
                            "template": "cold_email",
                            "tone": "professional"
                        },
                        {
                            "name": "B",
                            "weight": 0.5,
                            "template": "cold_email",
                            "tone": "casual"
                        }
                    ],
                    "bucketing_strategy": "traffic_split",
                    "start_date": "2024-01-15T00:00:00Z",
                    "end_date": "2024-02-15T00:00:00Z",
                    "min_sample_size": 500,
                    "significance_threshold": 0.95,
                    "campaign_id": "camp-123"
                }
            ]
        }


class ConversionRecord(BaseModel):
    """Record of a conversion event"""
    lead_id: str = Field(..., description="Lead who converted")
    experiment_id: str = Field(..., description="Experiment ID")
    variant: str = Field(..., description="Variant assigned")
    event_type: ConversionEvent = Field(..., description="Type of conversion")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    value: Optional[float] = Field(None, description="Conversion value (e.g., revenue)")
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "lead_id": "lead-123",
                    "experiment_id": "exp-tone-2024",
                    "variant": "A",
                    "event_type": "opened",
                    "timestamp": "2024-01-20T10:30:00Z",
                    "value": None
                }
            ]
        }


class VariantStats(BaseModel):
    """Statistics for a variant"""
    variant: str
    sample_size: int = 0
    conversions: Dict[ConversionEvent, int] = Field(default_factory=dict)
    conversion_rates: Dict[ConversionEvent, float] = Field(default_factory=dict)
    confidence_interval: Optional[Tuple[float, float]] = None
    is_significant: bool = False
    
    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "variant": "A",
                    "sample_size": 500,
                    "conversions": {
                        "sent": 500,
                        "opened": 285,
                        "clicked": 45
                    },
                    "conversion_rates": {
                        "sent": 1.0,
                        "opened": 0.57,
                        "clicked": 0.09
                    },
                    "confidence_interval": [0.52, 0.62],
                    "is_significant": True
                }
            ]
        }


class ExperimentResults(BaseModel):
    """Results and analysis of an experiment"""
    experiment_id: str
    status: ExperimentStatus
    variants_stats: List[VariantStats] = Field(..., description="Stats per variant")
    winner: Optional[str] = Field(None, description="Winning variant if significant")
    lift: Optional[float] = Field(None, description="Improvement of winner vs baseline (%)")
    recommendation: Optional[str] = Field(None, description="Action recommendation")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "experiment_id": "exp-tone-2024",
                    "status": "completed",
                    "variants_stats": [
                        {
                            "variant": "A",
                            "sample_size": 500,
                            "conversions": {"opened": 285},
                            "conversion_rates": {"opened": 0.57},
                            "is_significant": False
                        },
                        {
                            "variant": "B",
                            "sample_size": 500,
                            "conversions": {"opened": 328},
                            "conversion_rates": {"opened": 0.656},
                            "is_significant": True
                        }
                    ],
                    "winner": "B",
                    "lift": 15.1,
                    "recommendation": "Roll out variant B to all campaigns"
                }
            ]
        }


# ============ Core Functions ============

def assign_variant(
    lead_id: str,
    experiment_id: str,
    variants: List[VariantConfig],
    strategy: BucketStrategy = BucketStrategy.TRAFFIC_SPLIT
) -> str:
    """
    Deterministically assign a lead to a variant using consistent hashing.
    
    Args:
        lead_id: Lead identifier
        experiment_id: Experiment identifier
        variants: List of variant configs with weights
        strategy: Bucketing strategy (currently only TRAFFIC_SPLIT implemented)
    
    Returns:
        Assigned variant name
    
    Example:
        variant = assign_variant("lead-123", "exp-tone-2024", variants)
        # Returns "A" or "B" based on consistent hash
    """
    if not variants:
        raise ValueError("At least one variant required")
    
    # Create deterministic hash from lead_id + experiment_id
    hash_input = f"{lead_id}:{experiment_id}".encode('utf-8')
    hash_value = int(hashlib.md5(hash_input).hexdigest(), 16)
    
    # Normalize to 0-1 range
    bucket = (hash_value % 10000) / 10000.0
    
    # Assign to variant based on cumulative weights
    cumulative_weight = 0.0
    for variant in variants:
        cumulative_weight += variant.weight
        if bucket < cumulative_weight:
            return variant.name
    
    # Fallback to last variant
    return variants[-1].name


def track_conversion(
    lead_id: str,
    experiment_id: str,
    variant: str,
    event_type: ConversionEvent,
    value: Optional[float] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> ConversionRecord:
    """
    Record a conversion event for tracking and analysis.
    
    Args:
        lead_id: Lead who converted
        experiment_id: Associated experiment
        variant: Variant assigned to this lead
        event_type: Type of conversion event
        value: Optional value (e.g., revenue)
        metadata: Custom metadata
    
    Returns:
        ConversionRecord
    
    Example:
        record = track_conversion(
            lead_id="lead-123",
            experiment_id="exp-tone-2024",
            variant="A",
            event_type=ConversionEvent.OPENED
        )
    """
    return ConversionRecord(
        lead_id=lead_id,
        experiment_id=experiment_id,
        variant=variant,
        event_type=event_type,
        value=value,
        metadata=metadata or {}
    )


def calculate_conversion_rate(
    conversions: Dict[str, int],
    event_type: ConversionEvent,
    total_sample: int
) -> float:
    """
    Calculate conversion rate for an event type.
    
    Args:
        conversions: Dict of event_type -> count
        event_type: Event to calculate rate for
        total_sample: Total sample size
    
    Returns:
        Conversion rate (0-1)
    """
    if total_sample == 0:
        return 0.0
    
    count = conversions.get(event_type.value, 0)
    return count / total_sample


def calculate_confidence_interval(
    conversion_rate: float,
    sample_size: int,
    confidence: float = 0.95
) -> Tuple[float, float]:
    """
    Calculate 95% confidence interval for conversion rate using normal approximation.
    
    Args:
        conversion_rate: Observed conversion rate (0-1)
        sample_size: Sample size
        confidence: Confidence level (0.90-0.99)
    
    Returns:
        (lower_bound, upper_bound) tuple
    """
    if sample_size < 30:
        return (0.0, 1.0)  # Insufficient data
    
    # Z-score for 95% confidence = 1.96
    z_score = 1.96 if confidence == 0.95 else 2.576
    
    margin_of_error = z_score * (
        (conversion_rate * (1 - conversion_rate) / sample_size) ** 0.5
    )
    
    lower = max(0.0, conversion_rate - margin_of_error)
    upper = min(1.0, conversion_rate + margin_of_error)
    
    return (lower, upper)


def is_statistically_significant(
    control_rate: float,
    variant_rate: float,
    control_sample: int,
    variant_sample: int,
    confidence: float = 0.95
) -> bool:
    """
    Determine if difference between two conversion rates is statistically significant.
    
    Uses two-proportion z-test.
    
    Args:
        control_rate: Control variant conversion rate
        variant_rate: Test variant conversion rate
        control_sample: Control sample size
        variant_sample: Variant sample size
        confidence: Confidence level
    
    Returns:
        True if significant at given confidence level
    """
    if control_sample < 30 or variant_sample < 30:
        return False  # Insufficient data
    
    # Pooled proportion
    p_pool = (
        (control_rate * control_sample + variant_rate * variant_sample) /
        (control_sample + variant_sample)
    )
    
    # Standard error
    se = (p_pool * (1 - p_pool) * (1/control_sample + 1/variant_sample)) ** 0.5
    
    if se == 0:
        return False
    
    # Z-statistic
    z = (variant_rate - control_rate) / se
    
    # Critical z-value for 95% confidence (two-tailed) = 1.96
    z_critical = 1.96 if confidence == 0.95 else 2.576
    
    return abs(z) > z_critical


# ============ Storage & Retrieval (Placeholder) ============

class ABTestingStore:
    """Placeholder for experiment and conversion data storage.
    
    In production, this would persist to:
    - Redis Hashes for experiment config
    - PostgreSQL for conversion records
    - Redis HyperLogLog for unique lead counting
    """
    
    def __init__(self):
        self._experiments: Dict[str, ExperimentConfig] = {}
        self._conversions: List[ConversionRecord] = []
    
    def save_experiment(self, config: ExperimentConfig) -> None:
        """Save experiment configuration"""
        self._experiments[config.experiment_id] = config
    
    def get_experiment(self, experiment_id: str) -> Optional[ExperimentConfig]:
        """Retrieve experiment configuration"""
        return self._experiments.get(experiment_id)
    
    def record_conversion(self, record: ConversionRecord) -> None:
        """Record conversion event"""
        self._conversions.append(record)
    
    def get_conversions(
        self,
        experiment_id: str,
        event_type: Optional[ConversionEvent] = None,
        variant: Optional[str] = None
    ) -> List[ConversionRecord]:
        """Retrieve conversion records with optional filtering"""
        results = [
            c for c in self._conversions
            if c.experiment_id == experiment_id
        ]
        
        if event_type:
            results = [c for c in results if c.event_type == event_type]
        
        if variant:
            results = [c for c in results if c.variant == variant]
        
        return results
    
    def calculate_results(
        self,
        experiment_id: str,
        event_type: ConversionEvent = ConversionEvent.OPENED,
        control_variant: str = "A"
    ) -> ExperimentResults:
        """Calculate experiment results and statistics"""
        experiment = self.get_experiment(experiment_id)
        if not experiment:
            raise ValueError(f"Experiment {experiment_id} not found")
        
        conversions = self.get_conversions(experiment_id)
        
        # Group by variant
        variant_conversions: Dict[str, List[ConversionRecord]] = {}
        for variant_config in experiment.variants:
            variant_conversions[variant_config.name] = [
                c for c in conversions if c.variant == variant_config.name
            ]
        
        # Calculate stats per variant
        variants_stats = []
        for variant_config in experiment.variants:
            variant_records = variant_conversions[variant_config.name]
            sample_size = len(set(c.lead_id for c in variant_records))
            
            event_counts = {}
            for event in ConversionEvent:
                count = sum(
                    1 for c in variant_records if c.event_type == event
                )
                event_counts[event.value] = count
            
            rate = calculate_conversion_rate(
                event_counts, event_type, sample_size
            )
            
            ci = calculate_confidence_interval(rate, sample_size)
            
            stats = VariantStats(
                variant=variant_config.name,
                sample_size=sample_size,
                conversions={event.value: event_counts.get(event.value, 0) for event in ConversionEvent},
                conversion_rates={event.value: calculate_conversion_rate(event_counts, event, sample_size) for event in ConversionEvent},
                confidence_interval=ci,
                is_significant=False  # Will update below
            )
            variants_stats.append(stats)
        
        # Determine winner
        winner = None
        max_rate = 0.0
        control_stats = next((s for s in variants_stats if s.variant == control_variant), None)
        control_rate = control_stats.conversion_rates.get(event_type.value, 0.0) if control_stats else 0.0
        control_sample = control_stats.sample_size if control_stats else 0
        
        for stats in variants_stats:
            if stats.variant == control_variant:
                continue
            
            variant_rate = stats.conversion_rates.get(event_type.value, 0.0)
            is_sig = is_statistically_significant(
                control_rate,
                variant_rate,
                control_sample,
                stats.sample_size
            )
            
            stats.is_significant = is_sig
            
            if is_sig and variant_rate > max_rate:
                max_rate = variant_rate
                winner = stats.variant
        
        # Calculate lift
        lift = None
        if winner and control_stats:
            winner_rate = next(
                (s.conversion_rates.get(event_type.value, 0.0) for s in variants_stats if s.variant == winner),
                0.0
            )
            if control_rate > 0:
                lift = ((winner_rate - control_rate) / control_rate) * 100
        
        # Generate recommendation
        recommendation = None
        if winner:
            recommendation = f"Variant {winner} showed {lift:.1f}% improvement. Consider rolling out to all campaigns."
        elif any(s.is_significant for s in variants_stats):
            recommendation = "Experiment inconclusive. Continue testing."
        else:
            recommendation = "No significant differences detected. Consider larger sample size or longer duration."
        
        return ExperimentResults(
            experiment_id=experiment_id,
            status=ExperimentStatus.COMPLETED,
            variants_stats=variants_stats,
            winner=winner,
            lift=lift,
            recommendation=recommendation
        )


# ============ Example Usage ============

if __name__ == "__main__":
    # Create experiment config
    config = ExperimentConfig(
        experiment_id="exp-tone-2024",
        name="Professional vs Casual Tone",
        hypothesis="Casual tone increases open rates",
        variants=[
            VariantConfig(name="A", weight=0.5, template="cold_email", tone="professional"),
            VariantConfig(name="B", weight=0.5, template="cold_email", tone="casual"),
        ],
        start_date=datetime.utcnow(),
    )
    
    # Assign variant
    variant_a = assign_variant("lead-123", "exp-tone-2024", config.variants)
    variant_b = assign_variant("lead-456", "exp-tone-2024", config.variants)
    print(f"Lead 123 -> {variant_a}, Lead 456 -> {variant_b}")
    
    # Store experiment
    store = ABTestingStore()
    store.save_experiment(config)
    
    # Track conversions
    store.record_conversion(ConversionRecord(
        lead_id="lead-123",
        experiment_id="exp-tone-2024",
        variant="A",
        event_type=ConversionEvent.OPENED
    ))
    
    # Calculate results
    results = store.calculate_results("exp-tone-2024", ConversionEvent.OPENED)
    print(json.dumps(results.model_dump(default=str), indent=2))
