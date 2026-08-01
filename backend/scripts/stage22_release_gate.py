"""Production gate for the trusted intelligence network."""
from pathlib import Path
import subprocess,sys
ROOT=Path(__file__).resolve().parents[1];REPO=ROOT.parent
COMMANDS=[(ROOT,[sys.executable,"-m","compileall","-q","app","tests","scripts"]),(ROOT,[sys.executable,"-m","alembic","heads"]),(ROOT,[sys.executable,"-m","unittest","tests.test_trusted_ecosystem","tests.test_autonomous_enterprise","tests.test_commercialization","-v"]),(ROOT,[sys.executable,"-m","unittest","discover","-s","tests","-v"]),(REPO/"frontend",["npm.cmd","run","build"])]
def main()->int:
 for cwd,cmd in COMMANDS:
  print("GATE:"," ".join(cmd));result=subprocess.run(cmd,cwd=cwd)
  if result.returncode:return result.returncode
 print("Stage 22 trusted-network production gate passed.");return 0
if __name__=="__main__":raise SystemExit(main())
