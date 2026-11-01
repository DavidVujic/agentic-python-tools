import pytest
from agentic_python_tools.repl_mcp.core import mcp
from fastmcp.client import Client
from fastmcp.client.transports import FastMCPTransport


@pytest.fixture
async def main_mcp_client():
    async with Client(transport=mcp) as mcp_client:
        yield mcp_client


async def test_list_tools(main_mcp_client: Client[FastMCPTransport]):
    list_tools = await main_mcp_client.list_tools()

    assert len(list_tools) == 2
