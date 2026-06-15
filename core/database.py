"""ChromaDB persistence and retrieval helpers for stored experience entries.

This module owns the local vector collection, embedding-based search, hybrid
scoring, and CRUD-style entry management used by the resume generator.
"""

import uuid
import json
import chromadb
from core.embeddings import embed

CHROMA_PATH = "./data/chromadb"  # Local persistent vector store for user data.
COLLECTION_NAME = "experience_v2"  # Versioned collection name for stored experience.

VALID_TYPES = ("project", "job", "softskill")  # Supported entry categories.

_client = chromadb.PersistentClient(path=CHROMA_PATH)
_collection = _client.get_or_create_collection(COLLECTION_NAME)


def add_entry(
    entry_type: str,
    name: str,
    bullets: list[str],
    stack: str = "",
    role: str = "",
    description: str = "",
    entry_id: str = None,
) -> str:
    """Store a new experience entry in ChromaDB.

    Args:
        entry_type: The entry category, such as project or job.
        name: Human-readable entry name.
        bullets: Ordered bullet points describing the entry.
        stack: Optional tech stack or tool list.
        role: Optional role or job title.
        description: Optional short description of the entry.
        entry_id: Optional stable identifier to reuse on update.

    Returns:
        The entry ID that was stored.

    Side Effects:
        Writes embeddings and metadata to the persistent Chroma collection.
    """
    if entry_type not in VALID_TYPES:
        raise ValueError(f"Invalid type '{entry_type}'. Must be one of: {', '.join(VALID_TYPES)}")

    if not bullets:
        raise ValueError("At least one bullet point is required.")

    parts = [name]
    if stack:
        parts.append(stack)
    parts.append(" ".join(bullets))
    document_text = " | ".join(parts)

    vector = embed(document_text)
    new_id = entry_id or str(uuid.uuid4())

    _collection.add(
        ids=[new_id],
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
    return new_id


def delete_entry(entry_id: str) -> None:
    """Delete a stored experience entry by ID.

    Args:
        entry_id: The ChromaDB record identifier to remove.

    Returns:
        None

    Side Effects:
        Removes the matching document from the persistent collection.
    """
    _collection.delete(ids=[entry_id])


def update_entry(
    entry_id: str,
    entry_type: str,
    name: str,
    bullets: list[str],
    stack: str = "",
    role: str = "",
    description: str = "",
) -> None:
    """Replace an existing entry with updated content.

    Args:
        entry_id: The existing entry identifier.
        entry_type: The updated entry category.
        name: The updated entry name.
        bullets: The updated bullet list.
        stack: Optional updated tech stack.
        role: Optional updated role.
        description: Optional updated description.

    Returns:
        None

    Side Effects:
        Deletes the old record and writes a new one.
    """
    delete_entry(entry_id)
    add_entry(
        entry_type=entry_type,
        name=name,
        bullets=bullets,
        stack=stack,
        role=role,
        description=description,
    )


def query_entries(query_text: str, n_results: int = 10) -> list[dict]:
    """Return the nearest experience entries for a natural-language query.

    Args:
        query_text: Text used to generate the search embedding.
        n_results: Maximum number of matches to return.

    Returns:
        A list of normalized entry dictionaries ordered by vector distance.

    Side Effects:
        Performs an embedding call and a ChromaDB similarity query.
    """
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
    for id_, doc, meta, dist in zip(
        results["ids"][0],
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        entries.append({
            "id": id_,
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
    """Combine semantic and keyword signals into a single ranking score.

    Args:
        entry: A normalized entry dictionary with distance, stack, and document.
        keywords: Query keywords extracted from the job description.

    Returns:
        A blended relevance score between 0 and 1.
    """
    semantic = 1 - (entry["distance"] / 2)
    stack_and_doc = (entry["stack"] + " " + entry["document"]).lower()
    matched = sum(1 for kw in keywords if kw.lower() in stack_and_doc)
    keyword = matched / len(keywords) if keywords else 0
    return round(0.7 * semantic + 0.3 * keyword, 4)


def get_top_entries(
    query_text: str,
    keywords: list[str],
    top_projects: int = 4,
    top_jobs: int = 1,
) -> dict:
    """Rank projects, jobs, and soft skills for a job description query.

    Args:
        query_text: Text used to retrieve semantically relevant entries.
        keywords: Keywords used for the lexical portion of scoring.
        top_projects: Maximum number of project entries to return.
        top_jobs: Maximum number of job entries to return.

    Returns:
        A dictionary with ranked projects, jobs, and soft skills.
    """
    all_entries = query_entries(query_text, n_results=10)

    for entry in all_entries:
        entry["score"] = hybrid_score(entry, keywords)

    projects = sorted(
        [e for e in all_entries if e["type"] == "project"],
        key=lambda x: x["score"], reverse=True,
    )[:top_projects]

    jobs = sorted(
        [e for e in all_entries if e["type"] == "job"],
        key=lambda x: x["score"], reverse=True,
    )[:top_jobs]

    softskills = [e for e in all_entries if e["type"] == "softskill"]

    return {"projects": projects, "jobs": jobs, "softskills": softskills}


def get_all_entries() -> list[dict]:
    """Return every stored entry without ranking metadata.

    Returns:
        A list of all entries currently stored in the collection.
    """
    results = _collection.get(include=["documents", "metadatas"])
    entries = []
    for id_, doc, meta in zip(
        results["ids"],
        results["documents"],
        results["metadatas"],
    ):
        entries.append({
            "id": id_,
            "type": meta["type"],
            "name": meta["name"],
            "stack": meta.get("stack", ""),
            "role": meta.get("role", ""),
            "description": meta.get("description", ""),
            "bullets": json.loads(meta["bullets"]),
        })
    return entries


def entry_count() -> int:
    """Return the number of stored experience entries.

    Returns:
        The current collection size.
    """
    return _collection.count()


def clear_all() -> None:
    """Drop and recreate the experience collection.

    Returns:
        None

    Side Effects:
        Deletes all stored experience data in the local Chroma collection.
    """
    global _collection
    _client.delete_collection(COLLECTION_NAME)
    _collection = _client.get_or_create_collection(COLLECTION_NAME)