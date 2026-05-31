# LLM 采样参数限制移至 LLM 模型管理页面 - 变更日志

## 背景

将"高级设置"中的"LLM 采样参数限制"（温度 min/max/default）移至"LLM 模型管理"页面，使 LLM 相关配置集中管理。

## 修改文件清单

### 前端

1. [LLMSettingsTab.tsx](file:///Users/chendong/Projects/agentic-data-analyst/frontend/src/pages/AdminSettings/tabs/LLMSettingsTab.tsx)
   - 新增 `tempMin`/`tempMax`/`tempDefault` 状态变量，初始化自 `config.advanced.llm_temperature_range`
   - 在"全局策略"卡片下方新增"LLM 采样参数限制"卡片，包含温度 min/max 输入框和 default 滑动条
   - 更新 `handleSaveAll` 保存时包含 `llm_temperature_range`

2. [AdvancedSettingsTab.tsx](file:///Users/chendong/Projects/agentic-data-analyst/frontend/src/pages/AdminSettings/tabs/AdvancedSettingsTab.tsx)
   - 移除温度相关状态变量 (`tempMin`/`tempMax`/`tempDefault`)
   - 移除"LLM 采样参数限制"整个 UI 区块
   - 移除 `onSave` 中的 `llm_temperature_range` 字段
   - 将原双列布局改为单列布局，仅保留"会话与性能"区块

3. [en-US.json](file:///Users/chendong/Projects/agentic-data-analyst/frontend/src/i18n/locales/en-US.json)
   - 在 `llmSettings` 下新增 `samplingSection`/`temperatureMin`/`temperatureMax`/`temperatureDefault`/`temperatureHint` 翻译键

4. [zh-CN.json](file:///Users/chendong/Projects/agentic-data-analyst/frontend/src/i18n/locales/zh-CN.json)
   - 在 `llmSettings` 下新增 `samplingSection`/`temperatureMin`/`temperatureMax`/`temperatureDefault`/`temperatureHint` 翻译键

## 验证

- 前端 TypeScript 编译通过 (`tsc --noEmit` 无错误)
- 前端 120 个测试全部通过
- 后端 234 个测试全部通过
