"""Tests for the FastMCP server implementation."""

import os
import pytest
from mcp.server.fastmcp import FastMCP
from repomind.mcp.server import mcp
from repomind.mcp.tools import _get_index_dir, register_tools

def test_mcp_server_initialization():
    assert isinstance(mcp, FastMCP)
    assert mcp.name == "repomind-mcp-server"

def test_get_index_dir(tmp_path):
    repo = str(tmp_path)
    expected = os.path.join(repo, ".repomind")
    assert _get_index_dir(repo) == expected

@pytest.mark.asyncio
async def test_mcp_tools_registered():
    tools = await mcp.list_tools()
    tool_names = [t.name for t in tools]
    
    assert "repomind.index_repository" in tool_names
    assert "repomind.search_symbols" in tool_names
    assert "repomind.get_symbol_source" in tool_names
    assert "repomind.expand_symbol_relations" in tool_names
    assert "repomind.find_failure_evidence" in tool_names
    assert "repomind.run_diagnostic_agent" in tool_names
