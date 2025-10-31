# -*- coding: utf-8 -*-
"""Example: Using GraphKnowledgeBase with Neo4j.

This example demonstrates how to use the GraphKnowledgeBase with different
configurations and search modes.
"""

import asyncio
import os
import sys
from pathlib import Path

# 强制使用源码而不是安装的包
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from agentscope.rag import (
    GraphKnowledgeBase,
    Neo4jGraphStore,
    Document,
    DocMetadata,
)
from agentscope.embedding import DashScopeTextEmbedding
from agentscope.model import DashScopeChatModel

# 设置 DashScope API Key
DASHSCOPE_API_KEY = "sk-3ee953aac5fc4deeb57a0170112f0a00"
os.environ["DASHSCOPE_API_KEY"] = DASHSCOPE_API_KEY

# Neo4j 连接配置（请根据实际情况修改）
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "password"  # ⚠️ 请修改为你的实际密码


async def example_basic_vector_only():
    """Example 1: Basic usage (vector-only, no graph features)."""
    print("\n" + "="*80)
    print("Example 1: Basic Vector-Only Mode (No Graph Features)")
    print("="*80)
    
    # Initialize Neo4j graph store
    graph_store = Neo4jGraphStore(
        uri=NEO4J_URI,
        user=NEO4J_USER,
        password=NEO4J_PASSWORD,
        database="neo4j",
        collection_name="basic_knowledge",
        dimensions=1536,
    )
    
    # Initialize knowledge base (graph features disabled)
    knowledge = GraphKnowledgeBase(
        graph_store=graph_store,
        embedding_model=DashScopeTextEmbedding(
            model_name="text-embedding-v2",
            api_key=DASHSCOPE_API_KEY,
        ),
        llm_model=None,  # No LLM needed for vector-only mode
        enable_entity_extraction=False,
        enable_relationship_extraction=False,
        enable_community_detection=False,
    )
    
    # Create sample documents
    documents = [
        Document(
            id="doc1",
            metadata=DocMetadata(
                content={"type": "text", "text": "Alice works at OpenAI as a researcher specializing in language models."},
                doc_id="doc1",
                chunk_id=0,
                total_chunks=1,
            ),
        ),
        Document(
            id="doc2",
            metadata=DocMetadata(
                content={"type": "text", "text": "OpenAI is located in San Francisco and develops advanced AI systems."},
                doc_id="doc2",
                chunk_id=0,
                total_chunks=1,
            ),
        ),
        Document(
            id="doc3",
            metadata=DocMetadata(
                content={"type": "text", "text": "Bob collaborates with Alice on transformer architecture research."},
                doc_id="doc3",
                chunk_id=0,
                total_chunks=1,
            ),
        ),
    ]
    
    # Add documents to knowledge base
    print("\n📥 Adding documents...")
    await knowledge.add_documents(documents)
    print(f"✅ Added {len(documents)} documents")
    
    # Retrieve using vector search
    print("\n🔍 Searching: 'Where does Alice work?'")
    results = await knowledge.retrieve(
        query="Where does Alice work?",
        limit=2,
        search_mode="vector",
    )
    
    print(f"\n📄 Found {len(results)} results:")
    for i, doc in enumerate(results, 1):
        print(f"\n  {i}. [Score: {doc.score:.3f}]")
        print(f"     {doc.metadata.content['text']}")


async def example_with_graph_features():
    """Example 2: Full graph features (entities + relationships)."""
    print("\n" + "="*80)
    print("Example 2: With Graph Features (Entities + Relationships)")
    print("="*80)
    
    # Initialize Neo4j graph store
    graph_store = Neo4jGraphStore(
        uri=NEO4J_URI,
        user=NEO4J_USER,
        password=NEO4J_PASSWORD,
        database="neo4j",
        collection_name="graph_knowledge",
        dimensions=1536,
    )
    
    # Initialize knowledge base with graph features
    knowledge = GraphKnowledgeBase(
        graph_store=graph_store,
        embedding_model=DashScopeTextEmbedding(
            model_name="text-embedding-v2",
            api_key=DASHSCOPE_API_KEY,
        ),
        llm_model=DashScopeChatModel(
            model_name="qwen-max",
            api_key=DASHSCOPE_API_KEY,
            stream=False,  # Disable streaming for structured output
        ),
        enable_entity_extraction=True,
        entity_extraction_config={
            "max_entities_per_chunk": 10,
            "enable_gleanings": False,  # Disable for faster processing
        },
        enable_relationship_extraction=True,
        enable_community_detection=False,  # Disable for this example
    )
    
    # Create sample documents
    documents = [
        Document(
            id="doc4",
            metadata=DocMetadata(
                content={"type": "text", "text": "Alice works at OpenAI as a researcher specializing in language models."},
                doc_id="doc4",
                chunk_id=0,
                total_chunks=1,
            ),
        ),
        Document(
            id="doc5",
            metadata=DocMetadata(
                content={"type": "text", "text": "OpenAI is located in San Francisco and develops advanced AI systems."},
                doc_id="doc5",
                chunk_id=0,
                total_chunks=1,
            ),
        ),
        Document(
            id="doc6",
            metadata=DocMetadata(
                content={"type": "text", "text": "Bob collaborates with Alice on transformer architecture research."},
                doc_id="doc6",
                chunk_id=0,
                total_chunks=1,
            ),
        ),
    ]
    
    # Add documents (will extract entities and relationships)
    print("\n📥 Adding documents (with entity/relationship extraction)...")
    await knowledge.add_documents(documents)
    print(f"✅ Added {len(documents)} documents with graph features")
    
    # Test different search modes
    query = "Tell me about Alice's work"
    
    # Vector search
    print(f"\n🔍 [Vector Search] Query: '{query}'")
    vector_results = await knowledge.retrieve(
        query=query,
        limit=2,
        search_mode="vector",
    )
    print(f"   Found {len(vector_results)} results")
    
    # Graph search
    print(f"\n🔍 [Graph Search] Query: '{query}'")
    graph_results = await knowledge.retrieve(
        query=query,
        limit=2,
        search_mode="graph",
        max_hops=2,
    )
    print(f"   Found {len(graph_results)} results")
    
    # Hybrid search (recommended)
    print(f"\n🔍 [Hybrid Search] Query: '{query}'")
    hybrid_results = await knowledge.retrieve(
        query=query,
        limit=2,
        search_mode="hybrid",
        vector_weight=0.5,
        graph_weight=0.5,
    )
    print(f"   Found {len(hybrid_results)} results")
    
    print(f"\n📄 Hybrid search results:")
    for i, doc in enumerate(hybrid_results, 1):
        print(f"\n  {i}. [Score: {doc.score:.3f}]")
        print(f"     {doc.metadata.content['text']}")


async def example_with_community_detection():
    """Example 3: Full features including community detection."""
    print("\n" + "="*80)
    print("Example 3: Full Features (Entities + Relationships + Communities)")
    print("="*80)
    
    # Initialize Neo4j graph store
    graph_store = Neo4jGraphStore(
        uri=NEO4J_URI,
        user=NEO4J_USER,
        password=NEO4J_PASSWORD,
        database="neo4j",
        collection_name="full_knowledge",
        dimensions=1536,
    )
    
    # Initialize knowledge base with all features
    knowledge = GraphKnowledgeBase(
        graph_store=graph_store,
        embedding_model=DashScopeTextEmbedding(
            model_name="text-embedding-v2",
            api_key=DASHSCOPE_API_KEY,
        ),
        llm_model=DashScopeChatModel(
            model_name="qwen-max",
            api_key=DASHSCOPE_API_KEY,
            stream=False,  # Disable streaming for structured output
        ),
        enable_entity_extraction=True,
        entity_extraction_config={
            "max_entities_per_chunk": 10,
            "enable_gleanings": True,  # Enable for higher recall
            "gleanings_rounds": 2,
        },
        enable_relationship_extraction=True,
        enable_community_detection=True,  # Enable community detection
        community_algorithm="leiden",
    )
    
    # Create sample documents
    documents = [
        Document(
            id="doc7",
            metadata=DocMetadata(
                content={"type": "text", "text": "Alice works at OpenAI as a researcher specializing in language models."},
                doc_id="doc7",
                chunk_id=0,
                total_chunks=1,
            ),
        ),
        Document(
            id="doc8",
            metadata=DocMetadata(
                content={"type": "text", "text": "OpenAI is located in San Francisco and develops advanced AI systems."},
                doc_id="doc8",
                chunk_id=0,
                total_chunks=1,
            ),
        ),
        Document(
            id="doc9",
            metadata=DocMetadata(
                content={"type": "text", "text": "Bob collaborates with Alice on transformer architecture research."},
                doc_id="doc9",
                chunk_id=0,
                total_chunks=1,
            ),
        ),
        Document(
            id="doc10",
            metadata=DocMetadata(
                content={"type": "text", "text": "Google DeepMind in London also researches AI and machine learning."},
                doc_id="doc10",
                chunk_id=0,
                total_chunks=1,
            ),
        ),
    ]
    
    # Add documents (will trigger community detection in background on first call)
    print("\n📥 Adding documents (with all features)...")
    await knowledge.add_documents(documents)
    print(f"✅ Added {len(documents)} documents")
    print("   Community detection triggered in background...")
    
    # Wait a bit for community detection to complete
    await asyncio.sleep(5)
    
    # Manually trigger community detection (for demonstration)
    print("\n🔬 Manually triggering community detection...")
    result = await knowledge.detect_communities()
    print(f"✅ Community detection completed:")
    print(f"   - Communities: {result['community_count']}")
    print(f"   - Levels: {result['levels']}")
    print(f"   - Algorithm: {result['algorithm']}")
    
    # Test global search (community-level)
    print(f"\n🔍 [Global Search] Query: 'What are the main research topics?'")
    try:
        global_results = await knowledge.retrieve(
            query="What are the main research topics?",
            limit=3,
            search_mode="global",
            min_community_level=0,
        )
        print(f"   Found {len(global_results)} results")
        
        print(f"\n📄 Global search results:")
        for i, doc in enumerate(global_results, 1):
            print(f"\n  {i}. [Score: {doc.score:.3f}]")
            print(f"     {doc.metadata.content['text']}")
    except Exception as e:
        print(f"   ⚠️  Global search not fully implemented yet: {e}")


async def main():
    """Run all examples."""
    print("\n" + "="*80)
    print("GraphKnowledgeBase Usage Examples")
    print("="*80)
    print("\n📌 配置信息:")
    print(f"   - Neo4j URI: {NEO4J_URI}")
    print(f"   - Neo4j User: {NEO4J_USER}")
    print(f"   - DashScope API Key: {os.environ['DASHSCOPE_API_KEY'][:20]}...")
    print("\n⚠️  请确保:")
    print("   1. Neo4j 正在运行")
    print("   2. 修改了脚本中的 NEO4J_PASSWORD")
    
    try:
        # 示例 1: 基础向量检索
        await example_basic_vector_only()
        
        # 询问是否继续
        print("\n" + "="*80)
        user_input = input("\n继续运行示例2（实体提取）吗? (y/n): ")
        if user_input.lower() == 'y':
            await example_with_graph_features()
        
        # 询问是否运行社区检测
        print("\n" + "="*80)
        user_input = input("\n继续运行示例3（社区检测）吗? (需要GDS插件) (y/n): ")
        if user_input.lower() == 'y':
            await example_with_community_detection()
        
        print("\n" + "="*80)
        print("✅ 所有示例运行完成！")
        print("="*80)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())

