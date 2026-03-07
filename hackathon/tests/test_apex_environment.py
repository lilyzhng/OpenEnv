"""Tests for APEX environment.

Run with:
    PYTHONPATH=src:envs uv run pytest tests/envs/test_apex_environment.py -v
"""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "envs"))

from apex_env.models import ApexObservation, ApexState, BashAction
from apex_env.server.bash_executor import BashExecutor
from apex_env.server.reward import (
    collect_workspace_text,
    compute_reward,
    extract_keywords_from_rubric,
)


# ============================================================================
# Model Tests
# ============================================================================


class TestModels:
    def test_bash_action_serialization(self):
        action = BashAction(command="ls -la")
        assert action.command == "ls -la"
        data = action.model_dump()
        assert data["command"] == "ls -la"

    def test_apex_observation_defaults(self):
        obs = ApexObservation()
        assert obs.stdout == ""
        assert obs.stderr == ""
        assert obs.exit_code == 0
        assert obs.done is False
        assert obs.reward is None

    def test_apex_observation_with_values(self):
        obs = ApexObservation(
            stdout="hello\n", stderr="", exit_code=0, done=True, reward=0.8
        )
        assert obs.stdout == "hello\n"
        assert obs.done is True
        assert obs.reward == 0.8

    def test_apex_state_defaults(self):
        state = ApexState()
        assert state.task_id is None
        assert state.domain is None
        assert state.max_steps == 20
        assert state.files_in_workspace == []
        assert state.step_count == 0

    def test_apex_state_with_values(self):
        state = ApexState(
            episode_id="ep1",
            step_count=5,
            task_id="42",
            domain="Legal",
            max_steps=10,
        )
        assert state.task_id == "42"
        assert state.domain == "Legal"
        assert state.max_steps == 10


# ============================================================================
# Bash Executor Tests
# ============================================================================


class TestBashExecutor:
    def setup_method(self):
        self.executor = BashExecutor()
        self.tmpdir = Path(tempfile.mkdtemp())

    def test_echo(self):
        result = self.executor.run("echo hello", cwd=self.tmpdir)
        assert result.stdout.strip() == "hello"
        assert result.stderr == ""
        assert result.exit_code == 0

    def test_exit_code(self):
        result = self.executor.run("exit 42", cwd=self.tmpdir)
        assert result.exit_code == 42

    def test_stderr(self):
        result = self.executor.run("echo err >&2", cwd=self.tmpdir)
        assert "err" in result.stderr
        assert result.exit_code == 0

    def test_timeout(self):
        result = self.executor.run("sleep 10", cwd=self.tmpdir, timeout_s=0.5)
        assert result.exit_code == 124
        assert "timed out" in result.stderr.lower()

    def test_cwd(self):
        result = self.executor.run("pwd", cwd=self.tmpdir)
        # macOS resolves /var → /private/var via symlink
        assert os.path.realpath(result.stdout.strip()) == os.path.realpath(
            str(self.tmpdir)
        )

    def test_file_creation(self):
        self.executor.run("echo content > test.txt", cwd=self.tmpdir)
        assert (self.tmpdir / "test.txt").exists()
        assert (self.tmpdir / "test.txt").read_text().strip() == "content"

    def test_output_truncation(self):
        result = self.executor.run(
            "python3 -c \"print('x' * 20000)\"", cwd=self.tmpdir
        )
        assert len(result.stdout) <= 10000


# ============================================================================
# Reward Tests
# ============================================================================


class TestReward:
    def setup_method(self):
        self.tmpdir = Path(tempfile.mkdtemp())

    def test_no_output_no_rubric(self):
        task = {"rubric": []}
        score = compute_reward(task, self.tmpdir)
        assert score == 0.0

    def test_output_exists_no_rubric(self):
        (self.tmpdir / "output.txt").write_text("some analysis")
        task = {"rubric": []}
        score = compute_reward(task, self.tmpdir)
        assert score == 0.3

    def test_keyword_matching(self):
        (self.tmpdir / "output.txt").write_text(
            "The applicable statute is Section 1983 of Title 42."
        )
        task = {
            "rubric": [
                {
                    "criterion": "Identifies Section 1983",
                    "weight": 0.5,
                    "description": 'Agent should cite "Section 1983" and "Title 42"',
                }
            ]
        }
        score = compute_reward(task, self.tmpdir)
        assert score > 0.3  # At least file existence bonus

    def test_rubric_as_json_string(self):
        import json

        (self.tmpdir / "output.txt").write_text("analysis")
        rubric = [{"criterion": "Test", "weight": 1.0, "description": "desc"}]
        task = {"rubric": json.dumps(rubric)}
        score = compute_reward(task, self.tmpdir)
        assert score >= 0.3

    def test_extract_keywords(self):
        rubric = [
            {
                "criterion": "Identifies the Federal Reserve policy",
                "description": 'Must mention "quantitative easing"',
            }
        ]
        keywords = extract_keywords_from_rubric(rubric)
        assert len(keywords) > 0
        assert "quantitative easing" in keywords

    def test_collect_workspace_text(self):
        (self.tmpdir / "a.txt").write_text("hello")
        (self.tmpdir / "b.md").write_text("world")
        (self.tmpdir / "c.bin").write_bytes(b"\x00\x01")
        text = collect_workspace_text(self.tmpdir)
        assert "hello" in text
        assert "world" in text


# ============================================================================
# Environment Integration Tests (with mocked TaskLoader)
# ============================================================================


MOCK_TASK = {
    "task_id": "test_001",
    "domain": "Legal",
    "prompt": "Analyze the contract for liability clauses.",
    "rubric": [
        {
            "criterion": "Identifies Liability Clauses",
            "weight": 0.5,
            "description": 'Must identify "indemnification" provisions',
        },
        {
            "criterion": "Provides Recommendation",
            "weight": 0.5,
            "description": "Agent should recommend changes",
        },
    ],
}


class TestApexEnvironment:
    def setup_method(self):
        from apex_env.server.apex_environment import ApexEnvironment

        self.env = ApexEnvironment()
        # Patch task loader to avoid HF download
        self.env._task_loader._tasks = [MOCK_TASK]

    def teardown_method(self):
        self.env.close()

    def test_reset(self):
        obs = self.env.reset()
        assert isinstance(obs, ApexObservation)
        assert obs.done is False
        assert obs.reward is None
        assert "test_001" in obs.stdout
        assert "Legal" in obs.stdout
        assert self.env.state.task_id == "test_001"
        assert self.env.state.step_count == 0

    def test_step_ls(self):
        self.env.reset()
        obs = self.env.step(BashAction(command="ls"))
        assert isinstance(obs, ApexObservation)
        assert obs.exit_code == 0
        assert obs.done is False
        assert self.env.state.step_count == 1

    def test_step_creates_file(self):
        self.env.reset()
        self.env.step(BashAction(command="echo 'analysis' > output.txt"))
        assert "output.txt" in self.env.state.files_in_workspace

    def test_agent_done(self):
        self.env.reset()
        self.env.step(BashAction(command="echo 'result' > output.txt"))
        obs = self.env.step(BashAction(command="done"))
        assert obs.done is True
        assert obs.reward is not None
        assert obs.reward >= 0.0

    def test_step_limit(self):
        self.env.reset()
        self.env.state.max_steps = 3
        self.env.step(BashAction(command="echo 1"))
        self.env.step(BashAction(command="echo 2"))
        obs = self.env.step(BashAction(command="echo 3"))
        assert obs.done is True
        assert obs.reward is not None

    def test_reset_cleans_previous_workspace(self):
        self.env.reset()
        first_workspace = self.env._workspace_dir
        assert first_workspace is not None
        assert first_workspace.exists()
        self.env.reset()
        assert not first_workspace.exists()

    def test_reward_with_output(self):
        self.env.reset()
        self.env.step(
            BashAction(
                command="echo 'The indemnification clause provides liability protection' > output.txt"
            )
        )
        obs = self.env.step(BashAction(command="done"))
        assert obs.reward is not None
        assert obs.reward > 0.0

    def test_invalid_action_type(self):
        from openenv.core.env_server.types import Action

        self.env.reset()
        with pytest.raises(ValueError, match="Expected BashAction"):
            self.env.step(Action())

    def test_step_before_reset(self):
        with pytest.raises(RuntimeError, match="Must call reset"):
            self.env.step(BashAction(command="ls"))

    def test_reset_with_task_id(self):
        obs = self.env.reset(task_id="test_001")
        assert self.env.state.task_id == "test_001"

    def test_close_cleans_workspace(self):
        self.env.reset()
        workspace = self.env._workspace_dir
        assert workspace.exists()
        self.env.close()
        assert not workspace.exists()
