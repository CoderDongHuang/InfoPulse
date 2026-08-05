import subprocess,sys
COMMANDS=[[sys.executable,"-m","compileall","-q","app"],[sys.executable,"-m","pytest","-q","tests/test_cognitive_commons.py","tests/test_cognitive_infrastructure.py"]]
def main():
 for c in COMMANDS:
  print("+"," ".join(c),flush=True);r=subprocess.run(c,check=False)
  if r.returncode:return r.returncode
 print("Stage 28 release gate passed.");return 0
if __name__=="__main__":raise SystemExit(main())
