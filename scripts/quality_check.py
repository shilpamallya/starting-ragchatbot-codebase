#!/usr/bin/env python3
"""
Development script for running code quality checks.
"""

import subprocess
import sys
from pathlib import Path

# Ensure proper encoding for Windows
if sys.platform == "win32":
    import os
    os.system("chcp 65001 >nul")


def run_command(command: list[str], description: str) -> bool:
    """Run a command and return True if successful."""
    print(f"\n[CHECK] {description}")
    print(f"Running: {' '.join(command)}")
    
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        if result.stdout:
            print(result.stdout)
        print(f"[PASS] {description} - PASSED")
        return True
    except subprocess.CalledProcessError as e:
        print(f"[FAIL] {description} - FAILED")
        if e.stdout:
            print("STDOUT:")
            print(e.stdout)
        if e.stderr:
            print("STDERR:")
            print(e.stderr)
        return False


def main():
    """Run all code quality checks."""
    print("[START] Running code quality checks...")
    
    checks = [
        (["uv", "run", "black", "--check", "."], "Black formatting check"),
        (["uv", "run", "isort", "--check-only", "."], "Import sorting check"),
        (["uv", "run", "flake8", "."], "Flake8 linting"),
        (["uv", "run", "mypy", "."], "Type checking with mypy"),
    ]
    
    results = []
    for command, description in checks:
        success = run_command(command, description)
        results.append((description, success))
    
    print("\n" + "="*50)
    print("[SUMMARY] QUALITY CHECK SUMMARY")
    print("="*50)
    
    all_passed = True
    for description, success in results:
        status = "[PASS] PASSED" if success else "[FAIL] FAILED"
        print(f"{description:.<30} {status}")
        if not success:
            all_passed = False
    
    if all_passed:
        print("\n[SUCCESS] All quality checks passed!")
        sys.exit(0)
    else:
        print("\n[ERROR] Some quality checks failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()