import os
from fastmcp.server import FastMCP
from pathlib import Path

mcp = FastMCP("File-Reader")

BASE_DIR = Path(os.getenv("FILE_READER_BASE_DIR", "./documents"))  # Set a base directory for file access

@mcp.tool()
def read_file(filename: str) -> str:
# Ensure the file path is absolute and secure
    try:    
        file_path = BASE_DIR / filename
        if not str(file_path.resolve()).startswith(str(BASE_DIR.resolve())):
            return "Error: Access to the specified file is not allowed."
        
        content = file_path.read_text(encoding='utf-8')
        return f"File : {filename}\n\n {content}"

    except Exception as e:
        return f"Error reading file: {str(e)}"
    
@mcp.tool()
def list_files() -> str:
    """Lists all files in the base directory."""
    try:
        files = [f.name for f in BASE_DIR.iterdir() if f.is_file()]
        files_text = "\n".join(sorted(files)) if files else "No files found."
        return f"Files in directory:\n{files_text}"
        
    except Exception as e:
        return f"Error listing files: {str(e)}"
    
if __name__ == "__main__":
    print(f"Starting File Reader MCP with base directory: {BASE_DIR}")
    BASE_DIR.mkdir(parents=True, exist_ok=True)  # Ensure the base directory exists 
    mcp.run()
    