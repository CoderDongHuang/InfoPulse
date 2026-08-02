"""Stage 23 production gate."""
import subprocess
import sys


COMMANDS = [
    [sys.executable, "-m", "compileall", "-q", "app"],
    [sys.executable, "-m", "pytest", "-q", "tests/test_global_coordination.py", "tests/test_trusted_ecosystem.py"],
]


def main() -> int:
    for command in COMMANDS:
        print("+", " ".join(command), flush=True)
        result = subprocess.run(command, check=False)
        if result.returncode:
            return result.returncode
    print("Stage 23 release gate passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
