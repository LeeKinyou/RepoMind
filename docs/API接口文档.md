# API 接口文档

## 1. 概述

RepoMind 的核心功能通过四个服务类对外暴露：`IndexService`、`QueryService`、`RCAService`、`VisualizationService`。所有服务遵循接口-实现分离的设计，支持依赖注入和单元测试。

**模块导入**：

```python
from repomind.services import IndexService, QueryService, RCAService, VisualizationService
from repomind.models import (
    IndexOptions, IndexResult,
    QueryOptions, QueryResult,
    RCAResult, FixResult,
    SymbolInfo, CallGraphResult
)
```

---

## 2. IndexService — 索引服务

负责代码仓库的解析、索引构建和增量更新。

### 2.1 index_directory

索引本地目录。

```python
def index_directory(self, path: str, options: IndexOptions = None) -> IndexResult
```

**参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `path` | `str` | 是 | 项目目录的绝对或相对路径 |
| `options` | `IndexOptions` | 否 | 索引配置选项 |

**IndexOptions**：

```python
@dataclass
class IndexOptions:
    language: str = "python"              # 目标语言
    output_dir: str = ".repomind"         # 索引输出目录
    ignore_patterns: list[str] = None    # 忽略的文件模式
    max_file_size_mb: float = 5.0        # 单文件最大体积
    incremental: bool = False            # 是否增量更新
    verbose: bool = False                # 详细输出
```

**返回值 IndexResult**：

```python
@dataclass
class IndexResult:
    success: bool                        # 是否成功
    total_files: int                     # 扫描文件总数
    indexed_files: int                   # 成功索引文件数
    skipped_files: int                   # 跳过文件数
    total_symbols: int                   # 符号总数
    total_classes: int                   # 类数量
    total_functions: int                 # 函数数量
    total_imports: int                   # 导入关系数
    total_calls: int                     # 调用关系数
    elapsed_seconds: float               # 耗时（秒）
    index_path: str                      # 索引存储路径
    errors: list[str]                    # 错误信息列表
```

**异常**：

| 异常类型 | 说明 |
|---------|------|
| `PathNotFoundError` | 路径不存在 |
| `InvalidLanguageError` | 不支持的语言 |
| `IndexBuildError` | 索引构建失败 |

**示例**：

```python
service = IndexService()
result = service.index_directory("./my-project", IndexOptions(
    verbose=True,
    ignore_patterns=["**/test/**", "**/venv/**"]
))

print(f"索引了 {result.indexed_files} 个文件，耗时 {result.elapsed_seconds:.1f}s")
```

---

### 2.2 index_git_repo

克隆并索引远程 Git 仓库。

```python
def index_git_repo(self, url: str, options: IndexOptions = None) -> IndexResult
```

**参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `url` | `str` | 是 | Git 仓库 URL |
| `options` | `IndexOptions` | 否 | 索引配置选项 |

**返回值**：同 `index_directory`

**示例**：

```python
result = service.index_git_repo(
    "https://github.com/pallets/flask.git",
    IndexOptions(language="python")
)
```

---

### 2.3 update_index

增量更新索引（仅处理变更文件）。

```python
def update_index(self, path: str) -> UpdateResult
```

**参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `path` | `str` | 是 | 项目目录路径 |

**返回值 UpdateResult**：

```python
@dataclass
class UpdateResult:
    success: bool
    added_files: int           # 新增文件数
    modified_files: int        # 修改文件数
    deleted_files: int         # 删除文件数
    elapsed_seconds: float
```

---

### 2.4 get_stats

获取索引统计信息。

```python
def get_stats(self) -> IndexStats
```

**返回值 IndexStats**：

```python
@dataclass
class IndexStats:
    project_path: str
    index_time: datetime
    total_files: int
    total_lines: int
    total_symbols: int
    total_classes: int
    total_functions: int
    total_methods: int
    total_imports: int
    total_calls: int
    total_inherits: int
    type_hint_coverage: float      # 类型提示覆盖率
    inference_success_rate: float  # 推断成功率
    average_confidence: float      # 平均置信度
    index_size_mb: float           # 索引大小
    vector_size_mb: float          # 向量存储大小
```

---

### 2.5 clear_index

清除索引数据。

```python
def clear_index(self, path: str) -> bool
```

**参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `path` | `str` | 是 | 项目目录路径 |

**返回值**：`bool` — 是否成功清除

---

## 3. QueryService — 查询服务

负责混合检索、符号查询和调用图生成。

### 3.1 search

执行混合检索查询。

```python
def search(self, query: str, options: QueryOptions = None) -> QueryResult
```

**参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `query` | `str` | 是 | 查询文本（关键字或自然语言） |
| `options` | `QueryOptions` | 否 | 查询配置选项 |

**QueryOptions**：

```python
@dataclass
class QueryOptions:
    top_k: int = 10                    # 返回结果数量
    expand_hops: int = 2               # 图拓扑扩展跳数
    mode: str = "hybrid"               # 检索模式: keyword / semantic / hybrid
    bm25_weight: float = 0.4           # BM25 权重
    vector_weight: float = 0.6         # 向量权重
    min_score: float = 0.3             # 最小相似度阈值
    include_docstrings: bool = True    # 是否包含文档字符串
    include_signatures: bool = True    # 是否包含函数签名
```

**返回值 QueryResult**：

```python
@dataclass
class QueryResult:
    query: str                         # 原始查询
    seed_nodes: list[SearchResult]     # 种子节点（直接命中）
    expanded_nodes: list[SearchResult] # 扩展节点（图拓扑扩展）
    expanded_edges: list[Edge]         # 扩展边
    total_time_ms: float               # 查询耗时（毫秒）

@dataclass
class SearchResult:
    symbol_id: int
    symbol_name: str
    symbol_type: str                   # class / function / method
    qualified_name: str                # 完整限定名
    file_path: str
    start_line: int
    end_line: int
    score: float                       # 综合得分
    docstring: str | None
    signature: str | None
    code_snippet: str | None           # 代码片段

@dataclass
class Edge:
    source_id: int
    target_id: int
    edge_type: str                     # calls / imports / inherits
    confidence: float
```

**示例**：

```python
service = QueryService()
result = service.search("用户认证流程", QueryOptions(
    top_k=5,
    expand_hops=2,
    mode="hybrid"
))

for item in result.seed_nodes:
    print(f"[{item.score:.2f}] {item.qualified_name} ({item.file_path}:{item.start_line})")
```

---

### 3.2 get_symbol_info

获取符号的详细信息。

```python
def get_symbol_info(self, symbol_id: int) -> SymbolInfo
```

**参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `symbol_id` | `int` | 是 | 符号 ID |

**返回值 SymbolInfo**：

```python
@dataclass
class SymbolInfo:
    id: int
    name: str
    type: str                          # class / function / method
    qualified_name: str
    file_path: str
    start_line: int
    end_line: int
    docstring: str | None
    signature: str | None
    source_code: str                   # 完整源代码
    type_info: list[TypeInfo]          # 类型信息
    callers: list[SymbolRef]           # 调用者（谁调用了我）
    callees: list[SymbolRef]           # 被调用者（我调用了谁）
    imports: list[ImportRef]           # 导入关系
    inherits: list[InheritRef]         # 继承关系
    file: FileInfo                     # 所属文件信息

@dataclass
class TypeInfo:
    parameter_name: str | None
    type_annotation: str | None        # 显式类型提示
    inferred_type: str | None          # 推断类型
    confidence: float                  # 置信度
    strategy: str                      # 推断策略

@dataclass
class SymbolRef:
    symbol_id: int
    symbol_name: str
    file_path: str
    line_number: int
    edge_type: str
    confidence: float
```

---

### 3.3 get_call_graph

获取符号的调用图。

```python
def get_call_graph(self, symbol_id: int, depth: int = 2) -> CallGraphResult
```

**参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `symbol_id` | `int` | 是 | 根符号 ID |
| `depth` | `int` | 否 | 调用图深度（默认 2） |

**返回值 CallGraphResult**：

```python
@dataclass
class CallGraphResult:
    root: SymbolInfo                   # 根节点
    nodes: list[SymbolInfo]            # 所有节点
    edges: list[Edge]                  # 所有边
    depth: int                         # 实际深度
    total_nodes: int
    truncated: bool                    # 是否因节点数限制而截断
```

---

### 3.4 get_dependencies

获取符号的依赖关系。

```python
def get_dependencies(self, symbol_id: int) -> DependencyResult
```

**返回值 DependencyResult**：

```python
@dataclass
class DependencyResult:
    symbol: SymbolInfo
    direct_imports: list[ImportRef]    # 直接导入
    transitive_imports: list[ImportRef] # 传递导入
    dependents: list[SymbolRef]        # 被依赖（谁导入了我）
    coupling_score: float              # 耦合度评分
```

---

## 4. RCAService — 根因分析服务

负责 Stack Trace 解析、根因定位和修复方案生成。

### 4.1 analyze_trace

分析 Stack Trace。

```python
def analyze_trace(self, trace: str) -> RCAResult
```

**参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `trace` | `str` | 是 | Stack Trace 文本 |

**返回值 RCAResult**：

```python
@dataclass
class RCAResult:
    success: bool
    error_type: str                    # 异常类型
    error_message: str                 # 异常信息
    proximate_cause: ProximateCause    # 直接原因
    call_chain: list[CallFrame]        # 调用链
    root_cause_analysis: str           # 根因分析文本
    fix_suggestions: list[FixSuggestion] # 修复建议
    mermaid_diagram: str               # 调用链 Mermaid 图
    elapsed_seconds: float

@dataclass
class ProximateCause:
    file_path: str
    line_number: int
    function_name: str
    class_name: str | None
    source_code: str                   # 出错行的源代码
    context_code: str                  # 周围上下文代码

@dataclass
class CallFrame:
    file_path: str
    line_number: int
    function_name: str
    class_name: str | None
    code_snippet: str

@dataclass
class FixSuggestion:
    description: str                   # 修复描述
    diff: str                          # Diff 格式的修复补丁
    confidence: float                  # 置信度
    affected_files: list[str]          # 影响的文件
```

---

### 4.2 analyze_issue

从 Issue 描述中分析问题。

```python
def analyze_issue(self, issue: str) -> RCAResult
```

**参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `issue` | `str` | 是 | Issue 描述文本 |

**返回值**：同 `analyze_trace`

---

### 4.3 generate_fix

基于 RCA 结果生成修复补丁。

```python
def generate_fix(self, rca: RCAResult) -> FixResult
```

**参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `rca` | `RCAResult` | 是 | RCA 分析结果 |

**返回值 FixResult**：

```python
@dataclass
class FixResult:
    success: bool
    patches: list[Patch]               # 修复补丁列表
    test_code: str                     # 生成的测试代码
    explanation: str                   # 修复说明

@dataclass
class Patch:
    file_path: str                     # 目标文件
    diff: str                          # Diff 格式
    description: str                   # 补丁描述
```

---

### 4.4 validate_fix

在沙箱中验证修复补丁。

```python
def validate_fix(self, fix: FixResult, sandbox: bool = True) -> ValidationResult
```

**参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `fix` | `FixResult` | 是 | 修复补丁 |
| `sandbox` | `bool` | 否 | 是否使用沙箱（默认 True） |

**返回值 ValidationResult**：

```python
@dataclass
class ValidationResult:
    success: bool
    test_passed: bool                  # 测试是否通过
    test_output: str                   # 测试输出
    regression_passed: bool            # 回归测试是否通过
    regression_output: str             # 回归测试输出
    elapsed_seconds: float
```

---

## 5. VisualizationService — 可视化服务

负责生成架构可视化图表。

### 5.1 generate_mermaid

生成 Mermaid 格式的图表。

```python
def generate_mermaid(
    self,
    symbol_id: int,
    depth: int = 2,
    graph_type: str = "call"
) -> str
```

**参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `symbol_id` | `int` | 是 | 起始符号 ID |
| `depth` | `int` | 否 | 图深度（默认 2） |
| `graph_type` | `str` | 否 | 图类型：`call` / `dependency` / `inherit` / `import` |

**返回值**：`str` — Mermaid Markdown 文本

**示例**：

```python
service = VisualizationService()
mermaid_text = service.generate_mermaid(
    symbol_id=42,
    depth=3,
    graph_type="call"
)
print(mermaid_text)
# graph TD
#     A[AuthService] --> B[TokenManager]
#     A --> C[UserRepository]
#     ...
```

---

### 5.2 generate_d3_data

生成 D3.js 兼容的图数据。

```python
def generate_d3_data(
    self,
    symbol_id: int,
    depth: int = 2,
    graph_type: str = "call"
) -> dict
```

**返回值**：

```python
{
    "nodes": [
        {
            "id": 1,
            "name": "AuthService",
            "type": "class",
            "file": "auth/service.py",
            "group": "auth"
        },
        ...
    ],
    "links": [
        {
            "source": 1,
            "target": 2,
            "type": "calls",
            "confidence": 0.95
        },
        ...
    ]
}
```

---

### 5.3 generate_dot

生成 Graphviz DOT 格式。

```python
def generate_dot(
    self,
    symbol_id: int,
    depth: int = 2,
    graph_type: str = "call"
) -> str
```

**返回值**：`str` — DOT 格式文本

---

## 6. 数据模型参考

### 6.1 枚举类型

```python
from enum import Enum

class SymbolType(str, Enum):
    CLASS = "class"
    FUNCTION = "function"
    METHOD = "method"

class EdgeType(str, Enum):
    CALLS = "calls"
    IMPORTS = "imports"
    INHERITS = "inherits"
    IMPLEMENTS = "implements"

class SearchMode(str, Enum):
    KEYWORD = "keyword"
    SEMANTIC = "semantic"
    HYBRID = "hybrid"

class GraphType(str, Enum):
    CALL = "call"
    DEPENDENCY = "dependency"
    INHERIT = "inherit"
    IMPORT = "import"

class InferenceStrategy(str, Enum):
    EXPLICIT_HINT = "explicit_hint"       # 置信度 0.95
    IMPORT_MAPPING = "import_mapping"     # 置信度 0.90
    SELF_INFERENCE = "self_inference"     # 置信度 0.85
    ASSIGNMENT = "assignment"             # 置信度 0.70
    JEDI = "jedi"                         # 置信度 0.60
    DUCK_TYPING = "duck_typing"           # 置信度 0.40
```

### 6.2 异常类

```python
class RepoMindError(Exception):
    """基础异常类"""
    pass

class PathNotFoundError(RepoMindError):
    """路径不存在"""
    pass

class InvalidLanguageError(RepoMindError):
    """不支持的语言"""
    pass

class IndexBuildError(RepoMindError):
    """索引构建失败"""
    pass

class IndexNotFoundError(RepoMindError):
    """索引不存在"""
    pass

class SymbolNotFoundError(RepoMindError):
    """符号未找到"""
    pass

class SandboxError(RepoMindError):
    """沙箱执行错误"""
    pass

class LLMError(RepoMindError):
    """LLM 调用错误"""
    pass
```

---

## 7. 使用示例

### 7.1 完整工作流

```python
from repomind.services import IndexService, QueryService, RCAService, VisualizationService
from repomind.models import IndexOptions, QueryOptions

# 1. 索引
index_svc = IndexService()
result = index_svc.index_directory("./my-project", IndexOptions(verbose=True))
print(f"索引完成: {result.total_symbols} 个符号, 耗时 {result.elapsed_seconds:.1f}s")

# 2. 查询
query_svc = QueryService()
results = query_svc.search("用户认证", QueryOptions(top_k=5, expand_hops=2))
for item in results.seed_nodes:
    print(f"  [{item.score:.2f}] {item.qualified_name}")

# 3. 获取调用图
graph = query_svc.get_call_graph(results.seed_nodes[0].symbol_id, depth=2)
print(f"调用图: {graph.total_nodes} 个节点")

# 4. RCA
rca_svc = RCAService()
trace = """
Traceback (most recent call last):
  File "app/auth.py", line 42, in login
    user = authenticate(username, password)
AuthenticationError: Invalid credentials
"""
rca_result = rca_svc.analyze_trace(trace)
print(f"根因: {rca_result.proximate_cause.function_name}")

# 5. 可视化
viz_svc = VisualizationService()
mermaid = viz_svc.generate_mermaid(
    results.seed_nodes[0].symbol_id,
    depth=2,
    graph_type="call"
)
print(mermaid)
```

### 7.2 错误处理

```python
from repomind.models import RepoMindError, IndexNotFoundError, SymbolNotFoundError

try:
    result = query_svc.search("不存在的符号")
except IndexNotFoundError:
    print("请先运行 repomind index 构建索引")
except SymbolNotFoundError as e:
    print(f"符号未找到: {e}")
except RepoMindError as e:
    print(f"操作失败: {e}")
```
