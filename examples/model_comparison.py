#!/usr/bin/env python3
"""
Model Comparison for Style Consistency Environment.

This script allows you to:
1. Generate code with different models (Gemini, Claude, GPT, Qwen, etc.)
2. Save outputs to labeled directories
3. Score each model's output
4. Compare results across models

Usage:
    # First, start the server:
    cd envs/style_env && uv run uvicorn server.app:app --reload --port 8000
    
    # Generate code with a model and save it:
    python examples/model_comparison.py generate --model gemini --prompt-id enterprise-settings-001
    
    # Or provide code directly from a file:
    python examples/model_comparison.py evaluate --model gemini --code-file path/to/Settings.tsx --prompt-id enterprise-settings-001
    
    # Compare all models:
    python examples/model_comparison.py compare
    
    # List available prompts:
    python examples/model_comparison.py list-prompts
"""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

# Add the project root to the path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))
sys.path.insert(0, str(project_root / "envs"))

from style_env import StyleEnv, StyleAction


# Directory to store model outputs
OUTPUTS_DIR = project_root / "model_outputs"
PROMPTS_FILE = project_root / "envs" / "style_env" / "prompts" / "prompts.jsonl"


def load_prompts() -> dict:
    """Load all prompts from the prompts file."""
    prompts = {}
    with open(PROMPTS_FILE) as f:
        for line in f:
            line = line.strip()
            if line:
                prompt = json.loads(line)
                prompts[prompt["id"]] = prompt
    return prompts


def list_prompts():
    """List all available prompts."""
    prompts = load_prompts()
    print("\n📋 Available Prompts:")
    print("=" * 70)
    
    for pid, prompt in prompts.items():
        print(f"\n🔹 {pid}")
        print(f"   Profile: {prompt['profile']}")
        print(f"   Difficulty: {prompt['difficulty']}")
        print(f"   Target: {prompt['target_files']}")
        print(f"   Task: {prompt['task'][:80]}...")
    
    print("\n" + "=" * 70)
    print(f"Total: {len(prompts)} prompts")


def get_model_output_dir(model_name: str, prompt_id: str) -> Path:
    """Get the output directory for a model's response."""
    output_dir = OUTPUTS_DIR / model_name / prompt_id
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def save_code_for_model(model_name: str, prompt_id: str, code: str, filename: str):
    """Save generated code for a model."""
    output_dir = get_model_output_dir(model_name, prompt_id)
    code_file = output_dir / filename
    code_file.write_text(code)
    
    # Also save metadata
    meta_file = output_dir / "metadata.json"
    meta = {
        "model": model_name,
        "prompt_id": prompt_id,
        "filename": filename,
        "generated_at": datetime.now().isoformat(),
        "code_length": len(code),
    }
    meta_file.write_text(json.dumps(meta, indent=2))
    
    print(f"✅ Saved code to {code_file}")
    return code_file


def evaluate_code(
    model_name: str,
    prompt_id: str,
    code: str,
    base_url: str = "http://localhost:8000"
) -> dict:
    """Evaluate code against the style scorer."""
    prompts = load_prompts()
    if prompt_id not in prompts:
        print(f"❌ Unknown prompt ID: {prompt_id}")
        print(f"   Available: {list(prompts.keys())}")
        sys.exit(1)
    
    prompt = prompts[prompt_id]
    target_file = prompt["target_files"][0]  # Primary target
    
    print(f"\n🔍 Evaluating {model_name} on {prompt_id}...")
    print(f"   Profile: {prompt['profile']}")
    print(f"   Target: {target_file}")
    
    try:
        with StyleEnv(base_url=base_url) as env:
            # Reset with specific prompt
            result = env.reset(prompt_id=prompt_id)
            
            # Create the file with the model's code
            result = env.step(StyleAction(
                action_type="CREATE_FILE",
                path=target_file,
                content=code
            ))
            
            # Run scoring
            result = env.step(StyleAction(action_type="RUN", cmd_id="SCORE"))
            
            score_result = {
                "model": model_name,
                "prompt_id": prompt_id,
                "profile": prompt["profile"],
                "difficulty": prompt["difficulty"],
                "score": 0,
                "reward": result.reward,
                "hard_gates_passed": True,
                "violations": [],
                "penalties": 0,
            }
            
            if result.observation.score_breakdown:
                sb = result.observation.score_breakdown
                score_result["score"] = sb.total_score
                score_result["penalties"] = sb.penalties_total
                score_result["violations"] = [
                    {"rule": v.rule, "file": v.file, "line": v.line, "snippet": v.snippet[:50]}
                    for v in sb.rule_violations
                ]
                # hard_gates is a dict like {"build": True, "lint": True, "format": True}
                hard_gates = sb.hard_gates if sb.hard_gates else {}
                score_result["hard_gates_passed"] = all(hard_gates.values()) if hard_gates else True
            
            # Save score result
            output_dir = get_model_output_dir(model_name, prompt_id)
            score_file = output_dir / "score.json"
            score_file.write_text(json.dumps(score_result, indent=2))
            
            return score_result
            
    except ConnectionRefusedError:
        print(f"❌ Could not connect to server at {base_url}")
        print("   Start the server with: cd envs/style_env && uv run uvicorn server.app:app --reload")
        sys.exit(1)


def print_score_result(result: dict):
    """Pretty print a score result."""
    status = "✅" if result["score"] >= 90 else "⚠️" if result["score"] >= 70 else "❌"
    gates = "✅" if result["hard_gates_passed"] else "❌"
    
    print(f"\n{status} {result['model']} on {result['prompt_id']}")
    print(f"   Score: {result['score']}/100")
    print(f"   Reward: {result['reward']:.4f}")
    print(f"   Hard Gates: {gates}")
    print(f"   Penalties: {result['penalties']}")
    print(f"   Violations: {len(result['violations'])}")
    
    if result["violations"]:
        print("   Top violations:")
        for v in result["violations"][:3]:
            print(f"      - [{v['rule']}] {v['file']}:{v['line']}")


def compare_models(prompt_id: Optional[str] = None):
    """Compare scores across all models."""
    if not OUTPUTS_DIR.exists():
        print("❌ No model outputs found. Generate some first with:")
        print("   python examples/model_comparison.py generate --model <name> --prompt-id <id>")
        return
    
    results = []
    
    for model_dir in OUTPUTS_DIR.iterdir():
        if not model_dir.is_dir():
            continue
        
        model_name = model_dir.name
        
        for prompt_dir in model_dir.iterdir():
            if not prompt_dir.is_dir():
                continue
            
            if prompt_id and prompt_dir.name != prompt_id:
                continue
            
            score_file = prompt_dir / "score.json"
            if score_file.exists():
                with open(score_file) as f:
                    results.append(json.load(f))
    
    if not results:
        print("❌ No scored outputs found.")
        return
    
    # Group by prompt
    by_prompt = {}
    for r in results:
        pid = r["prompt_id"]
        if pid not in by_prompt:
            by_prompt[pid] = []
        by_prompt[pid].append(r)
    
    print("\n" + "=" * 70)
    print("MODEL COMPARISON RESULTS")
    print("=" * 70)
    
    for pid, prompt_results in sorted(by_prompt.items()):
        print(f"\n📋 {pid} ({prompt_results[0]['profile']} / {prompt_results[0]['difficulty']})")
        print("-" * 50)
        
        # Sort by score descending
        prompt_results.sort(key=lambda x: x["score"], reverse=True)
        
        for i, r in enumerate(prompt_results):
            rank = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else "  "
            status = "✅" if r["score"] >= 90 else "⚠️" if r["score"] >= 70 else "❌"
            print(f"   {rank} {r['model']:15} {status} Score: {r['score']:3}/100  Violations: {len(r['violations'])}")
    
    # Overall summary
    print("\n" + "=" * 70)
    print("OVERALL SUMMARY")
    print("=" * 70)
    
    by_model = {}
    for r in results:
        model = r["model"]
        if model not in by_model:
            by_model[model] = {"scores": [], "violations": 0, "passed": 0}
        by_model[model]["scores"].append(r["score"])
        by_model[model]["violations"] += len(r["violations"])
        if r["score"] >= 90:
            by_model[model]["passed"] += 1
    
    print(f"\n{'Model':15} {'Avg Score':>10} {'Pass Rate':>12} {'Violations':>12}")
    print("-" * 55)
    
    for model, stats in sorted(by_model.items(), key=lambda x: sum(x[1]["scores"])/len(x[1]["scores"]), reverse=True):
        avg = sum(stats["scores"]) / len(stats["scores"])
        pass_rate = stats["passed"] / len(stats["scores"]) * 100
        print(f"{model:15} {avg:>10.1f} {pass_rate:>10.0f}% {stats['violations']:>12}")


def cmd_generate(args):
    """Command: Generate placeholder for model output."""
    prompts = load_prompts()
    
    if args.prompt_id not in prompts:
        print(f"❌ Unknown prompt ID: {args.prompt_id}")
        list_prompts()
        sys.exit(1)
    
    prompt = prompts[args.prompt_id]
    target_file = Path(prompt["target_files"][0]).name
    
    output_dir = get_model_output_dir(args.model, args.prompt_id)
    code_file = output_dir / target_file
    
    print(f"\n📝 Generate code for: {args.prompt_id}")
    print(f"   Profile: {prompt['profile']}")
    print(f"   Task: {prompt['task']}")
    print(f"\n   Constraints:")
    for c in prompt["constraints"]:
        print(f"   - {c}")
    
    print(f"\n📁 Save your generated code to:")
    print(f"   {code_file}")
    
    print(f"\n   Then evaluate with:")
    print(f"   python examples/model_comparison.py evaluate --model {args.model} --prompt-id {args.prompt_id}")
    
    # Create a placeholder file
    if not code_file.exists():
        placeholder = f"""// TODO: Generate code for {args.prompt_id}
// Profile: {prompt['profile']}
// 
// Task: {prompt['task']}
//
// Constraints:
{chr(10).join(f'//   - {c}' for c in prompt['constraints'])}
//
// Replace this file with your generated code.
"""
        code_file.write_text(placeholder)
        print(f"\n   Created placeholder at {code_file}")


def cmd_evaluate(args):
    """Command: Evaluate a model's code."""
    prompts = load_prompts()
    
    if args.prompt_id not in prompts:
        print(f"❌ Unknown prompt ID: {args.prompt_id}")
        sys.exit(1)
    
    prompt = prompts[args.prompt_id]
    target_file = Path(prompt["target_files"][0]).name
    
    # Find the code file
    if args.code_file:
        code_path = Path(args.code_file)
    else:
        output_dir = get_model_output_dir(args.model, args.prompt_id)
        code_path = output_dir / target_file
    
    if not code_path.exists():
        print(f"❌ Code file not found: {code_path}")
        print(f"\n   First generate code with:")
        print(f"   python examples/model_comparison.py generate --model {args.model} --prompt-id {args.prompt_id}")
        sys.exit(1)
    
    code = code_path.read_text()
    
    # Check if it's just a placeholder
    if "TODO: Generate code" in code:
        print(f"❌ {code_path} still contains placeholder code.")
        print("   Replace it with actual generated code first.")
        sys.exit(1)
    
    # Save the code (in case it was provided via --code-file)
    save_code_for_model(args.model, args.prompt_id, code, target_file)
    
    # Evaluate
    result = evaluate_code(args.model, args.prompt_id, code, args.server)
    print_score_result(result)


def cmd_compare(args):
    """Command: Compare all models."""
    compare_models(args.prompt_id)


def cmd_list(args):
    """Command: List prompts."""
    list_prompts()


def main():
    parser = argparse.ArgumentParser(
        description="Model Comparison for Style Consistency Environment",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List available prompts
  python examples/model_comparison.py list-prompts
  
  # Prepare to generate code for a prompt
  python examples/model_comparison.py generate --model gemini --prompt-id enterprise-settings-001
  
  # Evaluate a model's code
  python examples/model_comparison.py evaluate --model gemini --prompt-id enterprise-settings-001
  
  # Evaluate from a specific file
  python examples/model_comparison.py evaluate --model claude --prompt-id enterprise-settings-001 --code-file /path/to/code.tsx
  
  # Compare all models
  python examples/model_comparison.py compare
  
  # Compare models on a specific prompt
  python examples/model_comparison.py compare --prompt-id enterprise-settings-001
"""
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # generate command
    gen_parser = subparsers.add_parser("generate", help="Prepare to generate code for a prompt")
    gen_parser.add_argument("--model", required=True, help="Model name (e.g., gemini, claude, gpt4, qwen)")
    gen_parser.add_argument("--prompt-id", required=True, help="Prompt ID to generate for")
    gen_parser.set_defaults(func=cmd_generate)
    
    # evaluate command
    eval_parser = subparsers.add_parser("evaluate", help="Evaluate a model's generated code")
    eval_parser.add_argument("--model", required=True, help="Model name")
    eval_parser.add_argument("--prompt-id", required=True, help="Prompt ID")
    eval_parser.add_argument("--code-file", help="Path to code file (optional, defaults to model_outputs/<model>/<prompt>/)")
    eval_parser.add_argument("--server", default="http://localhost:8000", help="Server URL")
    eval_parser.set_defaults(func=cmd_evaluate)
    
    # compare command
    cmp_parser = subparsers.add_parser("compare", help="Compare scores across models")
    cmp_parser.add_argument("--prompt-id", help="Filter to specific prompt ID")
    cmp_parser.set_defaults(func=cmd_compare)
    
    # list-prompts command
    list_parser = subparsers.add_parser("list-prompts", help="List available prompts")
    list_parser.set_defaults(func=cmd_list)
    
    args = parser.parse_args()
    
    if args.command is None:
        parser.print_help()
        sys.exit(1)
    
    args.func(args)


if __name__ == "__main__":
    main()

