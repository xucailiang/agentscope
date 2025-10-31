# Neo4j GraphKnowledgeBase 实施步骤计划

## 📋 文档概要

**版本**: v1.0  
**创建日期**: 2025-10-31  
**目标**: 提供清晰的实施步骤和关键要点，指导开发团队高效完成功能实现

---

## 🎯 核心设计理念

### 1. 架构原则
- **分层抽象**: StoreBase → VDBStoreBase/GraphStoreBase
- **职责分离**: Embedding阶段（纯语义） + 检索阶段（利用关系）
- **兼容优先**: 不破坏现有架构，新建GraphKnowledgeBase
- **渐进配置**: 默认轻量，可选增强（社区检测默认关闭）

### 2. 关键决策
| 决策点 | 方案 | 原因 |
|--------|------|------|
| Embedding策略 | 内容嵌入（不含关系） | 关系变化无需更新embedding，适合动态图谱 |
| 社区检测 | 用户主动调用 | 避免复杂自动触发机制，简化设计 |
| 数据模型 | 新功能用Pydantic，保留现有dataclass | 渐进式迁移，确保兼容性 |
| 重试机制 | 仅Neo4j连接重试 | OpenAI SDK已有重试，避免重复 |

---

## 📅 实施步骤（3周计划）

### 第一周：基础框架 🏗️

#### Day 1: 异常和数据模型（必须先行）

**新建文件**：
1. `src/agentscope/exception/_rag.py`
   - 定义RAG专用异常：`RAGExceptionBase`、`DatabaseConnectionError`、`GraphQueryError`等
   - 继承自`AgentOrientedExceptionBase`

2. `src/agentscope/rag/_graph_types.py`
   - 使用Pydantic定义数据模型：`Entity`、`Relationship`、`Community`
   - 定义TypedDict：`EntityDict`、`RelationshipDict`、`CommunityDict`
   - 定义Literal类型：`SearchMode`

**修改文件**：
- `src/agentscope/exception/__init__.py`：导出RAG异常

**验证点**：
- ✅ 异常类可以正常导入和使用
- ✅ Pydantic模型验证功能正常

---

#### Day 2-3: 存储层抽象重构

**修改文件**: `src/agentscope/rag/_store/_store_base.py`

**实施步骤**：
1. **新增StoreBase抽象基类**
   - 定义通用接口：`add()`、`delete()`、`search()`、`get_client()`
   
2. **修改VDBStoreBase**
   - 改为继承`StoreBase`
   - 保持现有接口不变（确保QdrantStore、MilvusLiteStore无需修改）

3. **新增GraphStoreBase抽象基类**
   - 继承`StoreBase`
   - 新增图特有方法：
     - `add_entities()` - 实体管理
     - `add_relationships()` - 关系管理
     - `search_entities()` - 实体检索
     - `search_with_graph()` - 图遍历检索
   - 可选方法：
     - `add_communities()` - 社区管理
     - `search_communities()` - 社区检索

4. **修改KnowledgeBase基类**
   - `embedding_store`类型改为`StoreBase`（原为`VDBStoreBase`）

**验证点**：
- ✅ 运行现有单元测试确保QdrantStore、MilvusLiteStore仍正常工作
- ✅ 类型检查通过

---

#### Day 4: Neo4j连接和基础功能

**新建文件**: `src/agentscope/rag/_store/_neo4j_graph_store.py`

**实施步骤**：
1. **实现Neo4jGraphStore类**
   - 初始化：接收uri、user、password等参数
   - 连接管理：实现`_ensure_connection()`带重试机制（3次，指数退避）
   - 索引管理：实现`_ensure_indexes()`自动创建向量索引

2. **实现StoreBase基础方法**
   - `add()` - 添加文档节点（含embedding）
   - `search()` - 纯向量检索文档
   - `delete()` - 删除文档
   - `get_client()` - 返回Neo4j driver

3. **错误处理**
   - 连接失败抛出`DatabaseConnectionError`
   - 查询失败抛出`GraphQueryError`

**关键要点**：
- 使用异步Neo4j driver（`AsyncGraphDatabase`）
- 批量操作使用`UNWIND`优化性能
- 记录详细日志（连接、查询、错误）

**验证点**：
- ✅ 能成功连接Neo4j
- ✅ 向量索引自动创建
- ✅ 文档节点增删查正常

---

#### Day 5: GraphKnowledgeBase骨架

**新建文件**: `src/agentscope/rag/_graph_knowledge.py`

**实施步骤**：
1. **类结构**
   - 继承`KnowledgeBase`
   - 接收`GraphStoreBase`作为存储

2. **实现基础功能（纯向量模式）**
   - `add_documents()` - 仅生成embedding并存储（不提取实体）
   - `retrieve()` - 支持`search_mode="vector"`
   - `_embed_documents()` - 批量生成文档embedding
   - `_embed_query()` - 生成查询embedding

3. **配置管理**
   - `enable_entity_extraction=False`（暂时关闭）
   - `enable_relationship_extraction=False`（暂时关闭）
   - `enable_community_detection=False`（默认关闭）

**验证点**：
- ✅ 可作为SimpleKnowledge的替代品使用
- ✅ 纯向量检索功能正常

**里程碑1**: ✅ 基础向量检索功能完成

---

### 第二周：实体和关系 🔗

#### Day 1-2: 实体提取

**实施步骤**：
1. **实现实体提取逻辑**（GraphKnowledgeBase）
   - `_extract_entities()` - 主入口，返回`list[Entity]`（Pydantic模型）
   - `_extract_entities_single_pass()` - 单轮提取
   - `_gleanings_pass()` - 可选的多轮检查
   - `_resolve_entities()` - 去重和合并

2. **实现存储端支持**（Neo4jGraphStore）
   - `add_entities()` - 批量添加实体节点
   - 创建`Document-[:MENTIONS]->Entity`关系

3. **LLM Prompt设计**
   - 实体提取Prompt：指定输出JSON格式`{name, type, description}`
   - Gleanings Prompt：基于已提取实体进行补充

**关键要点**：
- LLM返回数据用Pydantic自动验证（`Entity(**data)`）
- 验证失败记录warning日志并跳过
- 只嵌入实体内容（name + type + description），不含关系

**验证点**：
- ✅ 实体提取准确率测试
- ✅ Pydantic验证正常工作
- ✅ 实体节点正确存储到Neo4j

---

#### Day 3-4: 关系提取和图检索

**实施步骤**：
1. **实现关系提取**（GraphKnowledgeBase）
   - `_extract_relationships()` - 返回`list[Relationship]`（Pydantic模型）
   - LLM Prompt：提取`{source, target, type, description}`

2. **实现图存储端支持**（Neo4jGraphStore）
   - `add_relationships()` - 批量添加关系
   - `search_entities()` - 向量检索实体
   - `search_with_graph()` - 图遍历检索
     - 步骤1：向量检索种子实体
     - 步骤2：图遍历N跳扩展
     - 步骤3：收集关联文档

3. **实现检索模式**（GraphKnowledgeBase）
   - `_graph_search()` - 图遍历检索
   - `_hybrid_search()` - 混合检索（并行执行vector + graph）

**关键要点**：
- 关系不嵌入向量（只存储在图结构中）
- 图遍历使用Cypher的模式匹配
- 混合检索需合并去重和重排序

**验证点**：
- ✅ 关系正确提取和存储
- ✅ 图遍历检索返回相关文档
- ✅ 混合检索效果优于单一模式

---

#### Day 5: 测试和优化

**实施内容**：
1. **性能测试**
   - 索引吞吐量（文档/秒）
   - 检索延迟（P50/P95/P99）

2. **质量测试**
   - 实体提取准确率
   - 关系提取准确率
   - 检索Precision@K和Recall@K

3. **成本分析**
   - LLM调用次数统计
   - Embedding API调用次数统计

4. **Prompt优化**
   - 根据测试结果调整Prompt
   - 平衡准确率和成本

**里程碑2**: ✅ 实体和关系功能完成，图检索可用

---

### 第三周：社区检测和完善 🌐

#### Day 1-2: 社区检测核心（简化设计）

**实施步骤**：
1. **Neo4j GDS集成**（Neo4jGraphStore）
   - `add_communities()` - 存储社区节点
   - `search_communities()` - 检索社区
   - 实现Leiden和Louvain算法调用

2. **社区检测主流程**（GraphKnowledgeBase）
   - `detect_communities()` - 用户主动调用的独立方法
     - 步骤1：运行GDS算法
     - 步骤2：批量生成社区摘要（并发LLM调用）
     - 步骤3：批量生成社区embedding
     - 步骤4：存储到数据库

3. **首次自动触发逻辑**
   - `enable_community_detection=True`时，首次`add_documents()`后台触发
   - 使用`asyncio.create_task()`后台执行，不阻塞主流程

**关键要点**：
- 社区摘要只嵌入summary内容（不含实体列表）
- 使用`asyncio.gather()`批量并发生成摘要
- 限制并发数避免速率限制（Semaphore）
- 失败的社区使用简单规则生成摘要

**验证点**：
- ✅ 社区检测算法正常运行
- ✅ 首次自动触发正常
- ✅ 手动调用`detect_communities()`正常

---

#### Day 3: 全局搜索

**实施步骤**：
1. **实现全局检索**（GraphKnowledgeBase）
   - `_global_search()` - 基于社区的全局检索
     - 步骤1：向量检索相关社区
     - 步骤2：从社区提取代表性实体
     - 步骤3：收集关联文档

2. **集成到retrieve方法**
   - 支持`search_mode="global"`

**适用场景**：
- 总结性问题
- 主题发现
- 宏观理解

**验证点**：
- ✅ 全局检索返回主题相关文档
- ✅ 效果优于纯向量检索

---

#### Day 4: 文档和示例

**实施内容**：
1. **完善API文档**
   - 所有公开方法的docstring
   - 参数说明和返回值
   - 使用示例

2. **创建使用示例**
   - 基础使用（纯向量）
   - 完整使用（实体+关系）
   - 高级使用（社区检测）
   - ReActAgent集成示例

3. **更新README**
   - 功能介绍
   - 安装指南
   - 快速开始

**关键文档**：
- 配置说明（三种推荐配置组合）
- 检索模式对比表
- 常见问题FAQ

---

#### Day 5: 最终测试和发布

**实施内容**：
1. **端到端测试**
   - 完整索引流程
   - 所有检索模式
   - Agent集成
   - 异常场景

2. **性能基准测试**
   - 与SimpleKnowledge对比
   - 不同配置组合的性能对比

3. **代码审查**
   - 代码风格一致性
   - 类型注解完整性
   - 错误处理健壮性

4. **发布准备**
   - 更新`pyproject.toml`依赖
   - 更新`__init__.py`导出
   - 准备发布说明

**里程碑3**: ✅ 功能完整，生产就绪

---


## 🔑 关键实施要点

### 1. 存储层设计
```
StoreBase (顶层抽象)
├── VDBStoreBase (向量数据库) - 保持不变
│   ├── QdrantStore - 无需修改
│   └── MilvusLiteStore - 无需修改
└── GraphStoreBase (图数据库) - 新增
    └── Neo4jGraphStore - 新增
```

**要点**：
- VDBStoreBase只改继承关系，接口完全不变
- GraphStoreBase定义图特有方法
- KnowledgeBase的`embedding_store`改为StoreBase类型

---

### 2. Embedding策略（核心决策）

**内容嵌入，不含关系**：
- Document: `embed(content)`
- Entity: `embed(name + type + description)`
- Community: `embed(summary)`

**原因**：
- 关系变化无需更新embedding
- 向量空间稳定
- 适合动态图谱

**关系利用**：
- 通过图遍历在检索阶段利用
- `search_with_graph()`实现多跳查询

---

### 3. 社区检测策略（简化设计）

**设计原则**：用户主动调用，不自动触发

**配置**：
- `enable_community_detection=False`（默认）- 不启用
- `enable_community_detection=True` - 启用，首次自动执行

**使用方式**：
- 同步执行：`await knowledge.detect_communities()`
- 异步后台：`asyncio.create_task(knowledge.detect_communities())`

**避免复杂性**：
- 不设置阈值触发
- 不设置定期触发
- 不引入状态机

---

### 4. 异常处理

**专用异常类**（继承AgentOrientedExceptionBase）：
- `RAGExceptionBase` - 基类
- `DatabaseConnectionError` - 连接失败
- `GraphQueryError` - 查询失败
- `EntityExtractionError` - 实体提取失败
- `IndexNotFoundError` - 索引不存在

**重试策略**：
- ✅ Neo4j连接初始化：3次重试，指数退避
- ❌ 写入/查询操作：不重试，记录日志并抛出异常
- ❌ Embedding生成：依赖SDK自带重试（OpenAI有）
- ❌ LLM调用：依赖SDK自带重试

---

### 5. 数据模型

**使用Pydantic（新代码）**：
- `Entity` - Pydantic BaseModel
- `Relationship` - Pydantic BaseModel
- `Community` - Pydantic BaseModel

**保留dataclass（现有代码）**：
- `Document` - 保持不变
- `DocMetadata` - 保持不变

**优势**：
- 自动验证LLM返回数据
- 类型安全
- 渐进式迁移

---

### 6. Neo4j数据模型

**节点类型**：
```
(:Document) - 文档节点（必需）
  - id, content, embedding, doc_id, chunk_id
  
(:Entity) - 实体节点（可选）
  - name, type, description, embedding
  
(:Community) - 社区节点（可选）
  - id, level, title, summary, embedding
```

**关系类型**：
```
(:Document)-[:MENTIONS]->(:Entity)
(:Entity)-[:RELATED_TO]->(:Entity)
(:Entity)-[:BELONGS_TO]->(:Community)
(:Community)-[:PARENT_OF]->(:Community)
```

**索引**：
```
document_vector_idx - 文档向量索引（必需）
entity_vector_idx - 实体向量索引（可选）
community_vector_idx - 社区向量索引（可选）
```

---

### 7. 检索模式设计

| 模式 | 流程 | 适用场景 | 速度 | 质量 |
|------|------|---------|------|------|
| `vector` | 纯向量检索 | 简单语义搜索 | ⚡⚡⚡ | ⭐⭐⭐ |
| `graph` | 向量→图遍历→文档 | 关系推理 | ⚡⚡ | ⭐⭐⭐⭐ |
| `hybrid` | 并行vector+graph | 通用推荐 | ⚡⚡ | ⭐⭐⭐⭐⭐ |
| `global` | 社区检索→文档 | 全局理解 | ⚡ | ⭐⭐⭐⭐ |

---

### 8. Prompt设计示例

#### 实体提取Prompt
```
Extract key entities from the following text.

Text: {text}

Return a JSON list of entities:
[
  {
    "name": "entity name",
    "type": "PERSON|ORG|LOCATION|PRODUCT|EVENT|CONCEPT",
    "description": "brief description"
  }
]

Focus on the most important entities mentioned.
```

#### 关系提取Prompt
```
Extract relationships between entities in the text.

Text: {text}

Known entities: {entity_names}

Return a JSON list of relationships:
[
  {
    "source": "entity1 name",
    "target": "entity2 name",
    "type": "relationship type (e.g., WORKS_FOR, LOCATED_IN, CREATED)",
    "description": "brief description"
  }
]
```

#### 社区摘要Prompt
```
Summarize the following group of entities into a cohesive theme:

Entities: {entity_names}
Entity descriptions: {entity_descriptions}

Provide a brief summary (2-3 sentences) describing:
1. What these entities have in common
2. The main theme or topic they represent
3. Their significance in the knowledge base
```

---

### 9. 批量处理和并发控制

#### LLM调用批处理
```python
# 使用Semaphore限制并发数
MAX_CONCURRENT_LLM_CALLS = 5

async def _batch_extract_entities(
    self,
    documents: list[Document],
) -> list[Entity]:
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_LLM_CALLS)
    
    async def extract_with_limit(doc):
        async with semaphore:
            return await self._extract_entities_single(doc)
    
    tasks = [extract_with_limit(doc) for doc in documents]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # 处理异常
    entities = []
    for result in results:
        if isinstance(result, Exception):
            logger.error(f"Entity extraction failed: {result}")
        else:
            entities.extend(result)
    
    return entities
```

#### Embedding批处理
```python
# 批量生成embedding（利用API批处理能力）
async def _batch_embed(
    self,
    texts: list[str],
    batch_size: int = 100,
) -> list[list[float]]:
    embeddings = []
    
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i+batch_size]
        batch_embeddings = await self.embedding_model.embed(batch)
        embeddings.extend(batch_embeddings)
    
    return embeddings
```

#### Neo4j批量写入
```python
# 使用UNWIND批量插入
async def _batch_add_entities(
    self,
    entities: list[dict],
    batch_size: int = 1000,
) -> None:
    for i in range(0, len(entities), batch_size):
        batch = entities[i:i+batch_size]
        
        query = """
        UNWIND $entities AS entity
        MERGE (e:Entity {name: entity.name})
        SET e.type = entity.type,
            e.description = entity.description,
            e.embedding = entity.embedding,
            e.updated_at = datetime()
        """
        
        await self._execute_query(query, {"entities": batch})
```

---

### 10. 模块导出更新

#### 更新文件清单
```python
# src/agentscope/exception/__init__.py
from ._rag import (
    RAGExceptionBase,
    DatabaseConnectionError,
    GraphQueryError,
    EntityExtractionError,
    IndexNotFoundError,
)

# src/agentscope/rag/__init__.py
from ._graph_knowledge import GraphKnowledgeBase
from ._graph_types import Entity, Relationship, Community
from ._store._neo4j_graph_store import Neo4jGraphStore
from ._store._store_base import (
    StoreBase,
    VDBStoreBase,
    GraphStoreBase,
)

__all__ = [
    # 现有导出...
    "GraphKnowledgeBase",
    "Neo4jGraphStore",
    "GraphStoreBase",
    "Entity",
    "Relationship",
    "Community",
]
```

---

### 11. 日志记录策略

#### 日志级别使用
```python
# DEBUG: 详细的调试信息
logger.debug(f"Extracting entities from document {doc_id}")

# INFO: 关键操作节点
logger.info(f"Added {len(documents)} documents to graph store")
logger.info(f"Detected {community_count} communities")

# WARNING: 非致命错误
logger.warning(f"Entity extraction failed for document {doc_id}, skipping")
logger.warning(f"Pydantic validation failed: {e}")

# ERROR: 致命错误
logger.error(f"Neo4j connection failed: {e}")
logger.error(f"Graph query execution failed: {e}")
```

#### 关键日志点
- 连接建立和关闭
- 索引创建和检查
- 批量操作开始和完成
- LLM调用（记录tokens使用）
- 异常捕获和处理
- 性能指标（处理时间、文档数量等）

---

## 🎛️ 三种推荐配置

### 配置1: 默认配置（80%场景）
- 启用：实体提取、关系提取
- 关闭：Gleanings、社区检测
- 成本：+25%，质量：+30-40%
- 使用：hybrid检索

### 配置2: 高质量配置（专业领域）
- 启用：实体提取、关系提取、Gleanings、社区检测
- 成本：+75%，质量：+50-60%
- 使用：hybrid或global检索

### 配置3: 低成本配置（成本敏感）
- 关闭：所有图功能
- 成本：+5%，质量：+10-15%
- 使用：vector检索
- 作用：作为SimpleKnowledge的drop-in替代

---

## 🔍 关键Cypher查询示例

### 1. 向量检索（文档）
```cypher
CALL db.index.vector.queryNodes(
    'document_vector_idx',
    $limit,
    $query_embedding
)
YIELD node, score
WHERE score >= $score_threshold
RETURN node, score
ORDER BY score DESC
```

### 2. 图遍历检索
```cypher
// 步骤1: 向量检索种子实体
CALL db.index.vector.queryNodes(
    'entity_vector_idx',
    5,
    $query_embedding
)
YIELD node AS seed_entity

// 步骤2: 图遍历N跳
MATCH path = (seed_entity)-[:RELATED_TO*1..2]-(related_entity)

// 步骤3: 收集关联文档
MATCH (related_entity)<-[:MENTIONS]-(doc:Document)

RETURN DISTINCT doc, 
       length(path) as hops,
       seed_entity.name as seed_name
ORDER BY hops ASC
LIMIT $limit
```

### 3. 混合检索
```cypher
// 向量检索 + 图遍历结果合并
WITH $vector_results AS vector_docs, 
     $graph_results AS graph_docs

UNWIND vector_docs + graph_docs AS doc

// 去重并重排序
RETURN DISTINCT doc
ORDER BY doc.score DESC
LIMIT $limit
```

### 4. 社区检测（Leiden算法）
```cypher
// 创建图投影
CALL gds.graph.project(
    'entity-graph',
    'Entity',
    {
        RELATED_TO: {
            orientation: 'UNDIRECTED',
            properties: ['strength']
        }
    }
)

// 运行Leiden算法
CALL gds.leiden.write(
    'entity-graph',
    {
        writeProperty: 'communityId',
        includeIntermediateCommunities: true
    }
)
YIELD communityCount, levels
```

### 5. 批量插入实体
```cypher
UNWIND $entities AS entity
MERGE (e:Entity {name: entity.name})
SET e.type = entity.type,
    e.description = entity.description,
    e.embedding = entity.embedding,
    e.created_at = datetime()

// 创建文档关联
WITH e, entity
MATCH (d:Document {id: entity.document_id})
MERGE (d)-[r:MENTIONS]->(e)
ON CREATE SET r.count = 1
ON MATCH SET r.count = r.count + 1
```

---

## 🛡️ 错误恢复和容错

### 1. 连接重试策略
```python
async def _ensure_connection(self) -> None:
    """确保Neo4j连接可用（带重试）"""
    max_retries = 3
    retry_delay = 1  # 初始延迟1秒
    
    for attempt in range(max_retries):
        try:
            # 执行简单查询验证连接
            result = await self.driver.execute_query("RETURN 1")
            logger.info("Neo4j connection established")
            return
        except Exception as e:
            if attempt < max_retries - 1:
                logger.warning(
                    f"Connection attempt {attempt + 1} failed: {e}, "
                    f"retrying in {retry_delay}s"
                )
                await asyncio.sleep(retry_delay)
                retry_delay *= 2  # 指数退避
            else:
                logger.error(f"Failed to connect after {max_retries} attempts")
                raise DatabaseConnectionError(
                    f"Cannot connect to Neo4j: {e}"
                )
```

### 2. LLM调用容错
```python
async def _extract_entities_with_fallback(
    self,
    document: Document,
) -> list[Entity]:
    """带降级策略的实体提取"""
    try:
        # 尝试正常提取
        entities = await self._extract_entities_single(document)
        return entities
    except Exception as e:
        logger.warning(f"Entity extraction failed: {e}")
        
        # 降级策略：使用规则提取（正则表达式等）
        if self.enable_fallback:
            logger.info("Using fallback entity extraction")
            return self._rule_based_entity_extraction(document)
        else:
            # 记录错误但不中断流程
            return []
```

### 3. 部分失败处理
```python
async def add_documents(
    self,
    documents: list[Document],
) -> dict:
    """添加文档，返回成功和失败统计"""
    success_count = 0
    failure_count = 0
    errors = []
    
    for doc in documents:
        try:
            await self._add_single_document(doc)
            success_count += 1
        except Exception as e:
            failure_count += 1
            errors.append({
                "document_id": doc.id,
                "error": str(e),
            })
            logger.error(f"Failed to add document {doc.id}: {e}")
    
    return {
        "success": success_count,
        "failed": failure_count,
        "errors": errors,
    }
```

### 4. 事务回滚
```python
async def _add_with_transaction(
    self,
    documents: list[Document],
) -> None:
    """使用事务确保原子性"""
    async with self.driver.session() as session:
        async with session.begin_transaction() as tx:
            try:
                # 添加文档
                await self._add_documents_in_tx(tx, documents)
                
                # 提取实体
                if self.enable_entity_extraction:
                    entities = await self._extract_entities(documents)
                    await self._add_entities_in_tx(tx, entities)
                
                # 提交事务
                await tx.commit()
            except Exception as e:
                # 回滚事务
                await tx.rollback()
                logger.error(f"Transaction failed, rolled back: {e}")
                raise
```

---

## 📈 监控和指标

### 1. 性能指标收集
```python
# 在关键操作中记录指标
import time

class GraphKnowledgeBase:
    def __init__(self, ...):
        self.metrics = {
            "documents_indexed": 0,
            "entities_extracted": 0,
            "relationships_created": 0,
            "queries_executed": 0,
            "total_index_time": 0.0,
            "total_query_time": 0.0,
        }
    
    async def add_documents(self, documents):
        start_time = time.time()
        
        # ... 添加文档逻辑 ...
        
        elapsed = time.time() - start_time
        self.metrics["documents_indexed"] += len(documents)
        self.metrics["total_index_time"] += elapsed
        
        logger.info(
            f"Indexed {len(documents)} documents in {elapsed:.2f}s "
            f"({len(documents)/elapsed:.1f} docs/s)"
        )
```

### 2. 健康检查端点
```python
async def health_check(self) -> dict:
    """返回系统健康状态"""
    try:
        # 检查Neo4j连接
        await self.driver.execute_query("RETURN 1")
        neo4j_status = "healthy"
    except Exception as e:
        neo4j_status = f"unhealthy: {e}"
    
    # 统计数据
    stats = await self._get_statistics()
    
    return {
        "status": "healthy" if neo4j_status == "healthy" else "degraded",
        "neo4j": neo4j_status,
        "statistics": stats,
        "metrics": self.metrics,
    }

async def _get_statistics(self) -> dict:
    """获取图数据库统计信息"""
    query = """
    MATCH (d:Document) WITH count(d) as doc_count
    MATCH (e:Entity) WITH doc_count, count(e) as entity_count
    MATCH ()-[r:RELATED_TO]->() WITH doc_count, entity_count, count(r) as rel_count
    OPTIONAL MATCH (c:Community) WITH doc_count, entity_count, rel_count, count(c) as comm_count
    RETURN doc_count, entity_count, rel_count, comm_count
    """
    
    result = await self.driver.execute_query(query)
    return result[0] if result else {}
```

### 3. 关键指标监控
- **索引性能**: 文档/秒，实体提取耗时
- **查询性能**: 查询延迟（P50/P95/P99）
- **资源使用**: Neo4j内存使用，连接池状态
- **API调用**: LLM/Embedding API调用次数和成本
- **错误率**: 失败请求比例，异常类型分布
- **数据规模**: 文档数、实体数、关系数、社区数

---

## 🔄 数据迁移指南

### 1. 从SimpleKnowledge迁移

#### 步骤1: 导出现有数据
```python
# 从Qdrant导出
from agentscope.rag import SimpleKnowledge

old_knowledge = SimpleKnowledge(...)

# 获取所有文档（如果支持）
documents = []  # 从现有系统导出
```

#### 步骤2: 导入到GraphKnowledgeBase
```python
from agentscope.rag import GraphKnowledgeBase

new_knowledge = GraphKnowledgeBase(...)

# 批量导入
await new_knowledge.add_documents(documents)
```

#### 步骤3: 验证迁移
```python
# 对比检索结果
query = "test query"
old_results = await old_knowledge.retrieve(query)
new_results = await new_knowledge.retrieve(query, search_mode="vector")

# 验证相似度
assert len(old_results) == len(new_results)
```

### 2. 增量迁移策略
```python
# 双写模式：同时写入两个系统
async def add_documents_dual_write(documents):
    # 写入旧系统
    await old_knowledge.add_documents(documents)
    
    # 写入新系统
    try:
        await new_knowledge.add_documents(documents)
    except Exception as e:
        logger.error(f"New system write failed: {e}")
        # 不影响旧系统

# 读取时优先新系统
async def retrieve_with_fallback(query):
    try:
        return await new_knowledge.retrieve(query)
    except Exception as e:
        logger.warning(f"New system failed, using old: {e}")
        return await old_knowledge.retrieve(query)
```

### 3. 数据清理和优化
```python
# 清理重复实体
query = """
MATCH (e:Entity)
WITH e.name as name, collect(e) as entities
WHERE size(entities) > 1
CALL {
    WITH entities
    UNWIND entities[1..] as duplicate
    DETACH DELETE duplicate
}
"""

# 重建索引
await graph_store.rebuild_indexes()

# 重新计算社区
await knowledge.detect_communities()
```

---

## 📦 部署要点

### 依赖安装
```bash
pip install "agentscope[graph]"
```

### Neo4j部署（Docker推荐）
```bash
docker run -d \
  --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/password \
  -e NEO4J_PLUGINS='["graph-data-science"]' \
  neo4j:latest
```

**要点**：
- Neo4j版本：6.0.2+（支持向量索引）
- GDS插件：社区检测需要
- 端口：7474（HTTP）、7687（Bolt）

---

## ✅ 验收标准

### 功能完整性
- [ ] **存储层抽象**
  - [ ] StoreBase基类定义完整
  - [ ] VDBStoreBase继承正确，现有实现不受影响
  - [ ] GraphStoreBase接口定义完整
  - [ ] Neo4jGraphStore实现所有抽象方法

- [ ] **基础功能**
  - [ ] 纯向量检索正常工作
  - [ ] 文档增删查功能正常
  - [ ] 向量索引自动创建和管理
  - [ ] 连接重试机制生效

- [ ] **图功能**
  - [ ] 实体提取功能正常（含Gleanings）
  - [ ] 关系提取功能正常
  - [ ] 图遍历检索正常
  - [ ] 混合检索正常
  - [ ] 社区检测功能正常（用户主动调用）
  - [ ] 全局检索功能正常

- [ ] **数据验证**
  - [ ] Pydantic模型验证正常
  - [ ] LLM返回数据自动验证
  - [ ] 异常数据处理正确

### 兼容性
- [ ] **现有组件兼容**
  - [ ] QdrantStore正常工作（无需修改）
  - [ ] MilvusLiteStore正常工作（无需修改）
  - [ ] SimpleKnowledge功能不受影响
  - [ ] 现有embedding模型全部兼容

- [ ] **接口兼容**
  - [ ] KnowledgeBase接口保持一致
  - [ ] Document和DocMetadata保持不变
  - [ ] 可作为SimpleKnowledge的drop-in替代

- [ ] **集成兼容**
  - [ ] 与ReActAgent无缝集成
  - [ ] 支持retrieve_knowledge工具函数
  - [ ] Agent工具链正常工作

### 性能指标
- [ ] **索引性能**
  - [ ] 纯向量：>50 docs/s
  - [ ] 实体+关系：>8 docs/s
  - [ ] 含Gleanings：>4 docs/s
  - [ ] 批量操作支持正常

- [ ] **检索性能**
  - [ ] vector模式：P95 < 200ms
  - [ ] graph模式：P95 < 500ms
  - [ ] hybrid模式：P95 < 800ms
  - [ ] global模式：P95 < 2s

- [ ] **并发性能**
  - [ ] 支持10+ QPS稳定运行
  - [ ] Semaphore并发控制生效
  - [ ] 无连接泄漏

- [ ] **资源使用**
  - [ ] Neo4j内存使用在预期范围
  - [ ] 连接池管理正常
  - [ ] 无内存泄漏

### 质量标准
- [ ] **提取质量**
  - [ ] 实体提取准确率：>80%
  - [ ] 关系提取准确率：>70%
  - [ ] Gleanings提升召回率：>10%

- [ ] **检索质量**
  - [ ] Precision@5：>0.7
  - [ ] Recall@5：比SimpleKnowledge提升>10%
  - [ ] hybrid模式优于单一模式

- [ ] **代码质量**
  - [ ] 类型注解完整
  - [ ] 文档字符串完整（Google style）
  - [ ] 错误处理健壮
  - [ ] 日志记录完整

### 异常处理
- [ ] **异常定义**
  - [ ] RAG专用异常类定义完整
  - [ ] 异常继承关系正确
  - [ ] 异常信息清晰有用

- [ ] **错误恢复**
  - [ ] 连接重试机制正常
  - [ ] 部分失败不影响整体
  - [ ] 降级策略正常工作
  - [ ] 事务回滚正常

### 文档完整性
- [ ] **API文档**
  - [ ] 所有公开类有文档
  - [ ] 所有公开方法有文档
  - [ ] 参数和返回值说明清晰
  - [ ] 包含使用示例

- [ ] **使用指南**
  - [ ] 快速开始指南完整
  - [ ] 三种配置场景说明清晰
  - [ ] Agent集成示例完整
  - [ ] 配置参数说明完整

- [ ] **部署指南**
  - [ ] 依赖安装说明清晰
  - [ ] Neo4j部署指南完整
  - [ ] Docker方式说明详细
  - [ ] 常见问题FAQ完整

- [ ] **代码示例**
  - [ ] 基础使用示例完整
  - [ ] 完整功能示例完整
  - [ ] 高级功能示例完整
  - [ ] 错误处理示例完整

### 测试覆盖
- [ ] **单元测试**
  - [ ] StoreBase相关测试通过
  - [ ] Neo4jGraphStore测试通过
  - [ ] GraphKnowledgeBase测试通过
  - [ ] 数据模型测试通过
  - [ ] 代码覆盖率>80%

- [ ] **集成测试**
  - [ ] 完整索引流程测试通过
  - [ ] 四种检索模式测试通过
  - [ ] Agent集成测试通过
  - [ ] 错误场景测试通过

- [ ] **性能测试**
  - [ ] 索引吞吐量达标
  - [ ] 检索延迟达标
  - [ ] 并发性能达标
  - [ ] 内存使用正常

- [ ] **质量测试**
  - [ ] 实体提取质量达标
  - [ ] 关系提取质量达标
  - [ ] 检索质量达标
  - [ ] 端到端质量验证通过

---

## 🚨 风险和注意事项

### 1. Neo4j版本兼容性
- **风险**：低于6.0.2版本不支持向量索引
- **应对**：在连接初始化时检查版本，不满足要求抛出异常

### 2. LLM成本
- **风险**：实体/关系提取和社区摘要会增加LLM调用成本
- **应对**：提供配置开关，允许用户选择性启用功能

### 3. GDS插件依赖
- **风险**：社区检测需要GDS插件，用户可能未安装
- **应对**：在调用社区检测时检查插件，未安装抛出明确错误信息

### 4. 性能优化
- **风险**：图遍历在大规模图中可能较慢
- **应对**：限制遍历深度（max_hops），提供配置参数

### 5. 向后兼容
- **风险**：修改StoreBase可能影响现有代码
- **应对**：充分的单元测试，确保VDBStoreBase子类无需修改

---

## 📚 参考资源

- [设计与架构文档](Neo4j_GraphKnowledgeBase_设计与架构.md)
- [实施指南](Neo4j_GraphKnowledgeBase_实施指南.md)
- [Neo4j官方文档](https://neo4j.com/docs/)
- [Neo4j GDS文档](https://neo4j.com/docs/graph-data-science/current/)
- [GraphRAG论文](https://arxiv.org/abs/2404.16130)

---

**文档版本**: v1.0  
**文档类型**: 实施步骤计划  
**创建日期**: 2025-10-31  
**维护者**: AgentScope Team

