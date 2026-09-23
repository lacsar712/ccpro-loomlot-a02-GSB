# LoomLot-01 · 染坊缸染与色牢度抽检

靛蓝染坊台：按 **染坊 → 染缸 → 染程 → 色牢度** 工序推进，聚焦缸染调度与抽检，不是库存出入库系统。

## 技术栈

| 层 | 技术 |
| --- | --- |
| Backend | FastAPI + SQLAlchemy 2 + Pydantic v2 + Postgres + JWT |
| Frontend | Svelte 4 + Vite + svelte-spa-router |
| 部署 | docker-compose（db + backend + frontend/nginx） |

## 端口

| 服务 | 端口 |
| --- | --- |
| 前端 | **3600** |
| 后端 API | **8600** |
| PostgreSQL | **5439** |

数据库账号：`loomlot` / `loomlot` / 库名 `loomlot`。

## 演示账号

| 用户名 | 密码 | 角色 |
| --- | --- | --- |
| `admin` | `123456` | 染坊主管 |
| `dyer` | `123456` | 染程操作员 |

容器启动时 entrypoint 自动建表并 seed。

## 快速启动

```bash
cd D:\work\document\bytecode\claudeCodePro\LoomLot\LoomLot-01
docker compose up -d --build
```

浏览器：http://localhost:3600  
API：http://localhost:8600/api/health

停止：

```bash
docker compose down
```

## 业务实体

1. **DyeHouse** — `name`, `waterNote`, `notes`
2. **Vat** — `dyeHouseId`, `vatCode`, `fiberType`, `capacityL`, `status` ∈ `ready|dyeing|drain`，另记最近排液时刻 `drainedAt`
3. **DyeLot** — `vatId`, `recipeName`, `fabricKg`, `startedAt`, `operatorName`
4. **FastnessCheck** — `dyeLotId`, `checkedAt`, `washFastness`(1–5), `rubFastness`(>0), `tempC`, `notes`
5. **AuxDose（助剂加注单）** — `vatId`, `auxName`, `liters`(>0), `dosedAt`, `operatorName`，作废时刻 `voidedAt`

### 规则

- 仅当染缸状态为 `ready` 或 `dyeing` 时可新建染程，否则 409
- 新建染程后，染缸状态自动设为 `dyeing`
- 可选接口：`POST /api/vats/{id}/drain` 将染缸置为 `drain`，并记录排液时刻

#### 助剂加注联锁

- 加注字段：所属染缸、助剂名、加注升数（必须为正）、加注时刻、操作人。
- **状态限制**：仅 `dyeing`（染程中）或 `ready`（就绪）缸可加注；`drain`（排液）缸返回 **409**。
- **缸容约束**：同缸自最近一次排液以来（未排液则自始）的累计有效加注升数，连同本次，不得超过缸容升数的 **30%**；超出返回 **409**，并在响应中回显已累计升数（`accumulatedLiters`）及缸容/上限。作废单与排液时刻之前的加注不计入累计。
- **布重联锁（仅染程中）**：缸处于 `dyeing` 时，单次加注升数不得超过该缸最新染程布重（千克）换算的上限，否则 **400**。
  - **换算约定**：加注上限升数 = 最新染程布重 kg ÷ 2，即按 **每 1 kg 布最多加注 0.5 L 助剂** 换算。
- **权限**：操作员（`dyer`）与主管（`admin`）均可新建加注；**作废加注仅主管**可操作（`POST /api/aux-doses/{id}/void`），其余角色返回 **403**。

## 主要 API

- `POST /api/auth/login`（OAuth2 表单）
- `GET /api/auth/me`
- `GET/POST/PUT/DELETE /api/dye-houses`
- `GET/POST/PUT/DELETE /api/vats` · `POST /api/vats/{id}/drain`
- `GET/POST/PUT/DELETE /api/dye-lots`
- `GET/POST/PUT/DELETE /api/fastness-checks`
- `GET/POST /api/aux-doses` · `POST /api/aux-doses/{id}/void`（仅主管）
- `GET /api/dashboard/stats`（含 `auxDoseLitersThisWeek` 本周有效加注升数合计）

除登录外需 `Authorization: Bearer <token>`。字段对外为 camelCase。

### 看板口径

`auxDoseLitersThisWeek` 为本周一 00:00（UTC）起、未作废加注单的升数合计，与「助剂加注」列表中本周行（未作废）的求和一致。种子数据中就绪缸 **V-02**（缸容 600L）未排液期间已累计 170L（上限 180L），再提交超过 10L 的加注即触发 409 缸容超限，可直接演示失败回显。

## 目录

```
LoomLot-01/
├── docker-compose.yml
├── backend/          # FastAPI
├── frontend/         # Svelte 4 + Vite + nginx
└── README.md
```

## 本地开发

### 数据库

```bash
docker compose up -d db
```

### 后端

```bash
cd backend
python -m venv .venv
# Windows: .\.venv\Scripts\activate
pip install -r requirements.txt
$env:DATABASE_URL="postgresql+psycopg2://loomlot:loomlot@127.0.0.1:5439/loomlot"
python -c "from app.database import Base, engine; from app import models; Base.metadata.create_all(bind=engine)"
python -c "from app.seed import seed; seed()"
uvicorn app.main:app --reload --port 8600
```

### 前端

```bash
cd frontend
npm install
npm run dev
```

开发态 Vite 将 `/api` 代理到 `http://127.0.0.1:8600`。
