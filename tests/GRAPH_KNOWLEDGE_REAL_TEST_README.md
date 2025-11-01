# GraphKnowledgeBase 真实环境测试说明

## 概述

这是使用**真实Neo4j数据库**和**真实DashScope API**的集成测试。

## 测试文件

`tests/graph_knowledge_test.py`

## 前提条件

### 1. Neo4j 数据库

确保Neo4j数据库正在运行：

```bash
# 使用Docker启动Neo4j (推荐)
docker run -d \
  --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/password \
  neo4j:latest

# 或者使用本地安装的Neo4j
# 确保服务已启动在 bolt://localhost:7687
```

### 2. DashScope API Key

需要有效的DashScope API Key用于：
- 文本Embedding（text-embedding-v2）
- LLM调用（qwen-max）

### 3. Python依赖

```bash
# 激活虚拟环境
source .venv/bin/activate

# 确保安装了必要的依赖
pip install neo4j agentscope dashscope
```

## 配置说明

测试使用环境变量配置，如果未设置则使用默认值：

```bash
# Neo4j配置
export NEO4J_URI="bolt://localhost:7687"
export NEO4J_USER="neo4j"
export NEO4J_PASSWORD="password"  # 修改为你的密码
export NEO4J_DATABASE="neo4j"

# DashScope API Key
export DASHSCOPE_API_KEY="your-api-key"  # 修改为你的API Key
```

或者直接修改测试文件中的默认值：

```python
# tests/graph_knowledge_test.py
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "your-password")  # 修改这里
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "your-api-key")  # 修改这里
```

## 运行测试

### 运行所有测试

```bash
cd /home/justin/opensource/agentscope
source .venv/bin/activate
python -m unittest discover tests -p "graph_knowledge_test.py" -v
```

### 运行单个测试

```bash
# 测试基础向量模式
python -m unittest tests.graph_knowledge_test.GraphKnowledgeTest.test_basic_vector_mode -v

# 测试实体提取
python -m unittest tests.graph_knowledge_test.GraphKnowledgeTest.test_with_entity_extraction -v

# 测试关系提取
python -m unittest tests.graph_knowledge_test.GraphKnowledgeTest.test_with_relationship_extraction -v

# 测试混合搜索
python -m unittest tests.graph_knowledge_test.GraphKnowledgeTest.test_hybrid_search -v
```

## 测试用例

### 1. test_basic_vector_mode
- **功能**: 测试纯向量模式（不使用图功能）
- **验证**: 
  - 文档成功添加到Neo4j
  - Embedding成功生成（1536维）
  - 向量检索返回正确结果
- **API调用**: DashScope Embedding API

### 2. test_with_entity_extraction
- **功能**: 测试实体提取
- **验证**:
  - 使用真实LLM提取实体
  - 实体成功存储到Neo4j
- **API调用**: 
  - DashScope Embedding API
  - DashScope LLM API (qwen-max)

### 3. test_with_relationship_extraction
- **功能**: 测试实体和关系提取
- **验证**:
  - 实体和关系同时提取
  - 关系成功存储到Neo4j
- **API调用**:
  - DashScope Embedding API
  - DashScope LLM API (qwen-max)

### 4. test_hybrid_search
- **功能**: 测试混合检索（向量+图）
- **验证**:
  - 混合检索正常工作
  - 结果包含有效的分数
- **API调用**:
  - DashScope Embedding API
  - DashScope LLM API (qwen-max)

### 5. test_error_handling_no_llm
- **功能**: 测试错误处理
- **验证**:
  - 缺少必需的LLM时正确抛出ValueError

## 测试结果示例

```
test_basic_vector_mode ... 
  ✓ Vector search returned 2 results
ok

test_error_handling_no_llm ... 
  ✓ Correctly raised ValueError: llm_model is required when entity_extraction or relationship_extraction is enabled
ok

test_hybrid_search ... 
  ⏳ Adding documents with entity/relationship extraction...
  ⏳ Testing hybrid search...
  ✓ Hybrid search returned 2 results
ok

test_with_entity_extraction ... 
  ⏳ Extracting entities using LLM...
  ✓ Entities extracted successfully
ok

test_with_relationship_extraction ... 
  ⏳ Extracting entities and relationships using LLM...
  ✓ Entities and relationships extracted successfully
ok

----------------------------------------------------------------------
Ran 5 tests in 17.594s

OK
```

## 数据清理

测试会自动清理数据：

- 每个测试使用唯一的collection名称（基于时间戳）
- `asyncTearDown()`方法会在测试后删除所有测试数据
- 不会影响Neo4j中的其他数据

## 成本说明

⚠️ **注意**: 这些测试会调用真实的API，会产生费用：

### DashScope API成本（估算）

每次完整测试运行：
- **Embedding API**: ~10次调用（text-embedding-v2）
- **LLM API**: ~6次调用（qwen-max）
- **预估总成本**: ¥0.05 - ¥0.10 / 次

### 降低成本的建议

1. 只运行必要的测试：
   ```bash
   # 只测试基础功能（不调用LLM）
   python -m unittest tests.graph_knowledge_test.GraphKnowledgeTest.test_basic_vector_mode -v
   ```

2. 使用更便宜的模型：
   修改测试文件中的模型配置：
   ```python
   self.llm_model = DashScopeChatModel(
       model_name="qwen-turbo",  # 更便宜的模型
       api_key=DASHSCOPE_API_KEY,
       stream=False,
   )
   ```

## 故障排查

### Neo4j连接失败

```
Connection attempt 1 failed: Failed to read from defunct connection
```

**解决方案**:
1. 检查Neo4j是否正在运行: `docker ps | grep neo4j`
2. 检查端口7687是否可访问
3. 验证用户名密码是否正确

### DashScope API错误

```
Error: Invalid API Key
```

**解决方案**:
1. 检查API Key是否有效
2. 确认API Key有足够的配额
3. 检查网络连接

### 测试超时

某些测试可能需要较长时间（特别是实体提取）：
- `test_with_entity_extraction`: ~5-10秒
- `test_with_relationship_extraction`: ~5-10秒
- `test_hybrid_search`: ~8-15秒

这是正常的，因为需要调用真实的LLM API。

## 与Mock测试的对比

| 维度 | Mock测试（之前） | 真实测试（当前） |
|-----|----------------|----------------|
| Neo4j依赖 | ❌ 不需要 | ✅ 需要真实数据库 |
| API调用 | ❌ 模拟 | ✅ 真实调用 |
| 速度 | ⚡ 快（<1秒） | 🐢 慢（~18秒） |
| 成本 | 💰 免费 | 💸 产生费用 |
| 测试覆盖 | 基础逻辑 | 端到端集成 |
| 适用场景 | CI/CD快速验证 | 正式发布前验证 |

## 最佳实践

1. **开发阶段**: 使用Mock测试快速迭代
2. **提交前**: 运行真实测试确保集成正常
3. **CI/CD**: 配置可选的真实测试（仅在关键分支运行）

## 扩展测试

如需更全面的测试，可以添加：

- 社区检测测试（需要Neo4j GDS插件）
- 大规模数据测试
- 性能基准测试
- 并发操作测试
- 容错和恢复测试

## 总结

✅ 所有5个测试通过  
✅ 使用真实Neo4j数据库  
✅ 使用真实DashScope API  
✅ 自动数据清理  
✅ 完整的端到端验证  

测试确认GraphKnowledgeBase在真实环境中运行正常！

