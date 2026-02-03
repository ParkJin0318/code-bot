from typing import List, Set

from langchain.schema import Document


def format_context(documents: List[Document]) -> str:
    context_parts = []
    for i, doc in enumerate(documents, 1):
        file_path = doc.metadata.get("file_path", "unknown")
        module_name = doc.metadata.get("module_name", "unknown")
        context_parts.append(
            f"--- Source {i}: {file_path} (module: {module_name}) ---\n"
            f"{doc.page_content}\n"
        )
    return "\n".join(context_parts)


def extract_sources(documents: List[Document]) -> List[str]:
    sources: List[str] = []
    seen: Set[str] = set()
    for doc in documents:
        file_path = doc.metadata.get("file_path", "unknown")
        if file_path not in seen:
            seen.add(file_path)
            sources.append(file_path)
    return sources
