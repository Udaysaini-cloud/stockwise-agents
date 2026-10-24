# Changelog

All notable changes to the **StockWise Agents** project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.0] - 2026-10-24

### Added
- **uAgents Coordinator Agent**: Autonomous agent built on Fetch.ai uAgents framework (`0.25.5`) exposing `AgentChatProtocol` (`0.3.0`) for Agentverse and ASI:One discovery.
- **Inventory Analytics Engine**: Real-time burn rate, lead time, safety buffer, and target cover calculation for retail electronic SKUs.
- **Multi-Supplier Composite Scoring**: Weighted scoring engine factoring in landed unit price (50%), lead time (25%), quality rating (15%), and on-time delivery rate (10%).
- **Budget-Constrained Knapsack Optimizer**: Deterministic purchase order generator respecting pack sizes, supplier minimum order quantities (MOQ), and hard budget limits in INR (₹).
- **Purchase Order State Machine**: Strict SQLite-backed transactional lifecycle (`draft` → `pending_approval` → `approved` → `simulated_placed` / `rejected`).
- **Audit Logging**: Immutable event log tracking every purchase order state transition, actor ID, and reason timestamped in UTC.
- **Conversational Natural Language Interface**: Chat workspace supporting stock inquiries, store health summaries, runout alerts, vendor comparisons, and direct single-item order evaluations.
- **Next.js Web Dashboard**: Modern enterprise SaaS frontend featuring Overview metrics, Inventory shortage tables, Supplier comparisons, Budget Planner, Order Management, and Agent Workspace chat.
- **FastAPI REST Backend**: High-performance backend connecting Next.js dashboard to deterministic procurement services, SQLite persistence, and coordinator chat.
- **Autonomous Supplier Recovery**: Dynamic re-planning and supplier exclusion upon vendor failure or stock unavailability.
- **Comprehensive Test Suite**: 68 automated unit, integration, and regression tests covering optimization, state persistence, API endpoints, protocol messaging, and chat queries.
