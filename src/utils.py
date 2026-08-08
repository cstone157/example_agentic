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