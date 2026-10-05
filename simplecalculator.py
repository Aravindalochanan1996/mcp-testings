from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Simple-Calculator")

@mcp.tool()
def add(a: int, b: int) -> int:
    """Adds two numbers together."""
    return a + b

@mcp.tool()
def subtract(a: int, b: int) -> int:
    """Subtracts the second number from the first."""
    return a - b

@mcp.tool()
def multiply(a: int, b: int) -> int:
    """Multiplies two numbers together."""
    return a * b

@mcp.tool()
def divide(a: int, b: int) -> float:
    """Divides the first number by the second. Raises an error if the second number is zero."""
    if b == 0:
        raise ValueError("Cannot divide by zero.")
    return a / b

if __name__ == "__main__":
    mcp.run()