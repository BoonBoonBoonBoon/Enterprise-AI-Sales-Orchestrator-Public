"""
In-Memory Quota Manager

Simple in-memory quota tracking with time windows.
Good for: Development, testing, single-process applications

Features:
- No external dependencies
- Simple time-window based limiting
- Single process only (not distributed)
"""

import logging
import time
from collections import defaultdict
from typing import Dict

from core.harness.interfaces import IQuotaManager

logger = logging.getLogger(__name__)


class InMemoryQuota(IQuotaManager):
    """
    In-memory quota manager (simple time window).
    
    Tracks execution count per agent in rolling time windows.
    NOT suitable for production with multiple workers.
    
    Example:
        # Allow 1000 requests per hour
        quota = InMemoryQuota(
            requests_per_hour=1000,
            window_seconds=3600
        )
        
        # Check if execution allowed
        if await quota.can_execute("LeadsOrchestrator"):
            # Execute task
            await quota.record_execution("LeadsOrchestrator")
        else:
            raise QuotaExceededError("Rate limit exceeded")
    """
    
    def __init__(
        self,
        requests_per_hour: int = 1000,
        window_seconds: int = 3600
    ):
        """
        Initialize in-memory quota manager.
        
        Args:
            requests_per_hour: Maximum requests per hour
            window_seconds: Time window in seconds (default: 3600 = 1 hour)
        """
        self.requests_per_hour = requests_per_hour
        self.window_seconds = window_seconds
        
        # Track executions per agent: {agent_id: [(timestamp, count), ...]}
        self.executions: Dict[str, list] = defaultdict(list)
        
        logger.info(
            f"InMemoryQuota initialized: {requests_per_hour} requests per "
            f"{window_seconds}s window"
        )
    
    def _cleanup_old_executions(self, agent_id: str, now: float) -> None:
        """
        Remove executions outside the time window.
        
        Args:
            agent_id: Agent identifier
            now: Current timestamp
        """
        cutoff = now - self.window_seconds
        self.executions[agent_id] = [
            (ts, count) for ts, count in self.executions[agent_id]
            if ts >= cutoff
        ]
    
    def _count_recent_executions(self, agent_id: str) -> int:
        """
        Count executions within the time window.
        
        Args:
            agent_id: Agent identifier
        
        Returns:
            Number of executions in current window
        """
        return sum(count for _, count in self.executions[agent_id])
    
    async def can_execute(self, agent_id: str) -> bool:
        """
        Check if agent can execute (has quota).
        
        Args:
            agent_id: Agent identifier
        
        Returns:
            True if execution allowed, False otherwise
        """
        now = time.time()
        
        # Cleanup old executions
        self._cleanup_old_executions(agent_id, now)
        
        # Count recent executions
        recent_count = self._count_recent_executions(agent_id)
        
        # Check quota
        if recent_count < self.requests_per_hour:
            logger.debug(
                f"Quota check passed for {agent_id}: "
                f"{recent_count}/{self.requests_per_hour} requests"
            )
            return True
        else:
            logger.warning(
                f"Quota exceeded for {agent_id}: "
                f"{recent_count}/{self.requests_per_hour} requests"
            )
            return False
    
    async def record_execution(self, agent_id: str) -> None:
        """
        Record execution (increment counter).
        
        Args:
            agent_id: Agent identifier
        """
        now = time.time()
        self.executions[agent_id].append((now, 1))
        
        logger.debug(f"Execution recorded for {agent_id}")
    
    async def get_remaining_quota(self, agent_id: str) -> Dict[str, float]:
        """
        Get remaining quota for agent.
        
        Args:
            agent_id: Agent identifier
        
        Returns:
            Dictionary with 'remaining' and 'total'
        """
        now = time.time()
        
        # Cleanup old executions
        self._cleanup_old_executions(agent_id, now)
        
        # Count recent executions
        recent_count = self._count_recent_executions(agent_id)
        remaining = max(0, self.requests_per_hour - recent_count)
        
        return {
            'remaining': remaining,
            'total': self.requests_per_hour,
            'used': recent_count,
            'percentage': (remaining / self.requests_per_hour) * 100
        }
    
    def __repr__(self) -> str:
        """String representation for debugging"""
        return (
            f"InMemoryQuota(requests_per_hour={self.requests_per_hour}, "
            f"window={self.window_seconds}s)"
        )
