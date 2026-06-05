import uuid
import chromadb
from core.embeddings import embed
import time

CHROMA_PATH = "./data/chromadb"
COLLECTION_NAME = "experience"

VALID_CATEGORIES = ("project", "skill", "softskill", "job")

_client = chromadb.PersistentClient(path=CHROMA_PATH)
_collection = _client.get_or_create_collection(COLLECTION_NAME)


def add_chunk(text: str, category: str) -> None:
    if category not in VALID_CATEGORIES:
        raise ValueError(f"Invalid category '{category}'. Must be one of: {', '.join(VALID_CATEGORIES)}")

    vector = embed(text)
    _collection.add(
        ids=[str(uuid.uuid4())],
        embeddings=[vector],
        documents=[text],
        metadatas=[{"category": category}],
    )


def query_chunks(skill_text: str, n_results: int = 5) -> list[dict]:
    vector = embed(skill_text)
    count = _collection.count()

    if count == 0:
        return []

    capped = int(min(n_results, count))
    results = _collection.query(
        query_embeddings=[vector],
        n_results=capped,
        include=["documents", "metadatas", "distances"],
    )

    chunks = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        chunks.append({
            "text": doc,
            "category": meta["category"],
            "distance": dist,
        })

    return chunks


def query_chunks_by_category(skill_text: str, category: str, n_results: int = 5) -> list[dict]:
    if category not in VALID_CATEGORIES:
        raise ValueError(f"Invalid category '{category}'.")

    vector = embed(skill_text)
    count = _collection.count()

    if count == 0:
        return []

    capped = int(min(n_results, count))
    results = _collection.query(
        query_embeddings=[vector],
        n_results=capped,
        where={"category": category},
        include=["documents", "metadatas", "distances"],
    )

    chunks = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        chunks.append({
            "text": doc,
            "category": meta["category"],
            "distance": dist,
        })

    return chunks


def get_all_chunks() -> list[dict]:
    results = _collection.get(include=["documents", "metadatas"])
    chunks = []
    for doc, meta in zip(results["documents"], results["metadatas"]):
        chunks.append({
            "text": doc,
            "category": meta["category"],
        })
    return chunks


def get_chunks_by_category(category: str) -> list[dict]:
    if category not in VALID_CATEGORIES:
        raise ValueError(f"Invalid category '{category}'.")

    results = _collection.get(
        where={"category": category},
        include=["documents", "metadatas"],
    )
    chunks = []
    for doc, meta in zip(results["documents"], results["metadatas"]):
        chunks.append({
            "text": doc,
            "category": meta["category"],
        })
    return chunks


def chunk_count() -> int:
    return _collection.count()

def query_chunks_batch(skills: list[str], n_results: int = 1) -> dict[str, list[dict]]:
    """
    Query ChromaDB for multiple skills in a single batch operation.
    Returns dict mapping skill -> list of chunks.
    """
    from core.database import collection
    
    results = {}
    
    for skill in skills:
        try:
            response = collection.query(
                query_texts=[skill],
                n_results=n_results,
                include=["documents", "metadatas", "distances"]
            )
            
            chunks = []
            if response['documents'] and response['documents'][0]:
                for i, doc in enumerate(response['documents'][0]):
                    chunks.append({
                        "text": doc,
                        "category": response['metadatas'][0][i].get('category', 'unknown'),
                        "distance": response['distances'][0][i]
                    })
            results[skill] = chunks
            
        except Exception as e:
            print(f"⚠️ ChromaDB query failed for '{skill}': {e}")
            results[skill] = []
        
        # Small delay to avoid hammering ChromaDB
        time.sleep(0.05)
    
    return results