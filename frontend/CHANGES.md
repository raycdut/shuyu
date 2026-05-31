# 字体优化变更记录

## 2026-05-31

### 问题
页面字体在某些场景下不够清晰，小字可读性差。

### 修改内容

#### 1. `index.html`
- Google Fonts 新增加载 **Noto Sans SC**（无衬线屏显优化字体），权重 400/500/600
- 用于 body 默认字体栈，提升正文可读性

#### 2. `tailwind.config.js`
- **`font-sans`** 字体栈扩展：
  - 新增 `-apple-system`、`BlinkMacSystemFont`（macOS 系统 UI 字体）
  - 新增 `Hiragino Sans GB`（macOS 备选中文清晰字体）
  - 新增 `Noto Sans SC`（跨平台 Google 无衬线中文字体）
  - 保持 `PingFang SC`、`Microsoft YaHei` 作为主要中文回退
- **`font-kai`** 字体优先级调整：
  - 将系统 `KaiTi` 提升到首位（清晰、标准）
  - `ZCOOL XiaoWei` 降为末位备选（装饰性字体，小字号不清晰）
- **`font-song` 和 `font-kai`** 新增中文回退字体：
  - 修复两个字体栈末尾使用 `serif`（macOS 上为 Times New Roman，无中文字形）的问题
  - 统一在 `serif` 之前添加 `PingFang SC` 作为中文保底回退
  - 修复"返回聊天"按钮因字体回退到 Times New Roman 而显示方块字的问题

#### 3. `src/index.css`
- **移除 `antialiased`**：改为使用浏览器默认字体平滑（`-webkit-font-smoothing: auto`），解决文字过细/发虚问题
- **新增 `leading-relaxed`**：行高从默认 1.2 提升到 1.625，改善中文正文阅读体验
- **新增 `tracking-wide`**：添加微弱的字间距，提升中文文字辨识度

### 验证
- TypeScript 编译：通过
- Vite 生产构建：通过
- 全部 44 项测试：通过
