from search.indexer import get_or_create_collection
from core.audit import log

def search_meridian(query: str, n_results: int = 5) -> list:
    collection = get_or_create_collection("meridian_vault")
    try:
        results = collection.query(query_texts=[query], n_results=n_results)
        formatted = []
        for i in range(len(results["ids"][0])):
            formatted.append({
                "content": results["documents"][0][i],
                "source": results["metadatas"][0][i]["source"],
                "path": results["metadatas"][0][i]["path"],
                "relevance": 1 - results["distances"][0][i]
            })
        log(f"Semantic search: '{query}' — {len(formatted)} results", system="SEARCH")
        return formatted
    except Exception as e:
        log(f"Search failed: {e}", system="SEARCH")
        return []

def search_decisions(query: str, n_results: int = 5) -> list:
    collection = get_or_create_collection("decisions")
    try:
        results = collection.query(query_texts=[query], n_results=n_results)
        formatted = []
        for i in range(len(results["ids"][0])):
            formatted.append({
                "content": results["documents"][0][i],
                "timestamp": results["metadatas"][0][i]["timestamp"],
                "domain": results["metadatas"][0][i]["domain"]
            })
        return formatted
    except Exception:
        return []
