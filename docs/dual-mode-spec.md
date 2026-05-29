# 双模式对话设计规格

## 概述

用户可在快速模式 / 高质量模式之间切换，影响 Agent 的处理策略。

## 前端

### UI 位置
聊天输入框下方，提示文字左侧，一个切换开关：

```
[输入你的问题...] [发送]
○ 快速  ● 高质量    Ctrl+Enter 发送
```

### 交互
- 默认选中**快速模式**（覆盖 80% 的日常查询）
- 点击切换，当前会话后续消息使用新模式
- 切换后不需要刷新页面，即时生效
- 模式选择跟随会话（session.metadata 存储）

### API 变更
```typescript
// 发送消息时带上模式选择
sendMessage(message: string, sessionId?: string, dbId?: string, mode?: string)
```

```json
POST /api/chat
{
  "message": "帮我分析一下销售趋势",
  "session_id": "abc123",
  "db_id": "aw01",
  "mode": "quality"    // "fast" | "quality"
}
```

### 后端 ChatRequest 变更
```python
class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    db_id: str | None = None
    mode: str = "fast"  # "fast" | "quality"
```

---

## 后端：快速模式 (Fast / ReAct)

**与当前行为完全一致。**

```
用户消息 → Agent Loop (ReAct) → 最终回复

Agent Loop:
  第 1 轮: 调工具 / 直接回复
  第 2-X 轮: 观察结果 → 继续或结束
  上限: 10 轮
```

无需改动。

---

## 后端：高质量模式 (Quality / Plan → ReAct → Reflect)

### 阶段一：Plan（制定分析计划）

```
用户: "帮我分析一下销售趋势"
  ↓
系统 prompt 替换为 Plan prompt:
  "你是数据分析规划师。不要查数据，先根据用户问题和数据库结构
   制定分析计划。计划包含：
   1. 分析维度（按什么角度分析）
   2. 需要查询哪些数据
   3. 查询的顺序（先查什么、后查什么）
   
   输出格式：
   ## 分析计划
   ### 维度
   列出你要分析的维度
   ### 查询步骤
   1. 第一步：查询内容 → 为什么
   2. 第二步：查询内容 → 为什么
   3. ...
   
   以「是否按此计划执行？」结尾"
  ↓
Agent 输出计划给用户确认
```

**关键规则：**
- Plan 阶段**不注册任何工具**（`tools=[]` 或 `tools=None`）
- 强制 LLM 输出为文本计划，不能调数据
- 计划输出后，**不等用户确认，直接进入 ReAct 执行**

### 阶段二：ReAct（按计划执行）

```
  ↓
系统 prompt 替换为执行 prompt:
  "你正在执行以下分析计划：
   {上一步输出的计划全文}
   
   按计划步骤依次执行，每步调用 query_database 工具查询。
   完成后，进入下一步分析并输出阶段性发现。"
  ↓
Agent 按计划逐步执行，每步调工具、记录结果
```

**关键规则：**
- 注册 `query_database` 工具
- 使用 `tool_choice="auto"`（由模型决定要不要进一步查）
- 最大迭代轮数放宽到 **15 轮**（因为按计划执行可能多步）
- 每步完成后，让 Agent 输出阶段性总结

### 阶段三：Reflect（回顾与总结）

```
所有计划步骤执行完毕
  ↓
系统 prompt 替换为 Reflect prompt:
  "回顾刚才的分析过程和结果：
   1. 所有查询是否成功执行？
   2. 结果是否能回答用户的问题？
   3. 有没有什么有趣的发现或异常？
   4. 还需要补充什么信息吗？
   
   如果有需要补充的查询，可以继续调用 query_database。
   如果已经充分分析了，输出最终的汇总报告。"
  ↓
Agent 回顾结果 → 决定是否补充查询 → 输出最终报告
```

**关键规则：**
- Reflect 阶段**不注册工具**（防止死循环查数据）
- 让 Agent 基于已有的工具结果做分析
- 输出最终报告后结束

---

## 状态流转

```
[模式切换]

fast mode:   用户消息 → [ReAct loop] → 回复

quality mode: 用户消息 → [Plan (no tools)] → 计划文本
                        → [ReAct with plan (tools)] → 各步骤结果
                        → [Reflect (no tools)] → 汇总报告 → 回复
```

## 需要改动的文件

| 文件 | 改动 |
|------|------|
| `backend/app/models/schemas.py` | `ChatRequest` 加 `mode` 字段 |
| `backend/app/agent/loop.py` | 接受 `mode` 参数，支持三阶段 |
| `backend/app/agent/plan_prompts.py` | Plan / Reflect 系统 prompt 模板 |
| `backend/app/main.py` | `chat()` 根据 mode 调整行为 |
| `frontend/src/api/index.ts` | `sendMessage` 加 `mode` 参数 |
| `frontend/src/App.tsx` | 加 `mode` 状态 + 传给 sendMessage |
| `frontend/src/components/Chat.tsx` | 输入框旁加模式切换 UI |
