#!/usr/bin/env python3
"""Interactive planner CLI that uses LangChain-style agent prompting."""

from __future__ import annotations

import os
from pathlib import Path
from tempfile import gettempdir
from typing import Optional

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI

ROOT = Path(__file__).resolve().parent
AGENTS_PATH = ROOT / "agents" / "planner" / "AGENTS.md"
TEMP_DIR = ROOT / "temp"
TEMP_DIR.mkdir(parents=True, exist_ok=True)
PLAN_PATH = ROOT / "PLAN.md"


def _read_agent_prompt() -> str:
    if AGENTS_PATH.exists():
        return AGENTS_PATH.read_text(encoding="utf-8")
    return "You are a helpful product planner. Create a concise implementation plan."


def generate_plan(application_description: str, agent_prompt: Optional[str] = None, output_dir: Optional[Path] = None) -> str:
    """Generate a plan for an application description and persist it to disk."""
    prompt = agent_prompt or _read_agent_prompt()

    try:
        model = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        planner_prompt = PromptTemplate.from_template(
            "System: {agent_prompt}\n\nUser request: {application_description}\n\nReturn a concise plan in markdown."
        )
        chain = planner_prompt | model | StrOutputParser()
        plan_text = chain.invoke({
            "agent_prompt": prompt,
            "application_description": application_description,
        })
    except Exception:
        plan_text = (
            f"Planner prompt:\n{prompt}\n\n"
            f"Application request:\n{application_description}\n\n"
            "Suggested plan:\n"
            "1. Define the core user stories and app scope.\n"
            "2. Choose the architecture and key technologies.\n"
            "3. Implement the MVP and validate it with a quick demo."
        )

    target_dir = output_dir or TEMP_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    plan_path = target_dir / "PLAN.md"
    print(plan_path)
    plan_path.write_text(plan_text, encoding="utf-8")
    return plan_text


def run_cli() -> None:
    print("Describe the application you want to build.")
    print("Enter your description. Press Enter on an empty line when finished.")

    lines: list[str] = []
    while True:
        line = input()
        if line.strip() == "":
            if lines:
                break
            continue
        lines.append(line)

    application_description = "\n".join(lines).strip()
    if not application_description:
        print("No application description was provided.")
        return

    print("\nSubmitting your request to the planner agent...\n")
    plan_text = generate_plan(application_description)
    print(plan_text)
    print(f"\nPlan saved to {PLAN_PATH}\n")

    while True:
        try:
            review = input("Review the plan and enter corrections, or type 'done' to finish: ").strip()
        except EOFError:
            break
        if review.lower() == "done":
            break
        if review:
            print("\nUpdating the plan with your feedback...\n")
            plan_text = generate_plan(
                f"{application_description}\n\nUser corrections: {review}",
                agent_prompt=_read_agent_prompt(),
            )
            print(plan_text)
            print(f"\nPlan updated and saved to {PLAN_PATH}\n")


if __name__ == "__main__":
    run_cli()
