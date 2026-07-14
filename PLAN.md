# ML Workflow Plan: LangChain/LangGraph Application Pipeline

## Overview

A multi-agent workflow built with **LangGraph** that takes an application description and orchestrates a complete development lifecycle — from planning through deployment — using specialized agents at each stage.

```
┌─────────────────────────────────────────────────────────────────────┐
│                     APPLICATION WORKFLOW                           │
│                                                                     │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    │
│  │ Ingest   │───▶│ Plan     │───▶│ Draft    │───▶│ Implement│    │
│  │ App Desc │    │ Agent    │    │ Tasks    │    │ Agent    │    │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘    │
│       │                                              │              │
│       │                                              ▼              │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    │
│  │ Deploy   │◀───│ Test     │◀───│ Review   │◀───│ Code     │    │
│  │ Trivy    │    │ Suite    │    │ & Fix    │    │ Generate │    │
│  │ Scanner  │    │ Generator│    │ Agent    │    │ Agent    │    │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘    │
│                                                                     │
│                    LangGraph State Machine                         │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Phase 1: Project Structure

```
example_agentic/
├── agents/
│   ├── planner/
│   │   └── AGENTS.md          # Existing — turn app desc into implementation plan
│   ├── tasker/
│   │   └── AGENTS.md          # Existing — draft tasks from plan
│   ├── coder/
│   │   └── AGENTS.md          # NEW — implement tasks, write code
│   ├── tester/
│   │   └── AGENTS.md          # NEW — generate test suite for all code
│   └── security/
│       └── AGENTS.md          # NEW — configure & run Trivy scan
├── src/
│   ├── workflow/
│   │   ├── __init__.py
│   │   ├── state.py           # LangGraph State definition
│   │   ├── graph.py           # LangGraph compiled graph
│   │   ├── nodes.py           # Node implementations (agent calls)
│   │   └── prompts.py         # System prompts for each agent
│   ├── agents/
│   │   ├── base.py            # Shared agent factory & LLM client
│   │   └── llm_client.py      # OpenAI / LLM abstraction layer
│   └── tools/
│       ├── file_ops.py        # Read/write code files safely
│       ├── test_runner.py     # pytest execution tool
│       └── trivy_scanner.py   # Trivy Docker scan tool
├── tests/
│   └── test_workflow.py       # Tests for the workflow itself
├── docker-compose.yml         # Trivy scanner service
├── Dockerfile                 # App container (for Trivy to scan)
├── requirements.txt           # Existing dependencies
├── pyproject.toml             # Project metadata
└── README.md                  # Workflow documentation
```

---

## Phase 2: LangGraph State Definition

### `src/workflow/state.py`

Define a shared state schema that flows through every node:

```python
from typing import TypedDict, NotRequired
from langgraph.graph import MessagesState

class AppWorkflowState(MessagesState):
    # Input
    app_description: str                          # User's application description
    
    # Planner output
    implementation_plan: str                      # Structured plan from planner agent
    user_stories: list[str]                       # Extracted user stories
    tech_stack: dict[str, str]                    # Recommended frameworks/libraries
    
    # Tasker output
    tasks: list[dict[str, str]]                   # [{id, description, priority, status}]
    
    # Coder output
    generated_code: dict[str, str]                # {filepath: code_content}
    code_files_written: list[str]                 # Paths written to disk
    
    # Tester output
    test_suite: dict[str, str]                    # {test_filepath: test_content}
    test_results: dict[str, any]                  # pytest results summary
    tests_passed: bool                            # All tests green?
    
    # Security output
    trivy_report: dict[str, any]                  # Trivy scan results
    vulnerabilities_found: list[dict[str, str]]   # List of CVEs/issues
    security_passed: bool                         # No critical/high vulns?
    
    # Control flow
    status: str                                   # "planning" | "drafting" | "coding" | "testing" | "securing" | "complete" | "failed"
    errors: list[str]                             # Accumulated error log
```

---

## Phase 3: Agent Definitions

### 3.1 Planner Agent (Existing — extend)

**File:** `agents/planner/AGENTS.md`

- **Input:** Raw application description
- **Output:** Implementation plan with user stories, tech stack recommendations, architecture overview
- **LLM Role:** Analyze requirements and produce structured MVP plan

### 3.2 Tasker Agent (Existing — extend)

**File:** `agents/tasker/AGENTS.md`

- **Input:** Implementation plan from Planner
- **Output:** List of actionable tasks with priorities, dependencies, and estimated complexity
- **LLM Role:** Break plan into discrete coding/testing tasks

### 3.3 Coder Agent (NEW)

**File:** `agents/coder/AGENTS.md`

- **Input:** Drafted tasks from Tasker
- **Output:** Source code files for each task
- **Responsibilities:**
  - Implement code matching the plan and tasks
  - Write production-quality Python with type hints
  - Follow project conventions (PEP 8, docstrings)
  - Output file paths and code content to state
- **Tools Available:** File write tool, syntax validation (Pylance)

### 3.4 Tester Agent (NEW)

**File:** `agents/tester/AGENTS.md`

- **Input:** Generated code files from Coder
- **Output:** Complete test suite + pytest execution results
- **Responsibilities:**
  - Generate unit tests, integration tests, and edge-case coverage
  - Write tests for all public functions/classes
  - Execute `pytest` against generated code
  - Report pass/fail status with error details
- **Tools Available:** File write tool, test runner tool

### 3.5 Security Agent (NEW)

**File:** `agents/security/AGENTS.md`

- **Input:** Final codebase + test results
- **Output:** Trivy vulnerability scan report
- **Responsibilities:**
  - Build Docker image of the application
  - Run Trivy container scanner against the image
  - Parse and summarize findings (CVEs, severity levels)
  - Flag critical/high vulnerabilities for remediation
- **Tools Available:** Docker/Docker Compose, Trivy CLI

---

## Phase 4: LangGraph Workflow Graph

### `src/workflow/graph.py` — Node Definitions & Edges

```python
from langgraph.graph import StateGraph, START, END
from src.workflow.state import AppWorkflowState
from src.workflow.nodes import (
    run_planner,
    run_tasker,
    run_coder,
    run_tester,
    run_security_scanner,
)

# Build the graph
workflow = StateGraph(AppWorkflowState)

# Add nodes
workflow.add_node("planner", run_planner)
workflow.add_node("tasker", run_tasker)
workflow.add_node("coder", run_coder)
workflow.add_node("tester", run_tester)
workflow.add_node("security", run_security_scanner)

# Define edges (linear with conditional branches)
workflow.add_edge(START, "planner")
workflow.add_edge("planner", "tasker")
workflow.add_edge("tasker", "coder")
workflow.add_edge("coder", "tester")

# Conditional: if tests fail → loop back to coder for fixes
workflow.add_conditional_edges(
    "tester",
    should_fix_code,       # returns "coder" or "security"
    {"coder": "coder", "security": "security"}
)

workflow.add_edge("security", END)

# Compile the graph
app_graph = workflow.compile()
```

### Conditional Edge Logic

```python
def should_fix_code(state: AppWorkflowState) -> str:
    if not state.get("tests_passed", False):
        return "coder"  # Loop back to coder with test failure details
    return "security"   # Proceed to Trivy scan
```

---

## Phase 5: Node Implementations

### `src/workflow/nodes.py`

Each node is a function that:
1. Receives the current state
2. Calls the appropriate agent (LLM prompt + tool execution)
3. Updates state with results

```python
# Pseudocode for each node:

def run_planner(state: AppWorkflowState) -> dict:
    """Call planner agent to generate implementation plan."""
    plan = call_llm_agent(
        agent_config="agents/planner/AGENTS.md",
        input=state["app_description"]
    )
    return {
        "implementation_plan": plan.plan,
        "user_stories": plan.stories,
        "tech_stack": plan.tech_stack,
        "status": "drafting"
    }

def run_tasker(state: AppWorkflowState) -> dict:
    """Call tasker agent to draft tasks from plan."""
    tasks = call_llm_agent(
        agent_config="agents/tasker/AGENTS.md",
        input=state["implementation_plan"]
    )
    return {
        "tasks": tasks.list,
        "status": "coding"
    }

def run_coder(state: AppWorkflowState) -> dict:
    """Call coder agent to implement tasks."""
    code = call_llm_agent(
        agent_config="agents/coder/AGENTS.md",
        input=state["tasks"]
    )
    # Write files to disk
    written = write_files(code.files)
    return {
        "generated_code": code.files,
        "code_files_written": written,
        "status": "testing"
    }

def run_tester(state: AppWorkflowState) -> dict:
    """Generate and execute test suite."""
    tests = call_llm_agent(
        agent_config="agents/tester/AGENTS.md",
        input=state["generated_code"]
    )
    # Write test files
    write_files(tests.suite)
    # Run pytest
    results = run_pytest(state["code_files_written"])
    return {
        "test_suite": tests.suite,
        "test_results": results.summary,
        "tests_passed": results.all_passed,
        "status": "securing" if results.all_passed else "coding"
    }

def run_security_scanner(state: AppWorkflowState) -> dict:
    """Deploy Trivy and scan the application."""
    # Build Docker image
    build_docker_image()
    # Run Trivy scan
    report = run_trivy_scan()
    return {
        "trivy_report": report,
        "vulnerabilities_found": report.vulnerabilities,
        "security_passed": not report.critical_high_vulns,
        "status": "complete"
    }
```

---

## Phase 6: Trivy Docker Deployment

### `docker-compose.yml` — Trivy Scanner Service

```yaml
version: '3.8'

services:
  trivy-scan:
    image: aquasec/trivy:latest
    volumes:
      - ./app-image:/app:ro
    command: >
      image
      --format json
      --severity CRITICAL,HIGH,MEDIUM
      --exit-code 0
      /path/to/app-image
    environment:
      - TRIVY_SKIP_DB_UPDATE=true
      - TRIVY_SKIP_JAVA_DB_UPDATE=true
    networks:
      - scan-network

networks:
  scan-network:
    driver: bridge
```

### `Dockerfile` — Application Image (for Trivy to scan)

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY agents/ ./agents/

EXPOSE 8000

CMD ["python", "-m", "src.workflow.graph"]
```

### `src/tools/trivy_scanner.py` — Trivy CLI Wrapper

```python
import subprocess
import json
from pathlib import Path

def run_trivy_scan(image_name: str = "app-image:latest") -> dict:
    """Run Trivy container scan and return structured results."""
    result = subprocess.run(
        ["trivy", "image", "--format", "json", image_name],
        capture_output=True, text=True
    )
    report = json.loads(result.stdout)
    return {
        "vulnerabilities": extract_vulns(report),
        "severity_counts": count_by_severity(report),
        "exit_code": result.returncode
    }

def extract_vulns(report: dict) -> list[dict]:
    """Extract vulnerability details from Trivy report."""
    vulns = []
    for layer in report.get("Results", []):
        for v in layer.get("Vulnerabilities", []):
            vulns.append({
                "id": v.get("VulnerabilityID"),
                "severity": v.get("Severity"),
                "package": v.get("PkgName"),
                "installed_version": v.get("InstalledVersion"),
                "fixed_version": v.get("FixedVersion")
            })
    return vulns
```

---

## Phase 7: Entry Point & Usage

### `src/main.py` — CLI Entry Point

```python
import json
from src.workflow.graph import app_graph
from src.workflow.state import AppWorkflowState

def main():
    app_description = input("Enter your application description: ")
    
    initial_state = {
        "messages": [{"role": "user", "content": app_description}],
        "app_description": app_description,
        "status": "planning"
    }
    
    result = app_graph.invoke(initial_state)
    
    # Output final summary
    print(json.dumps({
        "plan": result.get("implementation_plan"),
        "tasks": result.get("tasks"),
        "files_written": result.get("code_files_written"),
        "tests_passed": result.get("tests_passed"),
        "vulnerabilities": result.get("vulnerabilities_found"),
        "status": result.get("status")
    }, indent=2))

if __name__ == "__main__":
    main()
```

---

## Phase 8: Implementation Checklist

| # | Task | Priority | Files |
|---|------|----------|-------|
| 1 | Create agent definitions (coder, tester, security) | High | `agents/coder/AGENTS.md`, `agents/tester/AGENTS.md`, `agents/security/AGENTS.md` |
| 2 | Define LangGraph state schema | High | `src/workflow/state.py` |
| 3 | Implement LLM client abstraction | High | `src/agents/llm_client.py` |
| 4 | Build planner & tasker node implementations | High | `src/workflow/nodes.py` (partial) |
| 5 | Create Coder agent + node | High | `src/workflow/nodes.py` (coder) |
| 6 | Create Tester agent + node | High | `src/workflow/nodes.py` (tester) |
| 7 | Implement Trivy scanner tool | Medium | `src/tools/trivy_scanner.py` |
| 8 | Create Dockerfile + docker-compose.yml | Medium | `Dockerfile`, `docker-compose.yml` |
| 9 | Build Security agent + node | Medium | `src/workflow/nodes.py` (security) |
| 10 | Wire up LangGraph graph with edges | High | `src/workflow/graph.py` |
| 11 | Create CLI entry point | Medium | `src/main.py` |
| 12 | Write workflow integration tests | Low | `tests/test_workflow.py` |
| 13 | Add README with usage examples | Low | `README.md` |

---

## Dependencies to Add

```txt
# Add to requirements.txt
docker-compose>=1.29.0
trivy-api>=0.1.0    # Optional: Python SDK for Trivy
pytest-docker>=1.0.0  # For testing Docker-based workflow
```

---

## Key Design Decisions

1. **LangGraph over LangChain chains** — Graph enables conditional loops (test → fix → retest cycle)
2. **Stateful nodes** — Each agent reads/writes a shared TypedDict state for full context visibility
3. **LLM abstraction layer** — `llm_client.py` supports swapping OpenAI ↔ other providers
4. **Trivy as Docker service** — Decouples security scanning; can run independently or inline
5. **Conditional edges** — Test failures loop back to coder; no manual intervention needed
6. **Agent configs as markdown** — `AGENTS.md` files serve as prompt templates (human-readable + machine-parseable)

---

## Risk Mitigations

| Risk | Mitigation |
|------|-----------|
| LLM generates broken code | Tester node loops back to coder with error details |
| Trivy false positives | Report all findings; flag only CRITICAL/HIGH as blocking |
| Large app descriptions overwhelm context | Planner splits into phased plans; tasker batches by priority |
| Docker not available in environment | Trivy can scan files directly (`trivy fs`) as fallback |
| Cost of multiple LLM calls | Cache planner/tasker outputs; batch agent calls where possible |
