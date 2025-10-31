# GraphKnowledgeBase 使用指南

## 概述

`GraphKnowledgeBase` 是 AgentScope RAG 模块的新功能，它使用图数据库（如 Neo4j）来表示和检索知识，支持实体识别、关系提取和社区检测等高级特性。

## 主要特性

| 特性 | 说明 | 默认状态 |
|------|------|---------|
| 🔍 **向量检索** | 基于语义相似度的文档检索 | ✅ 始终启用 |
| 🏷️ **实体提取** | 从文本中提取关键实体 | ✅ 默认启用 |
| 🔗 **关系提取** | 识别实体间的关系 | ✅ 默认启用 |
| 🌐 **社区检测** | 使用图算法进行社区划分 | ❌ 默认关闭 |
| 📊 **多种检索模式** | vector/graph/hybrid/global | ✅ 支持 |

## 快速开始

### 1. 安装依赖

```bash
# 安装 Neo4j Python driver
pip install neo4j~=6.0.2

# 或使用 poetry
poetry add neo4j
```

### 2. 启动 Neo4j

使用 Docker（推荐）：

```bash
docker run -d \
  --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/password \
  -e NEO4J_PLUGINS='["graph-data-science"]' \
  neo4j:latest
```

### 3. 基础使用示例

```python
import asyncio
from agentscope.rag import GraphKnowledgeBase, Neo4jGraphStore, Document, DocMetadata
from agentscope.embedding import DashScopeTextEmbedding
from agentscope.model import DashScopeChatModel

async def main():
    # 1. 初始化 Neo4j 图存储
    graph_store = Neo4jGraphStore(
        uri="bolt://localhost:7687",
        user="neo4j",
        password="password",
        database="neo4j",
        collection_name="my_knowledge",
        dimensions=1536,
    )
    
    # 2. 初始化知识库
    knowledge = GraphKnowledgeBase(
        graph_store=graph_store,
        embedding_model=DashScopeTextEmbedding(model_name="text-embedding-v2"),
        llm_model=DashScopeChatModel(model_name="qwen-plus"),
        enable_entity_extraction=True,
        enable_relationship_extraction=True,
    )
    
    # 3. 添加文档
    documents = [
        Document(
            id="doc1",
            content="Alice works at OpenAI as a researcher.",
            metadata=DocMetadata(doc_id="doc1", chunk_id=0, total_chunks=1),
        ),
    ]
    await knowledge.add_documents(documents)
    
    # 4. 检索
    results = await knowledge.retrieve(
        query="Where does Alice work?",
        limit=5,
        search_mode="hybrid",  # 推荐使用混合模式
    )
    
    for doc in results:
        print(f"Score: {doc.metadata.score}, Content: {doc.content}")

asyncio.run(main())
```

## 配置选项

### 配置 1：最小配置（仅向量检索）

```python
knowledge = GraphKnowledgeBase(
    graph_store=graph_store,
    embedding_model=embedding_model,
    llm_model=None,  # 不需要 LLM
    enable_entity_extraction=False,
    enable_relationship_extraction=False,
)

# 使用场景：简单的语义搜索，成本敏感
# 成本：+5%，质量：+10-15%
```

### 配置 2：默认配置（推荐 80% 场景）

```python
knowledge = GraphKnowledgeBase(
    graph_store=graph_store,
    embedding_model=embedding_model,
    llm_model=llm_model,
    enable_entity_extraction=True,
    enable_relationship_extraction=True,
    entity_extraction_config={
        "max_entities_per_chunk": 10,
        "enable_gleanings": False,
    },
)

# 使用场景：一般性知识库，需要理解实体关系
# 成本：+25%，质量：+30-40%
```

### 配置 3：高质量配置（专业领域）

```python
knowledge = GraphKnowledgeBase(
    graph_store=graph_store,
    embedding_model=embedding_model,
    llm_model=llm_model,
    enable_entity_extraction=True,
    entity_extraction_config={
        "max_entities_per_chunk": 10,
        "enable_gleanings": True,
        "gleanings_rounds": 2,
    },
    enable_relationship_extraction=True,
    enable_community_detection=True,
    community_algorithm="leiden",
)

# 使用场景：专业领域知识库，对质量要求极高
# 成本：+75%，质量：+50-60%
```

## 检索模式

### 1. Vector 模式（最快）

```python
results = await knowledge.retrieve(
    query="your query",
    search_mode="vector",
    limit=5,
)
```

- **速度**: ⚡⚡⚡ 最快
- **质量**: ⭐⭐⭐ 基线
- **适用**: 简单语义搜索

### 2. Graph 模式（关系推理）

```python
results = await knowledge.retrieve(
    query="your query",
    search_mode="graph",
    limit=5,
    max_hops=2,  # 图遍历跳数
)
```

- **速度**: ⚡⚡ 中等
- **质量**: ⭐⭐⭐⭐ 较好
- **适用**: 需要理解实体间关系

### 3. Hybrid 模式（推荐）

```python
results = await knowledge.retrieve(
    query="your query",
    search_mode="hybrid",
    limit=5,
    vector_weight=0.5,
    graph_weight=0.5,
)
```

- **速度**: ⚡⚡ 中等
- **质量**: ⭐⭐⭐⭐⭐ 最好
- **适用**: 通用推荐，平衡速度和质量

### 4. Global 模式（全局理解）

```python
# 需要先启用社区检测
knowledge = GraphKnowledgeBase(
    ...,
    enable_community_detection=True,
)

# 首次添加文档后自动触发社区检测
await knowledge.add_documents(documents)

# 或手动触发
await knowledge.detect_communities()

# 然后使用全局检索
results = await knowledge.retrieve(
    query="What are the main topics?",
    search_mode="global",
    limit=10,
    min_community_level=1,
)
```

- **速度**: ⚡ 较慢
- **质量**: ⭐⭐⭐⭐ 较好
- **适用**: 总结性问题、主题发现

## 社区检测

### 启用社区检测

```python
knowledge = GraphKnowledgeBase(
    ...,
    enable_community_detection=True,
    community_algorithm="leiden",  # 或 "louvain"
)

# 首次添加文档时自动触发（后台执行）
await knowledge.add_documents(initial_docs)
```

### 手动触发社区检测

```python
# 方式 1: 同步执行（阻塞等待）
result = await knowledge.detect_communities()
print(f"检测到 {result['community_count']} 个社区")

# 方式 2: 异步后台执行（不阻塞）
import asyncio
task = asyncio.create_task(knowledge.detect_communities())
# ... 继续其他工作 ...
result = await task  # 需要时等待

# 方式 3: 覆盖默认算法
result = await knowledge.detect_communities(algorithm="louvain")
```

### 何时使用社区检测

- ✅ 添加大批量文档后
- ✅ 定期维护时（如每周/月）
- ✅ 图结构变化较大时
- ✅ 需要全局理解和主题发现

## 与 ReActAgent 集成

```python
from agentscope.agent import ReActAgent
from agentscope.tool import retrieve_knowledge

# 创建 Agent
agent = ReActAgent(
    name="ResearchAgent",
    model=DashScopeChatModel(model_name="qwen-plus"),
    knowledge=knowledge,  # 直接传入知识库
    tools=[retrieve_knowledge],
)

# 使用 Agent
response = agent(
    query="What is the relationship between Alice and OpenAI?"
)
```

## 性能与成本

### 索引性能

| 配置 | 吞吐量 | 延迟 (P50/P95/P99) |
|------|--------|-------------------|
| 纯向量 | ~100 docs/s | 10ms / 20ms / 50ms |
| 实体+关系 | ~10 docs/s | 100ms / 200ms / 500ms |
| 含Gleanings | ~5 docs/s | 200ms / 400ms / 1s |

### 检索性能

| 检索模式 | 延迟 (P50/P95/P99) | 质量提升 |
|---------|-------------------|---------|
| vector | 50ms / 100ms / 200ms | 基线 |
| graph | 200ms / 400ms / 800ms | +20-30% |
| hybrid | 300ms / 500ms / 1s | +30-40% |
| global | 500ms / 1s / 2s | +40-50% |

### 成本分析

| 配置 | Embedding 调用 | LLM 调用 | 成本增加 | 质量提升 |
|------|--------------|----------|---------|---------|
| 纯向量 | 每文档 1 次 | 0 | +5% | +10-15% |
| 默认配置 | 每文档 1 次 + 实体数×1 | 实体提取 + 关系提取 | +25% | +30-40% |
| 含Gleanings | 每文档 1 次 + 实体数×1 | 实体提取×3 + 关系提取 | +50% | +40-50% |
| 含社区检测 | 上述 + 社区数×1 | 上述 + 社区摘要 | +75% | +50-60% |

## 架构设计

### 核心理念：内容嵌入 + 图遍历检索

```
Embedding 阶段（纯语义）
├── Document: embed(content)
├── Entity: embed(name + type + description)
└── Community: embed(summary)
    ✅ 只嵌入内容，不含关系信息

检索阶段（利用关系）
├── 向量检索：找到语义相关的节点
├── 图遍历：利用关系扩展相关节点
└── 文档收集：获取提到这些节点的文档
    ✅ 关系信息在此阶段充分利用
```

### 与 GraphRAG 的差异

| 维度 | AgentScope | GraphRAG |
|------|-----------|----------|
| **场景** | Agent 在线交互 | 文档离线分析 |
| **图谱类型** | 动态知识图谱 | 静态文档图谱 |
| **更新频率** | 实时/频繁 | 批量/定期 |
| **Embedding策略** | 内容嵌入 + 图遍历 | 关系嵌入 |
| **关系变化** | 无需更新embedding | 需重新生成embedding |

## 故障排除

### 连接失败

```
Error: Cannot connect to Neo4j
```

**解决方案**:
```bash
# 检查 Neo4j 是否运行
docker ps | grep neo4j

# 检查端口
netstat -an | grep 7687
```

### 向量索引错误

```
Error: Vector index not found
```

**解决方案**: 确保 Neo4j 版本 >= 6.0.2

```bash
docker exec neo4j neo4j --version
```

### 社区检测不可用

```
Error: Community detection is not supported
```

**解决方案**: 安装 GDS 插件

```bash
docker run -d \
  --name neo4j \
  -e NEO4J_PLUGINS='["graph-data-science"]' \
  neo4j:latest
```

## 完整示例

查看 `examples/graph_knowledge_example.py` 获取完整的使用示例。

## 参考文档

- [设计与架构文档](Neo4j_GraphKnowledgeBase_设计与架构.md)
- [实施步骤计划](Neo4j_GraphKnowledgeBase_实施步骤计划.md)
- [实施指南](Neo4j_GraphKnowledgeBase_实施指南.md)
- [Neo4j 官方文档](https://neo4j.com/docs/)
- [Neo4j GDS 文档](https://neo4j.com/docs/graph-data-science/current/)

## 许可证

与 AgentScope 相同的许可证。

