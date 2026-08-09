from pathlib import Path

def print_and_save_md(txt: str, type: str, file_name: str):
    print("=" * 60)
    print(f"CURRENT {type.upper()}:")
    print("=" * 60)
    print(txt)
    print("=" * 60)

    tmp_dir = Path(__file__).resolve().parent.parent / "tmp"
    tmp_dir.mkdir(exist_ok=True)
    plan_path = tmp_dir / file_name
    with open(plan_path, "w", encoding="utf-8") as f:
        f.write(txt)
    print(f"\n{type.capitalize()} saved to {plan_path}")

def load_file(file_name: str) -> str | None:
    """Load an existing plan from tmp/PLAN.md if it exists.

    Returns:
        The plan text if the file exists, otherwise None.
    """
    tmp_dir = Path(__file__).resolve().parent.parent / "tmp"
    plan_path = tmp_dir / file_name
    print(plan_path)
    if plan_path.exists():
        with open(plan_path, "r", encoding="utf-8") as f:
            return f.read()
    return None