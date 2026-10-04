"""Copy the calculator and curated references into the agent skill (tests check they match)."""
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "skills" / "consumer-justice-audit"

shutil.copyfile(ROOT / "backend" / "apr.py", SKILL / "scripts" / "apr.py")
for name in ("statutes.json", "rules.json"):
    shutil.copyfile(ROOT / "data" / name, SKILL / "references" / name)
print("skill synced")
