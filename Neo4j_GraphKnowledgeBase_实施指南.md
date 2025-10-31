# Neo4j GraphKnowledgeBase 实施指南

## 📋 文档信息

- **版本**: v1.0
- **创建日期**: 2025-10-30
- **文档类型**: 实施指南
- **目标**: 提供 Neo4j GraphKnowledgeBase 的使用指南、配置说明和实施计划
- **设计原则**: 渐进式配置、生产就绪、易于上手

---

## 目录

- [一、快速开始](#一快速开始)
- [二、使用示例](#二使用示例)
- [三、配置说明](#三配置说明)
- [五、实施计划](#五实施计划)
- [六、安装部署](#六安装部署)

---

## 一、快速开始

### 1.1 核心特性一览

| 特性             | 说明                       | 默认状态 | 执行方式 |
| ---------------- | -------------------------- | -------- | -------- |
| **实体提取**     | 从文本中提取关键实体       | ✅ 启用  | 同步（每次文档添加） |
| **关系提取**     | 识别实体间的关系           | ✅ 启用  | 同步（每次文档添加） |
| **社区检测**     | 使用图算法进行社区划分     | ❌ 关闭  | 异步（用户主动调用）⭐ |
| **Gleanings**    | 重复检查以提高召回率       | ❌ 关闭  | 同步（可选启用） |
| **多种检索模式** | vector/graph/hybrid/global | ✅ 支持  | - |

### 1.2 与 SimpleKnowledge 的对比

```
SimpleKnowledge (现有)          GraphKnowledgeBase (新增)
    │                                   │
    ├── 向量数据库存储                   ├── 图数据库存储
    ├── 纯向量检索                       ├── 实体识别
    ├── 速度快                           ├── 关系提取
    └── 适合简单场景                     ├── 图遍历检索
                                        ├── 社区检测（可选）
                                        └── 适合复杂知识图谱
```

### 1.3 何时选择 GraphKnowledgeBase

**推荐使用场景**：

✅ 需要理解实体间关系的场景
✅ 多跳推理需求（"朋友的朋友"）
✅ 知识图谱构建
✅ 需要全局视角（社区检测）
✅ 长文档的结构化理解

**不推荐场景**：

❌ 简单的语义搜索
❌ 成本敏感且对质量要求不高
❌ 实时性要求极高（<50ms）

---

## 二、使用示例

### 2.1 基础使用（最小配置）

```python
import asyncio
from agentscope.rag import GraphKnowledgeBase, Neo4jGraphStore
from agentscope.embedding import DashScopeTextEmbedding
from agentscope.model import DashScopeChatModel

# 1. 初始化存储
graph_store = Neo4jGraphStore(
    uri="bolt://localhost:7687",
    user="neo4j",
    password="your_password",
    database="neo4j",
    collection_name="my_knowledge",
    dimensions=1536,  # text-embedding-v2 维度
)

# 2. 初始化知识库（关闭图功能，仅向量检索）
knowledge = GraphKnowledgeBase(
    graph_store=graph_store,
    embedding_model=DashScopeTextEmbedding(
        model_name="text-embedding-v2",
    ),
    llm_model=None,  # 关闭图功能
    enable_entity_extraction=False,
    enable_relationship_extraction=False,
)

# 3. 添加文档
documents = [
    Document(
        id="doc1",
        content="Alice works at OpenAI as a researcher.",
        metadata=DocMetadata(doc_id="doc1", chunk_id=0, total_chunks=1),
    ),
    Document(
        id="doc2",
        content="OpenAI is located in San Francisco.",
        metadata=DocMetadata(doc_id="doc2", chunk_id=0, total_chunks=1),
    ),
]

await knowledge.add_documents(documents)

# 4. 检索（纯向量模式）
results = await knowledge.retrieve(
    query="Where does Alice work?",
    limit=5,
    search_mode="vector",
)

for doc in results:
    print(f"Score: {doc.metadata.score}, Content: {doc.content}")
```

---

### 2.2 完整使用（启用图功能）

```python
# 初始化知识库（启用实体和关系提取）
knowledge = GraphKnowledgeBase(
    graph_store=graph_store,
    embedding_model=DashScopeTextEmbedding(
        model_name="text-embedding-v2",
    ),
    llm_model=DashScopeChatModel(
        model_name="qwen-plus",
    ),
    # 启用实体提取
    enable_entity_extraction=True,
    entity_extraction_config={
        "max_entities_per_chunk": 10,
        "enable_gleanings": False,
    },
    # 启用关系提取
    enable_relationship_extraction=True,
    # 关闭社区检测（默认）
    enable_community_detection=False,
)

# 添加文档（会自动提取实体和关系）
await knowledge.add_documents(documents)

# 混合检索（推荐）
results = await knowledge.retrieve(
    query="Where does Alice work?",
    limit=5,
    search_mode="hybrid",  # 向量 + 图
)

# 图遍历检索
results = await knowledge.retrieve(
    query="Tell me about Alice",
    limit=5,
    search_mode="graph",
    max_hops=2,  # 2 跳图遍历
)
```

---

### 2.3 高级使用（启用社区检测）

```python
# 初始化知识库（启用所有功能）
knowledge = GraphKnowledgeBase(
    graph_store=graph_store,
    embedding_model=DashScopeTextEmbedding(
        model_name="text-embedding-v2",
    ),
    llm_model=DashScopeChatModel(
        model_name="qwen-plus",
    ),
    # 启用实体提取（带 Gleanings）
    enable_entity_extraction=True,
    entity_extraction_config={
        "max_entities_per_chunk": 10,
        "enable_gleanings": True,
        "gleanings_rounds": 2,  # 重复检查 2 轮
    },
    # 启用关系提取
    enable_relationship_extraction=True,
    # 启用社区检测（首次自动执行一次）⭐
    enable_community_detection=True,
    community_algorithm="leiden",  # 或 "louvain"
)

# 添加文档（首次会自动触发社区检测，后台执行）
await knowledge.add_documents(documents)

# 后续手动触发社区检测 ⭐
await knowledge.detect_communities()  # 同步执行，阻塞等待

# 或异步后台执行（不阻塞）
task = asyncio.create_task(knowledge.detect_communities())
# ... 继续其他工作 ...
result = await task  # 需要时等待

# 全局检索（基于社区）
results = await knowledge.retrieve(
    query="What are the main topics?",
    limit=10,
    search_mode="global",  # 社区级检索
)
```

---

### 2.4 集成到 ReActAgent

```python
from agentscope.agent import ReActAgent
from agentscope.tool import retrieve_knowledge

# 创建 Agent
agent = ReActAgent(
    name="ResearchAgent",
    model=DashScopeChatModel(model_name="qwen-plus"),
    knowledge=knowledge,  # 直接传入知识库
    tools=[retrieve_knowledge],  # 添加检索工具
)

# 使用 Agent
response = agent(
    query="What is the relationship between Alice and OpenAI?"
)
print(response)
```

---

## 三、配置说明

### 3.1 实体提取配置

```python
entity_extraction_config = {
    # 每个文档块最多提取的实体数
    "max_entities_per_chunk": 10,
  
    # 是否启用 Gleanings（重复检查）
    "enable_gleanings": False,
  
    # Gleanings 轮数（启用时有效）
    "gleanings_rounds": 2,
  
    # 实体类型（可自定义）
    "entity_types": [
        "PERSON",
        "ORG",
        "LOCATION",
        "PRODUCT",
        "EVENT",
        "CONCEPT",
    ],
  
    # 是否生成实体 embedding
    "generate_entity_embeddings": True,
}
```

**说明**：

- `max_entities_per_chunk`：控制成本和质量的平衡
- `enable_gleanings`：启用后可提高召回率，但成本增加 50%+
- `gleanings_rounds`：建议 1-3 轮，过多轮次收益递减
- `entity_types`：根据领域自定义实体类型

---

### 3.2 关系提取配置

```python
# 关系提取默认启用，无额外配置
enable_relationship_extraction = True
```

**说明**：

- 关系提取会在实体提取后自动执行
- 成本约为实体提取的 50%
- 提取的关系类型由 LLM 自动判断

---

### 3.3 社区检测配置（简化设计）⭐

**核心理念**：社区检测采用**用户主动调用**的简化设计，不引入复杂的自动触发机制。

**配置参数**：

```python
knowledge = GraphKnowledgeBase(
    ...,
    # 社区检测配置（仅 2 个参数）
    enable_community_detection=False,  # 是否启用（启用后首次自动执行，默认 False）
    community_algorithm="leiden",  # 社区检测算法（leiden 或 louvain）
)
```

**配置说明**：

- `enable_community_detection=False`（默认）：不启用社区检测功能
- `enable_community_detection=True`：启用社区检测，首次添加文档后自动执行一次，后续完全由用户手动调用

**算法选择**：

| 算法 | 优点 | 缺点 | 适用场景 |
|-----|------|------|---------|
| `leiden` | 质量更高，社区更准确 | 计算稍慢 | 推荐默认使用 |
| `louvain` | 速度更快 | 质量略逊 | 大规模图（10万+节点）|

**手动调用方式**：

```python
# 方式 1：同步执行（阻塞等待完成）
result = await knowledge.detect_communities()
print(f"检测到 {result['community_count']} 个社区")

# 方式 2：异步后台执行（不阻塞）
task = asyncio.create_task(knowledge.detect_communities())
# ... 继续其他工作 ...
result = await task  # 需要时等待

# 方式 3：覆盖默认算法
result = await knowledge.detect_communities(algorithm="louvain")
```

**典型使用场景**：

```python
# 场景 1：不启用社区检测（最简单，仅使用实体和关系）
knowledge = GraphKnowledgeBase(..., enable_community_detection=False)
await knowledge.add_documents(batch1)
await knowledge.add_documents(batch2)
# 不会自动执行社区检测，也不能手动调用

# 场景 2：启用社区检测（首次自动 + 后续手动）⭐ 推荐
knowledge = GraphKnowledgeBase(..., enable_community_detection=True)
await knowledge.add_documents(initial_docs)  # 首次自动触发后台社区检测
# 后续添加不会自动触发
await knowledge.add_documents(more_docs)
# 用户决定何时手动更新
await knowledge.detect_communities()

# 场景 3：后台异步执行（不阻塞主流程）
knowledge = GraphKnowledgeBase(..., enable_community_detection=True)
await knowledge.add_documents(docs)
# 后续更新时使用后台执行
task = asyncio.create_task(knowledge.detect_communities())
# ... 继续其他工作 ...
await task  # 需要时等待

# 场景 4：定期更新（用户自己实现）
async def periodic_update():
    while True:
        await asyncio.sleep(3600)  # 每小时
        try:
            await knowledge.detect_communities()
        except Exception as e:
            logger.error(f"Community detection failed: {e}")

asyncio.create_task(periodic_update())
```

---

### 3.4 检索模式配置

| 检索模式 | 说明 | 适用场景 | 速度 | 质量 |
|---------|------|---------|------|------|
| `vector` | 纯向量检索 | 简单语义搜索 | ⚡⚡⚡ | ⭐⭐⭐ |
| `graph` | 图遍历检索 | 需要理解关系 | ⚡⚡ | ⭐⭐⭐⭐ |
| `hybrid` | 向量+图混合 | 通用推荐 | ⚡⚡ | ⭐⭐⭐⭐⭐ |
| `global` | 社区级检索 | 全局理解、主题发现 | ⚡ | ⭐⭐⭐⭐ |

**示例**：

```python
# 向量检索（最快）
results = await knowledge.retrieve(
    query="...",
    search_mode="vector",
    limit=5,
)

# 图遍历检索
results = await knowledge.retrieve(
    query="...",
    search_mode="graph",
    limit=5,
    max_hops=2,  # 图遍历跳数
)

# 混合检索（推荐）
results = await knowledge.retrieve(
    query="...",
    search_mode="hybrid",
    limit=5,
    vector_weight=0.5,  # 向量检索权重
    graph_weight=0.5,   # 图检索权重
)

# 全局检索
results = await knowledge.retrieve(
    query="...",
    search_mode="global",
    limit=10,
    min_community_level=1,  # 最小社区层级
)
```

---

### 3.5 推荐配置组合

#### 场景 1：默认配置（推荐 80% 场景）

```python
# 成本：+25%，质量：+30-40%
knowledge = GraphKnowledgeBase(
    graph_store=graph_store,
    embedding_model=embedding_model,
    llm_model=llm_model,
    enable_entity_extraction=True,
    enable_relationship_extraction=True,
    entity_extraction_config={
        "enable_gleanings": False,
    },
    # 社区检测：不启用 ⭐
    enable_community_detection=False,
)

# 添加文档（不会触发社区检测）
await knowledge.add_documents(documents)

# 使用混合检索
results = await knowledge.retrieve(
    query="...",
    search_mode="hybrid",
)
```

**适用场景**：

- 一般性知识库
- 成本和质量的平衡
- 需要理解实体关系

---

#### 场景 2：高质量配置（科研/法律等专业领域）

```python
# 成本：+75%，质量：+50-60%
knowledge = GraphKnowledgeBase(
    graph_store=graph_store,
    embedding_model=embedding_model,
    llm_model=llm_model,
    enable_entity_extraction=True,
    enable_relationship_extraction=True,
    entity_extraction_config={
        "enable_gleanings": True,
        "gleanings_rounds": 2,
    },
    # 社区检测：启用（首次自动执行）⭐
    enable_community_detection=True,
    community_algorithm="leiden",
)

# 添加初始文档（首次自动触发社区检测）
await knowledge.add_documents(initial_documents)

# 后续添加更多文档（不会自动触发）
await knowledge.add_documents(more_documents)

# 手动更新社区（后台执行）
asyncio.create_task(knowledge.detect_communities())

# 使用混合检索或全局检索
results = await knowledge.retrieve(
    query="...",
    search_mode="hybrid",  # 或 "global"
)
```

**适用场景**：

- 专业领域知识库
- 对质量要求极高
- 需要全局理解和社区分析

---

#### 场景 3：低成本配置（成本敏感）

```python
# 成本：+5%，质量：+10-15%
knowledge = GraphKnowledgeBase(
    graph_store=graph_store,
    embedding_model=embedding_model,
    llm_model=None,  # 关闭 LLM
    enable_entity_extraction=False,
    enable_relationship_extraction=False,
    # 不启用社区检测
    enable_community_detection=False,
)

# 使用向量检索
results = await knowledge.retrieve(
    query="...",
    search_mode="vector",
)
```

**适用场景**：

- 成本敏感场景
- 简单语义搜索
- 不需要关系理解
- 作为 SimpleKnowledge 的 drop-in 替代

---

## 五、实施计划

### 5.1 开发计划（3周）

#### Week 1: 基础框架

**Day 1: 基础抽象和异常设计** ⭐

- [ ]  创建 `exception/_rag.py`：定义 RAG 专用异常类
- [ ]  更新 `exception/__init__.py`：导出 RAG 异常
- [ ]  创建 `rag/_graph_types.py`：定义 Pydantic 数据模型和 TypedDict
- [ ]  修改 `_store_base.py`：新增 `StoreBase` 基类
- [ ]  修改 `VDBStoreBase`：继承 `StoreBase`
- [ ]  新增 `GraphStoreBase`：定义图数据库抽象接口
- [ ]  修改 `_knowledge_base.py`：`embedding_store` 改为 `StoreBase` 类型
- [ ]  单元测试：确保现有 `QdrantStore`、`MilvusLiteStore` 正常工作

**Day 2-3: Neo4jGraphStore 实现**

- [ ]  实现 `Neo4jGraphStore(GraphStoreBase)` 基础功能
- [ ]  基础连接和配置
- [ ]  实现 `_ensure_connection()` 方法（带重试机制）
- [ ]  索引管理（`_ensure_indexes`）
- [ ]  实现 `add()`、`search()` 方法（StoreBase 接口）
- [ ]  异常处理：捕获并抛出 `DatabaseConnectionError`、`GraphQueryError`
- [ ]  单元测试

**Day 4: GraphKnowledgeBase 骨架**

- [ ]  类结构实现 `GraphKnowledgeBase(KnowledgeBase)`
- [ ]  `add_documents`（纯向量模式）
- [ ]  `retrieve`（vector 模式）
- [ ]  `_embed_documents` 和 `_embed_query`
- [ ]  集成测试

**Day 5: 文档和示例**

- [ ]  API 文档
- [ ]  基础使用示例
- [ ]  README 更新
- [ ]  代码审查

**里程碑 1**：基础向量检索功能完成

---

#### Week 2: 实体和关系

**Day 1-2: 实体提取**

- [ ]  `_extract_entities_single_pass`：返回 Pydantic `Entity` 模型列表
- [ ]  LLM 返回数据使用 Pydantic 自动验证
- [ ]  `_gleanings_pass`（可选）
- [ ]  `_resolve_entities`（去重）
- [ ]  实现 `Neo4jGraphStore.add_entities()`（GraphStoreBase 接口）
- [ ]  错误处理：捕获并处理 `EntityExtractionError`
- [ ]  测试

**Day 3-4: 关系提取**

- [ ]  `_extract_relationships`：返回 Pydantic `Relationship` 模型列表
- [ ]  LLM 返回数据使用 Pydantic 自动验证
- [ ]  实现 `Neo4jGraphStore.add_relationships()`（GraphStoreBase 接口）
- [ ]  实现 `Neo4jGraphStore.search_entities()`（GraphStoreBase 接口）
- [ ]  实现 `Neo4jGraphStore.search_with_graph()`（GraphStoreBase 接口）
- [ ]  graph 和 hybrid 检索模式
- [ ]  异常处理和日志记录
- [ ]  测试

**Day 5: 测试和优化**

- [ ]  性能测试
- [ ]  成本分析
- [ ]  优化 Prompt
- [ ]  文档更新

**里程碑 2**：实体和关系提取完成，图检索可用

---

#### Week 3: 社区检测和完善（简化实现）⭐

**Day 1-2: 社区检测核心功能**

- [ ]  Neo4j GDS 集成（Leiden/Louvain 算法）
- [ ]  实现 `detect_communities()` 方法（用户主动调用）
- [ ]  实现 `_batch_generate_summaries()`（批量并发 LLM 调用）
- [ ]  实现 `_batch_embed_communities()`（批量 embedding）
- [ ]  实现 `Neo4jGraphStore.add_communities()`（GraphStoreBase 可选接口）
- [ ]  首次自动触发逻辑（`enable_community_detection` 为 True 时）

**Day 3: 全局搜索**

- [ ]  实现 `Neo4jGraphStore.search_communities()`（GraphStoreBase 可选接口）
- [ ]  实现 `_global_search()` 方法
- [ ]  global 检索模式集成

**Day 4: 使用示例和文档**

- [ ]  补充社区检测使用示例（同步、异步、定期执行）
- [ ]  更新 API 文档
- [ ]  性能测试和优化

**Day 5: 完整测试和发布**

- [ ]  端到端测试
- [ ]  性能基准测试
- [ ]  完整文档
- [ ]  示例代码
- [ ]  发布准备

**里程碑 3**：功能完整，生产就绪

---

### 5.2 测试计划

#### 单元测试

- [ ]  Neo4jGraphStore 所有方法
- [ ]  GraphKnowledgeBase 核心方法
- [ ]  实体提取逻辑
- [ ]  关系提取逻辑
- [ ]  检索策略

#### 集成测试

- [ ]  完整索引流程
- [ ]  多种检索模式
- [ ]  Agent 集成
- [ ]  错误处理

#### 性能测试

- [ ]  索引吞吐量
- [ ]  检索延迟（P50/P95/P99）
- [ ]  内存使用
- [ ]  并发性能

#### 质量测试

- [ ]  实体提取准确率
- [ ]  关系提取准确率
- [ ]  检索 Precision@K
- [ ]  检索 Recall@K

---

## 六、安装部署

### 6.1 依赖项

```toml
# pyproject.toml

[project.dependencies]
neo4j = "^6.0.2.0"           # Neo4j Python Driver (async)
pydantic = "^2.0.0"         # 数据验证
# 其他已有依赖...

[project.optional-dependencies]
graph = [
    "neo4j>=6.0.2.0",
]
```

**安装命令**：

```bash
# 基础安装
pip install agentscope

# 安装图功能依赖
pip install "agentscope[graph]"

# 或使用 poetry
poetry install --extras graph
```

---

### 6.2 Neo4j 安装

#### Docker 方式（推荐）

```bash
# 启动 Neo4j 容器（含 GDS 插件）
docker run -d \
  --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/password \
  -e NEO4J_PLUGINS='["graph-data-science"]' \
  -v neo4j_data:/data \
  neo4j:latest

# 验证安装
# 浏览器访问 http://localhost:7474
# 默认用户名：neo4j
# 默认密码：password（首次登录需修改）
```

**说明**：

- `NEO4J_AUTH`：设置用户名和密码
- `NEO4J_PLUGINS`：安装 Graph Data Science 插件（社区检测需要）
- `-v neo4j_data:/data`：持久化数据

---

#### 本地安装方式

**Linux/Mac**：

```bash
# 下载 Neo4j
wget https://neo4j.com/artifact.php?name=neo4j-community-6.0.2.0-unix.tar.gz

# 解压
tar -xzf neo4j-community-6.0.2.0-unix.tar.gz
cd neo4j-community-6.0.2.0

# 启动
./bin/neo4j start

# 停止
./bin/neo4j stop
```

**Windows**：

1. 下载 [Neo4j Desktop](https://neo4j.com/download/)
2. 安装并启动
3. 创建新数据库
4. 安装 GDS 插件（可选）

---

### 6.3 连接验证

```python
import asyncio
from agentscope.rag import Neo4jGraphStore

async def test_connection():
    store = Neo4jGraphStore(
        uri="bolt://localhost:7687",
        user="neo4j",
        password="your_password",
    )
  
    # 验证连接
    try:
        client = store.get_client()
        print("Connection successful!")
    except Exception as e:
        print(f"Connection failed: {e}")
    finally:
        await store.close()

# 运行测试
asyncio.run(test_connection())
```

---

### 6.4 常见问题

#### Q1: 连接失败 "Unable to retrieve routing information"

**原因**：Neo4j 服务未启动或端口不可达

**解决**：

```bash
# 检查 Neo4j 是否运行
docker ps | grep neo4j

# 检查端口
netstat -an | grep 7687
```

---

#### Q2: 向量索引创建失败

**原因**：Neo4j 版本低于 6.0.2 或未启用向量索引功能

**解决**：

```bash
# 升级 Neo4j 到 6.0.2+
docker pull neo4j:latest

# 验证版本
docker exec neo4j neo4j --version
```

---

#### Q3: 社区检测功能不可用

**原因**：未安装 Graph Data Science 插件

**解决**：

```bash
# 重新启动容器并安装 GDS
docker run -d \
  --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/password \
  -e NEO4J_PLUGINS='["graph-data-science"]' \
  neo4j:latest

# 验证 GDS 是否安装
# 在 Neo4j Browser 中执行：
CALL gds.version()
```

---

## 参考资源

- [AgentScope 官方文档](https://doc.agentscope.io/)
- [Neo4j 官方文档](https://neo4j.com/docs/)
- [Neo4j Python Driver](https://neo4j.com/docs/python-manual/current/)
- [Neo4j Graph Data Science](https://neo4j.com/docs/graph-data-science/current/)
- [GraphRAG 论文](https://arxiv.org/abs/2404.16130)
- [Neo4j Desktop 下载](https://neo4j.com/download/)

---

**文档版本**: v1.0
**文档类型**: 实施指南
**最后更新**: 2025-10-30
**维护者**: AgentScope Team

