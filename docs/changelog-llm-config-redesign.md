# LLM 配置页面重构 - 变更日志

## 修改文件清单

### 后端 (Python)
1. [service.py](file:///Users/chendong/Projects/agentic-data-analyst/backend/app/admin_config/service.py)
   - `DEFAULT_SYSTEM_CONFIG`: 从 `provider_pool` 升级为 `models` 列表模型
   - 新增 `_mask_api_key()`: API Key 脱敏辅助函数
   - 新增 `_unmask_and_merge_api_keys()`: 保存时反脱敏合并逻辑
   - 新增 `_ensure_default_model()`: 确保 `is_system_default` 唯一性
   - 更新 `update_system_config()`: 支持 models 列表全量替换（非 dict 合并）
   - 新增 `get_system_config_masked()`: 返回脱敏后的系统配置
   - 更新 `_system_to_runtime()`: 基于 `models` 列表查找默认模型
   - 更新 `_merge_configs()`: 支持用户 `default_model_id` 覆盖
   - 更新 `get_user_available_options()`: 适配 `models` 结构并返回 `models` 列表

2. [router.py](file:///Users/chendong/Projects/agentic-data-analyst/backend/app/admin_config/router.py)
   - 导入 `get_system_config_masked`
   - `GET /api/admin/config` 改用 `get_system_config_masked()` 返回脱敏数据

3. [routes/config.py](file:///Users/chendong/Projects/agentic-data-analyst/backend/app/routes/config.py)
   - `GET /api/config` 返回 `id` 和 `name` 字段
   - `POST /api/config/llm/test` 使用 merged config 获取 API Key/Base/Model

### 前端 (TypeScript/React)
4. [types/index.ts](file:///Users/chendong/Projects/agentic-data-analyst/frontend/src/types/index.ts)
   - 新增 `LLMModelInstance` 接口
   - `SystemConfig.llm` 从 `provider_pool` 改为 `models`
   - `LLMConfig` 新增 `id` 和 `name` 字段
   - `UserAvailableOptions.llm` 新增 `models` 列表

5. [store/index.ts](file:///Users/chendong/Projects/agentic-data-analyst/frontend/src/store/index.ts)
   - `llmConfig` 初始状态增加 `name` 字段

6. [api/index.ts](file:///Users/chendong/Projects/agentic-data-analyst/frontend/src/api/index.ts)
   - `testLLM` 接口增加 `provider` 参数

7. [App.tsx](file:///Users/chendong/Projects/agentic-data-analyst/frontend/src/App.tsx)
   - StatusBar 传入 `llmName` 显示友好名称
   - 增加 2 分钟间隔的轮询连通性检测（`setInterval(checkLLM, 120000)`）

8. [StatusBar.tsx](file:///Users/chendong/Projects/agentic-data-analyst/frontend/src/components/StatusBar.tsx)
   - 新增 `llmName` prop
   - 显示 `llmName || llmModel`（优先显示友好名称）
   - tooltip 显示完整 model id

9. [AdminSettingsPage.tsx](file:///Users/chendong/Projects/agentic-data-analyst/frontend/src/pages/AdminSettingsPage.tsx)
   - `LLMSettingsTab` 完全重构：
     - 模型实例卡片列表（启用开关、名称、供应商/模型、默认标识）
     - 连通状态实时显示（绿色/红色/灰色）
     - 操作按钮：测试、设为默认、编辑、删除
   - 新增 `ModelDialog` 组件：
     - 添加/编辑模型表单
     - 常见供应商快速选择（OpenAI/DeepSeek/Azure/Anthropic/Ollama/自定义）
     - 内置测试连接功能

### 文档
10. [llm-config-redesign.md](file:///Users/chendong/Projects/agentic-data-analyst/docs/llm-config-redesign.md)
    - 更新状态栏展示设计
    - 更新连通性检测机制设计
    - 更新全部任务标记为已完成

### 数据库迁移
11. [persistence/__init__.py](file:///Users/chendong/Projects/agentic-data-analyst/backend/app/persistence/__init__.py)
    - 新增 `_migrate_llm_providers_to_models()` 迁移函数
    - 在 `_migrate_config_tables()` 完成后自动调用
    - 处理 3 种场景：
      - `system_config` 不存在 → 从 `llm_providers` 创建
      - `system_config` 存在但无 `models` → 合并（含旧 `provider_pool` 兼容）
      - `system_config` 已有 `models` → 跳过（幂等）
    - 迁移时自动补全 API Base URL（针对常见供应商）

## 核心架构变更

```
旧: system_config.llm = { provider_pool: [{provider, label, models[], enabled}], default_model: "gpt-4o" }
新: system_config.llm = { models: [{id, name, provider, model, api_key, api_base, timeout, enabled, is_system_default}] }
```

- 每个模型实例独立存储自己的 API Key/Base URL
- `is_system_default` 确保全局唯一
- API Key 返回前端时自动脱敏，保存时自动反合并
- 用户可通过 `default_model_id` 设置个人默认模型
