# -*- coding: utf-8 -*-
"""The retrieval-augmented generation (RAG) module in AgentScope."""

from ._document import (
    DocMetadata,
    Document,
)
from ._reader import (
    ReaderBase,
    TextReader,
    PDFReader,
    ImageReader,
)
from ._store import (
    StoreBase,
    VDBStoreBase,
    GraphStoreBase,
    QdrantStore,
    MilvusLiteStore,
    Neo4jGraphStore,
)
from ._knowledge_base import KnowledgeBase
from ._simple_knowledge import SimpleKnowledge
from ._graph_knowledge import GraphKnowledgeBase
from ._graph_types import (
    Entity,
    Relationship,
    Community,
    EntityDict,
    RelationshipDict,
    CommunityDict,
    SearchMode,
    CommunityAlgorithm,
)


__all__ = [
    # Readers
    "ReaderBase",
    "TextReader",
    "PDFReader",
    "ImageReader",
    # Documents
    "DocMetadata",
    "Document",
    # Stores
    "StoreBase",
    "VDBStoreBase",
    "GraphStoreBase",
    "QdrantStore",
    "MilvusLiteStore",
    "Neo4jGraphStore",
    # Knowledge bases
    "KnowledgeBase",
    "SimpleKnowledge",
    "GraphKnowledgeBase",
    # Graph types
    "Entity",
    "Relationship",
    "Community",
    "EntityDict",
    "RelationshipDict",
    "CommunityDict",
    "SearchMode",
    "CommunityAlgorithm",
]
