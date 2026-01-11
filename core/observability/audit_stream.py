"""
Redis Streams audit trail writer
"""

import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class AuditStreamWriter:
    """Write decision audit trail to Redis Streams"""
    
    def __init__(self, redis_client: Optional[Any] = None):
        self.redis = redis_client
        self.enabled = redis_client is not None
    
    def write(
        self,
        tier: str,
        tenant_id: str,
        execution_id: str,
        data: Dict[str, Any]
    ):
        """Write audit entry to Redis stream"""
        if not self.enabled:
            return
        
        try:
            # Stream naming: {tier}:decisions:{tenant_id}:{date}
            date_key = datetime.now().strftime("%Y-%m-%d")
            stream_name = f"{tier}:decisions:{tenant_id}:{date_key}"
            
            # Prepare entry
            entry = {
                "data": json.dumps(data),
                "execution_id": execution_id,
                "timestamp": datetime.utcnow().isoformat() + "Z",
            }
            
            # Write to stream
            self.redis.xadd(stream_name, entry, maxlen=10000)  # Keep last 10K entries
            
            # Set expiration (7 days)
            self.redis.expire(stream_name, 60 * 60 * 24 * 7)
            
        except Exception as e:
            logger.warning(f"Failed to write audit stream: {e}")
