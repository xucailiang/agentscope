# GraphKnowledgeBase 测试说明

## 测试文件

`tests/graph_knowledge_test.py`

## 测试覆盖范围

本测试套件提供了 GraphKnowledgeBase 的基本功能测试，涵盖以下场景：

### 1. 基础功能测试

#### test_basic_vector_mode
- **目的**: 测试纯向量模式（关闭所有图功能）
- **验证点**:
  - 文档正确添加到存储
  - Embedding 正确生成
  - 向量检索正常工作

#### test_empty_documents
- **目的**: 测试空文档列表处理
- **验证点**:
  - 不会抛出错误
  - 正确处理空列表

### 2. 实体和关系提取测试

#### test_with_entity_extraction
- **目的**: 测试实体提取功能
- **验证点**:
  - 实体被正确提取
  - 实体包含必需字段（name, type, description）

#### test_with_relationship_extraction
- **目的**: 测试关系提取功能
- **验证点**:
  - 关系被正确提取
  - 关系包含必需字段（source, target, type, description）

#### test_entity_deduplication
- **目的**: 测试实体去重功能
- **验证点**:
  - 多个文档提到的相同实体被正确处理

### 3. 检索模式测试

#### test_graph_search
- **目的**: 测试纯图遍历检索
- **验证点**:
  - 图检索正常执行
  - 返回正确的Document对象

#### test_hybrid_search
- **目的**: 测试混合检索（向量+图）
- **验证点**:
  - 混合检索正常工作
  - 返回结果包含有效的分数

#### test_search_modes_validation
- **目的**: 测试无效检索模式的错误处理
- **验证点**:
  - 无效模式抛出 ValueError

#### test_global_search_requires_community_detection
- **目的**: 测试全局检索需要社区检测
- **验证点**:
  - 未启用社区检测时抛出 ValueError

### 4. 错误处理测试

#### test_error_handling_no_llm
- **目的**: 测试缺少必需LLM的错误处理
- **验证点**:
  - 启用实体提取但未提供LLM时抛出 ValueError

## Mock 对象

测试使用以下Mock对象，无需真实的外部依赖：

### MockEmbeddingModel
- 模拟 Embedding 模型
- 基于文本哈希生成固定的3维向量

### MockChatModel
- 模拟 LLM 聊天模型
- 返回预定义的实体和关系JSON数据

### MockGraphStore
- 模拟图数据库存储
- 在内存中存储文档、实体、关系和社区
- 无需真实的Neo4j连接

## 运行测试

### 使用unittest运行

```bash
cd /home/justin/opensource/agentscope
python -m unittest discover tests -p "graph_knowledge_test.py" -v
```

### 直接运行测试文件

```bash
cd /home/justin/opensource/agentscope
python tests/graph_knowledge_test.py
```

## 测试结果

所有10个测试用例均通过：

```
test_basic_vector_mode ... ok
test_empty_documents ... ok
test_entity_deduplication ... ok
test_error_handling_no_llm ... ok
test_global_search_requires_community_detection ... ok
test_graph_search ... ok
test_hybrid_search ... ok
test_search_modes_validation ... ok
test_with_entity_extraction ... ok
test_with_relationship_extraction ... ok

----------------------------------------------------------------------
Ran 10 tests in 0.015s

OK
```

## 依赖说明

测试不需要以下外部依赖：
- ❌ Neo4j 数据库
- ❌ 真实的 LLM API
- ❌ 真实的 Embedding API

所有依赖都通过Mock对象模拟，确保测试可以在任何环境下运行。

## 未覆盖的功能

以下高级功能未在基础测试中覆盖（需要真实环境或更复杂的集成测试）：

- 社区检测的完整流程（需要Neo4j GDS）
- Gleanings多轮实体提取
- 大规模数据的性能测试
- 并发操作测试
- 真实Neo4j的集成测试

## 扩展测试建议

如需更详尽的测试，可以考虑：

1. **集成测试**: 使用真实的Neo4j容器进行端到端测试
2. **性能测试**: 测试大量文档的索引和检索性能
3. **质量测试**: 使用标准数据集验证实体提取和检索质量
4. **并发测试**: 测试多线程/多进程场景下的稳定性
5. **边界条件**: 测试各种异常输入和边界情况

## 代码质量

- ✅ 无 linter 错误
- ✅ 遵循项目代码风格
- ✅ 完整的类型注解
- ✅ 清晰的文档字符串

