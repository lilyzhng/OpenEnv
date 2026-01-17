# RefactorEnv MVP Plan

Build a tiny OpenEnv environment that does exactly one thing:

**"One refactor episode: reduce duplication/complexity while keeping tests + API contract passing."**

You can extend later to multi-stage release engineering, multi-task suites, richer action spaces. But the MVP should be one deterministic repo, one gate script, one metric script.

---

## What to Fork / Start From

Fork OpenEnv and copy the smallest example env (`echo_env`). Then implement your own env in `envs/refactor_env/`. This keeps you aligned with the challenge's "OpenEnv first" expectation.

Follow the existing patterns:
- **Client**: Extend `EnvClient` with your action/observation types (see `coding_env/client.py`)
- **Server**: Implement `Environment` interface with `reset()` and `step()` (see `coding_env/server/python_codeact_env.py`)
- **Models**: Define Pydantic models for actions/observations
- **Docker**: Package server in container for sandboxed execution

---

## MVP Architecture (Keep It Boring on Purpose)

### Target Repo (You Must Design This)

Bundle a small "bloated" repo inside your environment package (~200-300 LOC total). **Design it yourself** rather than using an existing OSS repo because:

1. You control the difficulty exactly
2. You guarantee the duplication is "solvable" (clear refactoring paths exist)  
3. Tests are written to exercise the duplicated code
4. Small enough to fit in LLM context

**Example structure:**
```
target_repo/
├── utils/
│   ├── string_helpers.py    # format_name(), format_title() - 80% identical
│   └── date_helpers.py      # parse_date(), parse_datetime() - duplicated parsing
├── core/
│   └── processor.py         # uses both, has inline duplicated validation
├── tests/
│   └── test_all.py          # covers the public API behavior
└── api_check.py             # asserts public symbols exist with correct signatures
```

**Design goals:**
- A human could refactor it in 15 minutes
- 2-3 clear wins (extract function, merge modules, DRY a pattern)
- Tests actually fail if you break behavior
- Metrics visibly improve after a good refactor

**Time investment:** ~1-2 hours to write bloated repo + tests + API check script.

---

### Action Space

Your environment exposes 4 actions via a single `RefactorAction` model:

```python
class RefactorAction(Action):
    action_type: Literal["READ_FILE", "SEARCH", "APPLY_PATCH", "RUN"]
    path: str | None = None           # for READ_FILE
    pattern: str | None = None        # for SEARCH  
    diff: str | None = None           # for APPLY_PATCH (unified diff text)
    cmd_id: Literal["TEST", "API_CHECK", "METRICS"] | None = None  # for RUN
```

### Observation Space

```python
class RefactorObservation(Observation):
    output: str                       # last command/file output
    tests_pass: bool | None = None    # None if not yet run
    api_pass: bool | None = None      # None if not yet run
    dup_score: float                  # duplication metric (lower = better)
    complexity_score: float           # cyclomatic complexity (lower = better)
    loc: int                          # lines of code
    steps_remaining: int              # budget countdown
```

---

### Metrics Implementation

**Keep metrics cheap** — if computation takes 5+ seconds, training will crawl.

| Metric | Tool | Notes |
|--------|------|-------|
| `dup_score` | Token n-gram shingles | Compare 5-grams across files, count duplicates |
| `complexity_score` | `radon` library | Cyclomatic complexity, sum across functions |
| `loc` | `wc -l` equivalent | Simple line count, exclude blanks/comments |

Consider caching baseline metrics at `reset()` and computing deltas incrementally.

---

### Reward Function

```python
if not tests_pass or not api_pass:
    reward = -1.0  # hard penalty for breaking things
else:
    # All metrics: lower = better, so we reward drops
    dup_drop = (baseline_dup - current_dup) / baseline_dup
    complexity_drop = (baseline_complexity - current_complexity) / baseline_complexity
    loc_drop = (baseline_loc - current_loc) / baseline_loc * 0.5  # weight LOC less
    
    step_penalty = 0.01  # small cost per step
    reward = dup_drop + complexity_drop + loc_drop - step_penalty
```

**Hardcode weights initially.** Don't make them configurable until you have data showing they need tuning.

---

### Sandbox Strategy

Use Docker (following the `coding_env` pattern):
- Container runs the FastAPI server
- `APPLY_PATCH` modifies files inside container
- `RUN(TEST)` executes pytest inside container
- Each `reset()` restores the original repo state

---

## First Win: The E2E Loop

Don't try to train anything at first. Just make this loop work end-to-end:

1. `reset()` produces repo state + baseline metrics
2. One `APPLY_PATCH` changes files  
3. `RUN(TEST)` actually runs in sandbox and returns pass/fail
4. `RUN(METRICS)` recomputes scores
5. Reward updates correctly

**That's your first win.** Verify manually before adding any training infrastructure.

---

## How to Avoid Complexity Creep

- ❌ Do not support arbitrary shell commands. Only allow fixed list: `TEST`, `API_CHECK`, `METRICS`
- ❌ Do not build a huge task suite. Ship 1 repo + 1 episode first
- ❌ Do not integrate W&B, GPUs, or real training. Your "ship gates" are tests + API + metrics
- ❌ Do not make reward weights configurable. Hardcode them

---

## Directory Layout

```
envs/refactor_env/
├── __init__.py
├── client.py              # RefactorEnv(EnvClient) 
├── models.py              # RefactorAction, RefactorObservation, RefactorState
├── openenv.yaml           # environment metadata
├── pyproject.toml         # standalone package config
├── README.md
├── server/
│   ├── __init__.py
│   ├── app.py             # FastAPI app via create_app()
│   ├── Dockerfile
│   ├── refactor_env.py    # Environment implementation
│   └── metrics.py         # dup_score, complexity_score, loc computation
└── target_repo/           # The bloated repo to refactor
    ├── utils/
    ├── core/
    ├── tests/
    └── api_check.py
```

---

## Extension Path (Later, When MVP Works)

1. Add a second repo instance (different duplication pattern)
2. Add a "budget" constraint (max test runs)
3. Add a release gate (packaging, lint)
4. Add curriculum: small refactor → medium → big
5. Support multiple languages (start with Python only)

---

## Implementation Checklist

- [ ] Create `envs/refactor_env/` directory structure
- [ ] Design and write the bloated target repo (~200-300 LOC)
- [ ] Write tests that cover target repo behavior
- [ ] Write `api_check.py` script
- [ ] Implement `metrics.py` (dup_score, complexity_score, loc)
- [ ] Implement `RefactorAction` and `RefactorObservation` models
- [ ] Implement `RefactorEnv` server with `reset()` and `step()`
- [ ] Implement `RefactorEnv` client
- [ ] Create Dockerfile
- [ ] Test the E2E loop manually
- [ ] Write a simple example script
