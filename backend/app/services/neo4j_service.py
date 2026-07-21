"""
app/services/neo4j_service.py — Derived asset-evidence graph service.

Neo4j is a READ-ONLY projection of MongoDB canonical records.
Never used as canonical store. Falls back safely to MongoDB when unavailable.

Node labels: Asset, Drawing, Document, Chunk, ReviewTask, AuditEvent
Edge types follow RAG_CC.md specification exactly.
"""
from __future__ import annotations

import structlog
from app.core.config import settings

log = structlog.get_logger(__name__)

_driver = None
_neo4j_available = None  # None = not yet probed


def _get_driver():
    global _driver, _neo4j_available
    if _driver is not None:
        try:
            _driver.verify_connectivity()
            return _driver
        except Exception:
            _driver = None # Try reconnecting
    try:
        from neo4j import GraphDatabase  # type: ignore
        _driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
            connection_timeout=5,
            max_connection_lifetime=3600,
        )
        _driver.verify_connectivity()
        _neo4j_available = True
        log.info("neo4j_connected", uri=settings.neo4j_uri)
        return _driver
    except Exception as e:
        log.warning("neo4j_unavailable", error=str(e))
        _neo4j_available = False
        return None


def reset_driver() -> None:
    global _driver, _neo4j_available
    if _driver:
        try:
            _driver.close()
        except Exception:
            pass
    _driver = None
    _neo4j_available = None


def health_check() -> bool:
    driver = _get_driver()
    if driver is None:
        return False
    try:
        with driver.session(database=settings.neo4j_database) as session:
            session.run("RETURN 1")
        return True
    except Exception:
        return False


def ensure_constraints() -> bool:
    """Create uniqueness constraints for all node types. Idempotent."""
    driver = _get_driver()
    if driver is None:
        return False
    constraints = [
        "CREATE CONSTRAINT asset_tag IF NOT EXISTS FOR (a:Asset) REQUIRE a.tag IS UNIQUE",
        "CREATE CONSTRAINT drawing_id IF NOT EXISTS FOR (d:Drawing) REQUIRE d.drawing_id IS UNIQUE",
        "CREATE CONSTRAINT document_id IF NOT EXISTS FOR (d:Document) REQUIRE d.document_id IS UNIQUE",
        "CREATE CONSTRAINT chunk_id IF NOT EXISTS FOR (c:Chunk) REQUIRE c.chunk_id IS UNIQUE",
        "CREATE CONSTRAINT review_task_id IF NOT EXISTS FOR (r:ReviewTask) REQUIRE r.task_id IS UNIQUE",
        "CREATE CONSTRAINT audit_event_id IF NOT EXISTS FOR (a:AuditEvent) REQUIRE a.event_id IS UNIQUE",
    ]
    try:
        with driver.session(database=settings.neo4j_database) as session:
            for cypher in constraints:
                session.run(cypher)
        log.info("neo4j_constraints_ensured")
        return True
    except Exception as e:
        log.warning("neo4j_constraints_failed", error=str(e))
        return False


PROJECTION_VERSION = "v1"


def upsert_asset_node(asset: dict) -> bool:
    """MERGE an Asset node from the verified P&ID registry."""
    driver = _get_driver()
    if driver is None:
        return False
    try:
        with driver.session(database=settings.neo4j_database) as session:
            session.run(
                """
                MERGE (a:Asset {tag: $tag})
                SET a.asset_type = $asset_type,
                    a.area = $area,
                    a.source_id = $source_id,
                    a.drawing_id = $drawing_id,
                    a.review_state = $review_state,
                    a.projection_version = $version
                """,
                tag=asset.get("tag", ""),
                asset_type=asset.get("asset_type", ""),
                area=asset.get("area", ""),
                source_id=asset.get("source_id", ""),
                drawing_id=asset.get("drawing_id", ""),
                review_state=asset.get("state", "verified"),
                version=PROJECTION_VERSION,
            )
        return True
    except Exception as e:
        log.warning("neo4j_upsert_asset_failed", error=str(e))
        return False


def upsert_drawing_node(drawing: dict) -> bool:
    driver = _get_driver()
    if driver is None:
        return False
    try:
        with driver.session(database=settings.neo4j_database) as session:
            session.run(
                """
                MERGE (d:Drawing {drawing_id: $drawing_id})
                SET d.title = $title,
                    d.source_id = $source_id,
                    d.projection_version = $version
                """,
                drawing_id=drawing.get("drawing_id", ""),
                title=drawing.get("title", ""),
                source_id=drawing.get("source_id", drawing.get("drawing_id", "")),
                version=PROJECTION_VERSION,
            )
        return True
    except Exception as e:
        log.warning("neo4j_upsert_drawing_failed", error=str(e))
        return False


def upsert_document_node(document: dict) -> bool:
    driver = _get_driver()
    if driver is None:
        return False
    try:
        with driver.session(database=settings.neo4j_database) as session:
            session.run(
                """
                MERGE (d:Document {document_id: $document_id})
                SET d.source_id = $source_id,
                    d.document_type = $document_type,
                    d.projection_version = $version
                """,
                document_id=document.get("document_id", document.get("source_id", "")),
                source_id=document.get("source_id", ""),
                document_type=document.get("document_type", ""),
                version=PROJECTION_VERSION,
            )
        return True
    except Exception as e:
        log.warning("neo4j_upsert_document_failed", error=str(e))
        return False


def upsert_entity_node(entity: dict) -> bool:
    driver = _get_driver()
    if driver is None:
        return False
    try:
        with driver.session(database=settings.neo4j_database) as session:
            session.run(
                """
                MERGE (e:Entity {entity_id: $entity_id})
                SET e.entity_type = $entity_type,
                    e.value = $value,
                    e.normalized_value = $normalized_value,
                    e.document_id = $document_id,
                    e.review_state = $review_state,
                    e.projection_version = $version
                """,
                entity_id=entity.get("entity_id", ""),
                entity_type=entity.get("entity_type", ""),
                value=entity.get("value", ""),
                normalized_value=entity.get("normalized_value", ""),
                document_id=entity.get("document_id", ""),
                review_state=entity.get("resolution", {}).get("state", "ai_proposed"),
                version=PROJECTION_VERSION,
            )
        return True
    except Exception as e:
        log.warning("neo4j_upsert_entity_failed", error=str(e))
        return False


def upsert_document_references_asset(doc_id: str, tag: str, source_hash: str, review_state: str) -> bool:
    driver = _get_driver()
    if driver is None:
        return False
    try:
        with driver.session(database=settings.neo4j_database) as session:
            session.run(
                """
                MATCH (d:Document {document_id: $doc_id})
                MATCH (a:Asset {tag: $tag})
                MERGE (d)-[r:REFERENCES]->(a)
                SET r.source_hash = $source_hash,
                    r.review_state = $review_state,
                    r.projection_version = $version
                """,
                doc_id=doc_id,
                tag=tag,
                source_hash=source_hash,
                review_state=review_state,
                version=PROJECTION_VERSION,
            )
        return True
    except Exception as e:
        log.warning("neo4j_doc_references_failed", error=str(e))
        return False


def upsert_asset_on_drawing(tag: str, drawing_id: str, source_id: str, source_hash: str) -> bool:
    """MERGE (:Asset)-[:APPEARS_ON]->(:Drawing). Verified only."""
    driver = _get_driver()
    if driver is None:
        return False
    try:
        with driver.session(database=settings.neo4j_database) as session:
            session.run(
                """
                MATCH (a:Asset {tag: $tag})
                MATCH (d:Drawing {drawing_id: $drawing_id})
                MERGE (a)-[r:APPEARS_ON]->(d)
                SET r.source_id = $source_id,
                    r.source_hash = $source_hash,
                    r.review_state = 'verified',
                    r.projection_version = $version
                """,
                tag=tag,
                drawing_id=drawing_id,
                source_id=source_id,
                source_hash=source_hash,
                version=PROJECTION_VERSION,
            )
        return True
    except Exception as e:
        log.warning("neo4j_appears_on_failed", error=str(e))
        return False


def upsert_asset_relationship(rel: dict) -> bool:
    """MERGE (:Asset)-[:RELATED_TO {type}]->(:Asset) from verified P&ID relationships."""
    driver = _get_driver()
    if driver is None:
        return False
    try:
        with driver.session(database=settings.neo4j_database) as session:
            session.run(
                """
                MATCH (a:Asset {tag: $from_tag})
                MATCH (b:Asset {tag: $to_tag})
                MERGE (a)-[r:RELATED_TO {rel_type: $rel_type}]->(b)
                SET r.source_id = $source_id,
                    r.source_hash = $source_hash,
                    r.review_state = $review_state,
                    r.projection_version = $version
                """,
                from_tag=rel.get("from_tag", ""),
                to_tag=rel.get("to_tag", ""),
                rel_type=rel.get("relationship_type", ""),
                source_id=rel.get("source_id", ""),
                source_hash=rel.get("source_hash", ""),
                review_state=rel.get("state", "verified"),
                version=PROJECTION_VERSION,
            )
        return True
    except Exception as e:
        log.warning("neo4j_relationship_failed", error=str(e))
        return False


def upsert_chunk_node(chunk: dict) -> bool:
    """MERGE a Chunk node from a DocumentChunkRecord."""
    driver = _get_driver()
    if driver is None:
        return False
    try:
        with driver.session(database=settings.neo4j_database) as session:
            session.run(
                """
                MERGE (c:Chunk {chunk_id: $chunk_id})
                SET c.source_id = $source_id,
                    c.source_hash = $source_hash,
                    c.provenance = $provenance,
                    c.review_state = $review_state,
                    c.chunk_type = $chunk_type,
                    c.page = $page,
                    c.text_excerpt = $text_excerpt,
                    c.projection_version = $version
                """,
                chunk_id=chunk.get("chunk_id", ""),
                source_id=chunk.get("source_id", ""),
                source_hash=chunk.get("source_hash", ""),
                provenance=chunk.get("provenance", ""),
                review_state=chunk.get("review_state", ""),
                chunk_type=chunk.get("chunk_type", ""),
                page=chunk.get("page"),
                text_excerpt=chunk.get("text", "")[:300],
                version=PROJECTION_VERSION,
            )
        return True
    except Exception as e:
        log.warning("neo4j_upsert_chunk_failed", error=str(e))
        return False


def upsert_chunk_mentions_asset(chunk_id: str, tag: str, source_hash: str, review_state: str) -> bool:
    """MERGE (:Chunk)-[:MENTIONS]->(:Asset) for OCR/document tag references."""
    driver = _get_driver()
    if driver is None:
        return False
    try:
        with driver.session(database=settings.neo4j_database) as session:
            session.run(
                """
                MATCH (c:Chunk {chunk_id: $chunk_id})
                MATCH (a:Asset {tag: $tag})
                MERGE (c)-[r:MENTIONS]->(a)
                SET r.source_hash = $source_hash,
                    r.review_state = $review_state,
                    r.projection_version = $version
                """,
                chunk_id=chunk_id,
                tag=tag,
                source_hash=source_hash,
                review_state=review_state,
                version=PROJECTION_VERSION,
            )
        return True
    except Exception as e:
        log.warning("neo4j_chunk_mentions_failed", error=str(e))
        return False


def get_asset_evidence_graph(tag: str, max_hops: int = 2) -> dict:
    """
    Return nodes and edges for the asset evidence graph (up to max_hops from tag).
    Used by GET /api/v1/assets/{tag}/evidence-graph.
    Falls back to empty graph dict if Neo4j is unavailable.
    """
    driver = _get_driver()
    if driver is None:
        return {"available": False, "nodes": [], "edges": [], "fallback": True}

    try:
        with driver.session(database=settings.neo4j_database) as session:
            # Collect the asset + its direct drawing + related assets (up to 2 hops)
            result = session.run(
                """
                MATCH (a:Asset {tag: $tag})
                OPTIONAL MATCH (a)-[r1:APPEARS_ON]->(d:Drawing)
                OPTIONAL MATCH (a)-[r2:RELATED_TO]-(b:Asset)
                OPTIONAL MATCH (c:Chunk)-[r3:MENTIONS]->(a)
                RETURN
                  a,
                  collect(DISTINCT {drawing: d, rel: r1}) as drawings,
                  collect(DISTINCT {asset: b, rel: r2}) as related,
                  collect(DISTINCT {chunk: c, rel: r3}) as chunks
                LIMIT 1
                """,
                tag=tag,
            )
            record = result.single()
            if not record:
                return {"available": True, "nodes": [], "edges": [], "fallback": False}

            nodes = []
            edges = []

            # Main asset
            asset_node = dict(record["a"])
            nodes.append({"id": f"asset:{tag}", "type": "Asset", "data": asset_node})

            # Drawing nodes
            for item in record["drawings"]:
                if item["drawing"]:
                    d = dict(item["drawing"])
                    did = d.get("drawing_id", "")
                    nodes.append({"id": f"drawing:{did}", "type": "Drawing", "data": d})
                    edges.append({
                        "source": f"asset:{tag}",
                        "target": f"drawing:{did}",
                        "type": "APPEARS_ON",
                        "data": dict(item["rel"] or {}),
                    })

            # Related asset nodes
            for item in record["related"]:
                if item["asset"]:
                    b = dict(item["asset"])
                    btag = b.get("tag", "")
                    nodes.append({"id": f"asset:{btag}", "type": "Asset", "data": b})
                    edges.append({
                        "source": f"asset:{tag}",
                        "target": f"asset:{btag}",
                        "type": "RELATED_TO",
                        "data": dict(item["rel"] or {}),
                    })

            # Chunk nodes
            for item in record["chunks"]:
                if item["chunk"]:
                    ch = dict(item["chunk"])
                    cid = ch.get("chunk_id", "")
                    nodes.append({"id": f"chunk:{cid}", "type": "Chunk", "data": ch})
                    edges.append({
                        "source": f"chunk:{cid}",
                        "target": f"asset:{tag}",
                        "type": "MENTIONS",
                        "data": dict(item["rel"] or {}),
                    })

        return {
            "available": True,
            "tag": tag,
            "nodes": _dedupe_nodes(nodes),
            "edges": edges,
            "fallback": False,
        }

    except Exception as e:
        log.warning("neo4j_graph_query_failed", tag=tag, error=str(e))
        return {"available": False, "nodes": [], "edges": [], "fallback": True, "error": str(e)}


def get_connected_chunks(tag: str) -> list[str]:
    """Return chunk_ids connected to an asset via Neo4j MENTIONS edges (up to 2-hops for retrieval)."""
    driver = _get_driver()
    if driver is None:
        return []
    try:
        with driver.session(database=settings.neo4j_database) as session:
            result = session.run(
                """
                MATCH (a:Asset {tag: $tag})
                OPTIONAL MATCH (c1:Chunk)-[:MENTIONS]->(a)
                OPTIONAL MATCH (a)-[:RELATED_TO]-(b:Asset)
                OPTIONAL MATCH (c2:Chunk)-[:MENTIONS]->(b)
                WITH coalesce(c1.chunk_id, c2.chunk_id) AS chunk_id, coalesce(c1.review_state, c2.review_state) AS review_state
                WHERE chunk_id IS NOT NULL AND review_state <> 'rejected' AND review_state <> 'unreadable'
                RETURN DISTINCT chunk_id
                LIMIT 20
                """,
                tag=tag,
            )
            return [r["chunk_id"] for r in result]
    except Exception as e:
        log.warning("neo4j_connected_chunks_failed", tag=tag, error=str(e))
        return []


def _dedupe_nodes(nodes: list[dict]) -> list[dict]:
    seen = set()
    out = []
    for n in nodes:
        if n["id"] not in seen:
            seen.add(n["id"])
            out.append(n)
    return out
