from pathlib import Path

import build


def test_buil_script_exists():
    path = Path(__file__).resolve().parent.parent / 'build.py'
    assert path.exists(), 'build.py should exist'


def test_planner_agent_file_exists():
    path = Path(__file__).resolve().parent.parent / 'agents' / 'planner' / 'AGENTS.md'
    assert path.exists(), 'Planner AGENTS.md should exist'


def test_generate_plan_returns_text_and_writes_plan_file(tmp_path):
    plan_text = build.generate_plan('Build a to-do app', agent_prompt='Planner instructions', output_dir=tmp_path)
    assert 'to-do app' in plan_text.lower()
    assert (tmp_path / 'PLAN.md').exists()
