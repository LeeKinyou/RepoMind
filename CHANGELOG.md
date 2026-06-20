# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- 项目初始化
- 完整文档体系搭建

### Fixed
- **Critical 修复**
  - GraphStore 持久化：索引后序列化到磁盘，查询/ RCA 服务自动加载（C1）
  - VectorStore SQL 注入：`delete()` 方法转义单引号（C2）
  - config 整数解析：`_safe_int()` 防御非法环境变量（C3）
  - RRF 融合公式：按 source 分组计算真实排名，替代 `int(1/score)` 近似（C4）

- **High 修复**
  - Windows 路径兼容：统一使用 `path_to_module()` + `PurePosixPath`（H1）
  - SQLite 连接复用：`_get_conn()` 懒加载，避免每次操作开关连接（H2）
  - TypeInference 集成：索引时自动调用推断引擎并存储结果（H3）
  - import alias 提取：解析 `as` 关键字后的别名（H4）
  - 向量维度参数化：`VectorStore` 支持 `embedding_dim` 配置（H5）

- **Medium 修复**
  - SymbolType 显式转换 + 回退（M1）
  - 符号解析逻辑统一到 `SymbolResolver`（M2）
  - docstring 三引号正确剥离（M3）
  - DuckType 输出排序稳定（M4）
  - BM25Index.build() 状态重置（M5）
  - 增量索引事务内清理旧数据（M6）
  - LIKE 通配符转义（M7）

- **Low 修复**
  - `import re` 移至文件顶部（L1）
  - `VectorEntry.metadata` 使用 `Field(default_factory=dict)`（L2）
  - `clear()` 使用 `frozenset` 白名单校验表名（L3）

- **TDD 补充修复（第二轮审查）**
  - GraphStore HMAC-SHA256 签名验证（C6）
  - Parser import 精确提取，避免重复（H4 补充）
  - Parser 函数体递归遍历，提取内部调用
  - TypeInference `infer()` 参数名统一为 `name`
  - `_strategy_self_inference` 行号偏移修正
  - config `get()` 空字符串语义修复（H6）

- **v2 审查修复（第三轮）**
  - `_safe_symbol_type` 提取到 schemas.py 消除重复定义（H10）
  - GraphStore.get_subgraph 使用 safe_symbol_type 转换类型（H11）
  - 签名提取改用 body_node 精确切取，支持类型注解（H7）
  - 返回类型解析改用正则，支持复杂泛型（H8）
  - _extract_call 后继续递归，修复嵌套调用丢失（H13）
  - IndexService 构建 symbol_index 传入 resolve_callee（C5）
  - symbol_index 改为 dict[str, list[str]] 避免同名覆盖（M12）
  - BM25 分词按 `_.\s` 分割，支持代码符号搜索（M13）
  - VisualizationService._node_shape 改用 SymbolType 枚举（M14）
  - CLI query 命令显示 answer 字段（M15）
  - duck_typing 排除注释行和行内注释（M16）
  - RCA _frame_to_qname 统一使用 path_to_module（M18）
  - VectorStore._get_table 异常捕获收窄（L8）
  - _collect_files fp.stat() 添加 TOCTOU 防御（L9）
  - docstring 提取处理 f/r/b 前缀（L10）
  - CLI rca 命令添加 trace_file 不存在检查（L11）
  - jedi 延迟到 _strategy_jedi 方法内导入（L5）
  - GraphStore 持久化从 pickle 迁移到 JSON（C6）
  - relative_to 单独捕获 ValueError（M9）

- **测试**
  - 新增 12 个测试文件，138 个测试用例
  - 覆盖全部公开 API（模型、存储、引擎、服务、CLI）
  - 单元测试 + 集成测试
  - ruff check 零错误

## [0.1.0] - 2026-06-20

### Added
- **核心解析引擎**
  - Tree-sitter Python 语法解析器
  - 符号提取（类、函数、方法、导入）
  - Python Type Hints 提取

- **渐进式类型推断**
  - 显式类型提示推断（置信度 0.95）
  - Import 映射绑定（置信度 0.90）
  - self 参数类型推断（置信度 0.85）
  - 赋值语句推断（置信度 0.70）
  - Jedi 引擎推断（置信度 0.60）
  - 鸭子类型匹配（置信度 0.40）

- **调用图构建**
  - 直接函数调用关系
  - 对象方法调用关系
  - self 调用关系
  - 鸭子类型推断调用

- **混合检索**
  - BM25 关键字检索
  - 向量语义检索（LanceDB + jina-code）
  - RRF 结果融合
  - 图拓扑 2-hop 扩展

- **根因分析**
  - Stack Trace 正则解析
  - 符号定位与图谱对齐
  - LLM 根因分析
  - 修复建议生成
  - Docker 沙箱验证

- **架构可视化**
  - Mermaid 调用图生成
  - Mermaid 依赖图生成
  - Mermaid 继承图生成
  - D3.js 数据导出

- **CLI 命令**
  - `repomind index` — 项目索引构建
  - `repomind query` — 智能查询
  - `repomind rca` — 根因分析
  - `repomind visualize` — 架构可视化
  - `repomind stats` — 索引统计

- **存储层**
  - SQLite 结构化存储
  - LanceDB 向量存储
  - NetworkX 内存图计算

- **安全机制**
  - Docker 沙箱隔离
  - 命令白名单过滤
  - Prompt 注入防御
  - 输出敏感信息过滤
  - 审计日志

- **文档**
  - README.md
  - 问题定义文档
  - 需求分析文档
  - 技术可行性调研文档
  - 技术架构文档
  - 产品设计文档
  - 开发环境搭建指南
  - 用户使用手册
  - API 接口文档
  - 数据库设计文档
  - 测试计划文档
  - 安全设计文档
  - 架构决策记录
