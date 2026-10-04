"""The agent skill must ship the exact same calculator and references as the app."""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "skills" / "consumer-justice-audit"


def test_skill_files_in_sync():
    assert (SKILL / "scripts" / "apr.py").read_bytes() == (ROOT / "backend" / "apr.py").read_bytes()
    for name in ("statutes.json", "rules.json"):
        assert (SKILL / "references" / name).read_bytes() == (ROOT / "data" / name).read_bytes(), name


def test_skill_frontmatter():
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    fm = re.match(r"^---\n(.*?)\n---\n", text, re.S).group(1)
    name = re.search(r"^name: (.+)$", fm, re.M).group(1).strip()
    desc = re.search(r"^description: (.+)$", fm, re.M).group(1).strip()
    assert name == SKILL.name and re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", name) and len(name) <= 64
    assert 0 < len(desc) <= 1024


def test_skill_script_runs_standalone():
    out = subprocess.run(
        [sys.executable, str(SKILL / "scripts" / "apr.py"), "--principal", "10000", "--n", "12",
         "--stated-rate", "12", "--rate-type", "flat", "--text"],
        capture_output=True, text=True, check=True,
    ).stdout
    assert "APR" in out
