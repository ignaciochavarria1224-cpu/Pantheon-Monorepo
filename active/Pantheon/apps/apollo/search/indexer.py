import chromadb
from pathlib import Path
from connectors.meridian import get_all_notes_metadata
from config import CHROMA_PATH
from core.audit import log

def get_chroma_client():
    return chromadb.PersistentClient(path=CHROMA_PATH)

def get_or_create_collection(name: str):
    return get_chroma_client().get_or_create_collection(name)

def index_meridian_vault():
    collection = get_or_create_collection("meridian_vault")
    notes = get_all_notes_metadata()
    indexed = skipped = 0
    for note in notes:
        try:
            content = Path(note["path"]).read_text(encoding="utf-8")
            if len(content.strip()) < 50:
                skipped += 1
                continue
            chunks = chunk_text(content, chunk_size=500, overlap=50)
            for i, chunk in enumerate(chunks):
                collection.upsert(
                    ids=[f"{note['name']}__chunk_{i}"],
                    documents=[chunk],
                    metadatas=[{
                        "source": note["name"],
                        "path": note["path"],
                        "modified": note["modified"],
                        "chunk_index": i
                    }]
                )
            indexed += 1
        except Exception as e:
            skipped += 1
    log(f"Indexed Meridian vault: {indexed} notes, {skipped} skipped", system="SEARCH")
    return {"indexed": indexed, "skipped": skipped}

def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list:
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunks.append(" ".join(words[i:i + chunk_size]))
        i += chunk_size - overlap
    return chunks

def index_decisions():
    from core.memory import get_decisions
    collection = get_or_create_collection("decisions")
    for d in get_decisions(limit=1000):
        text = f"Decision: {d['decision']}\nReasoning: {d.get('reasoning', '')}"
        collection.upsert(
            ids=[f"decision_{d['id']}"],
            documents=[text],
            metadatas=[{"timestamp": d["timestamp"], "domain": d.get("domain", "general")}]
        )
    log("Indexed decisions", system="SEARCH")

if __name__ == "__main__":
    print("Indexing Meridian vault...")
    print(index_meridian_vault())
    print("Indexing decisions...")
    index_decisions()
    print("Done.")
