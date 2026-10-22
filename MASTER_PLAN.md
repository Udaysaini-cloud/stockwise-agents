# StockWise Agents: Complete Implementation Roadmap

## 1. The final product

**StockWise Agents** is a procurement assistant for small retailers. It analyses inventory, identifies stock shortages, compares supplier offers, creates a budget-constrained purchase order and waits for approval before placing or simulating an order.

### The demo scenario

A retailer asks:

> Analyse my stock for the next seven days. I have ₹20,000 to spend. Find urgent shortages, compare suppliers, prepare the best purchase order and wait for my approval.

The system must:

1. Interpret the request.
2. Read inventory and supplier data.
3. Calculate stock requirements.
4. Compare available suppliers.
5. Optimize the order against the budget.
6. Generate an itemized purchase order.
7. Wait for explicit approval.
8. Recover if a supplier becomes unavailable.
9. Save the result and report the outcome.

All inventory and supplier data can be synthetic for the MVP, but must be labelled as demo data.

## 2. Technology stack

| Component               | Technology                                                  |
| ----------------------- | ----------------------------------------------------------- |
| Development environment | Google Antigravity                                          |
| Language                | Python 3.11 or a version supported by the current SDK       |
| Agent framework         | Fetch.ai uAgents                                            |
| Agent deployment        | Agentverse                                                  |
| Chat interface          | ASI:One using the supported Agent Chat Protocol integration |
| Reasoning               | ASI1 through the supported integration                      |
| Data validation         | Pydantic                                                    |
| Database                | SQLite                                                      |
| Testing                 | pytest                                                      |
| Version control         | Git and public GitHub repository                            |
| Optional UI             | React and Tailwind CSS                                      |

**Important:** Antigravity is the IDE, not the deployed StockWise agent. The product itself should use the Fetch.ai framework and official ASI:One integration examples.

Use the current official documentation:

- Fetch.ai: https://www.fetch.ai/docs
- Hackathon hackpack: https://www.fetch.ai/events/hackathons/fetch-a-thon-3/hackpack
- Agentverse setup: https://docs.agentverse.ai/documentation/agent-discovery/setup-guide
- Antigravity setup: https://www.antigravity.google/docs/getting-started?tab=ide

## 3. Phase 0 — Confirm access and prepare your environment

Before coding:

- Confirm your hackathon registration.
- Sign in to Agentverse and ASI:One.
- Check that you can create or deploy an agent.
- Open the current ACP integration guide.
- Confirm access to ASI1 or the supported reasoning service.
- Check GitHub access and repository permissions.

If registration is still pending, contact the organizers immediately.

### On your MacBook

Open Terminal and inspect the existing environment:

```bash
uname -m
python3 --version
git --version
```

Your Apple Silicon Mac should report `arm64`.

Create the project directory:

```bash
mkdir -p ~/Projects/stockwise-agents
cd ~/Projects/stockwise-agents
```

Open this folder in Google Antigravity using **New Project → Add Folder**.

Use a virtual environment rather than installing project dependencies globally:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

Do not install packages for the Fetch.ai framework until you have checked the current official example and its supported Python version.

## 4. Phase 1 — Make Antigravity your development partner

Start by asking Antigravity to inspect the workspace and create an implementation plan.

### Prompt 1: Project planning

Paste into the Antigravity agent panel:

> You are the lead engineer for StockWise Agents, a Python-first Agentic AI procurement assistant for a hackathon.
>
> The system must use Fetch.ai uAgents, Agentverse and the supported Agent Chat Protocol integration to work directly inside ASI:One. It must analyse inventory, compare suppliers, calculate a purchase order within a budget, wait for approval, recover from supplier failure and persist the result.
>
> First inspect the current workspace and the official documentation available to you. Identify the correct current SDK versions, official ACP integration pattern, deployment method and required environment variables.
>
> Do not write application code yet. Produce a step-by-step implementation plan, dependency list, architecture, repository structure, test strategy and deployment checklist. Separate mandatory requirements from optional features. Flag anything you cannot verify.

Review the plan before approving implementation.

### Prompt 2: Create the repository skeleton

> Create the StockWise Agents repository structure, README outline, `.gitignore`, `.env.example`, dependency file, Python package directories and initial tests directory. Use a virtual-environment-friendly setup. Never create real secrets, invent SDK methods or assume an undocumented protocol API. Explain each file and run basic checks.

The repository should look like this:

```text
stockwise-agents/
├── README.md
├── requirements.txt
├── .env.example
├── .gitignore
├── agents/
│   ├── __init__.py
│   └── coordinator.py
├── core/
│   ├── __init__.py
│   ├── schemas.py
│   ├── inventory.py
│   ├── supplier_scoring.py
│   ├── optimizer.py
│   ├── purchase_orders.py
│   └── persistence.py
├── data/
│   ├── inventory.json
│   └── suppliers.json
├── tests/
│   ├── test_inventory.py
│   ├── test_optimizer.py
│   └── test_supplier_failure.py
└── docs/
    └── architecture.md
```

Start with a single coordinator. Add separate helper agents only after the first deployed workflow works.

## 5. Phase 2 — Build the inventory and supplier data

Create 10–20 fictional products and three or four fictional suppliers.

Each product should have:

- SKU and product name.
- Current stock.
- Average daily sales.
- Existing outstanding purchase quantities.
- Safety stock.
- Target stock cover.
- Supplier references.

Each supplier should have:

- Supplier ID and name.
- Product availability.
- Unit cost.
- Lead time.
- Minimum order quantity.
- Pack size.
- Delivery charge, where applicable.

Use realistic but explicitly fictional values.

### Prompt 3: Generate the demo data

> Create synthetic inventory and supplier JSON datasets for a small Indian electronics retailer. Include 15 products, four suppliers, different lead times, minimum order quantities, pack sizes and unit prices in INR.
>
> Include at least three urgent stock shortages, one product unavailable from its preferred supplier and one item whose minimum order quantity makes it difficult to fit within the budget.
>
> Validate all identifiers and numerical fields. Add tests for malformed records. Label the data as synthetic. Do not use live commercial prices or invent claims about actual businesses.

## 6. Phase 3 — Implement the business logic

This is the heart of StockWise. The agent must call actual Python functions to calculate its recommendations.

### Inventory calculation

Use:

Target Stock = Average Daily Sales × (Lead Time + Target Stock Cover) + Safety Stock

Then:

Reorder Quantity = max(0, Target Stock − Available Stock − Outstanding Purchase Quantity)

Ensure that all time periods use the same unit and that outstanding orders are not counted twice.

### Supplier comparison

Rank feasible supplier offers based on:

- Total landed cost.
- Availability.
- Lead time.
- Minimum order quantity.
- Pack-size constraints.
- Stockout urgency.

A low unit price should not automatically win if the supplier cannot deliver in time.

### Budget optimization

Start with a simple deterministic strategy:

1. Rank products by urgency.
2. Remove supplier offers that violate availability or delivery constraints.
3. Calculate feasible order quantities.
4. Select combinations that fit the ₹20,000 budget.
5. Check the final totals.
6. Explain items that were deferred.

### Prompt 4: Implement the procurement engine

> Implement the inventory calculation, supplier scoring and budget-constrained purchase-order engine in separate Python modules. Use Pydantic schemas and Decimal for monetary calculations.
>
> Enforce supplier availability, minimum order quantities, pack sizes, lead times and the total budget. Return a structured result containing selected products, supplier IDs, quantities, unit prices, line totals, total order cost, remaining budget and deferred items with reasons.
>
> Do not let the LLM perform arithmetic. Implement deterministic functions and add pytest coverage for budget limits, stock calculations, unavailable suppliers, insufficient capacity and impossible orders.

Do not proceed until the tests pass and you can run the engine without any AI service.

## 7. Phase 4 — Add the purchase-order approval workflow

Define explicit order states:

- `draft`
- `pending_approval`
- `approved`
- `simulated_placed`
- `rejected`
- `failed`

The hackathon demo should not place real commercial orders.

### Prompt 5: Add persistence and approval

> Implement SQLite persistence for inventory snapshots, procurement requests, purchase orders, approval decisions and audit events.
>
> Give each request and order a unique ID. Make approval idempotent so repeating the same approval request cannot create duplicate orders. Revalidate the budget, supplier availability and order contents immediately before approval.
>
> The agent must never claim that a purchase was placed unless the corresponding operation actually succeeded. For the demo, use an explicitly labelled simulated placement operation. Add tests for repeated approval, rejected orders and failed operations.

## 8. Phase 5 — Implement the agent and ASI:One integration

This is the most important integration milestone.

First, deploy a minimal agent that can respond to a simple request. Then connect the procurement engine.

### Prompt 6: Build the public coordinator

> Implement the StockWise coordinator using the current official Fetch.ai uAgents and ASI:One-compatible ACP example.
>
> Follow the official documentation for imports, protocol handlers, request/response schemas, agent registration and deployment. Do not invent package names, handler decorators or undocumented SDK methods.
>
> The coordinator should accept a procurement request, validate it, call the deterministic inventory and supplier tools, generate a purchase order, save the draft and return a concise explanation with itemized totals.
>
> Support missing information, invalid budgets, unavailable suppliers, duplicate requests and tool failures. The primary workflow must complete inside ASI:One without requiring a custom frontend.
>
> First implement the smallest valid integration and demonstrate it working. Then add the procurement workflow. Provide exact run commands and report which integration steps require my account credentials or dashboard actions.

Test this sequence:

1. Run the agent locally.
2. Send a simple test request.
3. Verify the response.
4. Register or deploy it through the supported Agentverse flow.
5. Confirm the Agentverse profile is active.
6. Test direct discovery and interaction through ASI:One.
7. Run a full procurement request from beginning to end.

**Do not leave ASI:One integration until the end.** It is a mandatory part of the challenge.

## 9. Phase 6 — Add genuine multi-agent collaboration

Once the coordinator works, add helper agents if time permits.

- Inventory agent: analyses stock and identifies urgent products.
- Supplier agent: returns structured supplier offers.
- Coordinator: invokes both, computes the final basket and handles failures.

### Prompt 7: Add helper agents

> Extend the working coordinator with separately identifiable helper agents using the current supported uAgents communication pattern. The inventory agent must return structured stock analysis, and the supplier agent must return available offers with price, lead time and constraints.
>
> The coordinator must validate their responses and independently enforce all budget and order rules. Handle timeouts, unavailable agents and malformed responses. Add integration tests and document each agent's address.
>
> If multi-agent deployment threatens the deadline, keep the coordinator working and expose the same tested functionality through internal Python modules instead.

Do not fake agent collaboration by having one LLM produce multiple differently named responses.

## 10. Phase 7 — Test the failure scenario

Your demo needs a clear recovery story.

Test these cases:

- A supplier rejects the preferred item.
- The next supplier is too expensive.
- No supplier can meet the delivery deadline.
- The basket exceeds the budget.
- A purchase order is approved twice.
- The coordinator receives malformed input.
- A helper agent is unavailable.

### Prompt 8: Reliability audit

> Act as a skeptical QA engineer. Inspect the entire repository, run all automated tests, and identify correctness, security, deployment and protocol issues.
>
> Verify that no order exceeds the budget, no unavailable supplier is selected, no invalid approval is accepted, no duplicate order is created and no simulated outcome is described as real. Test failure recovery and preserve audit records.
>
> Fix issues with focused changes. Do not add new features until the mandatory ASI:One workflow passes.

## 11. Phase 8 — GitHub and final submission

Publish the repository publicly, excluding:

- API keys and tokens.
- `.env` files.
- Private credentials.
- Personal data.
- Unnecessary logs or local database contents.

The `.gitignore` should cover at least:

```text
.venv/
__pycache__/
.env
.env.*
!.env.example
*.db
.pytest_cache/
.DS_Store
```

Before committing, inspect `git status` and the staged files.

The README must contain:

- Problem statement.
- Architecture diagram.
- Setup and run instructions.
- Environment-variable documentation.
- Synthetic dataset explanation.
- Test commands.
- Agent names and deployed addresses.
- Agentverse profile URL.
- ASI:One shared chat URL.
- Known limitations.
- Required hackathon badges.

Record a 3–5 minute demonstration and submit the deliverables through the official challenge platform.

## 12. Hackathon-day priorities

### First priority

Deploy a discoverable ACP-compatible coordinator and confirm ASI:One can use it.

### Second priority

Make the inventory-to-purchase-order workflow work end to end.

### Third priority

Demonstrate a supplier failure and successful recalculation.

### Fourth priority

Add helper agents, Interactive Cards or other bonus features.

### Final priority

Polish the README, demo and presentation.

A reliable single coordinator with real tool execution is better than several broken agents.

## 13. Definition of done

StockWise is ready to submit only when:

- The public agent is active and discoverable.
- The primary workflow runs through ASI:One.
- Inventory and supplier decisions use actual structured data.
- Purchase orders are calculated and persisted.
- Budget and supplier constraints are enforced.
- Approval is explicit and repeatable safely.
- Supplier failure produces a valid recovery or a clear failure report.
- Tests pass.
- The public repository and demo video are ready.
- The Agentverse and ASI:One URLs are available for submission.
