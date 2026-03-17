"""Tests for optional research tool loading and extra_groups filtering."""

from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock, patch


class TestGetAvailableToolsExtraGroups(unittest.TestCase):
    """get_available_tools respects opt: groups and extra_groups."""

    def _get_config_with_opt_tool(self):
        """Return a minimal AppConfig mock with one standard tool and one opt: tool."""
        tool_standard = MagicMock()
        tool_standard.name = "web_search"
        tool_standard.group = "web"
        tool_standard.use = "src.community.tavily.tools:web_search_tool"

        tg_opt = MagicMock()
        tg_opt.name = "exa_search"
        # Simulate ToolGroupConfig with 'use' extra field
        tg_opt.use = "src.community.exa.tools:exa_search_tool"
        tg_opt.group = "opt:exa"

        cfg = MagicMock()
        cfg.tools = [tool_standard]
        cfg.tool_groups = [tg_opt]
        cfg.models = []
        cfg.get_model_config.return_value = None
        return cfg

    def test_opt_group_excluded_by_default(self):
        """Tools in opt: groups must not appear when extra_groups is empty."""
        import sys
        sys.modules.setdefault("src.mcp.cache", MagicMock(get_cached_mcp_tools=lambda: []))
        sys.modules.setdefault("src.config.extensions_config", MagicMock(
            ExtensionsConfig=MagicMock(from_file=lambda: MagicMock(get_enabled_mcp_servers=lambda: {}))
        ))

        from src.tools.tools import _include_tool_group

        # Standard group is included by default (groups=None)
        self.assertTrue(_include_tool_group("web", None, set()))
        # opt: group is excluded by default
        self.assertFalse(_include_tool_group("opt:exa", None, set()))

    def test_opt_group_included_when_requested(self):
        """Tools in opt: groups appear when their group is in extra_groups."""
        from src.tools.tools import _include_tool_group

        self.assertTrue(_include_tool_group("opt:exa", None, {"opt:exa"}))
        self.assertFalse(_include_tool_group("opt:serper", None, {"opt:exa"}))

    def test_standard_group_filtered_by_groups_list(self):
        """When groups list is provided, only those groups are included (excluding opt:)."""
        from src.tools.tools import _include_tool_group

        self.assertTrue(_include_tool_group("web", ["web"], set()))
        self.assertFalse(_include_tool_group("bash", ["web"], set()))
        # opt: is still excluded even if groups is specified
        self.assertFalse(_include_tool_group("opt:exa", ["web", "opt:exa"], set()))
        # opt: is included only via extra_groups
        self.assertTrue(_include_tool_group("opt:exa", ["web"], {"opt:exa"}))


class TestExaTool(unittest.TestCase):
    """EXA search tool graceful fallback."""

    def test_missing_api_key_returns_error_payload(self):
        with patch.dict("os.environ", {}, clear=True):
            with patch("src.community.exa.tools.get_app_config") as mock_cfg:
                mock_cfg.return_value.get_tool_config.return_value = None
                from src.community.exa.tools import _exa_search
                result = _exa_search("test query", num_results=3)
        self.assertEqual(len(result), 1)
        self.assertIn("error", result[0])
        self.assertIn("EXA_API_KEY", result[0]["error"])

    def test_api_error_returns_error_payload(self):
        import httpx
        with patch.dict("os.environ", {"EXA_API_KEY": "test-key"}):
            with patch("src.community.exa.tools.get_app_config") as mock_cfg:
                mock_cfg.return_value.get_tool_config.return_value = None
                with patch("httpx.Client") as mock_client_cls:
                    mock_client = MagicMock()
                    mock_client_cls.return_value.__enter__.return_value = mock_client
                    mock_client.post.side_effect = httpx.ConnectError("connection refused")
                    from importlib import reload
                    import src.community.exa.tools as exa_mod
                    reload(exa_mod)
                    result = exa_mod._exa_search("test query", num_results=3)
        self.assertEqual(len(result), 1)
        self.assertIn("error", result[0])


class TestSerperTool(unittest.TestCase):
    """Serper search tool graceful fallback."""

    def test_missing_api_key_returns_error_payload(self):
        with patch.dict("os.environ", {}, clear=True):
            with patch("src.community.serper.tools.get_app_config") as mock_cfg:
                mock_cfg.return_value.get_tool_config.return_value = None
                from src.community.serper.tools import _serper_search
                result = _serper_search("test query", num_results=3)
        self.assertEqual(len(result), 1)
        self.assertIn("error", result[0])
        self.assertIn("SERPER_API_KEY", result[0]["error"])


class TestFactCheckTool(unittest.TestCase):
    """Fact-check tool graceful fallback without library."""

    def test_no_service_no_library_returns_error(self):
        with patch.dict("os.environ", {}, clear=True):
            with patch("src.community.factcheck.tools.get_app_config") as mock_cfg:
                mock_cfg.return_value.get_tool_config.return_value = None
                with patch.dict("sys.modules", {"factcheck": None}):
                    from src.community.factcheck.tools import fact_check_tool
                    result = fact_check_tool.invoke({"text": "The sky is green."})
        self.assertIn("unavailable", result.lower())


class TestKnowledgeUniverseTool(unittest.TestCase):
    """Knowledge Universe tool graceful fallback."""

    def test_missing_api_key_returns_error_payload(self):
        with patch.dict("os.environ", {}, clear=True):
            from src.community.knowledge_universe.tools import _ku_discover
            result = _ku_discover("LangGraph agents", difficulty=3)
        self.assertEqual(len(result), 1)
        self.assertIn("error", result[0])
        self.assertIn("KU_API_KEY", result[0]["error"])

    def test_connection_error_returns_error_payload(self):
        import httpx
        with patch.dict("os.environ", {"KU_API_KEY": "ku_test_fake", "KU_BASE_URL": "http://localhost:19999"}):
            with patch("httpx.Client") as mock_client_cls:
                mock_client = MagicMock()
                mock_client_cls.return_value.__enter__.return_value = mock_client
                mock_client.post.side_effect = httpx.ConnectError("connection refused")
                from importlib import reload
                import src.community.knowledge_universe.tools as ku_mod
                reload(ku_mod)
                result = ku_mod._ku_discover("test query", difficulty=3)
        self.assertEqual(len(result), 1)
        self.assertIn("error", result[0])


class TestResearchRegistry(unittest.TestCase):
    """Research registry includes new tools."""

    def test_new_tools_registered(self):
        from src.research.registry import _REGISTRY
        self.assertIn("exa", _REGISTRY)
        self.assertIn("serper", _REGISTRY)
        self.assertIn("factcheck", _REGISTRY)
        self.assertIn("zep", _REGISTRY)
        self.assertIn("knowledge-universe", _REGISTRY)

    def test_exa_requires_env_var(self):
        from src.research.registry import _REGISTRY
        exa = _REGISTRY["exa"]
        self.assertEqual(exa.env_var, "EXA_API_KEY")

    def test_missing_env_var_not_available(self):
        from src.research.registry import _REGISTRY
        with patch.dict("os.environ", {}, clear=True):
            self.assertFalse(_REGISTRY["exa"].is_available())
            self.assertFalse(_REGISTRY["serper"].is_available())

    def test_set_env_var_makes_available(self):
        from src.research.registry import _REGISTRY
        with patch.dict("os.environ", {"EXA_API_KEY": "test-key"}):
            self.assertTrue(_REGISTRY["exa"].is_available())
