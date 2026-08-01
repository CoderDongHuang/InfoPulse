"""Executable production gate for stages 18-20. Run from the backend directory."""
from pathlib import Path
import subprocess,sys
ROOT=Path(__file__).resolve().parents[1];REPO=ROOT.parent
COMMANDS=[
 (ROOT,[sys.executable,"-m","compileall","-q","app","tests"]),
 (ROOT,[sys.executable,"-m","alembic","heads"]),
 (ROOT,[sys.executable,"-m","unittest","tests.test_global_intelligence","tests.test_stage18_19_e2e","tests.test_commercialization","-v"]),
 (ROOT,[sys.executable,"-m","unittest","discover","-s","tests","-v"]),
 (REPO/"frontend",["npm.cmd","run","build"]),
]
def main()->int:
 for cwd,command in COMMANDS:
  print(f"GATE: {' '.join(command)}")
  result=subprocess.run(command,cwd=cwd)
  if result.returncode:return result.returncode
 heads=subprocess.run([sys.executable,"-m","alembic","heads"],cwd=ROOT,capture_output=True,text=True)
 if len([x for x in heads.stdout.splitlines() if x.strip()])!=1:print("BLOCKED: migration graph must have exactly one head");return 1
 print("Stage 20 production gate passed.");return 0
if __name__=="__main__":raise SystemExit(main())
