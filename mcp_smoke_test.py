from mcp.server.fastmcp import FastMCP

mcp = FastMCP("smoke-test")

@mcp.tool()
def ping() -> str:
    """Return a simple diagnostic response."""
    return "pong"

if __name__ == "__main__":
    mcp.run(transport="stdio")
