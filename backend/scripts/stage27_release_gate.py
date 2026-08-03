"""Stage 27 production gate."""
import subprocess,sys
COMMANDS=[[sys.executable,"-m","compileall","-q","app"],[sys.executable,"-m","pytest","-q","tests/test_cognitive_infrastructure.py","tests/test_planetary_resilience.py"]]
def main()->int:
 for command in COMMANDS:
  print("+"," ".join(command),flush=True);result=subprocess.run(command,check=False)
  if result.returncode:return result.returncode
 print("Stage 27 release gate passed.");return 0
if __name__=="__main__":raise SystemExit(main())
