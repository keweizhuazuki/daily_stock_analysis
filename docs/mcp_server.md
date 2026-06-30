# MCP Server — DSA Watchlist & Stock Tools

将 Daily Stock Analysis 的自选股管理、行情查询和分析触发能力暴露为
**MCP (Model Context Protocol)** 工具，供 Claude Desktop、Claude Code、
Cursor 等 AI 客户端直接调用。

## 快速开始

### 1. 安装依赖

```bash
pip install mcp>=1.0.0
```

或重新安装项目依赖：

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

在 `.env` 中添加（可选，默认值已可用）：

```ini
# 启用 MCP Server（默认 false）
MCP_SERVER_ENABLED=true

# 传输模式：stdio（默认）或 sse
MCP_SERVER_TRANSPORT=stdio

# SSE 模式相关（仅 MCP_SERVER_TRANSPORT=sse 时生效）
MCP_SERVER_HOST=127.0.0.1
MCP_SERVER_PORT=8080
```

### 3. 运行

**Stdio 模式（用于 Claude Desktop）：**

```bash
python -m mcp_server
```

**SSE 模式（用于远程客户端）：**

```bash
MCP_SERVER_TRANSPORT=sse python -m mcp_server
```

**与 FastAPI 共存（SSE 模式）：**

```bash
MCP_SERVER_ENABLED=true MCP_SERVER_TRANSPORT=sse python server.py
```

## 接入 Claude Desktop

编辑 Claude Desktop 配置文件：

- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "dsa-watchlist": {
      "command": "python",
      "args": ["-m", "mcp_server"],
      "cwd": "/path/to/daily_stock_analysis"
    }
  }
}
```

重启 Claude Desktop 后，即可在对话中使用以下工具。

## 可用工具

### 自选股管理

| 工具 | 参数 | 说明 |
|------|------|------|
| `list_watchlist` | (无) | 列出当前自选股列表 |
| `add_stock` | `stock_code: str` | 添加股票到自选股 |
| `remove_stock` | `stock_code: str` | 从自选股中删除股票 |

**支持的股票代码格式：**

- A股：`600519`、`SH600519`、`600519.SH`
- 港股：`HK00700`、`00700.HK`、`00700`
- 美股：`AAPL`、`TSLA`

### 行情查询

| 工具 | 参数 | 说明 |
|------|------|------|
| `search_stock` | `query: str`, `include_quote?: bool` | 按代码/名称搜索股票 |
| `get_stock_quote` | `stock_code: str` | 获取实时行情 |
| `get_stock_history` | `stock_code: str`, `period?: str`, `days?: int` | 获取历史K线数据 |

### 分析触发

| 工具 | 参数 | 说明 |
|------|------|------|
| `trigger_analysis` | `stock_codes?: list[str]` | 触发AI分析（默认分析全部自选股） |
| `get_analysis_status` | `query_id: str` | 查询分析任务状态 |

## 对话示例

在 Claude Desktop 中：

> **你**: 帮我把茅台加入自选股
>
> **Claude**: (调用 `search_stock("茅台")` → 找到 `600519` 贵州茅台 → 调用 `add_stock("600519")`)
> 已将贵州茅台 (600519) 加入自选股，当前共 5 只股票。

> **你**: 分析我的自选股
>
> **Claude**: (调用 `trigger_analysis()` → 提交分析任务)
> 已提交 5 只股票的分析任务。分析完成后你会收到通知。

## Bot 集成

自选股管理也支持通过机器人在对话中操作：

| 命令 | 说明 |
|------|------|
| `/wl` | 查看自选股列表 |
| `/wl add <代码>` | 添加股票 |
| `/wl remove <代码>` | 删除股票 |
| `/wl help` | 显示帮助 |

支持的平台：飞书、Discord、钉钉。

## 架构

```
AI Client (Claude Desktop/Code)
        │ MCP (stdio/SSE)
        ▼
┌──────────────────┐
│  mcp_server/     │
│  ├─ server.py    │  FastMCP 实例 + 工具注册
│  └─ tools/       │
│     ├─ watchlist.py
│     ├─ stocks.py
│     └─ analysis.py
└──────┬───────────┘
       │ 调用
       ▼
┌──────────────────────────┐
│  src/services/           │
│  ├─ watchlist_service.py │  ← 新增（提取共享逻辑）
│  ├─ stock_service.py     │
│  └─ analysis_service.py  │
└──────────────────────────┘
       │
       ▼
┌──────────────────┐
│  SystemConfig +  │
│  SQLite DB       │
└──────────────────┘
```
