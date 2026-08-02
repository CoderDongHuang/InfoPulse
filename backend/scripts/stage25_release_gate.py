"""Stage 25 production gate."""
import subprocess, sys

COMMANDS = [[sys.executable, "-m", "compileall", "-q", "app"], [sys.executable, "-m", "pytest", "-q", "tests/test_provable_autonomy.py", "tests/test_adaptive_intelligence.py"]]


def main() -> int:
    for command in COMMANDS:
        print("+", " ".join(command), flush=True); result = subprocess.run(command, check=False)
        if result.returncode: return result.returncode
    print("Stage 25 release gate passed."); return 0


if __name__ == "__main__": raise SystemExit(main())
