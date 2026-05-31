# LLM 配置页面重构设计文档

## 1. 需求背景
当前 LLM 配置较为分散且固定，无法满足多模型管理、连通性实时展示以及个人偏好设置的需求。用户期望能够：
- 默认展示已配置且连通的大模型。
- 支持在页面添加新模型。
- 支持设置系统级默认模型，同时允许每个用户有自己的默认模型。
- 确保存储的安全性和一致性。

## 2. 核心设计变更

### 2.1 数据模型 (Data Model)
将 `system_config` 中的 `llm` 部分从简单的“提供商池”升级为“模型实例管理”。

#### 系统配置 (`system_config.llm`)
```json
{
  "models": [
    {
      "id": "uuid-1",
      "name": "生产级 OpenAI",
      "provider": "openai",
      "model": "gpt-4o",
      "api_key": "sk-...", // 存储时加密或脱敏处理
      "api_base": "https://api.openai.com/v1",
      "timeout": 120,
      "enabled": true,
      "is_connected": true, // 缓存的连接状态
      "is_system_default": true
    }
  ]
}
```

#### 用户配置 (`user_configs.llm`)
```json
{
  "default_model_id": "uuid-1" // 用户选中的默认模型 ID
}
```

### 2.2 后端逻辑变更
- **模型管理**: 增加添加、编辑、删除模型实例的接口。
- **连通性测试**: 提供 `/api/config/llm/test` 接口，支持对特定实例 ID 或即时输入的配置进行连通性测试。
- **配置合并**: `get_merged_config` 将根据用户 ID 获取其 `default_model_id`。如果未设置，则回退到系统级的 `is_system_default` 模型。
- **存储安全**: 
    - API Key 在保存前进行简单加密或至少在返回前端时进行脱敏处理（如 `sk-...abcd`）。
    - 确保任何时候都有且仅有一个系统默认模型。

### 2.3 前端 UI 重构

#### 状态栏展示 (`StatusBar.tsx`)
- **位置**: 页面右下角。
- **内容**: 
    - 展示当前选中的模型友好名称（`name`）。
    - 实时状态灯：
        - **绿色**: 连接成功。
        - **灰色/红色**: 连接失败或检测中。
- **交互**: 鼠标悬停显示详细错误信息或连通时间。

#### 管理员设置页 (`AdminSettingsPage.tsx`)
- **模型管理列表**: 
    - 采用网格或列表布局，每个卡片显示模型名称、模型 ID（如 `gpt-4o`）、提供商图标/文字。
    - **状态标识**: 显眼的连通性状态（在线/离线）。
    - **操作按钮**:
        - **编辑**: 修改 API Key、Base URL 等信息。
        - **测试**: 立即触发后端连通性测试。
        - **设为默认**: 一键切换系统全局默认模型。
        - **删除**: 移除模型实例。
- **添加模型对话框**: 
    - 支持快速选择常见 Provider (OpenAI, DeepSeek, Ollama, Anthropic, Azure)。
    - 表单字段：显示名称、模型 ID、API Key、Base URL、超时时间。
    - 包含“保存前测试”功能。

#### 连通性检测机制
- **初次加载**: App 启动时自动触发一次全局默认模型的连通性检查。
- **轮询检测**: 前端每隔 2 分钟（可配置）自动调用一次 `/api/config/llm/test` 以确保状态真实。
- **手动触发**: 用户切换默认模型或修改配置后，立即触发检测。

## 3. 任务列表 (Todo List)

### 阶段 1: 后端服务升级
- [x] 扩展 `SystemConfig` 类型定义，支持 `models` 列表。
- [x] 修改 `service.py` 中的 `update_system_config` 以处理模型实例的增删改。
- [x] 实现连通性测试的后端逻辑，并支持状态缓存。
- [x] 更新 `get_merged_config` 逻辑，支持基于 ID 的默认模型查找。
- [x] 新增 `get_system_config_masked()` 返回脱敏后的配置。
- [x] 新增 `_ensure_default_model()` 确保 `is_system_default` 唯一性。

### 阶段 2: 前端页面重构
- [x] 更新 `types/index.ts` 中的配置接口（`LLMModelInstance` + `SystemConfig`）。
- [x] 重构 `LLMSettingsTab`：
    - [x] 实现模型实例列表展示（卡片布局，含启用/禁用、默认标识、连通状态）。
    - [x] 实现添加/编辑模型对话框（支持常见供应商快速填充）。
    - [x] 实现连通性测试交互（列表内即时测试 + 对话框内保存前测试）。
- [x] `StatusBar` 右下角显示当前模型名称 + 真实连通状态（2分钟轮询检测）。

### 阶段 3: 存储与安全优化
- [x] 实现 API Key 的脱敏逻辑（`_mask_api_key` + `get_system_config_masked`）。
- [x] 确保 `system_config` 更新时的事务性和默认模型唯一性校验（`_ensure_default_model`）。
- [x] API Key 保存时反脱敏合并（`_unmask_and_merge_api_keys`）。

## 4. 存储注意事项
1. **唯一性**: 增加校验逻辑，确保 `is_system_default` 在模型列表中唯一。
2. **脱敏**: 接口返回 `SystemConfig` 时，对 `api_key` 进行掩码处理。
3. **备份**: 每次重大配置变更（如删除模型）前，自动触发 `config_changelog` 记录。
