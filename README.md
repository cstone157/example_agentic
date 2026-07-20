# Multi-Agent Development Workflow

A LangGraph-based multi-agent system that orchestrates a complete development lifecycle — from planning through deployment — using specialized agents at each stage.

## Overview

This project implements an automated software development pipeline where five specialized AI agents collaborate to:

1. **Plan** — Analyze requirements and create implementation plans
2. **Task** — Break plans into actionable, prioritized tasks
3. **Code** — Generate production-quality source code
4. **Test** — Create and execute comprehensive test suites
5. **Secure** — Scan for vulnerabilities using Trivy

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│ Planner  │───▶│ Tasker   │───▶│ Coder    │───▶│ Tester   │───▶│ Security │
│          │    │          │    │          │    │          │    │ (Trivy)  │
└──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘
                        ▲                    │
                        └───── Loop back ────┘ (if tests fail)
```

## Project Structure

```
example_agentic/
├── agents/                    # Agent configuration files
│   ├── planner/AGENTS.md      # Requirements analysis & planning
│   ├── tasker/AGENTS.md       # Task decomposition
│   ├── coder/AGENTS.md        # Code generation
│   ├── tester/AGENTS.md       # Test suite generation
│   └── security/AGENTS.md     # Vulnerability scanning
├── src/
│   ├── agents/
│   │   ├── llm_client.py      # LLM abstraction layer (OpenAI, Anthropic, etc.)
│   │   └── base.py            # Shared agent utilities
│   ├── tools/
│   │   ├── file_ops.py        # Safe file read/write operations
│   │   ├── test_runner.py     # Pytest execution wrapper
│   │   └── trivy_scanner.py   # Trivy vulnerability scanner
│   ├── workflow/
│   │   ├── state.py           # LangGraph state schema
│   │   ├── graph.py           # Compiled LangGraph workflow
│   │   ├── nodes.py           # Node implementations (agent calls)
│   │   └── prompts.py         # System prompts for agents
│   └── main.py                # CLI entry point
├── tests/
│   └── test_workflow.py       # Integration tests
├── Dockerfile                 # Application image for Trivy scanning
├── docker-compose.yml         # Trivy scanner service
├── requirements.txt           # Python dependencies
└── README.md                  # This file
```

## Installation

### Prerequisites

- Python 3.12+
- OpenAI API key (or other LLM provider)
- Docker (optional, for security scanning)
- Trivy CLI (optional, for vulnerability scanning)

### Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/example_agentic.git
cd example_agentic

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set your API key
export OPENAI_API_KEY="your-api-key-here"
```

## Usage

### Interactive CLI

Run the workflow interactively by providing an application description:

```bash
python -m src.main
```

**Example session:**

```
======================================================================
  Multi-Agent Development Workflow
  LangGraph | Planner → Tasker → Coder → Tester → Security
======================================================================

Workflow Structure:
  Name: Multi-Agent Development Workflow
  Nodes: planner, tasker, coder, tester, security
  Description: Linear workflow with conditional test-fix loop...

Enter your application description:
(Type your description and press Enter, or Ctrl+D to submit)

Build a REST API for managing a todo list with CRUD operations.

Processing: Build a REST API for managing a todo list with CRUD operat...
Running multi-agent workflow...

======================================================================
  IMPLEMENTATION PLAN
======================================================================
Architecture: Layered architecture with FastAPI, SQLAlchemy, and SQLite...

======================================================================
  USER STORIES
======================================================================
  1. As a user, I want to create todos
  2. As a user, I want to view my todos
  3. As a user, I want to update todos
  4. As a user, I want to delete todos

======================================================================
  TECH STACK
======================================================================
  - fastapi: 0.109.0
  - sqlalchemy: 2.0.25
  - pydantic: 2.5.0

======================================================================
  TASKS
======================================================================
  [P0] Set up FastAPI project structure (pending)
  [P0] Create Todo model with SQLAlchemy (pending)
  [P1] Implement CRUD endpoints (pending)
  [P1] Add input validation (pending)
  [P2] Write unit tests (pending)

======================================================================
  GENERATED CODE FILES
======================================================================
  ✓ /tmp/agentic_workspace_xxx/main.py
  ✓ /tmp/agentic_workspace_xxx/models.py
  ✓ /tmp/agentic_workspace_xxx/routers.py

======================================================================
  TEST RESULTS
======================================================================
  Passed: 12
  Failed: 0
  Errors: 0
  Skipped: 0
  Duration: 3.45s
  Summary: All tests passed
  Status: ✓ PASSED

======================================================================
  SECURITY SCAN RESULTS
======================================================================
  Vulnerabilities Found: 0
  Security Passed: ✓ YES

======================================================================
  WORKFLOW STATUS
======================================================================
  Final Status: COMPLETE

Results saved to: /path/to/example_agentic/workflow_results.json
```

### Programmatic Usage

Use the workflow in your own Python code:

```python
from src.workflow.graph import app_graph

# Define your application description
app_description = "Build a blog API with user authentication and post management"

# Run the workflow
result = app_graph.invoke({
    "app_description": app_description,
    "status": "planning",
})

# Access results
print("Plan:", result["implementation_plan"])
print("Tasks:", len(result["tasks"]))
print("Tests passed:", result["tests_passed"])
print("Vulnerabilities:", len(result["vulnerabilities_found"]))
```

### Piped Input (Automation)

Use the workflow in scripts or CI/CD pipelines:

```bash
# From a file
cat app_description.txt | python -m src.main

# From a variable
echo "Build a REST API for user management" | python -m src.main

# In a Makefile
make workflow APP_DESC="Build a todo app"
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key | Required |
| `OPENAI_MODEL` | Model to use | `gpt-4o` |
| `OPENAI_TEMP` | Sampling temperature | `0.0` |
| `LLM_PROVIDER` | LLM provider (`openai`, `anthropic`) | `openai` |
| `TRIVY_SKIP_DB_UPDATE` | Skip Trivy DB updates | `false` |

### Switching LLM Providers

```python
# Use Anthropic Claude instead of OpenAI
import os
os.environ["LLM_PROVIDER"] = "anthropic"
os.environ["ANTHROPIC_API_KEY"] = "your-api-key"

from src.workflow.graph import app_graph
result = app_graph.invoke({...})
```

## Agent Definitions

Each agent is configured via an `AGENTS.md` file that defines its role, input/output format, and responsibilities.

### Planner Agent
- **Input:** Raw application description
- **Output:** Implementation plan with user stories and tech stack
- **Role:** Analyze requirements and produce structured MVP plans

### Tasker Agent
- **Input:** Implementation plan from Planner
- **Output:** Prioritized task list with dependencies
- **Role:** Break down plans into actionable coding tasks

### Coder Agent
- **Input:** Drafted tasks from Tasker
- **Output:** Source code files for each task
- **Role:** Generate production-quality Python code

### Tester Agent
- **Input:** Generated code from Coder
- **Output:** Test suite + pytest execution results
- **Role:** Create and run comprehensive tests

### Security Agent
- **Input:** Final codebase + test results
- **Output:** Trivy vulnerability scan report
- **Role:** Scan for security vulnerabilities

## Workflow Graph

The workflow is implemented as a LangGraph state machine with conditional edges:

```python
from src.workflow.graph import app_graph, get_workflow_summary

# View workflow structure
summary = get_workflow_summary()
print(summary["nodes"])  # ['planner', 'tasker', 'coder', 'tester', 'security']
print(summary["edges"])  # List of (source, target, type) tuples

# Run the workflow
result = app_graph.invoke(initial_state)
```

### Conditional Logic

The workflow includes a test-fix loop:
- If tests **pass** → proceed to security scanning
- If tests **fail** → loop back to coder for fixes

This ensures code quality before deployment.

## Testing

Run the integration tests:

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html

# Run specific test class
pytest tests/test_workflow.py::TestGraphCompilation -v
```

### Test Categories

- **State Schema** — Validates TypedDict structure
- **Graph Compilation** — Verifies LangGraph setup
- **Node Execution** — Tests each agent node (mocked)
- **Conditional Edges** — Tests routing logic
- **Tool Integration** — Tests file_ops, test_runner, trivy_scanner
- **End-to-End** — Full pipeline simulation
- **CLI** — Tests output formatting

## Docker & Security Scanning

### Build Application Image

```bash
docker build -t app-image:latest .
```

### Run Trivy Scan

```bash
# Using Docker Compose
docker-compose up trivy-scan

# Direct Trivy CLI
trivy image --format json --severity CRITICAL,HIGH,MEDIUM app-image:latest
```

### Fallback Scanning

If Docker is unavailable, the security agent falls back to filesystem scanning:

```python
from src.tools.trivy_scanner import run_trivy_scan

report = run_trivy_scan(target_path="/path/to/project")
print(report["vulnerabilities"])
```

## Output Format

The workflow produces a structured JSON output saved to `workflow_results.json`:

```json
{
  "app_description": "Build a todo API",
  "implementation_plan": "...",
  "user_stories": ["As a user, I want to..."],
  "tech_stack": {"fastapi": "0.109.0"},
  "tasks": [...],
  "generated_code": {...},
  "code_files_written": ["/tmp/.../main.py"],
  "test_suite": {...},
  "test_results": {
    "passed": 12,
    "failed": 0,
    "summary": "All tests passed"
  },
  "tests_passed": true,
  "trivy_report": {...},
  "vulnerabilities_found": [],
  "security_passed": true,
  "status": "complete",
  "errors": []
}
```

## Extending the Workflow

### Adding a New Agent

1. Create `agents/<name>/AGENTS.md` with agent configuration
2. Add node function in `src/workflow/nodes.py`
3. Register node in `src/workflow/graph.py`:
   ```python
   workflow.add_node("new_agent", run_new_agent)
   workflow.add_edge("previous_node", "new_agent")
   ```

### Customizing Prompts

Edit the `AGENTS.md` files to modify agent behavior:

```markdown
# Coder Agent

## Role
[Your custom role description]

## Responsibilities
- [Custom responsibility 1]
- [Custom responsibility 2]
```

### Adding New Tools

Create tools in `src/tools/` and integrate them into nodes:

```python
from src.tools.my_tool import my_function

def run_my_node(state: AppWorkflowState) -> dict:
    result = my_function(state["some_input"])
    return {"output": result, "status": "complete"}
```

## Architecture Decisions

1. **LangGraph over LangChain chains** — Enables conditional loops (test → fix → retest)
2. **TypedDict state** — Type-safe shared state between nodes
3. **LLM abstraction** — Swappable providers without changing agent code
4. **Agent configs as markdown** — Human-readable + machine-parseable prompts
5. **Trivy as Docker service** — Decouples security scanning

## License

MIT License
