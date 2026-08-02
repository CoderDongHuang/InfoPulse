"""Stage 24 production gate."""
import subprocess
import sys

COMMANDS = [
    [sys.executable, "-m", "compileall", "-q", "app"],
    [sys.executable, "-m", "pytest", "-q", "tests/test_adaptive_intelligence.py", "tests/test_global_coordination.py"],
]


def main() -> int:
    for command in COMMANDS:
        print("+", " ".join(command), flush=True)
        result = subprocess.run(command, check=False)
        if result.returncode: return result.returncode
    print("Stage 24 release gate passed."); return 0


if __name__ == "__main__": raise SystemExit(main())
