"""Production gate for autonomous enterprise controls."""
from pathlib import Path
import subprocess,sys
ROOT=Path(__file__).resolve().parents[1];REPO=ROOT.parent
COMMANDS=[(ROOT,[sys.executable,"-m","compileall","-q","app","tests","scripts"]),(ROOT,[sys.executable,"-m","alembic","heads"]),(ROOT,[sys.executable,"-m","unittest","tests.test_autonomous_enterprise","tests.test_commercialization","tests.test_stage18_19_e2e","-v"]),(ROOT,[sys.executable,"-m","unittest","discover","-s","tests","-v"]),(REPO/"frontend",["npm.cmd","run","build"])]
def evidence_errors()->list[str]:
 from app.models.autonomous_enterprise import RecoveryDrill,SafetyEvaluation
 required={"recovery_gate":RecoveryDrill.__tablename__,"safety_gate":SafetyEvaluation.__tablename__}
 return [f"missing gate model: {key}" for key,value in required.items() if not value]
def main()->int:
 for cwd,cmd in COMMANDS:
  print("GATE:"," ".join(cmd));result=subprocess.run(cmd,cwd=cwd)
  if result.returncode:return result.returncode
 errors=evidence_errors()
 if errors:
  for error in errors:print("BLOCKED:",error)
  return 1
 print("Stage 21 production gate passed.");return 0
if __name__=="__main__":raise SystemExit(main())
