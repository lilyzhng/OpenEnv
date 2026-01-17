# Refactor Environment

An RL environment for code refactoring tasks. The agent must reduce duplication and complexity while keeping tests and API contracts passing.

## Overview

This environment presents a "bloated" Python codebase with obvious duplication and complexity issues. The agent's goal is to refactor the code to:

1. **Reduce duplication** (measured by n-gram similarity)
2. **Reduce complexity** (measured by cyclomatic complexity)  
3. **Reduce lines of code** (while maintaining functionality)

All while ensuring:
- Unit tests continue to pass
- The public API contract remains intact

## Action Space

The agent has 4 available actions:

| Action | Parameters | Description |
|--------|------------|-------------|
| `READ_FILE` | `path` | Read contents of a file |
| `SEARCH` | `pattern` | Search for a regex pattern in the codebase |
| `APPLY_PATCH` | `diff` | Apply a unified diff patch |
| `RUN` | `cmd_id` | Run a command: `TEST`, `API_CHECK`, or `METRICS` |

## Observation Space

Each observation contains:

| Field | Type | Description |
|-------|------|-------------|
| `output` | `str` | Output from the last action |
| `tests_pass` | `bool \| None` | Whether tests are passing |
| `api_pass` | `bool \| None` | Whether API check is passing |
| `dup_score` | `float` | Duplication score (0-1, lower is better) |
| `complexity_score` | `float` | Cyclomatic complexity (lower is better) |
| `loc` | `int` | Lines of code |
| `steps_remaining` | `int` | Steps remaining in episode |

## Reward

- If tests or API fail: `reward = -1.0`
- If both pass: `reward = dup_improvement + complexity_improvement + 0.5*loc_improvement - 0.01`

Where improvements are normalized relative to baseline metrics.

## Quick Start

### Using the Client

```python
from envs.refactor_env import RefactorEnv, RefactorAction

# Connect to a running server
with RefactorEnv(base_url="http://localhost:8000") as env:
    # Reset and get initial state
    result = env.reset()
    print(f"Initial metrics:")
    print(f"  Duplication: {result.observation.dup_score:.4f}")
    print(f"  Complexity: {result.observation.complexity_score:.1f}")
    print(f"  LOC: {result.observation.loc}")
    
    # Read a file
    result = env.step(RefactorAction(
        action_type="READ_FILE",
        path="utils/string_helpers.py"
    ))
    print(result.observation.output)
    
    # Run tests
    result = env.step(RefactorAction(
        action_type="RUN",
        cmd_id="TEST"
    ))
    print(f"Tests passed: {result.observation.tests_pass}")
```

### Running the Server

```bash
# From the environment directory
cd envs/refactor_env
uv run --project . server

# Or using Docker
openenv build refactor_env
openenv serve refactor_env
```

## Target Repository

The bundled target repo (`target_repo/`) contains:

- `utils/string_helpers.py` - String formatting with duplicated validation
- `utils/date_helpers.py` - Date parsing with duplicated validation  
- `core/processor.py` - Data processor that duplicates logic from utils
- `tests/test_all.py` - Comprehensive tests
- `api_check.py` - API contract verification

### Refactoring Opportunities

1. **Extract common validation** - The "validate input → strip → check empty" pattern appears in every function
2. **Reuse utility functions** - `processor.py` reimplements logic that exists in `utils/`
3. **Combine similar functions** - `parse_date` and `parse_datetime` share most of their code

## Files

```
refactor_env/
├── __init__.py           # Package exports
├── client.py             # RefactorEnv client
├── models.py             # RefactorAction, RefactorObservation
├── openenv.yaml          # Environment metadata
├── pyproject.toml        # Package configuration
├── README.md             # This file
├── server/
│   ├── __init__.py
│   ├── app.py            # FastAPI application
│   ├── Dockerfile        # Container build
│   ├── metrics.py        # Metric computation
│   └── refactor_environment.py  # Environment implementation
└── target_repo/          # The codebase to refactor
    ├── api_check.py
    ├── core/
    │   └── processor.py
    ├── tests/
    │   └── test_all.py
    └── utils/
        ├── date_helpers.py
        └── string_helpers.py
```

## Development

### Running Tests Locally

```bash
cd envs/refactor_env/target_repo
PYTHONPATH=. pytest -v tests/
```

### Computing Metrics

```bash
cd envs/refactor_env
python -c "from server.metrics import compute_all_metrics; print(compute_all_metrics('target_repo'))"
```

