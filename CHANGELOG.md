# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- 项目初始化
- 完整文档体系搭建

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
