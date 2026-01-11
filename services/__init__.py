"""
Services Layer - Shared infrastructure and integrations

The services layer provides reusable, cross-tier services and integrations:
- **persistence**: Database operations and adapters
- **redis**: Redis client and stream utilities
- **vector_db**: Vector database client and operations
- **external_apis**: Third-party API integrations

Each service is designed to be:
- Independent: Can be used by any tier
- Testable: Mock-friendly interfaces
- Configurable: Environment-based settings
- Observable: Comprehensive logging and metrics

Exported Services:
- PersistenceService: Database write operations
- RedisPubSub: Redis pub/sub and streams client
- VectorDBClient: Vector database operations
- ExternalAPIClient: Third-party API base client
"""

__all__ = [
    "persistence",
    "redis",
    "vector_db",
    "external_apis",
]
