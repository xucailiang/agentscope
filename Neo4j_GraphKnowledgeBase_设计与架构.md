# Neo4j GraphKnowledgeBase 设计与架构文档

## 📋 文档信息

- **版本**: v1.0
- **创建日期**: 2025-10-30
- **文档类型**: 设计与架构文档
- **目标**: 详细描述 Neo4j GraphKnowledgeBase 的设计理念、架构和实现细节
- **设计原则**: 兼容性优先、渐进式配置、生产就绪

---

## 目录

- [一、设计概述](#一设计概述)
- [二、架构设计](#二架构设计)
- [三、详细设计](#三详细设计)
- [四、兼容性保证](#四兼容性保证)
- [五、参考资源](#五参考资源)

---

## 一、设计概述

### 1.1 核心目标

为 AgentScope RAG 模块提供**基于图数据库的知识表示和检索能力**，同时保持与现有架构的完全兼容。

### 1.2 设计原则

1. **分层抽象设计** ⭐：新建 `StoreBase` 和 `GraphStoreBase`，实现领域模型分离
2. **新建 GraphKnowledgeBase**：不修改现有 SimpleKnowledge 实现
3. **兼容性优先**：完全兼容现有 embedding 和检索接口，`VDBStoreBase` 保持不变
4. **依赖倒置原则**：`KnowledgeBase` 依赖 `StoreBase` 抽象，支持多种存储类型
5. **关注点分离** ⭐：Embedding 阶段（纯语义）与检索阶段（利用关系）职责分离
6. **渐进式配置**：默认轻量，可选增强
7. **异步全流程**：保持 AgentScope 的异步风格
8. **代码风格一致**：遵循项目规范

### 1.3 核心特性


| 特性             | 说明                       | 默认状态 | 执行方式 |
| ---------------- | -------------------------- | -------- | -------- |
| **实体提取**     | 从文本中提取关键实体       | ✅ 启用  | 同步（每次文档添加） |
| **关系提取**     | 识别实体间的关系           | ✅ 启用  | 同步（每次文档添加） |
| **社区检测**     | 使用图算法进行社区划分     | ❌ 关闭  | 异步（用户主动调用）⭐ |
| **Gleanings**    | 重复检查以提高召回率       | ❌ 关闭  | 同步（可选启用） |
| **多种检索模式** | vector/graph/hybrid/global | ✅ 支持  | - |

**核心设计理念**：

本方案采用**内容嵌入 + 图遍历检索**的架构设计：

- **Embedding 策略**：纯内容嵌入，不包含关系信息
  - Document: 只嵌入文档内容
  - Entity: 只嵌入实体描述（名称、类型、描述）
  - Community: 只嵌入社区摘要
  - ✅ 保持语义纯净性，向量空间稳定

- **关系利用**：通过图遍历在检索阶段利用
  - vector 模式：纯向量检索
  - graph 模式：向量检索 + 图遍历
  - hybrid 模式：结合两者优势（推荐）
  - ✅ 关系变化无需更新 embedding

**与 GraphRAG 的差异**：
- GraphRAG：关系嵌入方案，适合静态文档的离线分析
- AgentScope：内容嵌入方案，适合动态图谱的在线交互
- 详见 [3.2.0 Embedding 生成策略](#320-embedding-生成策略设计决策-)

### 1.4 与现有架构的关系

```
# 存储层架构
StoreBase (所有存储的顶层抽象) ⭐ 新增
    │
    ├── VDBStoreBase (向量数据库) - 已有
    │   ├── QdrantStore
    │   └── MilvusLiteStore
    │
    └── GraphStoreBase (图数据库) ⭐ 新增
        ├── Neo4jGraphStore ⭐ 新增
        └── (未来可扩展 TigerGraph、JanusGraph 等)

# 知识库层架构
KnowledgeBase (抽象基类)
    ├── SimpleKnowledge (已有 - 基于向量)
    │   └── 使用 VDBStoreBase (Qdrant/Milvus)
    │
    └── GraphKnowledgeBase (新增 - 基于图) ⭐
        └── 使用 GraphStoreBase (Neo4j等)
```

**完全兼容**：

- ✅ 实现相同的抽象接口
- ✅ 可以无缝替换 SimpleKnowledge
- ✅ 支持所有现有的 Agent 集成方式
- ✅ 通过新建 GraphStoreBase 实现领域模型分离，不破坏现有架构

---

## 二、架构设计

### 2.1 文件结构

```
src/agentscope/
├── exception/
│   ├── __init__.py              # 更新：导出 RAG 异常
│   ├── _exception_base.py       # 已有
│   ├── _tool.py                 # 已有
│   └── _rag.py                  # 新增：RAG 专用异常 ⭐
│
└── rag/
    ├── _knowledge_base.py       # 已有：抽象基类
    ├── _simple_knowledge.py     # 已有：基于向量的实现
    ├── _graph_knowledge.py      # 新增：基于图的实现 ⭐
    ├── _graph_types.py          # 新增：Pydantic 数据模型 ⭐
    │
    ├── _store/
    │   ├── _store_base.py       # 修改：新增 StoreBase 和 GraphStoreBase ⭐
    │   ├── _qdrant_store.py     # 已有：继承 VDBStoreBase
    │   ├── _milvuslite_store.py # 已有：继承 VDBStoreBase
    │   └── _neo4j_graph_store.py # 新增：继承 GraphStoreBase ⭐
    │
    ├── _reader/                  # 已有
    ├── _document.py              # 已有
    └── __init__.py               # 更新 exports
```

### 2.2 类层次结构

```python
# === 存储层抽象 ===

StoreBase (所有存储的顶层抽象) ⭐ 新增
    ├── add(documents)              # 所有存储都需要实现
    ├── delete(...)                 # 所有存储都需要实现
    ├── search(query_embedding)     # 所有存储都需要实现
    └── get_client()                # 获取底层客户端

VDBStoreBase(StoreBase)  # 向量数据库抽象 - 保持不变
    └── (继承所有 StoreBase 方法)

GraphStoreBase(StoreBase)  # 图数据库抽象 ⭐ 新增
    ├── (继承所有 StoreBase 方法)
    ├── add_entities(entities)           # 图特有：添加实体
    ├── add_relationships(relationships) # 图特有：添加关系
    ├── search_entities(query_embedding) # 图特有：实体检索
    ├── search_with_graph(...)          # 图特有：图遍历检索
    └── [可选] add_communities(...)      # 图特有：社区检测

# === 存储层实现 ===

QdrantStore(VDBStoreBase)        # 已有
MilvusLiteStore(VDBStoreBase)    # 已有
Neo4jGraphStore(GraphStoreBase)  # 新增 ⭐

# === 知识库层抽象 ===

KnowledgeBase
    ├── embedding_store: StoreBase  # ⭐ 改为 StoreBase，支持所有存储类型
    ├── embedding_model: EmbeddingModelBase
    ├── add_documents(documents)
    └── retrieve(query, limit, score_threshold)

# === 知识库层实现 ===

SimpleKnowledge(KnowledgeBase)   # 已有
    └── 使用 VDBStoreBase (Qdrant/Milvus)

GraphKnowledgeBase(KnowledgeBase)  # 新增 ⭐
    ├── 使用 GraphStoreBase (Neo4j等)
    ├── 支持实体、关系、社区
    └── 提供多种检索策略 (vector/graph/hybrid/global)
```

### 2.3 数据模型（Neo4j）

```cypher
// === 节点类型 ===

// 1. 文档节点（必需，基础功能）
(:Document {
    id: string,              // 文档唯一 ID
    content: string,         // 文本内容
    embedding: vector,       // 向量嵌入：embed(content) - 只包含文档内容
    doc_id: string,          // 原始文档 ID
    chunk_id: int,           // 块 ID
    total_chunks: int,       // 总块数
    created_at: datetime
})

// 2. 实体节点（可选，默认启用）
(:Entity {
    name: string,            // 实体名称
    type: string,            // 实体类型（PERSON/ORG/LOCATION等）
    description: string,     // 描述
    embedding: vector,       // 向量（可选）：embed(name + type + description)
                             // 注意：不包含关系信息，保持语义纯净
    created_at: datetime
})

// 3. 社区节点（可选，默认关闭）
(:Community {
    id: string,              // 社区 ID
    level: int,              // 层级（0,1,2...）
    title: string,           // 标题
    summary: string,         // 摘要
    rating: float,           // 重要性评分
    embedding: vector,       // 摘要的向量：embed(summary) - LLM 生成的摘要
    entity_count: int,       // 实体数量
    created_at: datetime
})

// === 关系类型 ===

// 文档提到实体
(:Document)-[:MENTIONS {count: int}]->(:Entity)

// 实体之间的关系
(:Entity)-[:RELATED_TO {
    type: string,
    description: string,
    strength: float
}]->(:Entity)

// 实体属于社区
(:Entity)-[:BELONGS_TO]->(:Community)

// 社区层次结构
(:Community)-[:PARENT_OF]->(:Community)

// === 向量索引 ===

// 文档向量索引（必需）
CREATE VECTOR INDEX document_vector_idx
FOR (d:Document)
ON d.embedding
OPTIONS {
    indexConfig: {
        `vector.dimensions`: 1536,
        `vector.similarity_function`: 'cosine'
    }
}

// 实体向量索引（可选）
CREATE VECTOR INDEX entity_vector_idx
FOR (e:Entity)
ON e.embedding

// 社区向量索引（可选）
CREATE VECTOR INDEX community_vector_idx
FOR (c:Community)
ON c.embedding
```

---

## 三、详细设计

### 3.0 存储层抽象设计

#### 3.0.1 设计理念

为了支持向量数据库和图数据库两种存储方式，我们采用**分层抽象**的设计：

```
StoreBase (顶层抽象 - 所有存储的共同接口)
    ├── VDBStoreBase (向量数据库抽象)
    └── GraphStoreBase (图数据库抽象)
```

**设计原则：**

1. **领域模型分离**：向量数据库和图数据库有不同的领域模型，应该有各自的抽象
2. **依赖倒置**：`KnowledgeBase` 依赖 `StoreBase` 抽象，而非具体实现
3. **接口隔离**：图数据库特有的方法（如实体、关系）在 `GraphStoreBase` 中定义
4. **开闭原则**：未来可扩展其他图数据库（TigerGraph、JanusGraph）而不影响现有代码
5. **完全兼容**：现有 `VDBStoreBase` 保持不变，确保向后兼容

#### 3.0.2 StoreBase（顶层抽象）

**职责**：定义所有存储类型的通用接口

**核心接口**：

```python
class StoreBase(ABC):
    """所有存储的基类。
  
    提供所有存储类型（向量数据库、图数据库等）的通用接口。
    """
  
    @abstractmethod
    async def add(self, documents: list[Document], **kwargs: Any) -> None:
        """添加文档到存储。"""
  
    @abstractmethod
    async def delete(self, *args: Any, **kwargs: Any) -> None:
        """从存储中删除文档。"""
  
    @abstractmethod
    async def search(
        self,
        query_embedding: Embedding,
        limit: int,
        score_threshold: float | None = None,
        **kwargs: Any,
    ) -> list[Document]:
        """检索相关文档（基于向量相似度）。"""
  
    def get_client(self) -> Any:
        """获取底层存储客户端。"""
```

**说明**：

- 所有存储都必须实现这三个核心方法：添加、删除、检索
- `search()` 方法要求基于向量相似度，这是所有存储的共同需求
- `get_client()` 允许开发者访问底层存储的完整功能

#### 3.0.3 VDBStoreBase（向量数据库抽象）

**职责**：向量数据库的中间层抽象

**接口设计**：

```python
class VDBStoreBase(StoreBase):
    """向量数据库存储基类。
  
    专门用于向量数据库（Qdrant、Milvus 等）的抽象层。
    继承自 StoreBase，不添加额外的抽象方法。
    """
    pass  # 保持现有接口不变
```

**说明**：

- ✅ 保持现有接口不变，确保向后兼容
- ✅ `QdrantStore`、`MilvusLiteStore` 无需任何修改
- ✅ 现有的 `SimpleKnowledge` 继续正常工作

#### 3.0.4 GraphStoreBase（图数据库抽象）⭐ 新增

**职责**：图数据库的中间层抽象

**核心接口**：

```python
class GraphStoreBase(StoreBase):
    """图数据库存储基类。
  
    专门用于图数据库（Neo4j、TigerGraph 等）的抽象层。
    在 StoreBase 的基础上，增加图特有的操作。
    """
  
    # === 继承基础方法 ===
    # add(), delete(), search() 继承自 StoreBase
  
    # === 图特有的抽象方法 ===
  
    @abstractmethod
    async def add_entities(
        self,
        entities: list[dict],
        document_id: str,
        **kwargs: Any,
    ) -> None:
        """添加实体节点并关联到文档。
  
        Args:
            entities: 实体列表，格式：[{name, type, description}, ...]
            document_id: 关联的文档ID
        """
  
    @abstractmethod
    async def add_relationships(
        self,
        relationships: list[dict],
        **kwargs: Any,
    ) -> None:
        """添加实体间的关系。
  
        Args:
            relationships: 关系列表，格式：[{source, target, type, description}, ...]
        """
  
    @abstractmethod
    async def search_entities(
        self,
        query_embedding: Embedding,
        limit: int,
        **kwargs: Any,
    ) -> list[dict]:
        """基于向量搜索实体。"""
  
    @abstractmethod
    async def search_with_graph(
        self,
        query_embedding: Embedding,
        max_hops: int = 2,
        limit: int = 5,
        **kwargs: Any,
    ) -> list[Document]:
        """基于图遍历的检索。
  
        流程：
        1. 向量检索找相关实体
        2. 图遍历找相关实体（N跳）
        3. 收集提到这些实体的文档
        """
  
    # === 可选的社区检测方法 ===
  
    async def add_communities(
        self,
        communities: list[dict],
        **kwargs: Any,
    ) -> None:
        """添加社区节点（可选功能）。
  
        默认实现抛出 NotImplementedError，子类可选择性实现。
        """
        raise NotImplementedError(
            f"Community detection is not supported in {self.__class__.__name__}."
        )
  
    async def search_communities(
        self,
        query_embedding: Embedding,
        min_level: int = 1,
        limit: int = 10,
        **kwargs: Any,
    ) -> list[dict]:
        """搜索相关社区（可选功能）。"""
        raise NotImplementedError(
            f"Community search is not supported in {self.__class__.__name__}."
        )
```

**说明**：

- ✅ 继承 `StoreBase` 的所有方法
- ✅ 添加图特有的方法：实体、关系、图遍历
- ✅ 社区检测为可选功能，提供默认实现
- ✅ 为未来的图数据库实现提供清晰的接口契约

#### 3.0.5 KnowledgeBase 修改

```python
class KnowledgeBase:
    """知识库抽象基类。"""
  
    embedding_store: StoreBase  # ⭐ 改为 StoreBase，支持所有存储类型
    embedding_model: EmbeddingModelBase
  
    def __init__(
        self,
        embedding_store: StoreBase,  # ⭐ 接受 StoreBase 类型
        embedding_model: EmbeddingModelBase,
    ) -> None:
        """Initialize the knowledge base."""
        self.embedding_store = embedding_store
        self.embedding_model = embedding_model
```

**改动说明**：

- ✅ `embedding_store` 类型从 `VDBStoreBase` 改为 `StoreBase`
- ✅ 现在可以接受向量数据库和图数据库两种存储
- ✅ 完全向后兼容，因为 `VDBStoreBase` 是 `StoreBase` 的子类

---

### 3.1 Neo4jGraphStore（存储层）

**职责**：管理 Neo4j 连接、图结构存储和底层检索

**继承关系**：`Neo4jGraphStore(GraphStoreBase)`

**核心接口**：

```python
class Neo4jGraphStore(GraphStoreBase):
    """Neo4j 图数据库存储实现。
  
    继承自 GraphStoreBase，实现所有抽象方法。
    """
  
    def __init__(
        self,
        uri: str = "bolt://localhost:7687",
        user: str = "neo4j",
        password: str = "password",
        database: str = "neo4j",
        collection_name: str = "knowledge",
        dimensions: int = 1536,
    ) -> None:
        """初始化 Neo4j 连接。
  
        Args:
            uri: Neo4j 连接URI
            user: 用户名
            password: 密码
            database: 数据库名
            collection_name: 集合名称（用作节点标签前缀）
            dimensions: 向量维度
        """
  
    # === 实现 StoreBase 的基础方法 ===
  
    async def add(
        self, 
        documents: list[Document],
        **kwargs: Any,
    ) -> None:
        """添加文档节点（实现 StoreBase.add）"""
  
    async def delete(
        self,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """删除文档（实现 StoreBase.delete）"""
  
    async def search(
        self,
        query_embedding: Embedding,
        limit: int = 5,
        score_threshold: float | None = None,
        **kwargs: Any,
    ) -> list[Document]:
        """向量检索文档（实现 StoreBase.search）"""
  
    def get_client(self) -> Any:
        """获取 Neo4j driver（实现 StoreBase.get_client）"""
  
    # === 实现 GraphStoreBase 的图特有方法 ===
  
    async def add_entities(
        self,
        entities: list[dict],
        document_id: str,
        **kwargs: Any,
    ) -> None:
        """添加实体节点并关联文档（实现 GraphStoreBase.add_entities）
  
        Args:
            entities: 实体列表 [{name, type, description}, ...]
            document_id: 关联的文档ID
        """
  
    async def add_relationships(
        self,
        relationships: list[dict],
        **kwargs: Any,
    ) -> None:
        """添加实体间关系（实现 GraphStoreBase.add_relationships）
  
        Args:
            relationships: 关系列表 [{source, target, type, description}, ...]
        """
  
    async def search_entities(
        self,
        query_embedding: Embedding,
        limit: int = 5,
        **kwargs: Any,
    ) -> list[dict]:
        """向量检索实体（实现 GraphStoreBase.search_entities）"""
  
    async def search_with_graph(
        self,
        query_embedding: Embedding,
        max_hops: int = 2,
        limit: int = 5,
        **kwargs: Any,
    ) -> list[Document]:
        """图遍历增强检索（实现 GraphStoreBase.search_with_graph）
  
        流程：
        1. 向量检索找相关实体
        2. 图遍历找相关实体（N跳）
        3. 收集提到这些实体的文档
        """
  
    # === 可选实现 GraphStoreBase 的社区检测方法 ===
  
    async def add_communities(
        self,
        communities: list[dict],
        **kwargs: Any,
    ) -> None:
        """添加社区节点（可选实现）"""
  
    async def search_communities(
        self,
        query_embedding: Embedding,
        min_level: int = 1,
        limit: int = 10,
        **kwargs: Any,
    ) -> list[dict]:
        """社区级检索（可选实现）"""
  
    # === Neo4j 特有的辅助方法 ===
  
    async def _ensure_indexes(self) -> None:
        """确保向量索引存在（内部方法）"""
  
    async def close(self) -> None:
        """关闭 Neo4j 连接"""
```

**实现要点**：

1. **继承 GraphStoreBase**：实现所有抽象方法，遵循接口契约
2. **异步设计**：所有操作使用 `async/await`
3. **批量操作**：使用 Cypher 的 `UNWIND` 实现批量插入
4. **索引管理**：自动创建和管理 Neo4j 向量索引
5. **连接池**：复用 Neo4j driver 连接，提高性能
6. **错误处理**：统一的异常捕捉和日志记录

---

### 3.1.1 异常处理设计 ⭐

#### RAG 专用异常类

**设计理念**：

为 RAG 模块创建专用异常类，继承自 AgentScope 的 `AgentOrientedExceptionBase`，保持项目异常处理风格的一致性。

**新增异常文件**：`src/agentscope/exception/_rag.py`

**异常层次结构**：

```
AgentOrientedExceptionBase (已有)
    └── RAGExceptionBase (新增 - RAG 模块异常基类)
        ├── DatabaseConnectionError (数据库连接失败)
        ├── GraphQueryError (图查询失败)
        ├── EntityExtractionError (实体提取失败)
        └── IndexNotFoundError (索引不存在)
```

**说明**：

- **DatabaseConnectionError**：当无法连接到 Neo4j 或连接健康检查失败时抛出
- **GraphQueryError**：当 Cypher 查询执行失败时抛出
- **EntityExtractionError**：当 LLM 实体提取失败且配置要求抛出异常时使用
- **IndexNotFoundError**：当必需的向量索引不存在时抛出

**与现有异常的关系**：

- Embedding 生成失败：由 `EmbeddingModelBase` 自行处理（OpenAI SDK 有内置重试）
- LLM 调用失败：由 `ModelWrapperBase` 自行处理（不需要额外重试）
- 仅为 Neo4j 特定的错误创建专用异常

---

### 3.1.2 Neo4j 连接重试机制 ⭐

#### 重试策略

**核心设计**：仅为 Neo4j 数据库连接提供重试机制，不为 Embedding 和 LLM 调用添加重试。

**理由分析**：

1. **OpenAI SDK 已有重试**：`AsyncClient` 默认 `max_retries=2`，自动处理临时性网络错误和速率限制
2. **DashScope SDK 无重试**：如果不稳定，用户应切换到更可靠的服务商，而非在我们的代码中添加重试
3. **Neo4j Driver 无重试**：Neo4j Python Driver 不提供内置重试机制，需要我们自己实现

**重试场景**：

| 操作类型 | 是否需要重试 | 说明 |
|---------|-------------|------|
| Neo4j 连接初始化 | ✅ 需要 | 网络波动、服务重启等临时性问题 |
| Neo4j 写入操作 | ❌ 不需要 | 失败后记录日志，抛出异常让调用者处理 |
| Neo4j 查询操作 | ❌ 不需要 | 失败后记录日志，抛出异常让调用者处理 |
| Embedding 生成 | ❌ 不需要 | OpenAI 已有重试，DashScope 用户自选 |
| LLM 调用 | ❌ 不需要 | OpenAI 已有重试，DashScope 用户自选 |

**实现方案**：

在 `Neo4jGraphStore.__init__()` 方法中，初始化 Neo4j driver 后立即验证连接：

1. **连接验证**：执行简单的健康检查查询（`RETURN 1`）
2. **重试次数**：最多 3 次尝试
3. **退避策略**：指数退避（1秒、2秒、4秒）
4. **错误处理**：3 次失败后抛出 `DatabaseConnectionError`
5. **日志记录**：每次重试都记录 warning 日志，最终失败记录 error 日志

**不使用装饰器的理由**：

- 仅一个地方需要重试（连接初始化），不值得创建通用装饰器
- 简单的循环重试逻辑更清晰、更容易维护
- 避免增加不必要的抽象层

**伪代码示例**：

```
在 Neo4jGraphStore.__init__() 中：
1. 创建 Neo4j driver
2. 调用 _ensure_connection() 验证连接（带重试）
   - 尝试 3 次
   - 每次失败后等待 2^attempt 秒
   - 最终失败抛出 DatabaseConnectionError
3. 记录成功日志
```

**写入和查询操作的错误处理**：

对于 Neo4j 的写入和查询操作，不实现自动重试，而是：

1. 使用 try-except 捕获异常
2. 记录详细的错误日志（包括操作类型、参数等）
3. 抛出 `GraphQueryError` 异常
4. 让调用者（GraphKnowledgeBase 或用户代码）决定是否重试

---

### 3.1.3 Pydantic 数据模型 ⭐

#### 使用 Pydantic 的策略

**核心决策**：渐进式迁移，新代码使用 Pydantic，保留现有 dataclass 以确保兼容性。

**原因分析**：

1. **现有 `Document` 和 `DocMetadata`**：
   - 已在多处使用
   - 继承了 `DashScopeResponse.DictMixin`，与 DashScope SDK 集成
   - 直接替换会破坏现有代码

2. **用户规则要求**：
   - 明确指出使用 Pydantic 优于 dataclass
   - Pydantic 提供更好的数据验证和性能

**实施策略**：

**保持不变**：
- `Document` 类：继续使用 dataclass
- `DocMetadata` 类：继续使用 dataclass

**新增 Pydantic 模型**：
为图数据库特有的数据结构创建 Pydantic 模型。

**新建文件**：`src/agentscope/rag/_graph_types.py`

**Pydantic 模型设计**：

```
Entity (Pydantic BaseModel)
    - name: str (必需，最小长度1)
    - type: Literal["PERSON", "ORG", "LOCATION", "PRODUCT", "EVENT"]
    - description: str (默认空字符串)
    - embedding: list[float] | None (可选)

Relationship (Pydantic BaseModel)
    - source: str (必需，最小长度1)
    - target: str (必需，最小长度1)
    - type: str (必需)
    - description: str (默认空字符串)
    - strength: float (0.0-1.0，默认1.0)

Community (Pydantic BaseModel)
    - id: str (必需)
    - level: int (>=0)
    - title: str (必需)
    - summary: str (必需)
    - rating: float (0.0-1.0，默认0.0)
    - entity_count: int (>=0)
    - entity_ids: list[str] (默认空列表)
```

**配置选项**：

- `extra="forbid"`：禁止额外字段，确保数据结构严格
- `validate_assignment=True`：赋值时自动验证
- `arbitrary_types_allowed=True`：允许非 Pydantic 类型（如需要）

**使用方式**：

1. **在 GraphKnowledgeBase 中**：
   - `_extract_entities()` 返回 `list[Entity]` 而非 `list[dict]`
   - LLM 返回的原始数据通过 `Entity(**raw_data)` 自动验证
   - 验证失败的数据记录 warning 日志并跳过

2. **与存储层交互**：
   - 调用 `Neo4jGraphStore.add_entities()` 时，将 Pydantic 模型转换为字典
   - 使用 `entity.model_dump(exclude_none=True)` 方法

3. **向后兼容**：
   - Pydantic 模型提供 `to_dict()` 方法
   - 可以轻松转换为普通字典与现有代码交互

**优势**：

1. **自动验证**：LLM 返回的数据自动验证格式和类型
2. **类型安全**：IDE 可以提供更好的自动补全和类型检查
3. **清晰的数据契约**：字段约束（如最小值、最大值）明确定义
4. **性能优化**：Pydantic V2 提供了优秀的性能
5. **兼容性**：不影响现有的 `Document` 和 `DocMetadata`

**TypedDict 类型定义**：

除了 Pydantic 模型，还提供 `TypedDict` 用于类型注解：

```
在 _graph_types.py 中定义：
- EntityDict (TypedDict)：用于类型注解
- RelationshipDict (TypedDict)：用于类型注解
- CommunityDict (TypedDict)：用于类型注解
- SearchMode (Literal)：检索模式类型
```

这样在 `GraphStoreBase` 的接口定义中可以使用 `list[EntityDict]` 作为类型注解，提供更好的 IDE 支持。

---

### 3.2 GraphKnowledgeBase（业务层）

**职责**：协调实体提取、关系构建、社区检测和检索策略

**继承关系**：`GraphKnowledgeBase(KnowledgeBase)`

**核心接口**：

```python
class GraphKnowledgeBase(KnowledgeBase):
    """基于图数据库的知识库实现。
  
    使用 GraphStoreBase（如 Neo4jGraphStore）作为存储后端，
    提供实体提取、关系构建、社区检测和多种检索策略。
    """
  
    def __init__(
        self,
        graph_store: GraphStoreBase,  # ⭐ 接受 GraphStoreBase 类型
        embedding_model: EmbeddingModelBase,
        llm_model: ModelWrapperBase | None = None,
  
        # 实体提取配置（同步处理）
        enable_entity_extraction: bool = True,
        entity_extraction_config: dict | None = None,
  
        # 关系提取配置（同步处理）
        enable_relationship_extraction: bool = True,
  
        # 社区检测配置（异步批量处理，用户主动调用）⭐
        enable_community_detection: bool = False,  # 启用后首次自动执行一次，后续手动
        community_algorithm: Literal["leiden", "louvain"] = "leiden",
    ) -> None:
        """初始化图知识库。
  
        Args:
            graph_store: 图数据库存储（GraphStoreBase 类型）
            embedding_model: 嵌入模型
            llm_model: 大语言模型（用于实体/关系提取和社区摘要）
            enable_entity_extraction: 是否启用实体提取（每次文档添加都执行）
            entity_extraction_config: 实体提取配置
            enable_relationship_extraction: 是否启用关系提取（每次文档添加都执行）
            enable_community_detection: 是否启用社区检测（启用后首次自动执行，后续手动调用）
            community_algorithm: 社区检测算法（leiden 或 louvain）
        """
        # 调用父类构造函数
        super().__init__(
            embedding_store=graph_store,  # ⭐ graph_store 是 StoreBase 的子类
            embedding_model=embedding_model,
        )
  
        self.graph_store = graph_store  # 保留图存储的引用
        self.llm_model = llm_model
        self.enable_entity_extraction = enable_entity_extraction
        # ... 其他配置
  
    # === 核心方法（实现抽象接口）===
  
    async def add_documents(
        self,
        documents: list[Document],
        **kwargs: Any,
    ) -> None:
        """添加文档到图知识库
  
        流程：
        1. 生成文档 embedding（同步）
        2. 存储文档节点（同步）
        3. [可选] 提取实体（同步，如果 enable_entity_extraction=True）
        4. [可选] 提取关系（同步，如果 enable_relationship_extraction=True）
        5. [可选] 首次自动触发社区检测（异步后台，不阻塞）
        
        说明：
            - 实体和关系提取在每次添加文档时同步执行
            - 社区检测：仅当 enable_community_detection=True 时，
              首次调用 add_documents() 会自动触发后台社区检测
            - 后续添加文档不会自动触发，需要用户手动调用 detect_communities()
        """
  
    async def retrieve(
        self,
        query: str,
        limit: int = 5,
        score_threshold: float | None = None,
        search_mode: Literal["vector", "graph", "hybrid", "global"] = "hybrid",
        **kwargs: Any,
    ) -> list[Document]:
        """检索相关文档
  
        Args:
            search_mode:
                - "vector": 纯向量检索
                - "graph": 基于图遍历
                - "hybrid": 向量+图混合（推荐）
                - "global": 社区级检索
        """
```

---

#### 3.2.0 Embedding 生成策略（设计决策） ⭐

**核心原则**：内容嵌入 + 图遍历检索

##### 设计理念

本方案采用**关注点分离（Separation of Concerns）**的设计哲学：

```
┌─────────────────────────────────────────────────────────┐
│  Embedding 阶段：纯语义表示                               │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━        │
│  • Document: embed(content)                            │
│  • Entity:   embed(name + type + description)         │
│  • Community: embed(summary)                           │
│                                                         │
│  ✅ 只关注内容本身的语义                                  │
│  ✅ 不包含关系信息                                       │
│  ✅ 保持向量空间的纯净性和稳定性                          │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  检索阶段：利用图结构                                      │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━        │
│  1. 向量检索：找到语义相关的节点                          │
│  2. 图遍历：利用关系扩展相关节点                          │
│  3. 文档收集：获取提到这些节点的文档                       │
│                                                         │
│  ✅ 关系信息在此阶段充分利用                              │
│  ✅ 图遍历反映最新的关系结构                              │
│  ✅ 无需重新生成 embedding                               │
└─────────────────────────────────────────────────────────┘
```

##### 为什么不在 Embedding 中包含关系信息？

| 设计考量 | 内容嵌入方案<br>（AgentScope） | 关系嵌入方案<br>（GraphRAG） |
|---------|---------------------------|------------------------|
| **语义纯净性** | ✅ 向量只反映内容语义 | ⚠️ 混合内容和结构信息 |
| **关系变化影响** | ✅ 新增关系无影响<br>图遍历立即可用 | ❌ 需要重新生成 embedding |
| **维护成本** | ✅ 低（embedding 生成一次） | ⚠️ 高（需定期重建） |
| **向量稳定性** | ✅ 高（内容不变则不变） | ⚠️ 低（关系变化导致变化） |
| **适用场景** | ✅ 在线系统、动态图谱 | ✅ 离线分析、静态文档 |
| **Agent 集成** | ✅ 实时交互、频繁更新 | ⚠️ 批量处理、定期索引 |

##### 设计优势

**1. 关系动态性**
- 新增或删除关系时，无需更新 embedding
- 图遍历立即反映最新的图结构
- 适合动态变化的知识图谱

**2. 成本效益**
- Document/Entity/Community 的 embedding 只需生成一次
- 避免因关系变化导致的频繁 API 调用
- 降低系统维护复杂度

**3. 语义一致性**
- 向量空间保持稳定，不受关系变化影响
- 相似实体的向量始终接近
- 向量检索结果更可预测

**4. 架构清晰**
- 向量检索：专注语义相似度匹配
- 图遍历：专注结构化关系查询
- 职责分离，易于理解和优化

##### 如何利用关系信息？

虽然 embedding 不包含关系，但通过**检索模式**充分利用关系信息：

**模式分层设计**：

```
vector 模式（最快）
  └─> 纯向量检索，只用 embedding
  
graph 模式（关系优先）
  └─> 向量找种子实体 → 图遍历 N 跳 → 收集文档
  
hybrid 模式（推荐）
  └─> 并行执行 vector + graph → 合并去重 → 重排序
  
global 模式（全局视角）
  └─> 社区摘要检索 → 提取代表性文档
```

**检索流程示例**：

```
查询："OpenAI 的合作伙伴有哪些？"

步骤 1: 向量检索（基于纯内容 embedding）
  → 找到实体：[OpenAI, Microsoft, Anthropic, ...]
  → 原因：这些实体的描述与查询语义相关

步骤 2: 图遍历（利用关系结构）
  MATCH (openai:Entity {name: "OpenAI"})
        -[:PARTNER_OF|COLLABORATES_WITH]-(partner)
  → 找到合作伙伴：[Microsoft, ...]

步骤 3: 文档收集
  MATCH (partner)-[:MENTIONED_IN]->(doc:Document)
  → 返回相关文档

结果：✅ 准确回答问题，无需在 embedding 中编码关系
```

##### 与 GraphRAG 的对比

**GraphRAG 方案**（关系嵌入）：
```
优势：
• 向量本身包含关系上下文
• 向量匹配可能更精确

劣势：
• 关系变化需要重新生成 embedding
• 适合静态文档集合的离线处理
• 定期全量重建索引（每周/月）
• 维护成本高
```

**AgentScope 方案**（内容嵌入）：
```
优势：
• 向量空间稳定，语义纯净
• 关系变化无影响，图遍历立即生效
• 适合动态知识图谱的在线系统
• 维护成本低

权衡：
• 向量匹配可能略逊于关系嵌入
• 但通过图遍历弥补，整体效果相当或更优
```

**系统定位差异**：

| 维度 | AgentScope | GraphRAG |
|-----|-----------|----------|
| **场景** | Agent 在线交互 | 文档离线分析 |
| **图谱类型** | 动态知识图谱 | 静态文档图谱 |
| **更新频率** | 实时/频繁 | 批量/定期 |
| **关系变化** | 常见 | 罕见 |
| **最佳方案** | 内容嵌入 + 图遍历 | 关系嵌入 |

##### 何时需要更新 Embedding？

**需要更新的情况**：
- ✅ Document 内容修改
- ✅ Entity 描述修改
- ✅ Entity 类型变化
- ✅ Community 摘要重新生成

**不需要更新的情况**：
- ❌ 新增/删除关系
- ❌ 关系描述修改
- ❌ 关系强度变化
- ❌ 邻居节点变化

这正是本设计的核心优势：**关系层面的变化不影响向量表示**。

---

**关键方法**：

#### 3.2.1 实体提取

```python
async def _extract_entities(
    self, 
    documents: list[Document]
) -> list[dict]:
    """提取实体（支持一次性或多轮 gleanings）
  
    配置项：
        max_entities_per_chunk: 每块最多提取实体数
        enable_gleanings: 是否重复检查
        gleanings_rounds: 重复检查轮数
  
    流程：
        1. 第一轮提取（_extract_entities_single_pass）
        2. [可选] Gleanings 轮次（_gleanings_pass）
        3. 实体解析（_resolve_entities）
    """
```

**Prompt 设计（实体提取）**：

```
Extract key entities from the following text.

Text: {text}

Return a JSON list of entities:
[
  {
    "name": "entity name",
    "type": "PERSON|ORG|LOCATION|PRODUCT|EVENT|...",
    "description": "brief description"
  },
  ...
]

Focus on the most important entities mentioned.
```

**Gleanings Prompt**：

```
You already extracted these entities: {existing_names}

Review the text again and find any entities you might have missed:

Text: {text}

Return ONLY new entities (not in the list above) in JSON format.
```

#### 3.2.2 关系提取

```python
async def _extract_relationships(
    self,
    documents: list[Document]
) -> list[dict]:
    """提取实体间关系
  
    返回格式：
    [
        {
            "source": "entity1",
            "target": "entity2",
            "type": "relationship_type",
            "description": "description",
            "strength": 0.8
        },
        ...
    ]
    """
```

**Prompt 设计（关系提取）**：

```
Extract relationships between entities in the text.

Text: {text}

Return a JSON list of relationships:
[
  {
    "source": "entity1 name",
    "target": "entity2 name",
    "type": "relationship type (e.g., WORKS_FOR, LOCATED_IN, CREATED)",
    "description": "brief description of the relationship"
  },
  ...
]

Focus on clear and important relationships.
```

#### 3.2.3 社区检测（异步批量处理）⭐

**设计理念**：

社区检测采用**用户主动调用**的简化设计：
- ✅ 提供独立的 `detect_communities()` 方法
- ✅ 用户完全控制执行时机
- ✅ 使用 `asyncio.create_task` 实现后台执行
- ✅ `enable_community_detection=True` 时首次自动执行一次（默认 False）
- ✅ 不引入复杂的自动触发机制（无阈值、定期等）

**为什么采用这种设计？**

```
社区检测特性：
- 计算粒度：全图级别（非文档级别）
- 计算复杂度：O(n²) ~ O(n³)
- 执行时间：分钟级~小时级（非秒级）
- 适合实时处理：❌ 否
- 适合批量处理：✅ 是

结论：应由用户主动决定何时执行，而非系统自动触发
```

**核心方法**：

```python
async def detect_communities(
    self,
    algorithm: Literal["leiden", "louvain"] | None = None,
    **kwargs: Any,
) -> dict:
    """手动触发社区检测（用户主动调用）
  
    这是一个独立的方法，用户可以在任何时候调用：
    - 添加大批量文档后
    - 定期维护时
    - 觉得图结构变化较大时
  
    Args:
        algorithm: 社区检测算法（覆盖默认配置）
        **kwargs: 其他参数（如 max_level）
  
    Returns:
        检测结果统计信息
  
    说明：
        - 这是一个异步方法，会阻塞直到完成
        - 如果不想阻塞，用户可以用 asyncio.create_task 包装
  
    流程：
        1. 运行 Neo4j GDS 社区检测算法
        2. 批量生成社区摘要（并发调用 LLM）
        3. 批量生成社区 embedding
        4. 存储到数据库
    """
```

**使用模式**：

```python
# 模式 A：启用社区检测（首次自动执行）
knowledge = GraphKnowledgeBase(
    ...,
    enable_community_detection=True,  # 启用社区检测
)
await knowledge.add_documents(docs)  # 首次自动触发后台社区检测

# 后续手动调用（同步执行，阻塞等待）
await knowledge.detect_communities()

# 模式 B：手动调用（异步后台执行，不阻塞）
task = asyncio.create_task(knowledge.detect_communities())
# ... 继续其他工作 ...
result = await task  # 需要时等待

# 模式 C：不启用社区检测（仅使用实体和关系）
knowledge = GraphKnowledgeBase(
    ...,
    enable_community_detection=False,  # 不启用社区检测
)
# 不会自动执行，也不能手动调用 detect_communities()
```

**社区摘要 Prompt**：

```
Summarize the following group of entities into a cohesive theme:

Entities: {entity_names}

Provide a brief summary (2-3 sentences) describing:
1. What these entities have in common
2. The main theme or topic they represent
3. Their significance in the knowledge base
```

**批量处理优化**：

```python
async def _batch_generate_summaries(
    self,
    communities: list[Community],
) -> list[Community]:
    """批量生成社区摘要（并发处理）
    
    优化策略：
    - 使用 asyncio.gather 并发调用 LLM
    - 限制并发数量避免速率限制（semaphore）
    - 失败的社区使用简单规则生成摘要
    """
    
async def _batch_embed_communities(
    self,
    communities: list[Community],
) -> list[Community]:
    """批量生成社区 embedding
    
    优化策略：
    - 一次性调用 embedding API（批量处理）
    - 利用 embedding 模型的批处理能力
    """
```

**设计优势总结**：

| 维度 | 复杂自动触发方案 | 简化用户调用方案 ✅ |
|-----|----------------|-------------------|
| **配置复杂度** | 高（阈值、周期、触发模式等）| 低（1 个开关 + 1 个算法）|
| **代码量** | ~300 行 | ~50 行 |
| **理解成本** | 高（需理解触发机制）| 低（就是个函数调用）|
| **灵活性** | 固定的触发策略 | 用户完全控制 |
| **维护成本** | 高（状态机、调度器）| 低（无复杂状态）|
| **调试难度** | 高（异步状态追踪）| 低（显式调用）|
| **职责边界** | 模糊（系统决策执行时机）| 清晰（系统提供能力，用户决策）|

**设计决策**：采用简化方案，**将"何时执行"的决策权交给用户**。
- `enable_community_detection=True`：启用功能，首次自动执行
- 后续由用户主动调用 `detect_communities()` 方法

---

#### 3.2.4 检索策略

**向量检索**（vector）：

```python
async def _vector_search(
    self,
    query_embedding: Embedding,
    limit: int,
    score_threshold: float | None,
) -> list[Document]:
    """纯向量检索（最快，基线）
  
    流程：
        1. 向量相似度搜索
        2. 过滤阈值
        3. 返回 Document 列表
    """
```

**图遍历检索**（graph）：

```python
async def _graph_search(
    self,
    query_embedding: Embedding,
    limit: int,
    score_threshold: float | None,
    max_hops: int = 2,
) -> list[Document]:
    """基于图遍历的检索
  
    流程：
        1. 向量检索找相关实体
        2. 图遍历找相关实体（N跳）
        3. 收集提到这些实体的文档
        4. 按相关性排序
    """
```

**混合检索**（hybrid，推荐）：

```python
async def _hybrid_search(
    self,
    query_embedding: Embedding,
    limit: int,
    score_threshold: float | None,
    **kwargs: Any,
) -> list[Document]:
    """混合检索（向量 + 图）
  
    流程：
        1. 并行执行向量检索和图检索
        2. 合并结果并去重
        3. 按分数重新排序
    """
```

**全局检索**（global）：

```python
async def _global_search(
    self,
    query_embedding: Embedding,
    limit: int,
    **kwargs: Any,
) -> list[Document]:
    """全局检索（基于社区）
  
    流程：
        1. 检索相关社区
        2. 从社区中提取代表性文档
        3. 返回结果
  
    适用于：
        - 总结性问题
        - 宏观理解
        - 主题发现
    """
```

---

## 四、兼容性保证

### 4.1 存储层架构兼容性 ⭐

✅ **新增 StoreBase 和 GraphStoreBase**：

**修改内容**：

```python
# _store_base.py 修改
class StoreBase(ABC):           # 新增：顶层抽象
    """所有存储的基类"""

class VDBStoreBase(StoreBase):  # 修改：继承 StoreBase
    """向量数据库存储基类"""
    pass  # 保持现有接口不变

class GraphStoreBase(StoreBase): # 新增：图数据库抽象
    """图数据库存储基类"""
    # 添加图特有的方法
```

**兼容性保证**：

- ✅ `VDBStoreBase` 保持所有现有方法不变
- ✅ `QdrantStore`、`MilvusLiteStore` **无需任何修改**
- ✅ 所有继承 `VDBStoreBase` 的类自动继承 `StoreBase`
- ✅ 现有代码可以无缝运行

**KnowledgeBase 修改**：

```python
# _knowledge_base.py 修改
class KnowledgeBase:
    embedding_store: StoreBase  # 从 VDBStoreBase 改为 StoreBase
```

**为什么向后兼容**：

- `VDBStoreBase` 是 `StoreBase` 的子类
- 里氏替换原则：子类可以替换父类
- 现有代码传入 `QdrantStore` 等仍然有效

### 4.2 与现有代码兼容

✅ **接口兼容**：

- 实现 `KnowledgeBase` 抽象接口
- `add_documents()` 签名一致
- `retrieve()` 签名一致
- 支持 `retrieve_knowledge()` 工具函数

✅ **数据结构兼容**：

- 使用相同的 `Document` 类
- 使用相同的 `DocMetadata` 类
- 使用相同的 `Embedding` 类型

✅ **模型兼容**：

- 兼容所有 `EmbeddingModelBase` 实现
- 兼容所有 `ModelWrapperBase` 实现
- 支持 DashScope、OpenAI 等

✅ **Agent 集成兼容**：

- 可作为工具函数使用
- 可直接传入 `knowledge` 参数
- 与 `ReActAgent` 无缝集成

### 4.3 代码风格一致性

✅ **命名规范**：

- 类名：PascalCase（`GraphKnowledgeBase`）
- 方法名：snake_case（`add_documents`）
- 私有方法：下划线前缀（`_extract_entities`）

✅ **类型注解**：

- 所有公开方法都有类型注解
- 使用 `from typing import` 导入类型
- 使用 `| None` 而非 `Optional`

✅ **Docstrings**：

- 所有类和公开方法都有文档字符串
- 使用 Google style docstring
- 包含 Args、Returns、Raises

✅ **异步设计**：

- 所有 I/O 操作使用 `async/await`
- 保持与 AgentScope 一致的异步风格

✅ **错误处理**：

- 使用 `logger` 记录错误
- 抛出适当的异常
- 提供有用的错误消息

### 4.4 迁移指南

**从 SimpleKnowledge 迁移到 GraphKnowledgeBase**：

```python
# 原代码
from agentscope.rag import SimpleKnowledge, QdrantStore
knowledge = SimpleKnowledge(
    embedding_store=QdrantStore(...),
    embedding_model=DashScopeTextEmbedding(...),
)

# 新代码（最小改动）
from agentscope.rag import GraphKnowledgeBase, Neo4jGraphStore
knowledge = GraphKnowledgeBase(
    graph_store=Neo4jGraphStore(...),      # 只改这里
    embedding_model=DashScopeTextEmbedding(...),
    llm_model=None,                        # 关闭图功能
    enable_entity_extraction=False,
    enable_relationship_extraction=False,
)

# 其他代码完全不变
await knowledge.add_documents(documents)
results = await knowledge.retrieve(query)
```

---

## 五、参考资源

- [AgentScope 官方文档](https://doc.agentscope.io/)
- [Neo4j 官方文档](https://neo4j.com/docs/)
- [Neo4j Python Driver](https://neo4j.com/docs/python-manual/current/)
- [Neo4j Graph Data Science](https://neo4j.com/docs/graph-data-science/current/)
- [GraphRAG 论文](https://arxiv.org/abs/2404.16130)

---

**文档版本**: v1.0
**文档类型**: 设计与架构
**最后更新**: 2025-10-30
**维护者**: AgentScope Team

