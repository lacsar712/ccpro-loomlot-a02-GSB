# LoomLot-01 · 染坊缸染与色牢度抽检

靛蓝染坊台：按 **染坊 → 染缸 → 染程 → 助剂加注 → 色牢度** 工序推进，聚焦缸染调度、助剂加注联锁与抽检，不是库存出入库系统。

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
2. **Vat** — `dyeHouseId`, `vatCode`, `fiberType`, `capacityL`, `status` ∈ `ready|dyeing|drain`
3. **DyeLot** — `vatId`, `recipeName`, `fabricKg`, `startedAt`, `operatorName`
4. **ChemicalDose** — `vatId`, `chemicalName`, `doseL`, `dosedAt`, `operatorName`，以及作废信息 `voided` / `voidedAt` / `voidedByName`
5. **FastnessCheck** — `dyeLotId`, `checkedAt`, `washFastness`(1–5), `rubFastness`(>0), `tempC`, `notes`

### 规则

- 仅当染缸状态为 `ready` 或 `dyeing` 时可新建染程，否则 409
- 新建染程后，染缸状态自动设为 `dyeing`
- 可选接口：`POST /api/vats/{id}/drain` 将染缸置为 `drain`，并记录排液时刻

#### 助剂加注联锁

- 加注字段：所属染缸、助剂名、加注升数（必须为正，否则 400）、加注时刻、操作人
- **状态联锁**：仅 `ready`（就绪）或 `dyeing`（染程中）缸可加注；`drain`（排液）缸返回 409
- **缸容联锁**：同缸「未排液期间」（自上次排液时刻之后）的有效（未作废）加注，累计升数连同本次不得超过缸容的 **30%**；超出返回 **409** 并在 `detail` 回显该缸已累计升数
- **布重联锁（仅染程中）**：`dyeing` 缸单笔加注升数还不得超过该缸**最新染程布重（kg）的一半**
  - 换算约定：**1 kg 布重折合 1 升**助剂加注液，即单笔上限 = `最新染程 fabricKg(kg) × 1 L/kg × 0.5`；违反返回 **400**，错误信息带换算说明
  - 就绪缸无在缸染程，不受布重联锁，仅受缸容 30% 约束
- **权限**：染程操作员（`dyer`）与主管（`admin`）均可新建加注；**作废加注仅主管**（`POST /api/chemical-doses/{id}/void`），操作员返回 403。作废只标记、不删除记录，并释放对应缸容占用
- 缸容在写入前于同一事务内对染缸加锁校验（`SELECT ... FOR UPDATE`），杜绝“加注成功却不校验缸容”

> 种子数据的 `V-01`（缸容 800L，30%=240L；最新染程布重 42.5kg，单笔上限 21.25L）已预置 11 笔 × 21L = **231L**。此时再向其加注 10L（合计 241L）即触发缸容超限 409，便于演示失败路径。

## 主要 API

- `POST /api/auth/login`（OAuth2 表单）
- `GET /api/auth/me`
- `GET/POST/PUT/DELETE /api/dye-houses`
- `GET/POST/PUT/DELETE /api/vats` · `POST /api/vats/{id}/drain`
- `GET/POST/PUT/DELETE /api/dye-lots`
- `GET/POST /api/chemical-doses` · `GET /api/chemical-doses/{id}` · `POST /api/chemical-doses/{id}/void`（仅主管）
- `GET/POST/PUT/DELETE /api/fastness-checks`
- `GET /api/dashboard/stats`（含 `dosesLThisWeek` 本周有效加注升数合计与 `weekStart` 本周一 UTC 00:00 口径）

除登录外需 `Authorization: Bearer <token>`。字段对外为 camelCase。

看板「本周助剂加注」与助剂加注列表的**本周行**按同一 `weekStart`（本周一 UTC 00:00，仅统计未作废单）求和，二者数值一致。

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
