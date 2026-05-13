from langchain.tools import tool
from pathlib import Path

@tool("Searchinator")
def search_file(file: str):
    """Search for file before writing documentation for the respective file.

    Args:
        file: file to write documentation for
    """
    file = file.strip()
    if not file:
        return None, "File name must not be empty"

    root = Path(__file__).parent.parent.parent
    matches = list(root.rglob(file))

    if not matches:
        return None, "File not found"

    target = matches[0]
    try:
        content = target.read_text(encoding='utf-8')
    except (PermissionError, OSError) as e:
        return None, f"Could not read file: {e}"

    return str(target), content
