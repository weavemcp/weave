#!/usr/bin/env python3
"""Test runner script for Weave CLI tests"""

import sys
import subprocess
import os


def run_command(cmd, description):
    """Run a command and report results"""
    print(f"\n{'='*60}")
    print(f"Running: {description}")
    print(f"Command: {cmd}")
    print("=" * 60)

    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

    if result.stdout:
        print("STDOUT:")
        print(result.stdout)

    if result.stderr:
        print("STDERR:")
        print(result.stderr)

    if result.returncode == 0:
        print(f"✅ {description} - PASSED")
        return True
    else:
        print(f"❌ {description} - FAILED (exit code: {result.returncode})")
        return False


def main():
    """Main test runner"""
    print("🧪 Weave CLI Test Suite Runner")
    print("==============================")

    # Set up environment
    test_env = os.environ.copy()
    test_env.pop("WEAVE_TEST_TOKEN", None)  # Remove integration token for unit tests

    tests = [
        ("uv run pytest --version", "Check pytest installation"),
        ("uv run pytest --collect-only -q", "Test collection"),
        ("uv run pytest tests/unit/ -v --tb=short", "Unit tests"),
        (
            "uv run pytest tests/integration/ --collect-only",
            "Integration test collection",
        ),
    ]

    results = []
    for cmd, description in tests:
        success = run_command(cmd, description)
        results.append((description, success))

    # Summary
    print(f"\n{'='*60}")
    print("TEST SUMMARY")
    print("=" * 60)

    total_tests = len(results)
    passed_tests = sum(1 for _, success in results if success)

    for description, success in results:
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"{status}: {description}")

    print(f"\nTotal: {passed_tests}/{total_tests} tests passed")

    if passed_tests == total_tests:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n💥 {total_tests - passed_tests} test(s) failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
