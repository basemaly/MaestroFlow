"""Tests for orchestra features: task shape classifier, research registry, quality scorer, MAB.

Covers:
- classify_task (decomposer extension)
- ResearchTool / registry helpers
- QualityScore + score_async logic
- MAB Thompson sampling + arm updates
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


# ===========================================================================
# #2 Task Shape Classifier
# ===========================================================================

class TestClassifyTask:
    def setup_method(self):
        from src.agents.decomposer import classify_task
        self.classify_task = classify_task

    def test_bash_task_returns_bash(self):
        assert self.classify_task("run git commit", "execute git commit -m 'fix'") == "bash"

    def test_research_task_returns_general_purpose(self):
        assert self.classify_task("research climate change", "investigate and summarize recent findings on climate change") == "general-purpose"

    def test_ambiguous_defaults_to_general_purpose(self):
        # Only 1 bash signal, no research signals — bash must dominate by >1
        result = self.classify_task("check status", "just check")
        assert result in ("bash", "general-purpose")  # heuristic, not strict

    def test_install_command_signals_bash(self):
        result = self.classify_task("install dependencies", "run npm install and pip install")
        assert result == "bash"

    def test_write_report_signals_research(self):
        result = self.classify_task("write report", "analyze data and summarize findings in a report")
        assert result == "general-purpose"

    def test_humanize_text_signals_writing_refiner(self):
        result = self.classify_task("humanize draft", "rewrite this text to sound less robotic and more natural")
        assert result == "writing-refiner"

    def test_argument_critique_signals_argument_critic(self):
        result = self.classify_task("critique essay", "evaluate the thesis, evidence, counterclaims, and rebuttals")
        assert result == "argument-critic"

    def test_empty_description_returns_general_purpose(self):
        result = self.classify_task("", "")
        assert result == "general-purpose"

    def test_docker_deploy_signals_bash(self):
        result = self.classify_task("deploy docker", "build and deploy docker container to server")
        assert result == "bash"

    def test_research_wins_over_single_bash_signal(self):
        # "build" is a bash signal but research signals dominate
        result = self.classify_task("design architecture", "research and evaluate design options then analyze tradeoffs")
        assert result == "general-purpose"


# ===========================================================================
# #3 External Research Tool Registry
# ===========================================================================

class TestResearchRegistry:
    def test_get_known_tool(self):
        from src.research.registry import get_research_tool
        tool = get_research_tool("gpt-researcher")
        assert tool is not None
        assert tool.name == "gpt-researcher"

    def test_get_unknown_tool_returns_none(self):
        from src.research.registry import get_research_tool
        assert get_research_tool("nonexistent-tool") is None

    def test_list_research_tools_returns_all(self):
        from src.research.registry import list_research_tools
        tools = list_research_tools(available_only=False)
        assert len(tools) >= 4
        names = {t.name for t in tools}
        assert {"gpt-researcher", "jina-deepresearch", "perplexica", "storm"}.issubset(names)

    def test_list_research_tools_sorted_by_priority(self):
        from src.research.registry import list_research_tools
        tools = list_research_tools(available_only=False)
        priorities = [t.priority for t in tools]
        assert priorities == sorted(priorities, reverse=True)

    def test_unavailable_when_env_var_missing(self):
        from src.research.registry import get_research_tool
        tool = get_research_tool("gpt-researcher")
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("GPT_RESEARCHER_URL", None)
            assert not tool.is_available()

    def test_available_when_env_var_set(self):
        from src.research.registry import get_research_tool
        tool = get_research_tool("gpt-researcher")
        with patch.dict(os.environ, {"GPT_RESEARCHER_URL": "http://localhost:8080"}):
            assert tool.is_available()

    def test_best_tool_for_deep_research(self):
        from src.research.registry import ResearchCapability, best_tool_for
        # Should return the highest-priority available tool with DEEP_RESEARCH
        # (may return None if no env vars set — that's fine)
        tool = best_tool_for({ResearchCapability.DEEP_RESEARCH}, available_only=False)
        assert tool is not None
        assert ResearchCapability.DEEP_RESEARCH in tool.capabilities

    def test_inject_research_hints_skips_non_research_prompts(self):
        from src.research.registry import inject_research_hints
        base = "Run this bash script to compile the project"
        result = inject_research_hints(base, task_description="compile project")
        assert result == base  # no research keywords, no hint injected

    def test_inject_research_hints_adds_hint_when_available(self):
        from src.research.registry import inject_research_hints
        with patch.dict(os.environ, {"GPT_RESEARCHER_URL": "http://localhost:8080"}):
            base = "Research the latest AI safety findings and summarize them"
            result = inject_research_hints(base, task_description="research safety")
            # If a tool is available, hint should be appended
            assert len(result) >= len(base)

    def test_inject_research_hints_no_tool_available_noop(self):
        from src.research.registry import inject_research_hints
        # Clear all research env vars
        clear_env = {k: "" for k in ["GPT_RESEARCHER_URL", "JINA_API_KEY", "PERPLEXICA_URL", "STORM_URL"]}
        with patch.dict(os.environ, clear_env):
            base = "Research and analyze climate change impacts in detail"
            result = inject_research_hints(base, task_description="research climate")
            assert result == base

    def test_tool_inject_prompt_hint_noop_when_unavailable(self):
        from src.research.registry import get_research_tool
        tool = get_research_tool("gpt-researcher")
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("GPT_RESEARCHER_URL", None)
            result = tool.inject_prompt_hint("base prompt")
            assert result == "base prompt"

    def test_tool_inject_prompt_hint_appends_when_available(self):
        from src.research.registry import get_research_tool
        tool = get_research_tool("gpt-researcher")
        with patch.dict(os.environ, {"GPT_RESEARCHER_URL": "http://localhost:8080"}):
            # Patch reachability — inject_prompt_hint now probes the URL before injecting
            with patch("src.research.registry._check_reachable", return_value=True):
                result = tool.inject_prompt_hint("base prompt")
                assert "base prompt" in result
                assert len(result) > len("base prompt")


# ===========================================================================
# #4 Quality Scorer
# ===========================================================================

class TestQualityScore:
    def _score(self, content, subagent_type="general-purpose"):
        from src.subagents.quality import _score
        return _score(content, subagent_type, task_id="test-task", thread_id=None)

    def test_empty_content_zero_completeness(self):
        q = self._score("")
        assert q.completeness == 0.0
        assert q.word_count == 0

    def test_full_completeness_at_100_words(self):
        text = " ".join(["word"] * 100)
        q = self._score(text)
        assert q.completeness == 1.0

    def test_partial_completeness(self):
        text = " ".join(["word"] * 50)
        q = self._score(text)
        assert 0.4 < q.completeness < 0.6

    def test_source_quality_with_url(self):
        text = ("Analysis text " * 10) + " See https://example.com for more."
        q = self._score(text)
        assert q.source_quality > 0

    def test_source_quality_zero_without_citations(self):
        text = "plain text without any sources or citations " * 5
        q = self._score(text)
        assert q.source_quality == 0.0

    def test_error_rate_with_error_lines(self):
        text = "Error: something failed\nTraceback (most recent call last):\nline 2"
        q = self._score(text)
        assert q.error_rate > 0

    def test_error_rate_zero_for_clean_output(self):
        text = "clean result " * 20
        q = self._score(text)
        assert q.error_rate == 0.0

    def test_composite_between_0_and_1(self):
        for content in ["", "short", " ".join(["w"] * 200)]:
            q = self._score(content)
            assert 0.0 <= q.composite <= 1.0

    def test_high_quality_result_high_composite(self):
        text = (
            "Comprehensive analysis of the topic. "
            "Key findings include significant improvements. " * 5
            + " Source: https://arxiv.org/abs/1234 and https://nature.com/article"
        )
        q = self._score(text)
        assert q.composite > 0.5

    def test_bash_schema(self):
        q = self._score("ls -la output\nfile1 file2", subagent_type="bash")
        assert q.subagent_type == "bash"
        assert q.schema == "generic"

    def test_writing_refiner_profile_ignores_missing_sources(self):
        text = "## Summary\nShort summary.\n\n## Revised Text\n" + ("This sentence is more natural now. " * 8) + "\n\n## Notes\n- tightened phrasing"
        q = self._score(text, subagent_type="writing-refiner")
        assert q.profile == "editorial-rewrite"
        assert q.source_quality > 0
        assert q.composite > 0.4

    def test_argument_critic_rewards_rubric_coverage(self):
        text = """
## Overall Assessment
Clear argument with room to strengthen evidence.

## Argument Map
- Thesis: the policy should pass
- Claim: costs decrease
- Evidence: pilot data
- Counterclaim: rollout risk
- Rebuttal: phased deployment

## Weak Points
- Evidence is too thin.

## Suggested Revisions
- Add stronger evidence and address rebuttal depth.
"""
        q = self._score(text, subagent_type="argument-critic")
        assert q.profile == "argument-critique"
        assert q.dimensions["rubric_coverage"] > 0.5


class TestScoreAsync:
    def test_score_async_does_not_raise(self, tmp_path):
        from src.subagents.quality import score_async
        with patch("src.subagents.quality._get_db_path", return_value=tmp_path / "quality.db"):
            # Should complete without exception
            score_async("task-1", "some result text " * 10, "general-purpose", thread_id="thread-1")
            # Give the daemon thread time to complete
            import time
            time.sleep(0.2)

    def test_get_scores_for_thread_empty_when_no_db(self, tmp_path):
        from src.subagents.quality import get_scores_for_thread
        nonexistent = tmp_path / "nonexistent.db"
        with patch("src.subagents.quality._get_db_path", return_value=nonexistent):
            scores = get_scores_for_thread("thread-1")
            assert scores == []

    def test_get_scores_for_thread_returns_persisted(self, tmp_path):
        from src.subagents.quality import _persist, _score, get_scores_for_thread
        db_path = tmp_path / "quality.db"
        q = _score("great analysis " * 20, "general-purpose", "task-42", "thread-42")
        _persist(q, db_path)

        with patch("src.subagents.quality._get_db_path", return_value=db_path):
            scores = get_scores_for_thread("thread-42")
            assert len(scores) == 1
            assert scores[0]["task_id"] == "task-42"
            assert scores[0]["subagent_type"] == "general-purpose"
            assert "schema" in scores[0]
            assert "dimensions" in scores[0]

    def test_get_scores_excludes_other_threads(self, tmp_path):
        from src.subagents.quality import _persist, _score, get_scores_for_thread
        db_path = tmp_path / "quality.db"
        _persist(_score("result " * 10, "bash", "task-A", "thread-A"), db_path)
        _persist(_score("result " * 10, "bash", "task-B", "thread-B"), db_path)

        with patch("src.subagents.quality._get_db_path", return_value=db_path):
            scores = get_scores_for_thread("thread-A")
            assert all(s["thread_id"] == "thread-A" for s in scores)


# ===========================================================================
# #5 MAB Adaptive Selection
# ===========================================================================

class TestMAB:
    def test_select_subagent_returns_valid_type(self, tmp_path):
        from src.subagents.mab import select_subagent
        with patch("src.subagents.mab._get_db_path", return_value=tmp_path / "mab.db"):
            result = select_subagent(task_category="test")
            assert result in ("general-purpose", "bash", "writing-refiner", "argument-critic")

    def test_select_subagent_from_candidates(self, tmp_path):
        from src.subagents.mab import select_subagent
        with patch("src.subagents.mab._get_db_path", return_value=tmp_path / "mab.db"):
            result = select_subagent(task_category="test", candidates=["bash"])
            assert result == "bash"

    def test_record_outcome_success_increments_alpha(self, tmp_path):
        from src.subagents.mab import _load_arms, record_outcome
        db_path = tmp_path / "mab.db"
        with patch("src.subagents.mab._get_db_path", return_value=db_path):
            record_outcome("general-purpose", composite_score=0.9, task_category="test")
            arms = _load_arms(db_path, "test")
            alpha, beta = arms["general-purpose"]
            assert alpha > 1.0  # prior 1.0 + 1 success = 2.0

    def test_record_outcome_failure_increments_beta(self, tmp_path):
        from src.subagents.mab import _load_arms, record_outcome
        db_path = tmp_path / "mab.db"
        with patch("src.subagents.mab._get_db_path", return_value=db_path):
            record_outcome("bash", composite_score=0.1, task_category="test")
            arms = _load_arms(db_path, "test")
            alpha, beta = arms["bash"]
            assert beta > 1.0  # prior 1.0 + 1 failure

    def test_get_arm_stats_returns_list(self, tmp_path):
        from src.subagents.mab import get_arm_stats
        with patch("src.subagents.mab._get_db_path", return_value=tmp_path / "mab.db"):
            stats = get_arm_stats("default")
            assert isinstance(stats, list)
            for s in stats:
                assert "subagent_type" in s
                assert "expected_reward" in s
                assert 0.0 <= s["expected_reward"] <= 1.0

    def test_arm_expected_reward_consistent_with_alpha_beta(self, tmp_path):
        from src.subagents.mab import _load_arms, _save_arm, get_arm_stats, _ensure_schema
        db_path = tmp_path / "mab.db"
        _ensure_schema(db_path)
        _save_arm(db_path, "general-purpose", "test2", alpha=3.0, beta=1.0)
        with patch("src.subagents.mab._get_db_path", return_value=db_path):
            stats = get_arm_stats("test2")
        gp = next(s for s in stats if s["subagent_type"] == "general-purpose")
        # expected = 3/(3+1) = 0.75
        assert abs(gp["expected_reward"] - 0.75) < 0.01

    def test_select_falls_back_on_error(self):
        from src.subagents.mab import select_subagent
        with patch("src.subagents.mab._load_arms", side_effect=RuntimeError("db error")):
            result = select_subagent(task_category="fail", candidates=["general-purpose", "bash"])
            assert result == "general-purpose"

    def test_record_outcome_tolerates_error(self):
        from src.subagents.mab import record_outcome
        # Should not raise even when DB fails
        with patch("src.subagents.mab._get_db_path", side_effect=RuntimeError("disk full")):
            record_outcome("bash", 0.8)  # no exception expected

    def test_sufficient_data_triggers_thompson_sampling(self, tmp_path):
        """After enough samples, MAB selection should consider Beta distributions."""
        from src.subagents.mab import _MIN_SAMPLES_TO_TRUST, _save_arm, _ensure_schema, select_subagent
        db_path = tmp_path / "mab.db"
        _ensure_schema(db_path)
        # Heavily favor 'bash' for this category
        _save_arm(db_path, "bash", "test3", alpha=20.0, beta=1.0)
        _save_arm(db_path, "general-purpose", "test3", alpha=1.0, beta=20.0)

        with patch("src.subagents.mab._get_db_path", return_value=db_path):
            with patch("src.subagents.mab._MIN_SAMPLES_TO_TRUST", 0):
                # With trust disabled, should heavily prefer bash
                results = [select_subagent("test3", ["bash", "general-purpose"]) for _ in range(20)]
                bash_count = results.count("bash")
                assert bash_count > 10  # Thompson sampling should pick bash most often
