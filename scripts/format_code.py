#!/usr/bin/env python3
"""
Development script for formatting code automatically.
"""

import subprocess
import sys

# Ensure proper encoding for Windows
if sys.platform == "win32":
    import os
    os.system("chcp 65001 >nul")


def run_command(command: list[str], description: str) -> bool:
    """Run a command and return True if successful."""
    print(f"\n[FORMAT] {description}")
    print(f"Running: {' '.join(command)}")
    
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        if result.stdout:
            print(result.stdout)
        print(f"[DONE] {description} - COMPLETED")
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
    """Format code automatically."""
    print("[START] Auto-formatting code...")
    
    formatting_steps = [
        (["uv", "run", "isort", "."], "Sorting imports with isort"),
        (["uv", "run", "black", "."], "Formatting code with black"),
    ]
    
    results = []
    for command, description in formatting_steps:
        success = run_command(command, description)
        results.append((description, success))
    
    print("\n" + "="*50)
    print("[SUMMARY] FORMATTING SUMMARY")
    print("="*50)
    
    all_passed = True
    for description, success in results:
        status = "[DONE] COMPLETED" if success else "[FAIL] FAILED"
        print(f"{description:.<30} {status}")
        if not success:
            all_passed = False
    
    if all_passed:
        print("\n[SUCCESS] Code formatting completed successfully!")
        print("[INFO] Run 'python scripts/quality_check.py' to verify quality checks pass.")
        sys.exit(0)
    else:
        print("\n[ERROR] Some formatting steps failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()