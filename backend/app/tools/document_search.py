"""NOVA — Document Search Tool."""

from __future__ import annotations

from typing import Any

from app.tools.base import BaseTool, ToolParameter, ToolResult


class DocumentSearchTool(BaseTool):
    @property
    def name(self) -> str:
        return "document_search"

    @property
    def description(self) -> str:
        return "Search through uploaded documents for relevant information."

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(name="query", type="string", description="The search query"),
        ]

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        query = str(params.get("query", "")).strip()
        if not query:
            return ToolResult(success=False, error="Search query is required")

        try:
            from app.rag.retriever import search_documents

            results = await search_documents(query)
            if not results:
                return ToolResult(
                    success=True,
                    result=[],
                    display_text="No relevant information found in uploaded documents.",
                )

            formatted = []
            for r in results:
                formatted.append({
                    "document": r["document_name"],
                    "content": r["content"][:500],
                    "score": round(r["score"], 3),
                })

            display_lines = []
            for r in formatted:
                display_lines.append(f"📄 **{r['document']}** (relevance: {r['score']})\n{r['content'][:200]}...")

            return ToolResult(
                success=True,
                result=formatted,
                display_text="\n\n".join(display_lines),
            )
        except Exception as e:
            return ToolResult(success=False, error=f"Document search failed: {str(e)}")
