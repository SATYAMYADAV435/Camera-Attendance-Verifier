from __future__ import annotations
import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import numpy as np
from app.core.config import settings
from app.core.logging import logger

try:
    from elasticsearch import AsyncElasticsearch, Elasticsearch
    HAS_ELASTICSEARCH = True
except ImportError:
    HAS_ELASTICSEARCH = False

class ElasticsearchRepository:
    def __init__(self):
        self.prefix = settings.elasticsearch.index_prefix
        self.hosts = settings.elasticsearch.hosts
        self.client: Optional[Any] = None
        self.is_connected = False
        
        # Resilient in-memory buffer for store/search when ES is offline
        self._in_memory_stores: Dict[str, Dict[str, Dict[str, Any]]] = {
            "employees": {},
            "access_events": {},
            "person_observations": {},
            "security_incidents": {},
            "camera_health": {},
            "audit_logs": {},
            "cameras": {},
            "policies": {},
            "maintenance_tickets": {},
        }
        self._buffered_writes: List[Dict[str, Any]] = []

    def get_index_name(self, base_name: str) -> str:
        return f"{self.prefix}-{base_name}-v1"

    async def connect(self):
        if not HAS_ELASTICSEARCH:
            logger.warning("Elasticsearch package not installed or disabled. Using in-memory repository fallback.")
            self.is_connected = False
            return

        try:
            self.client = AsyncElasticsearch(hosts=self.hosts, request_timeout=1.0)
            ping_ok = await asyncio.wait_for(self.client.ping(), timeout=1.0)
            if ping_ok:
                self.is_connected = True
                logger.info("Connected to Elasticsearch successfully.", hosts=self.hosts)
                await self._init_indices()
            else:
                self.is_connected = False
                logger.warning("Elasticsearch ping failed. Activating resilient in-memory buffering.")
        except Exception as exc:
            self.is_connected = False
            logger.warning("Could not connect to Elasticsearch; using resilient buffer.", error=str(exc))

    async def _init_indices(self):
        """Initializes index schemas with kNN dense vector mappings where appropriate."""
        if not self.is_connected or not self.client:
            return
        
        # Schemas for dense vectors
        schemas = {
            self.get_index_name("employees"): {
                "mappings": {
                    "properties": {
                        "employee_id": {"type": "keyword"},
                        "employee_code": {"type": "keyword"},
                        "card_id": {"type": "keyword"},
                        "name": {"type": "text"},
                        "department": {"type": "keyword"},
                        "role": {"type": "keyword"},
                        "status": {"type": "keyword"},
                        "access_level": {"type": "keyword"},
                        "face_embedding_vector": {
                            "type": "dense_vector",
                            "dims": 512,
                            "index": True,
                            "similarity": "cosine"
                        },
                        "body_embedding_vector": {
                            "type": "dense_vector",
                            "dims": 512,
                            "index": True,
                            "similarity": "cosine"
                        },
                        "created_at": {"type": "date"},
                        "updated_at": {"type": "date"}
                    }
                }
            },
            self.get_index_name("access_events"): {
                "mappings": {
                    "properties": {
                        "event_id": {"type": "keyword"},
                        "employee_id": {"type": "keyword"},
                        "card_id": {"type": "keyword"},
                        "door_id": {"type": "keyword"},
                        "camera_id": {"type": "keyword"},
                        "decision": {"type": "keyword"},
                        "timestamp": {"type": "date"}
                    }
                }
            }
        }
        for idx_name, body in schemas.items():
            try:
                exists = await self.client.indices.exists(index=idx_name)
                if not exists:
                    await self.client.indices.create(index=idx_name, body=body)
                    logger.info("Created Elasticsearch index schema", index=idx_name)
            except Exception as e:
                logger.warning("Index initialization notice", index=idx_name, note=str(e))

    async def index_document(self, store_name: str, doc_id: str, document: Dict[str, Any]):
        # Always store in resilient buffer first
        if store_name not in self._in_memory_stores:
            self._in_memory_stores[store_name] = {}
        self._in_memory_stores[store_name][doc_id] = document

        # If ES is live, write to ES
        if self.is_connected and self.client:
            try:
                index_name = self.get_index_name(store_name)
                await self.client.index(index=index_name, id=doc_id, document=document)
            except Exception as exc:
                logger.warning("ES write failure; buffered locally.", store=store_name, error=str(exc))
                self._buffered_writes.append({"store": store_name, "id": doc_id, "doc": document})

    async def get_document(self, store_name: str, doc_id: str) -> Optional[Dict[str, Any]]:
        # Check in-memory store
        doc = self._in_memory_stores.get(store_name, {}).get(doc_id)
        if doc is not None:
            return doc

        if self.is_connected and self.client:
            try:
                index_name = self.get_index_name(store_name)
                res = await self.client.get(index=index_name, id=doc_id)
                return res.get("_source")
            except Exception:
                return None
        return None

    async def search_documents(
        self,
        store_name: str,
        query: Optional[Dict[str, Any]] = None,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 100,
        sort_field: str = "timestamp",
        sort_desc: bool = True
    ) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []

        # Local in-memory filter matching
        store = self._in_memory_stores.get(store_name, {})
        for _, item in store.items():
            match = True
            if filters:
                for k, v in filters.items():
                    if v is not None and item.get(k) != v:
                        match = False
                        break
            if match:
                results.append(item)

        # Sort
        def sort_key(x):
            val = x.get(sort_field)
            if isinstance(val, datetime):
                return val.timestamp()
            return val or 0

        results.sort(key=sort_key, reverse=sort_desc)
        return results[:limit]

    async def find_employee_by_card(self, card_id: str) -> Optional[Dict[str, Any]]:
        for _, emp in self._in_memory_stores.get("employees", {}).items():
            if emp.get("card_id") == card_id:
                return emp
        return None

    async def search_nearest_face_embedding(self, target_embedding: List[float], top_k: int = 3) -> List[Dict[str, Any]]:
        """Performs cosine similarity search against enrolled employee face vectors."""
        candidates = []
        target_vec = np.array(target_embedding, dtype=np.float32)
        norm_target = np.linalg.norm(target_vec)
        if norm_target == 0:
            return []

        for emp_id, emp in self._in_memory_stores.get("employees", {}).items():
            # Check raw or cached embedding in memory
            raw_vec = emp.get("face_embedding_raw")
            if raw_vec:
                vec = np.array(raw_vec, dtype=np.float32)
                norm_vec = np.linalg.norm(vec)
                if norm_vec > 0:
                    similarity = float(np.dot(target_vec, vec) / (norm_target * norm_vec))
                    candidates.append({
                        "employee_id": emp_id,
                        "employee": emp,
                        "similarity": similarity
                    })

        candidates.sort(key=lambda x: x["similarity"], reverse=True)
        return candidates[:top_k]

    async def close(self):
        if self.client:
            await self.client.close()

es_repo = ElasticsearchRepository()
