#!/usr/bin/env python3
"""
Simple example demonstrating the Style Consistency Environment.

This script shows how to:
1. Connect to a running StyleEnv server
2. Get the current task and profile
3. Create a page that follows style guidelines
4. Run scoring to evaluate style consistency

Usage:
    # First, start the server:
    docker run -p 8000:8000 style-env:latest
    # or
    cd envs/style_env && uvicorn server.app:app --reload

    # Then run this script:
    python examples/style_simple.py
"""

import sys
from pathlib import Path

# Add the project root to the path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))
sys.path.insert(0, str(project_root / "envs"))

from style_env import StyleEnv, StyleAction


def main():
    """Run a simple style environment episode."""
    base_url = "http://localhost:8000"

    print("=" * 60)
    print("Style Consistency Environment Example")
    print("=" * 60)
    print()

    try:
        with StyleEnv(base_url=base_url) as env:
            # Reset the environment
            print("Resetting environment...")
            result = env.reset()

            print(f"\n📋 Task assigned:")
            print(f"   Profile: {result.observation.current_profile}")
            print(f"   Task: {result.observation.task_description}")
            print(f"   Steps remaining: {result.observation.steps_remaining}")
            print()

            # Get the profile rules
            print("📜 Getting profile rules...")
            result = env.step(StyleAction(action_type="GET_PROFILE"))
            print(result.observation.output[:500])
            print("..." if len(result.observation.output) > 500 else "")
            print()

            # Read an existing file to understand the structure
            print("📖 Reading App.tsx to understand structure...")
            result = env.step(StyleAction(
                action_type="READ_FILE",
                path="src/App.tsx"
            ))
            print(result.observation.output[:400])
            print()

            # Create a simple Settings page following the rules
            # Create a Settings page using proper components (should score 100)
            print("✏️ Creating Settings.tsx...")
            settings_code = '''import { useState } from "react";
import { Button } from "../components/ui/Button";
import { Input } from "../components/ui/Input";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/Card";

export default function Settings() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="mx-auto max-w-4xl">
        <h1 className="mb-6 text-2xl font-semibold text-gray-900">Settings</h1>

        {/* Sidebar */}
        <div className="flex gap-6">
          <nav className="w-48 space-y-2">
            <Button variant="primary" className="w-full justify-start">
              Profile
            </Button>
            <Button variant="ghost" className="w-full justify-start">
              Security
            </Button>
            <Button variant="ghost" className="w-full justify-start">
              Notifications
            </Button>
          </nav>

          {/* Main content */}
          <Card className="flex-1">
            <CardHeader>
              <CardTitle>Profile Settings</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700">
                  Name
                </label>
                <Input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Enter your name"
                />
              </div>

              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700">
                  Email
                </label>
                <Input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="Enter your email"
                />
              </div>

              <div className="pt-4">
                <Button>Save Changes</Button>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
'''

            result = env.step(StyleAction(
                action_type="CREATE_FILE",
                path="src/pages/Settings.tsx",
                content=settings_code
            ))
            print(f"   {result.observation.output}")
            print()

            # Run scoring
            print("🎯 Running style scoring...")
            result = env.step(StyleAction(action_type="RUN", cmd_id="SCORE"))

            print("\n" + "=" * 60)
            print("SCORE RESULTS")
            print("=" * 60)
            print(result.observation.output)
            print()

            if result.observation.score_breakdown:
                sb = result.observation.score_breakdown
                print(f"\n📊 Final Score: {sb.total_score}/100")
                print(f"   Penalties: {sb.penalties_total}")
                print(f"   Violations: {len(sb.rule_violations)}")

                if sb.rule_violations:
                    print("\n   Top violations:")
                    for v in sb.rule_violations[:5]:
                        print(f"   - [{v.rule}] {v.file}:{v.line} - {v.snippet[:40]}")

            print(f"\n💰 Reward: {result.reward:.4f}")
            print(f"   Done: {result.done}")

    except ConnectionRefusedError:
        print("❌ Error: Could not connect to server at", base_url)
        print("   Make sure the server is running:")
        print("   docker run -p 8000:8000 style-env:latest")
        print("   or")
        print("   cd envs/style_env && uvicorn server.app:app --reload")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

