"""
S3 Checkpointer

Stores checkpoints in AWS S3 for persistent storage.
Good for: Production, audit trails, long-term retention

Features:
- Persistent cloud storage
- Configurable retention (30 days, 1 year, etc.)
- Queryable via AWS CLI/Console
- Cost-effective for long-term storage

Installation:
    pip install boto3
"""

import json
import logging
from typing import Dict, Any, Optional

from core.harness.interfaces import ICheckpointer, CheckpointError

logger = logging.getLogger(__name__)

# Try to import boto3 (optional dependency)
try:
    import boto3
    from botocore.exceptions import ClientError
    
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False
    logger.warning("boto3 not installed. Install with: pip install boto3")


class S3Checkpointer(ICheckpointer):
    """
    S3-based checkpointing (persistent, audit trail).
    
    Stores execution state in AWS S3 for long-term retention.
    Perfect for production audit trails and compliance.
    
    Requires installation:
        pip install boto3
    
    AWS Configuration:
        Set environment variables or AWS config file:
        - AWS_ACCESS_KEY_ID
        - AWS_SECRET_ACCESS_KEY
        - AWS_DEFAULT_REGION
    
    Example:
        checkpointer = S3Checkpointer(
            bucket_name="prod-checkpoints",
            prefix="agentic-system/",
            region="us-east-1"
        )
        
        # Save checkpoint
        await checkpointer.save("exec_123", {"state": "data"})
        
        # Load checkpoint
        state = await checkpointer.load("exec_123")
        
        # Delete checkpoint
        await checkpointer.delete("exec_123")
    """
    
    def __init__(
        self,
        bucket_name: str,
        prefix: str = "checkpoints/",
        region: str = "us-east-1"
    ):
        """
        Initialize S3 checkpointer.
        
        Args:
            bucket_name: S3 bucket name
            prefix: S3 key prefix (default: "checkpoints/")
            region: AWS region (default: "us-east-1")
        """
        if not BOTO3_AVAILABLE:
            raise ImportError("boto3 not installed. Install with: pip install boto3")
        
        self.bucket_name = bucket_name
        self.prefix = prefix
        self.region = region
        
        # Initialize S3 client
        try:
            self.s3 = boto3.client('s3', region_name=region)
            
            # Test bucket access
            self.s3.head_bucket(Bucket=bucket_name)
            
            logger.info(
                f"S3Checkpointer initialized: bucket={bucket_name}, "
                f"prefix={prefix}, region={region}"
            )
        except ClientError as e:
            logger.error(f"S3 bucket access failed: {e}")
            raise CheckpointError(f"S3 bucket access failed: {e}") from e
    
    async def save(self, execution_id: str, state: Dict[str, Any]) -> bool:
        """
        Save execution state to S3.
        
        Args:
            execution_id: Unique execution ID
            state: State dictionary to save
        
        Returns:
            True if save successful, False otherwise
        """
        key = f"{self.prefix}{execution_id}.json"
        
        try:
            # Serialize state to JSON
            serialized = json.dumps(state, indent=2)
            
            # Upload to S3
            self.s3.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=serialized,
                ContentType='application/json',
                Metadata={
                    'execution_id': execution_id,
                    'checkpoint_version': '1.0'
                }
            )
            
            logger.debug(
                f"Checkpoint saved to S3: {execution_id} "
                f"(size={len(serialized)} bytes, key={key})"
            )
            return True
            
        except ClientError as e:
            logger.error(f"S3 checkpoint save failed for {execution_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Checkpoint save failed for {execution_id}: {e}")
            return False
    
    async def load(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """
        Load execution state from S3.
        
        Args:
            execution_id: Unique execution ID
        
        Returns:
            State dictionary if found, None if not found
        """
        key = f"{self.prefix}{execution_id}.json"
        
        try:
            # Download from S3
            response = self.s3.get_object(Bucket=self.bucket_name, Key=key)
            data = response['Body'].read()
            
            # Deserialize from JSON
            state = json.loads(data)
            logger.debug(f"Checkpoint loaded from S3: {execution_id}")
            return state
            
        except self.s3.exceptions.NoSuchKey:
            logger.debug(f"Checkpoint not found in S3: {execution_id}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"S3 checkpoint deserialization failed for {execution_id}: {e}")
            return None
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                logger.debug(f"Checkpoint not found in S3: {execution_id}")
                return None
            logger.error(f"S3 checkpoint load failed for {execution_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Checkpoint load failed for {execution_id}: {e}")
            return None
    
    async def delete(self, execution_id: str) -> bool:
        """
        Delete execution state from S3.
        
        Args:
            execution_id: Unique execution ID
        
        Returns:
            True if deleted, False if not found
        """
        key = f"{self.prefix}{execution_id}.json"
        
        try:
            # Delete from S3
            self.s3.delete_object(Bucket=self.bucket_name, Key=key)
            logger.debug(f"Checkpoint deleted from S3: {execution_id}")
            return True
            
        except ClientError as e:
            logger.error(f"S3 checkpoint deletion failed for {execution_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Checkpoint deletion failed for {execution_id}: {e}")
            return False
    
    def __repr__(self) -> str:
        """String representation for debugging"""
        return (
            f"S3Checkpointer(bucket={self.bucket_name}, "
            f"prefix={self.prefix}, region={self.region})"
        )
