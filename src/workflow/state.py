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