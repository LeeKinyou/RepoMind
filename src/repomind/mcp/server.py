"""Model Context Protocol (MCP) server implementation for RepoMind."""

from __future__ import annotations

import logging
from mcp.server.fastmcp import FastMCP
from repomind.mcp.tools import register_tools

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("repomind-mcp-server")

mcp = FastMCP("repomind-mcp-server")
register_tools(mcp)

class MCPServer:
    """Wrapper class for backwards compatibility, if anyone uses MCPServer."""
    def __init__(self):
        pass
        
    def start(self):
        mcp.run()

if __name__ == "__main__":
    mcp.run()
