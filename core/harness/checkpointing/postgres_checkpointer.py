"""
PostgreSQL Checkpointer

Stores checkpoints in PostgreSQL database.
Good for: Analytics, queryable storage, relational queries

Features:
- SQL queries for analysis
- Relational joins with other data
- Forever retention (until manually deleted)
- Full-text search on checkpoint data

Installation:
    pip install asyncpg
"""

import json
import logging
from typing import Dict, Any, Optional

from core.harness.interfaces import ICheckpointer, CheckpointError

logger = logging.getLogger(__name__)

# Try to import asyncpg (optional dependency)
try:
    import asyncpg
    
    ASYNCPG_AVAILABLE = True
except ImportError:
    ASYNCPG_AVAILABLE = False
    logger.warning("asyncpg not installed. Install with: pip install asyncpg")


class PostgreSQLCheckpointer(ICheckpointer):
    """
    PostgreSQL-based checkpointing (queryable, analytics).
    
    Stores execution state in PostgreSQL for analysis and reporting.
    Perfect for analytics workloads and complex queries.
    
    Requires installation:
        pip install asyncpg
    
    Database Schema:
        CREATE TABLE checkpoints (
            execution_id VARCHAR(255) PRIMARY KEY,
            state JSONB NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
            agent_type VARCHAR(255),
            tenant_id VARCHAR(255)
        );
        
        CREATE INDEX idx_checkpoints_created_at ON checkpoints(created_at);
        CREATE INDEX idx_checkpoints_agent_type ON checkpoints(agent_type);
        CREATE INDEX idx_checkpoints_tenant_id ON checkpoints(tenant_id);
    
    Example:
        checkpointer = PostgreSQLCheckpointer(
            connection_string="postgresql://user:pass@localhost/db"
        )
        
        # Save checkpoint
        await checkpointer.save("exec_123", {
            "state": "data",
            "agent_type": "LeadsOrchestrator",
            "tenant_id": "acme"
        })
        
        # Load checkpoint
        state = await checkpointer.load("exec_123")
        
        # Delete checkpoint
        await checkpointer.delete("exec_123")
    """
    
    def __init__(self, connection_string: str):
        """
        Initialize PostgreSQL checkpointer.
        
        Args:
            connection_string: PostgreSQL connection string
                              (e.g., "postgresql://user:pass@localhost/db")
        """
        if not ASYNCPG_AVAILABLE:
            raise ImportError("asyncpg not installed. Install with: pip install asyncpg")
        
        self.connection_string = connection_string
        
        logger.info("PostgreSQLCheckpointer initialized")
        
        # Note: Connection is established per operation (pool would be better for production)
    
    async def _ensure_table_exists(self):
        """Ensure checkpoints table exists (idempotent)"""
        conn = await asyncpg.connect(self.connection_string)
        try:
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS checkpoints (
                    execution_id VARCHAR(255) PRIMARY KEY,
                    state JSONB NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
                )
            ''')
            
            # Create indexes if they don't exist
            await conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_checkpoints_created_at 
                ON checkpoints(created_at)
            ''')
        finally:
            await conn.close()
    
    async def save(self, execution_id: str, state: Dict[str, Any]) -> bool:
        """
        Save execution state to PostgreSQL.
        
        Args:
            execution_id: Unique execution ID
            state: State dictionary to save
        
        Returns:
            True if save successful, False otherwise
        """
        try:
            # Ensure table exists
            await self._ensure_table_exists()
            
            # Connect to database
            conn = await asyncpg.connect(self.connection_string)
            try:
                # Serialize state to JSON
                serialized = json.dumps(state)
                
                # Upsert checkpoint
                await conn.execute('''
                    INSERT INTO checkpoints (execution_id, state, created_at, updated_at)
                    VALUES ($1, $2, NOW(), NOW())
                    ON CONFLICT (execution_id)
                    DO UPDATE SET state = $2, updated_at = NOW()
                ''', execution_id, serialized)
                
                logger.debug(
                    f"Checkpoint saved to PostgreSQL: {execution_id} "
                    f"(size={len(serialized)} bytes)"
                )
                return True
                
            finally:
                await conn.close()
                
        except Exception as e:
            logger.error(f"PostgreSQL checkpoint save failed for {execution_id}: {e}")
            return False
    
    async def load(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """
        Load execution state from PostgreSQL.
        
        Args:
            execution_id: Unique execution ID
        
        Returns:
            State dictionary if found, None if not found
        """
        try:
            # Connect to database
            conn = await asyncpg.connect(self.connection_string)
            try:
                # Query checkpoint
                row = await conn.fetchrow(
                    'SELECT state FROM checkpoints WHERE execution_id = $1',
                    execution_id
                )
                
                if row is None:
                    logger.debug(f"Checkpoint not found in PostgreSQL: {execution_id}")
                    return None
                
                # Deserialize from JSON
                state = json.loads(row['state'])
                logger.debug(f"Checkpoint loaded from PostgreSQL: {execution_id}")
                return state
                
            finally:
                await conn.close()
                
        except json.JSONDecodeError as e:
            logger.error(
                f"PostgreSQL checkpoint deserialization failed for {execution_id}: {e}"
            )
            return None
        except Exception as e:
            logger.error(f"PostgreSQL checkpoint load failed for {execution_id}: {e}")
            return None
    
    async def delete(self, execution_id: str) -> bool:
        """
        Delete execution state from PostgreSQL.
        
        Args:
            execution_id: Unique execution ID
        
        Returns:
            True if deleted, False if not found
        """
        try:
            # Connect to database
            conn = await asyncpg.connect(self.connection_string)
            try:
                # Delete checkpoint
                result = await conn.execute(
                    'DELETE FROM checkpoints WHERE execution_id = $1',
                    execution_id
                )
                
                # Check if row was deleted
                deleted = result == "DELETE 1"
                
                if deleted:
                    logger.debug(f"Checkpoint deleted from PostgreSQL: {execution_id}")
                else:
                    logger.debug(
                        f"Checkpoint not found for deletion in PostgreSQL: {execution_id}"
                    )
                
                return deleted
                
            finally:
                await conn.close()
                
        except Exception as e:
            logger.error(
                f"PostgreSQL checkpoint deletion failed for {execution_id}: {e}"
            )
            return False
    
    def __repr__(self) -> str:
        """String representation for debugging"""
        # Mask password in connection string
        safe_conn_str = self.connection_string.split('@')[-1] if '@' in self.connection_string else self.connection_string
        return f"PostgreSQLCheckpointer(connection=...@{safe_conn_str})"
