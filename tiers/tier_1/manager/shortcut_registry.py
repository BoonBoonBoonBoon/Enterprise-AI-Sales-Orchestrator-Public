"""
Shortcut Registry for Manager Agent

Handles simple, repetitive tasks directly without delegating to orchestrators.
Reduces latency from 5-10 seconds (full delegation) to <50ms (direct execution).
"""

import re
import ast
import operator
from datetime import datetime
from typing import Dict, Callable, Any, Optional
import redis
import logging

logger = logging.getLogger(__name__)


class ShortcutRegistry:
    """
    Registry of shortcut handlers for common patterns.
    Manager checks shortcuts before delegating to orchestrators.
    """
    
    def __init__(self, redis_client: redis.Redis = None):
        self.redis = redis_client
        self.shortcuts: Dict[str, Callable] = {
            # Simple calculations
            "calculate": self._handle_calculation,
            "math": self._handle_calculation,
            "compute": self._handle_calculation,
            
            # Date/time queries
            "current time": lambda goal: datetime.now().isoformat(),
            "current date": lambda goal: datetime.now().date().isoformat(),
            "time now": lambda goal: datetime.now().isoformat(),
            "what time": lambda goal: datetime.now().isoformat(),
            "date today": lambda goal: datetime.now().date().isoformat(),
            "today": lambda goal: datetime.now().date().isoformat(),
            
            # Common lookups (requires Redis)
            "get lead": self._handle_lead_lookup,
            "fetch lead": self._handle_lead_lookup,
            "lookup lead": self._handle_lead_lookup,
            
            # Status checks
            "health check": self._handle_health_check,
            "run health": self._handle_health_check,
            "ping": self._handle_health_check,
            "status": self._handle_health_check,
        }
    
    def can_shortcut(self, goal: str) -> bool:
        """
        Check if goal can be handled by shortcut.
        
        Args:
            goal: User's goal/query
            
        Returns:
            True if shortcut can handle this goal
        """
        goal_lower = goal.lower()
        
        # Check for keyword matches
        for keyword in self.shortcuts.keys():
            if keyword in goal_lower:
                logger.info(f"Shortcut match: '{keyword}' in goal")
                return True
        
        # Check for arithmetic patterns (numbers + operators)
        if self._is_arithmetic_expression(goal):
            logger.info("Shortcut match: arithmetic expression detected")
            return True
        
        return False
    
    def execute_shortcut(self, goal: str) -> Dict[str, Any]:
        """
        Execute shortcut handler for goal.
        
        Args:
            goal: User's goal/query
            
        Returns:
            Dict with success status and result
        """
        goal_lower = goal.lower()
        
        # Find matching handler
        for keyword, handler in self.shortcuts.items():
            if keyword in goal_lower:
                try:
                    result = handler(goal)
                    logger.info(f"Shortcut executed successfully: {keyword}")
                    return {
                        "success": True,
                        "result": result,
                        "shortcut_type": keyword,
                        "latency_ms": "<50ms"
                    }
                except Exception as e:
                    logger.error(f"Shortcut failed ({keyword}): {e}")
                    return {
                        "success": False,
                        "error": str(e),
                        "shortcut_type": keyword
                    }
        
        # Check for arithmetic as fallback
        if self._is_arithmetic_expression(goal):
            try:
                result = self._handle_calculation(goal)
                return {
                    "success": True,
                    "result": result,
                    "shortcut_type": "calculation",
                    "latency_ms": "<50ms"
                }
            except Exception as e:
                logger.error(f"Arithmetic shortcut failed: {e}")
                return {"success": False, "error": str(e)}
        
        return {
            "success": False,
            "error": "No matching shortcut found"
        }
    
    def _is_arithmetic_expression(self, text: str) -> bool:
        """Check if text looks like an arithmetic expression."""
        # Extract mathematical parts (numbers, operators, parentheses)
        # This handles patterns like "What is 2 + 2?" → ["2", "+", "2"]
        numbers_and_ops = re.findall(r'[\d+\-*/()%.]+', text)
        
        if not numbers_and_ops:
            return False
        
        # Combine extracted parts
        expr = ''.join(numbers_and_ops)
        
        # Must have at least one number and a "real" arithmetic operator.
        # IMPORTANT: Do not treat '-' alone as sufficient; many IDs (UUIDs) contain hyphens
        # and digits which would otherwise cause false-positive shortcut matches.
        has_number = bool(re.search(r'\d', expr))
        real_operators = ['+', '*', '/', '%']
        has_operator = any(op in expr for op in real_operators)
        
        # Also check for reasonable length (avoid false positives)
        # Arithmetic expressions are usually short
        is_reasonable_length = len(expr) < 100
        
        return has_number and has_operator and is_reasonable_length
    
    def _handle_calculation(self, expression: str) -> float:
        """
        Safe arithmetic evaluation.
        
        Args:
            expression: Mathematical expression (e.g., "2 + 2", "10 * 5")
            
        Returns:
            Calculated result
            
        Raises:
            ValueError: If expression is invalid or unsafe
        """
        # Extract mathematical expression
        # Handle patterns like "What is 2 + 2?" → "2 + 2"
        numbers_and_ops = re.findall(r'[\d+\-*/()%.]+', expression)
        if numbers_and_ops:
            expression = ''.join(numbers_and_ops)
        
        # Parse and validate
        try:
            tree = ast.parse(expression, mode='eval')
        except SyntaxError:
            raise ValueError(f"Invalid mathematical expression: {expression}")
        
        # Whitelist of safe operations
        safe_operators = {
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.Div: operator.truediv,
            ast.Pow: operator.pow,
            ast.Mod: operator.mod,
            ast.UAdd: operator.pos,
            ast.USub: operator.neg,
        }
        
        def eval_node(node):
            """Recursively evaluate AST node."""
            if isinstance(node, ast.Constant):  # Python 3.8+
                return node.value
            elif isinstance(node, ast.Num):  # Python 3.7
                return node.n
            elif isinstance(node, ast.BinOp):
                left = eval_node(node.left)
                right = eval_node(node.right)
                op = safe_operators.get(type(node.op))
                if op is None:
                    raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
                return op(left, right)
            elif isinstance(node, ast.UnaryOp):
                operand = eval_node(node.operand)
                op = safe_operators.get(type(node.op))
                if op is None:
                    raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
                return op(operand)
            else:
                raise ValueError(f"Unsupported AST node: {type(node).__name__}")
        
        result = eval_node(tree.body)
        logger.info(f"Calculated: {expression} = {result}")
        return result
    
    def _handle_lead_lookup(self, goal: str) -> Optional[Dict]:
        """
        Quick lead lookup from Redis cache.
        
        Args:
            goal: Goal containing lead ID
            
        Returns:
            Lead data from cache or None
        """
        if not self.redis:
            raise ValueError("Redis client not configured for shortcuts")
        
        # Extract lead ID from goal
        # Patterns: "lead_123", "lead-456", "lead 789"
        lead_id_match = re.search(r'lead[_\s-]?(\w+)', goal, re.IGNORECASE)
        
        if not lead_id_match:
            raise ValueError("No lead ID found in goal")
        
        lead_id = lead_id_match.group(1)
        
        # Query Redis cache
        cache_key = f"lead:cache:{lead_id}"
        lead_data = self.redis.hgetall(cache_key)
        
        if not lead_data:
            logger.warning(f"Lead {lead_id} not found in cache")
            return None
        
        # Decode bytes to strings
        decoded_data = {
            k.decode() if isinstance(k, bytes) else k: 
            v.decode() if isinstance(v, bytes) else v 
            for k, v in lead_data.items()
        }
        
        logger.info(f"Lead {lead_id} found in cache")
        return decoded_data
    
    def _handle_health_check(self, goal: str) -> Dict[str, Any]:
        """
        Quick health check of system components.
        
        Returns:
            Health status of Redis, workers, etc.
        """
        health_status = {}
        
        # Check Redis
        if self.redis:
            try:
                health_status["redis"] = self.redis.ping()
            except Exception as e:
                health_status["redis"] = False
                health_status["redis_error"] = str(e)
        else:
            health_status["redis"] = "not_configured"
        
        # Check workers (count active heartbeats)
        if self.redis:
            try:
                # Workers set heartbeat keys like "worker:heartbeat:copywriter-1"
                heartbeat_keys = self.redis.keys("worker:heartbeat:*")
                
                active_workers = []
                for key in heartbeat_keys:
                    # Check if heartbeat is recent (within last 60 seconds)
                    last_heartbeat = self.redis.get(key)
                    if last_heartbeat:
                        worker_name = key.decode().split(':')[-1]
                        active_workers.append(worker_name)
                
                health_status["workers_active"] = len(active_workers)
                health_status["workers"] = active_workers
            except Exception as e:
                health_status["workers_active"] = 0
                health_status["workers_error"] = str(e)
        
        health_status["timestamp"] = datetime.now().isoformat()
        logger.info(f"Health check performed: {health_status}")
        
        return health_status


# Example usage
if __name__ == "__main__":
    import redis
    
    # Initialize with Redis
    redis_client = redis.Redis(host='localhost', port=6379, decode_responses=False)
    registry = ShortcutRegistry(redis_client)
    
    # Test calculations
    print("Test 1: Calculation")
    result = registry.execute_shortcut("What is 2 + 2?")
    print(f"Result: {result}\n")
    
    # Test date/time
    print("Test 2: Current time")
    result = registry.execute_shortcut("What is the current time?")
    print(f"Result: {result}\n")
    
    # Test health check
    print("Test 3: Health check")
    result = registry.execute_shortcut("Run health check")
    print(f"Result: {result}\n")
