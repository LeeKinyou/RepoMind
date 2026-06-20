# 贡献指南

感谢你对 RepoMind 项目的关注！本文档将帮助你快速了解如何参与贡献。

## 1. 开发流程

### 1.1 Fork & Clone

```bash
# 1. 在 GitHub 上 Fork 项目
# 2. 克隆你的 Fork
git clone git@github.com:your-username/RepoMind.git
cd RepoMind

# 3. 添加上游远程仓库
git remote add upstream git@github.com:LeeKinyou/RepoMind.git
```

### 1.2 创建分支

```bash
# 同步上游
git fetch upstream
git checkout main
git merge upstream/main

# 创建功能分支
git checkout -b feat/my-feature
```

分支命名规范：

| 前缀 | 说明 | 示例 |
|------|------|------|
| `feat/` | 新功能 | `feat/multi-language-support` |
| `fix/` | Bug 修复 | `fix/parser-crash-on-empty-file` |
| `docs/` | 文档 | `docs/update-api-reference` |
| `refactor/` | 重构 | `refactor/simplify-type-inference` |
| `test/` | 测试 | `test/add-call-graph-tests` |
| `chore/` | 构建/工具 | `chore/update-dependencies` |

### 1.3 开发

```bash
# 安装开发依赖
uv pip install -e ".[dev]"

# 编写代码...

# 运行测试
uv run pytest tests/unit/

# 格式化代码
uv run ruff format src/ tests/

# Lint 检查
uv run ruff check src/ tests/

# 类型检查
uv run mypy src/repomind/
```

### 1.4 提交

```bash
git add .
git commit -m "feat(parser): add support for async functions"
```

### 1.5 推送 & PR

```bash
git push origin feat/my-feature
# 然后在 GitHub 上创建 Pull Request
```

---

## 2. Commit Message 规范

遵循 [Conventional Commits](https://www.conventionalcommits.org/) 规范：

```
<type>(<scope>): <subject>

<body>

<footer>
```

### 2.1 类型 (type)

| 类型 | 说明 |
|------|------|
| `feat` | 新功能 |
| `fix` | Bug 修复 |
| `docs` | 文档变更 |
| `style` | 代码格式（不影响逻辑） |
| `refactor` | 重构（既不是新功能也不是修复） |
| `perf` | 性能优化 |
| `test` | 测试相关 |
| `chore` | 构建/工具变更 |
| `ci` | CI/CD 相关 |

### 2.2 范围 (scope)

可选，表示影响范围：

| 范围 | 说明 |
|------|------|
| `parser` | 解析引擎 |
| `type-inference` | 类型推断 |
| `call-graph` | 调用图 |
| `retrieval` | 检索引擎 |
| `rca` | 根因分析 |
| `cli` | 命令行界面 |
| `storage` | 存储层 |
| `sandbox` | 沙箱 |
| `docs` | 文档 |

### 2.3 示例

```
feat(parser): add support for async function parsing

- Detect `async def` syntax in AST
- Mark async functions with `is_async` attribute
- Add tests for async/await patterns

Closes #42
```

```
fix(retrieval): handle empty query gracefully

Previously, an empty query string would cause a ZeroDivisionError
in the BM25 scorer. Now returns empty results immediately.

Fixes #38
```

```
refactor(type-inference): simplify confidence scoring

Merge the six separate strategy classes into a single
ProgressiveTypeInference with a strategy list. Reduces
code duplication and makes it easier to add new strategies.
```

---

## 3. 代码规范

### 3.1 Python 代码风格

- 遵循 PEP 8
- 使用 Ruff 进行格式化和 Lint
- 最大行宽 88 字符（Ruff 默认）
- 使用类型注解

```python
# ✅ Good
def process_symbol(symbol: Symbol, config: Config) -> ProcessResult:
    """Process a single symbol.

    Args:
        symbol: The symbol to process.
        config: Processing configuration.

    Returns:
        The processing result.
    """
    result = analyze(symbol, config)
    return ProcessResult(success=True, data=result)

# ❌ Bad
def process_symbol(symbol, config):
    result = analyze(symbol, config)
    return {"success": True, "data": result}
```

### 3.2 命名规范

| 元素 | 风格 | 示例 |
|------|------|------|
| 模块 | snake_case | `type_inference.py` |
| 类 | PascalCase | `ProgressiveTypeInference` |
| 函数/方法 | snake_case | `infer_type()` |
| 常量 | UPPER_SNAKE_CASE | `MAX_HOPS` |
| 私有成员 | _前缀 | `_internal_method()` |
| 类型变量 | PascalCase | `T`、`SymbolT` |

### 3.3 文档字符串

使用 Google 风格的 docstring：

```python
def search(
    self,
    query: str,
    top_k: int = 10,
    mode: str = "hybrid"
) -> QueryResult:
    """Execute a hybrid search query.

    Performs BM25 keyword search and vector semantic search in parallel,
    then fuses results using Reciprocal Rank Fusion (RRF).

    Args:
        query: The search query text.
        top_k: Maximum number of results to return. Defaults to 10.
        mode: Search mode - 'keyword', 'semantic', or 'hybrid'.
            Defaults to 'hybrid'.

    Returns:
        QueryResult containing seed nodes, expanded nodes, and edges.

    Raises:
        IndexNotFoundError: If no index exists for the project.
        InvalidQueryError: If the query is empty or invalid.

    Example:
        >>> service = QueryService()
        >>> result = service.search("user authentication", top_k=5)
        >>> for item in result.seed_nodes:
        ...     print(f"{item.score:.2f} {item.qualified_name}")
    """
```

### 3.4 错误处理

```python
# ✅ Good: 具体异常类型
class IndexNotFoundError(RepoMindError):
    """索引不存在"""
    def __init__(self, path: str):
        super().__init__(f"索引不存在: {path}")
        self.path = path

# ✅ Good: 使用自定义异常
def get_index(path: str) -> Index:
    if not os.path.exists(os.path.join(path, ".repomind")):
        raise IndexNotFoundError(path)
    return load_index(path)

# ❌ Bad: 使用裸 Exception
def get_index(path):
    if not os.path.exists(path):
        raise Exception("Not found")
```

---

## 4. 测试规范

### 4.1 测试文件命名

```
tests/
├── unit/
│   ├── test_parser.py
│   ├── test_type_inference.py
│   └── test_call_graph.py
├── integration/
│   ├── test_index_service.py
│   └── test_query_service.py
└── conftest.py
```

### 4.2 测试函数命名

```python
# ✅ Good: 描述性的测试名
def test_parse_class_definition_with_docstring():
    ...

def test_infer_type_from_explicit_hint_returns_high_confidence():
    ...

def test_graph_expansion_limits_nodes_when_max_exceeded():
    ...

# ❌ Bad: 模糊的测试名
def test_parser():
    ...

def test_type():
    ...
```

### 4.3 测试结构

使用 Arrange-Act-Assert 模式：

```python
def test_parse_class_definition(parser, tmp_path):
    """测试类定义解析"""
    # Arrange
    source = '''
class UserService:
    """用户服务"""
    def get_user(self, user_id: int) -> User:
        pass
'''
    file = tmp_path / "service.py"
    file.write_text(source)

    # Act
    result = parser.parse_file(str(file))

    # Assert
    assert len(result.symbols) == 2
    cls = result.symbols[0]
    assert cls.name == "UserService"
    assert cls.type == "class"
    assert cls.docstring == "用户服务"
```

### 4.4 Fixtures

```python
@pytest.fixture
def sample_project(tmp_path):
    """创建示例项目"""
    project = tmp_path / "sample"
    project.mkdir()
    # ... 创建测试文件 ...
    return project

@pytest.fixture
def parser():
    """创建解析器实例"""
    return TreeSitterParser("python")
```

### 4.5 运行测试

```bash
# 运行所有测试
pytest

# 运行特定目录
pytest tests/unit/

# 运行特定文件
pytest tests/unit/test_parser.py

# 运行特定测试
pytest tests/unit/test_parser.py::test_parse_class_definition

# 运行并显示覆盖率
pytest --cov=src/repomind --cov-report=term-missing

# 跳过慢测试
pytest -m "not slow"

# 并行运行
pytest -n auto
```

---

## 5. Pull Request 规范

### 5.1 PR 标题

遵循 Commit Message 规范：

```
feat(parser): add support for async functions
fix(retrieval): handle empty query gracefully
docs(api): update QueryService documentation
```

### 5.2 PR 描述模板

```markdown
## 描述

简要描述这个 PR 做了什么。

## 变更类型

- [ ] 新功能 (feat)
- [ ] Bug 修复 (fix)
- [ ] 文档 (docs)
- [ ] 重构 (refactor)
- [ ] 测试 (test)
- [ ] 其他 (chore)

## 测试

- [ ] 添加了新的测试
- [ ] 所有现有测试通过
- [ ] 覆盖率未下降

## 截图（如适用）

## 相关 Issue

Closes #42
```

### 5.3 PR 检查清单

- [ ] 代码遵循项目风格指南
- [ ] 所有测试通过
- [ ] 新增代码有测试覆盖
- [ ] 文档已更新（如需要）
- [ ] Commit Message 符合规范
- [ ] 没有引入新的警告
- [ ] 覆盖率未下降

---

## 6. Issue 规范

### 6.1 Bug Report

```markdown
## 描述

简要描述 bug。

## 复现步骤

1. 运行 `repomind index ...`
2. 运行 `repomind query ...`
3. 观察到错误

## 期望行为

描述你期望发生什么。

## 实际行为

描述实际发生了什么。

## 环境信息

- OS: Windows 11 / macOS 14 / Ubuntu 22.04
- Python: 3.13.0
- RepoMind: 0.1.0

## 错误日志

```
粘贴错误日志
```
```

### 6.2 Feature Request

```markdown
## 描述

简要描述你想要的功能。

## 使用场景

描述这个功能解决什么问题。

## 建议方案

描述你期望的实现方式。

## 替代方案

描述你考虑过的其他方案。
```

---

## 7. 开发者证书 (DCO)

提交代码时，你需要确认你有权提交这些代码。在 commit message 中添加：

```
Signed-off-by: Your Name <your.email@example.com>
```

或使用 `git commit -s` 自动添加。
