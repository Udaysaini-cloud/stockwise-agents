# Contributing to StockWise Agents

Thank you for your interest in contributing to **StockWise Agents**! We welcome bug reports, documentation enhancements, feature proposals, and pull requests.

## Code of Conduct

Please be respectful, constructive, and collaborative in all discussions and code reviews.

---

## Getting Started

1. **Fork and Clone**:
   ```bash
   git clone https://github.com/<your-username>/stockwise-agents.git
   cd stockwise-agents
   ```

2. **Set Up Python Environment**:
   ```bash
   python3.12 -m venv .venv
   source .venv/bin/activate
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

3. **Set Up Frontend**:
   ```bash
   cd frontend
   npm install
   cd ..
   ```

4. **Environment Configuration**:
   ```bash
   cp .env.example .env
   # Configure any local overrides without committing sensitive secrets
   ```

---

## Development Guidelines

### Branching Strategy
- Branch from `master` (or `main`).
- Use descriptive branch names: `feature/shortage-forecasting`, `fix/moq-rounding-edge-case`, `docs/setup-clarification`.

### Python Code Quality
- Target Python 3.12+.
- Use strict type annotations with Pydantic v2 schemas where applicable.
- Keep procurement and optimization logic deterministic in `core/`.
- Ensure all database interactions go through `core/persistence.py` with transactional rollbacks.

### Frontend Code Quality
- Follow Next.js App Router conventions in `frontend/src/app`.
- Adhere to the established Tailwind CSS design system with curated slate/indigo tokens.
- Maintain responsive layouts and accessibility standards.

---

## Testing Requirements

Before submitting a pull request, ensure all tests pass and frontend builds cleanly:

1. **Run Pytest Test Suite**:
   ```bash
   pytest
   ```
   All tests in `tests/` must pass. Add unit/integration tests for any new features or bug fixes.

2. **Run Frontend Production Build**:
   ```bash
   cd frontend
   npm run build
   cd ..
   ```
   Ensure zero TypeScript compilation or linting errors.

---

## Submitting a Pull Request

1. Push your branch to your GitHub fork.
2. Open a Pull Request against the upstream repository.
3. Include a concise summary of changes, rationale, and testing evidence.
4. Verify that no private keys, agent seeds, API keys, or `.env` files are included in the commits.
