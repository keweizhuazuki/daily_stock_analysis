# MCP 集成实施日志 — daily_stock_analysis

> 本文档供其他 AI（Claude Code、Cursor、Codex 等）阅读，
> 用于理解本次改造的背景、已完成工作、以及后续待办事项。
> 最后更新：2026-06-30

---

## 1. 用户需求

用户 fork 了 [daily_stock_analysis](https://github.com/keweizhuazuki/daily_stock_analysis) 项目。
原始项目是一个功能完善的 A 股 / 港股 / 美股智能分析系统（FastAPI 后端 + LLM 分析 + Bot 集成），
但缺少 **MCP (Model Context Protocol)** 支持。

用户的核心诉求：

1. **让 AI 可以通过对话的方式管理自选股**（添加 / 删除 / 查看自选股列表）
2. **做成 MCP 与 AI 兼容** — 使用 MCP 协议将自选股管理能力暴露给 Claude Desktop / Claude Code 等 AI 工具
3. **后续接入微信 clawbot 或飞书 bot** — 希望现有的 Bot 层也能通过对话操作自选股

一句话总结：**"用对话的方式让AI添加/删除自选"**

---

## 2. 原始项目结构概览

在改造前，项目的关键分层：

```
daily_stock_analysis/
├── api/
│   ├── app.py                          # FastAPI 应用工厂 + lifespan
│   ├── deps.py                         # 依赖注入
│   └── v1/
│       ├── router.py
│       └── endpoints/
│           ├── stocks.py               # 自选股 CRUD + 行情/历史接口
│           ├── analysis.py             # 分析触发接口
│           ├── agent.py                # Agent 对话接口（SSE 流式）
│           ├── alerts.py               # 告警系统
│           ├── decision_signals.py     # 决策信号
│           ├── intelligence.py         # 情报/新闻源管理
│           └── alphasift.py            # AlphaSift 量化筛选
├── src/
│   ├── config.py                       # 全局配置（Config dataclass + .env 解析）
│   ├── services/
│   │   ├── system_config_service.py    # 系统配置持久化（STOCK_LIST 等）
│   │   ├── stock_service.py            # 股票行情/历史数据服务
│   │   ├── analysis_service.py         # 分析触发服务
│   │   ├── alert_service.py            # 告警服务
│   │   ├── task_queue.py              # 任务队列
│   │   └── ...
│   ├── agent/                          # Agent 框架（工具注册/LLM 适配/Skill）
│   ├── core/
│   │   ├── pipeline.py                 # 分析流水线
│   │   └── config_registry.py          # 配置元数据注册表
│   └── analyzer.py                     # LLM 分析器
├── bot/
│   ├── commands/                       # Bot 命令处理器
│   │   ├── __init__.py                 # ALL_COMMANDS 注册表
│   │   ├── base.py                     # BotCommand 抽象基类
│   │   ├── analyze.py, ask.py, chat.py, ...
│   │   └── watchlist.py               # ★ 新增
│   ├── dispatcher.py                   # 命令分发器
│   └── platforms/                      # Bot 平台适配（Discord/飞书/钉钉）
├── data_provider/                      # 多源行情数据获取层
├── tests/                              # 测试
└── requirements.txt
```

**自选股管理的现有实现方式：**

- 自选股列表存储在 `.env` 的 `STOCK_LIST` 键中（逗号分隔的股票代码）
- 读写通过 `SystemConfigService` → `.env` 文件
- REST API 端点：
  - `GET /api/v1/stocks/watchlist` → 获取自选股列表
  - `POST /api/v1/stocks/watchlist/add` → 添加股票
  - `POST /api/v1/stocks/watchlist/remove` → 删除股票
- 自选股操作的核心逻辑在 `api/v1/endpoints/stocks.py` 中以**模块级私有函数**存在：
  - `_read_watchlist_codes()`, `_write_watchlist_codes()`
  - `_validate_and_normalize_stock_code()`, `_watchlist_match_key()`

---

## 3. 实施计划

### 整体设计思路

**不做**：直接在 REST API 层暴露 MCP（会导致两种协议耦合）
**要做**：新建 `mcp_server/` 包，使用 Python MCP SDK（`mcp` 包中的 `FastMCP`），
从现有 services 层复用业务逻辑。

### 核心原则

1. **提取共享层**：将自选股逻辑从 `api/v1/endpoints/stocks.py` 提取到 `src/services/watchlist_service.py`
2. **MCP 工具 = 薄包装**：MCP 工具函数仅做参数转换，实质调用共享 service
3. **Bot 命令 = 薄包装**：Bot 命令同样调用共享 service
4. **零破坏性**：所有新功能默认关闭（`MCP_SERVER_ENABLED=false`），不影响现有功能

### 实施顺序（9 个 Phase）

| Phase | 内容 |
|-------|------|
| 1 | 从 stocks.py 提取 WatchlistService |
| 2 | 在 Config dataclass 添加 MCP 配置字段 |
| 3 | 在 requirements.txt 添加 `mcp>=1.0.0` |
| 4 | 创建 `mcp_server/` 包骨架 |
| 5 | 实现 MCP 工具函数（watchlist / stocks / analysis） |
| 6 | 实现传输层（stdio + SSE） |
| 7 | 添加 Bot WatchlistCommand |
| 8 | 编写测试和文档 |
| 9 | 添加 API 共存支持（在 app_lifespan 中启动 MCP SSE） |

---

## 4. 已完成的修改

### 4.1 新建文件

#### `src/services/watchlist_service.py` — 共享自选股服务层

提取自 `api/v1/endpoints/stocks.py` 的私有函数，封装为 `WatchlistService` 类：

```python
class WatchlistService:
    def __init__(self, system_config_service)
    def get_codes() -> List[str]          # 读取自选股列表
    def add_code(code: str) -> List[str]   # 添加（含去重、格式验证）
    def remove_code(code: str) -> List[str] # 删除（含变体匹配）
    @staticmethod validate_code(code) -> str  # 验证 + 规范化
    @staticmethod match_key(code) -> str      # 等价匹配键
```

同时定义了 `WatchlistError` 异常（`error` + `message`），
使 MCP 和 Bot 层不依赖 HTTPException。

#### `mcp_server/` 包 — MCP 服务器模块

```
mcp_server/
├── __init__.py          # 导出 create_server(), run_server()
├── server.py            # FastMCP 实例 + 工具注册 + __main__ 入口
└── tools/
    ├── __init__.py
    ├── watchlist.py     # list_watchlist, add_stock, remove_stock
    ├── stocks.py        # search_stock, get_stock_quote, get_stock_history
    └── analysis.py      # trigger_analysis, get_analysis_status
```

**server.py 核心逻辑：**

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("dsa-watchlist")

# 注册 8 个工具
mcp.tool()(list_watchlist)
mcp.tool()(add_stock)
mcp.tool()(remove_stock)
mcp.tool()(search_stock)
mcp.tool()(get_stock_quote)
mcp.tool()(get_stock_history)
mcp.tool()(trigger_analysis)
mcp.tool()(get_analysis_status)

# __main__ 入口
if __name__ == "__main__":
    run_server()  # 根据 MCP_SERVER_TRANSPORT 选择 stdio 或 sse
```

#### `bot/commands/watchlist.py` — Bot 自选股命令

```python
class WatchlistCommand(BotCommand):
    name = "watchlist"
    aliases = ["wl", "自选", "addstock", "removestock", "watchlist"]
    # 子命令: list (默认), add <code>, remove <code>, help
```

支持的命令：
- `/wl` — 查看自选股列表
- `/wl add 600519` — 添加 A 股
- `/wl remove HK00700` — 删除港股
- `/wl add AAPL` — 添加美股
- `/addstock 600519` — 快捷添加
- `/removestock 600519` — 快捷删除

#### `tests/test_mcp_tools.py` — 单元测试

包含 19 个测试用例：
- `TestWatchlistService`（12 个测试）：增删查、去重、变体匹配、格式验证
- `TestMcpWatchlistTools`（5 个测试）：MCP 工具函数的隔离测试

所有测试使用 `FakeSystemConfigService`（内存模拟），无需数据库或 .env 文件。

#### `docs/mcp_server.md` — MCP 服务器使用文档

面向用户的文档，包含：
- 安装和配置说明
- Claude Desktop 配置示例
- 8 个 MCP 工具的详细说明
- 对话示例
- 架构图

### 4.2 修改文件

#### `src/config.py`

在 `Config` dataclass 中新增 4 个字段：

```python
mcp_server_enabled: bool = False       # MCP_SERVER_ENABLED
mcp_server_transport: str = "stdio"    # MCP_SERVER_TRANSPORT
mcp_server_host: str = "127.0.0.1"     # MCP_SERVER_HOST
mcp_server_port: int = 8080            # MCP_SERVER_PORT
```

在 `_from_env()` 中新增对应的 `os.getenv()` 解析。

#### `api/v1/endpoints/stocks.py`

- 移除了 4 个私有函数（`_read_watchlist_codes`, `_write_watchlist_codes`, `_STOCK_CODE_RE`, `_watchlist_match_key`）
- `_validate_and_normalize_stock_code` 改为委托给 `WatchlistService.validate_code()`
- `get_watchlist`, `add_to_watchlist`, `remove_from_watchlist` 三个端点改为使用 `WatchlistService`
- 新增 `WatchlistError` → HTTPException 的转换

#### `bot/commands/__init__.py`

在 `ALL_COMMANDS` 列表中注册 `WatchlistCommand`。

#### `api/app.py`

在 `app_lifespan` 中添加 MCP SSE 共存支持：

```python
def _start_mcp_sse_if_enabled(app: FastAPI) -> Optional[asyncio.Task]
```

- 仅在 `MCP_SERVER_ENABLED=true` 且 `MCP_SERVER_TRANSPORT=sse` 时启动
- 作为后台 `asyncio.Task` 运行
- 在 lifespan shutdown 时取消

#### `requirements.txt`

新增一行：`mcp>=1.0.0  # MCP Python SDK`

---

## 5. 工具清单

### 5.1 MCP 工具（通过 AI 对话调用）

| 工具名 | 分类 | 参数 | 返回值 |
|--------|------|------|--------|
| `list_watchlist` | 自选股管理 | 无 | `{stock_codes: [...], count: N}` |
| `add_stock` | 自选股管理 | `stock_code: str` | `{success, stock_code, message, current_count}` |
| `remove_stock` | 自选股管理 | `stock_code: str` | `{success, stock_code, message, current_count}` |
| `search_stock` | 行情查询 | `query: str`, `include_quote?: bool` | `{matches: [...], total_count}` |
| `get_stock_quote` | 行情查询 | `stock_code: str` | `{success, price, change_percent, ...}` |
| `get_stock_history` | 行情查询 | `stock_code, period?, days?` | `{success, klines: [...], data_points}` |
| `trigger_analysis` | 分析触发 | `stock_codes?: list[str]` | `{success, tasks: [...]}` |
| `get_analysis_status` | 分析触发 | `query_id: str` | `{success, status, progress, result}` |

### 5.2 Bot 命令（通过飞书/钉钉/Discord 对话调用）

| 命令 | 说明 |
|------|------|
| `/wl` | 查看自选股列表 |
| `/wl add <代码>` | 添加股票 |
| `/wl remove <代码>` | 删除股票 |
| `/wl help` | 帮助 |
| `/addstock <代码>` | 快捷添加 |
| `/removestock <代码>` | 快捷删除 |

---

## 6. 架构图

```
                    ┌──────────────────────────────────────┐
                    │        AI / Bot 客户端                │
                    │                                       │
                    │  Claude Desktop ──→ MCP (stdio)       │
                    │  Claude Code    ──→ MCP (stdio)       │
                    │  Cursor         ──→ MCP (stdio)       │
                    │  飞书 Bot       ──→ HTTP /wl 命令     │
                    │  钉钉 Bot       ──→ HTTP /wl 命令     │
                    │  Discord Bot    ──→ HTTP /wl 命令     │
                    └────────┬──────────────┬───────────────┘
                             │              │
              MCP 协议 (stdio/SSE)     Bot 命令分发
                             │              │
                    ┌────────▼──────┐  ┌───▼───────────┐
                    │  mcp_server/  │  │ bot/commands/ │
                    │  server.py    │  │ watchlist.py  │
                    │  tools/       │  │ (WatchlistCmd)│
                    │  8 tools      │  └───┬───────────┘
                    └──────┬────────┘      │
                           │               │
                           └───────┬───────┘
                                   │ 调用
                          ┌────────▼────────────────────┐
                          │  src/services/              │
                          │  ├─ watchlist_service.py ★  │
                          │  ├─ stock_service.py        │
                          │  └─ analysis_service.py     │
                          └────────┬────────────────────┘
                                   │
                          ┌────────▼────────┐
                          │ SystemConfig    │
                          │ + SQLite DB     │
                          └─────────────────┘
```

---

## 7. 后续待办事项

### 7.1 必须完成（才能正常运行 MCP）

#### ① 安装 MCP Python SDK

在项目虚拟环境中安装：

```bash
pip install mcp>=1.0.0
```

#### ② 验证股票索引文件存在

`search_stock` 工具依赖 `data/stocks.index.json` 文件进行股票搜索。
确认该文件存在：

```bash
ls -la data/stocks.index.json
```

如果不存在，需要先生成。该项目可能有生成脚本（如 `trade_data/` 或启动时的 `_schedule_stock_index_background_refresh`）。

#### ③ 验证 `src/services/stock_service.py` 的 API

`get_stock_quote` 和 `get_stock_history` 工具调用了 `StockService` 的方法：

```python
stock_service.get_realtime_quote(stock_code)
stock_service.get_history_data(stock_code, period=period, days=days)
```

需要确认这些方法的实际签名和返回类型，必要时调整 `mcp_server/tools/stocks.py` 中的调用代码。
特别是：
- `get_history_data` 的参数名是 `period` 还是 `freq` / `interval`？
- 返回类型是 dataclass 还是 dict？
- 返回结构中的 K 线数据字段名是 `data`、`klines` 还是其他？

#### ④ 验证 `src/services/analysis_service.py` 的 API

`trigger_analysis` 工具调用了：

```python
analysis_service.analyze_stock(code)
```

需要确认该方法是否存在、签名是否正确。
如果实际入口不同（如需要通过 `StockAnalysisPipeline`），需要调整 `mcp_server/tools/analysis.py`。

#### ⑤ 验证 `src/services/task_queue.py` 的 API

`get_analysis_status` 工具调用了：

```python
task_queue.get_task(query_id)
```

需要确认：
- `TaskQueue` 是否需要单例模式初始化？
- `get_task` 的参数名是 `query_id` 还是 `task_id`？

### 7.2 建议完成（提升质量）

#### ⑥ 运行全部测试

```bash
# MCP 工具测试
pytest tests/test_mcp_tools.py -v

# 已有的自选股 API 测试（确保未破坏）
pytest tests/test_stock_watchlist_api.py -v

# 全部测试
pytest tests/ -v
```

#### ⑦ Claude Desktop 联调测试

在 Claude Desktop 配置文件（`claude_desktop_config.json`）中添加：

```json
{
  "mcpServers": {
    "dsa-watchlist": {
      "command": "python",
      "args": ["-m", "mcp_server"],
      "cwd": "/absolute/path/to/daily_stock_analysis"
    }
  }
}
```

重启 Claude Desktop，然后尝试以下对话：

1. "列出我的自选股"
2. "把 600519 加入自选"
3. "搜索茅台"
4. "分析我的自选股"

#### ⑧ 添加集成测试

在 `tests/` 中添加 MCP 服务器的端到端集成测试：
使用 `mcp` 包的 `stdio_client` + `ClientSession` 连接到 `mcp_server` 子进程，
验证完整的 JSON-RPC 流程。

```python
# 伪代码
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

server_params = StdioServerParameters(
    command="python", args=["-m", "mcp_server"], cwd=PROJECT_DIR
)
async with stdio_client(server_params) as (read, write):
    async with ClientSession(read, write) as session:
        await session.initialize()
        tools = await session.list_tools()
        # assert "add_stock" in [t.name for t in tools.tools]
```

#### ⑨ 更新 README.md

在项目 README 中添加 MCP 支持的简要说明和链接到 `docs/mcp_server.md`。

### 7.3 可选扩展

#### ⑩ 接入 WeChat clawbot

如果要接入微信 clawbot（基于 MCP 的微信机器人），
需要在 clawbot 的 MCP 配置中指向本项目的 SSE 端点：

```json
{
  "mcpServers": {
    "dsa-watchlist": {
      "url": "http://your-server:8080/sse"
    }
  }
}
```

或直接使用 stdio 模式连接。

#### ⑪ 添加更多 MCP 工具

可考虑从现有的 `src/agent/tools/` 中迁移更多工具到 MCP：
- 市场指数查询
- 板块排名
- 筹码分布分析
- K 线形态识别

#### ⑫ 添加 MCP Resource

除了工具（Tools），MCP 还支持资源（Resources）和提示（Prompts）。
可考虑将每日分析报告作为 Resource 暴露。

---

## 8. 关键文件路径

| 文件 | 说明 |
|------|------|
| `src/services/watchlist_service.py` | 共享自选股服务（新） |
| `src/config.py` | 全局配置（已添加 MCP 字段） |
| `api/v1/endpoints/stocks.py` | REST API 自选股端点（已重构） |
| `api/app.py` | FastAPI 应用 + MCP SSE 共存 |
| `mcp_server/server.py` | MCP 服务器主文件 |
| `mcp_server/tools/watchlist.py` | 自选股 MCP 工具 |
| `mcp_server/tools/stocks.py` | 行情查询 MCP 工具 |
| `mcp_server/tools/analysis.py` | 分析触发 MCP 工具 |
| `bot/commands/watchlist.py` | Bot 自选股命令 |
| `bot/commands/__init__.py` | 命令注册表 |
| `tests/test_mcp_tools.py` | MCP 单元测试 |
| `docs/mcp_server.md` | MCP 使用文档 |
| `docs/IMPLEMENTATION_LOG.md` | 本文档 |

---

## 9. 启动检查清单

在尝试启动 MCP 服务器之前，请按顺序检查：

- [ ] `.env` 文件中存在有效的 `STOCK_LIST` 配置（可以为空：`STOCK_LIST=`）
- [ ] 已安装 `mcp` Python 包：`pip show mcp`
- [ ] `data/stocks.index.json` 文件存在（`search_stock` 依赖）
- [ ] 可选：设置 `MCP_SERVER_ENABLED=true`（SSE 模式需要）
- [ ] 运行 `python -m mcp_server`（stdio 模式，不应报错）
- [ ] 运行 `pytest tests/test_mcp_tools.py -v`（应全部通过）
