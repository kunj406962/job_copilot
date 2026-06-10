import uuid
import json
import chromadb
from core.embeddings import embed

CHROMA_PATH = "./data/chromadb"
COLLECTION_NAME = "experience_v2"

VALID_TYPES = ("project", "job", "softskill")

_client = chromadb.PersistentClient(path=CHROMA_PATH)
_collection = _client.get_or_create_collection(COLLECTION_NAME)


def add_entry(
    entry_type: str,
    name: str,
    bullets: list[str],
    stack: str = "",
    role: str = "",
    description: str = "",
) -> None:
    if entry_type not in VALID_TYPES:
        raise ValueError(f"Invalid type '{entry_type}'. Must be one of: {', '.join(VALID_TYPES)}")

    if not bullets:
        raise ValueError("At least one bullet point is required.")

    # Build the document text for embedding
    # Format: "Name | Stack | Bullet 1. Bullet 2. Bullet 3."
    parts = [name]
    if stack:
        parts.append(stack)
    parts.append(" ".join(bullets))
    document_text = " | ".join(parts)

    vector = embed(document_text)

    _collection.add(
        ids=[str(uuid.uuid4())],
        embeddings=[vector],
        documents=[document_text],
        metadatas=[{
            "type": entry_type,
            "name": name,
            "stack": stack,
            "role": role,
            "description": description,
            "bullets": json.dumps(bullets),
        }],
    )


def query_entries(query_text: str, n_results: int = 10) -> list[dict]:
    count = _collection.count()
    if count == 0:
        return []

    vector = embed(query_text)
    capped = int(min(n_results, count))

    results = _collection.query(
        query_embeddings=[vector],
        n_results=capped,
        include=["documents", "metadatas", "distances"],
    )

    entries = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        entries.append({
            "type": meta["type"],
            "name": meta["name"],
            "stack": meta.get("stack", ""),
            "role": meta.get("role", ""),
            "description": meta.get("description", ""),
            "bullets": json.loads(meta["bullets"]),
            "distance": round(dist, 4),
            "document": doc,
        })

    return entries


def hybrid_score(entry: dict, keywords: list[str]) -> float:
    """0.7 semantic + 0.3 keyword overlap score."""
    semantic = 1 - (entry["distance"] / 2)

    stack_and_doc = (entry["stack"] + " " + entry["document"]).lower()
    matched = sum(1 for kw in keywords if kw.lower() in stack_and_doc)
    keyword = matched / len(keywords) if keywords else 0

    return round(0.7 * semantic + 0.3 * keyword, 4)


def get_top_entries(
    query_text: str,
    keywords: list[str],
    top_projects: int = 3,
    top_jobs: int = 2,
) -> dict:
    all_entries = query_entries(query_text, n_results=10)

    # Score all entries
    for entry in all_entries:
        entry["score"] = hybrid_score(entry, keywords)

    # Split by type and sort by hybrid score
    projects = sorted(
        [e for e in all_entries if e["type"] == "project"],
        key=lambda x: x["score"],
        reverse=True,
    )[:top_projects]

    jobs = sorted(
        [e for e in all_entries if e["type"] == "job"],
        key=lambda x: x["score"],
        reverse=True,
    )[:top_jobs]

    softskills = [e for e in all_entries if e["type"] == "softskill"]

    return {
        "projects": projects,
        "jobs": jobs,
        "softskills": softskills,
    }


def get_all_entries() -> list[dict]:
    results = _collection.get(include=["documents", "metadatas"])
    entries = []
    for doc, meta in zip(results["documents"], results["metadatas"]):
        entries.append({
            "type": meta["type"],
            "name": meta["name"],
            "stack": meta.get("stack", ""),
            "role": meta.get("role", ""),
            "description": meta.get("description", ""),
            "bullets": json.loads(meta["bullets"]),
        })
    return entries


def entry_count() -> int:
    return _collection.count()


def clear_all() -> None:
    global _collection
    _client.delete_collection(COLLECTION_NAME)
    _collection = _client.get_or_create_collection(COLLECTION_NAME)