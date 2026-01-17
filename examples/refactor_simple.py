#!/usr/bin/env python3
"""
Simple example demonstrating the Refactor Environment.

This example shows how to:
1. Connect to the environment
2. Reset and inspect initial state
3. Read files and search for patterns
4. Run tests and metrics
5. Apply a simple patch

Usage:
    # First start the server:
    cd envs/refactor_env && uv run --project . server
    
    # Then run this example (from OpenEnv root):
    PYTHONPATH=envs/refactor_env python examples/refactor_simple.py
    
    # Or from the refactor_env directory:
    cd envs/refactor_env && uv run python ../../examples/refactor_simple.py
"""

import sys
from pathlib import Path

# Add refactor_env to path for imports
refactor_env_path = Path(__file__).parent.parent / "envs" / "refactor_env"
sys.path.insert(0, str(refactor_env_path))

from client import RefactorEnv
from models import RefactorAction


def main():
    print("=" * 60)
    print("Refactor Environment Demo")
    print("=" * 60)
    
    # Connect to the environment server
    with RefactorEnv(base_url="http://localhost:8000") as env:
        # Reset the environment
        print("\n[1] Resetting environment...")
        result = env.reset()
        
        print(f"\nInitial observation:")
        print(f"  Duplication Score: {result.observation.dup_score:.4f}")
        print(f"  Complexity Score:  {result.observation.complexity_score:.1f}")
        print(f"  Lines of Code:     {result.observation.loc}")
        print(f"  Steps Remaining:   {result.observation.steps_remaining}")
        print(f"\n{result.observation.output}")
        
        # Read a file to see the duplication
        print("\n" + "=" * 60)
        print("[2] Reading utils/string_helpers.py...")
        result = env.step(RefactorAction(
            action_type="READ_FILE",
            path="utils/string_helpers.py"
        ))
        # Print first 50 lines
        lines = result.observation.output.split("\n")[:50]
        print("\n".join(lines))
        if len(result.observation.output.split("\n")) > 50:
            print("... (truncated)")
        
        # Search for duplicated patterns
        print("\n" + "=" * 60)
        print("[3] Searching for duplicated validation pattern...")
        result = env.step(RefactorAction(
            action_type="SEARCH",
            pattern="if.*is None"
        ))
        print(f"\n{result.observation.output}")
        
        # Run tests to establish baseline
        print("\n" + "=" * 60)
        print("[4] Running tests...")
        result = env.step(RefactorAction(
            action_type="RUN",
            cmd_id="TEST"
        ))
        print(f"\nTests passed: {result.observation.tests_pass}")
        
        # Run API check
        print("\n" + "=" * 60)
        print("[5] Running API check...")
        result = env.step(RefactorAction(
            action_type="RUN",
            cmd_id="API_CHECK"
        ))
        print(f"\nAPI check passed: {result.observation.api_pass}")
        
        # Show current metrics
        print("\n" + "=" * 60)
        print("[6] Getting detailed metrics...")
        result = env.step(RefactorAction(
            action_type="RUN",
            cmd_id="METRICS"
        ))
        print(f"\n{result.observation.output}")
        
        # Show final reward
        print("\n" + "=" * 60)
        print("Final State:")
        print(f"  Reward: {result.reward:.4f}")
        print(f"  Done: {result.done}")
        print(f"  Steps Remaining: {result.observation.steps_remaining}")
        
        print("\n" + "=" * 60)
        print("Demo complete! The environment is ready for refactoring.")
        print("Try applying patches to reduce duplication and complexity.")
        print("=" * 60)


if __name__ == "__main__":
    main()

