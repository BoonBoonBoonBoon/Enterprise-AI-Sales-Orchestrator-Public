# Changelog

All notable changes to the Agentic System will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Comprehensive MkDocs documentation overhaul
- Architecture Decision Records (ADRs) section
- Roadmap with in-progress and future plans
- Environment setup guide with all variables documented

### Changed

- Documentation structure reorganized around user journey
- Archived outdated documentation to `docs/archive/`

### Deprecated

- Old documentation files moved to archive

### Fixed

- Documentation relative link warnings resolved

---

## [0.1.0] - 2026-01-12

### Added

#### Core Infrastructure

- Three-tier agent architecture (Manager → Orchestrators → Agents)
- Redis Streams messaging backbone
- Agent Harness pattern with retries and circuit breakers
- Message Envelope schema (TaskEnvelope, ResultEnvelope)
- Multi-tenant stream isolation

#### Tier 1 - Manager

- Manager Agent with intent classification
- Policy-based routing
- Shortcut registry for fast paths
- Delegation tools for orchestrator communication

#### Tier 2 - Orchestrators

- Leads Orchestrator for lead qualification and enrichment
- Outreach Orchestrator for campaign execution
- Inbound Orchestrator (skeleton)
- Vertical-only communication enforcement

#### Tier 3 - Agents

- RAG Agent for context retrieval and vector search
- Persistence Agent for database CRUD operations
- Copywriter Agent for AI content generation
- Scheduler Agent (skeleton)

#### Services

- Redis Service with consumer groups
- Persistence Service with Supabase adapter
- Vector DB Service for embeddings
- Email Service with Gmail integration

#### Database

- Supabase integration with RLS
- 3-layer authentication (API Gateway + GRANT + RLS)
- Core tables: clients, campaigns, leads, conversations, messages
- Staging tables for pre-qualification

#### Observability

- OpenTelemetry tracing integration
- Datadog exporter support
- Structured logging

#### Development

- Docker Compose for local development
- Comprehensive test suite (unit, integration, e2e)
- Windows PowerShell support

### Security

- Tenant isolation at database level
- Role-based database access (agent_reader, agent_writer)
- JWT-based authentication

---

## Version History

| Version | Date       | Highlights                                   |
| ------- | ---------- | -------------------------------------------- |
| 0.1.0   | 2026-01-12 | Initial pre-release with core infrastructure |

---

## Upgrade Guides

### Upgrading to 0.1.0

This is the initial release. No upgrade path required.

For future versions, upgrade guides will be documented here with:

1. Breaking changes
2. Migration steps
3. Rollback procedure
