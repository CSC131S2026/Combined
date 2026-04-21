import sys
from pathlib import Path
from pydantic import BaseModel, Field
from langchain_ollama import ChatOllama
from tools import search_file

class FileInfo(BaseModel):
    name: str = Field(description="Name of the python file being observed")
    description: str = Field(description="Complete description of the code presented")
    suggestions: str = Field(description="Ideas on what to do better, or fix later")

def to_markdown(info: FileInfo) -> str:
    return f"# {info.name}\n\n## Description\n{info.description}\n\n## Suggestions\n{info.suggestions}"

def main():
    user_input = input("Enter file you want to search:\n").strip()
    if not user_input:
        print("No file specified.", file=sys.stderr)
        sys.exit(1)

    file_path, file_contents = search_file.invoke(user_input)
    if file_path is None:
        print(f"Error: {file_contents}", file=sys.stderr)
        sys.exit(1)

    llm = ChatOllama(model="gemma4:latest", format="json")
    structured_llm = llm.with_structured_output(FileInfo)

    result = structured_llm.invoke(
        f"You are a Senior Software Engineer reviewing code for a conflict-of-interest detection backend "
        f"that processes Sacramento County Board of Supervisors agenda packets. "
        f"Describe what this file does and provide specific, actionable suggestions for improvement.\n\n{file_contents}"
    )
    result.name = Path(file_path).stem

    output_path = Path(file_path).parent / f"{result.name}.md"
    output_path.write_text(to_markdown(result), encoding='utf-8')

if __name__ == "__main__":
    main()
