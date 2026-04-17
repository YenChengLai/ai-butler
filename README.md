# 🤖 AI Butler

<p align="center">
  <strong>你的智慧生活管家 — 行程管理、記帳追蹤、記憶對話，一句話搞定。</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.11-blue?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-0.135-009688?logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/LLM-Gemini%20%7C%20Claude-blueviolet" alt="LLM">
  <img src="https://img.shields.io/badge/deploy-Cloud%20Functions%20Gen2-4285F4?logo=googlecloud&logoColor=white" alt="Deploy">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
</p>

---

這是一個基於 **Serverless 架構** 的 AI 管家機器人，核心使用 Python 開發，支援多個 AI 模型 Provider（目前支援 **Google Gemini** 與 **Anthropic Claude**），可透過單一環境變數快速切換。

本專案採用 **Router-Agent-Skill** 架構模式，將「意圖判斷」、「參數解析」與「執行邏輯」分離，實現極高的穩定性與擴充性。

專案同時提供兩個入口：**LINE Webhook**（`main.py`，部署至 Cloud Functions）以及 **FastAPI**（`app.py`，本地開發用），不需要 LINE 或 ngrok 即可在本地以 curl 測試所有核心邏輯。

## ✨ 核心特色

- **🧠 學習記憶系統 (Memory RAG)**：內建 **GCP Firestore Vector Search** 組件。
  - 隨手傳入技術筆記、個人偏好、解題紀錄等資訊，AI 自動產生摘要、標籤與向量嵌入。
  - 聊天時透過語意搜尋 + **時間半衰期 (Time-decay)** 排序，精準召回相關記憶注入上下文 (RAG)。
  - 記憶類型支援：`technical_log` / `personal_fact` / `task_note` / `daily_log`。
- **⚡ 全非同步架構**：核心採用原生 `async/await`，意圖分類與向量運算同步並發（`asyncio.gather`），大幅降低 Serverless Cold Start 延遲。
- **🔌 可替換 AI Provider**：透過 `LLM_PROVIDER` 環境變數一鍵切換 Gemini / Claude，**不需修改任何業務邏輯**。
- **極速意圖判斷 (Router)**：使用 Flash / Haiku 等輕量模型，路由判斷延遲低於 0.5 秒。
- **原子化技能 (Atomic Skills)**：將商業邏輯封裝為純 Python 函式，確保執行結果 100% 準確（不依賴 AI 寫程式）。
- **📅 自然語言行事曆管理**：
  - **建立**: 「明天晚上七點跟小明吃飯」
  - **查詢**: 「下週有什麼行程？」
  - **智慧改期 (Reschedule)**: 「把明天的會議延後一小時」（自動執行：搜尋 → 刪除舊行程 → 建立新行程）。
  - **模糊刪除 (Fuzzy Delete)**: 「取消晚上的健身課」。
  - **批量建立**: 「每週三早上 10 點開會」（自動展開未來 4 週行程）。
- **💰 記帳追蹤**：「午餐花了 150 元」— 自動識別金額並寫入 Google Sheets。
- **🔔 自動化行程報告**：
  - **每日日報**：每晚 **21:30** 自動發送明天的行程預告。
  - **每週週報**：每週 **週日 21:30** 自動發送未來七天的行程總覽。
  - **Serverless Cron**：基於 **GitHub Actions** 運行，無需維護額外伺服器。
- **👥 支援群組對話**：機器人可加入群組協作！使用關鍵字 **「管家」** 喚醒（例如：「管家，幫我查行程」）。
- **🛡️ 容錯機制 (Robustness)**：內建 `_normalize_args` 參數清洗層，自動修正 AI 產生的幻覺參數（例如 `summary` → `title`）。
- **☁️ 無伺服器架構**：部署於 **Google Cloud Functions (Gen 2)**，按用量計費。
- **🖥️ 本地開發友善**：`app.py` 提供純 FastAPI 入口，用 curl 即可測試，完全不依賴 LINE SDK。

## 🛠️ 技術棧

| 類別 | 技術 |
|------|------|
| **語言** | Python 3.11 |
| **Web 框架** | FastAPI（本地開發）/ functions-framework（Cloud Functions） |
| **雲端平台** | Google Cloud Functions Gen 2 (Cloud Run) |
| **AI Provider** | Google Gemini (`google-genai` SDK) / Anthropic Claude（可切換） |
| **記憶 / 向量** | GCP Firestore Native Vector Search + `gemini-embedding-001` |
| **訊息平台** | LINE Messaging API (SDK v3) |
| **CI/CD** | GitHub Actions（Lint + 排程報告） |
| **設計模式** | Router-Agent-Skill Pattern |

## 🏗️ 系統架構

```mermaid
graph TD
    User["👤 使用者"] --> Line["LINE Platform"]
    User --> Curl["cURL / Swagger UI"]

    Line -- "Webhook" --> MainPy["⚡ main.py\n(Cloud Function)"]
    Curl -- "POST /chat" --> AppPy["⚡ app.py\n(FastAPI)"]

    MainPy --> Gateway["Core Logic\n(共用 handle_message)"]
    AppPy --> Gateway

    subgraph Intelligence["🧠 Intelligence Layer"]
        Gateway -- "1. 並發" --> RouterLLM["LLM Router\n(Intent + needs_memory)"]
        Gateway -- "1. 並發" --> Embed["EmbeddingService\n(gemini-embedding-001)"]
        Gateway -- "2. 依意圖派發" --> CalAgent["📅 Calendar Agent"]
        Gateway -- "2. 依意圖派發" --> ExpAgent["💰 Expense Agent"]
        Gateway -- "2. 依意圖派發" --> ChatAgent["💬 Chat Agent"]
    end

    subgraph Memory["🧠 Memory RAG Layer"]
        Embed -- "Query Vector" --> Firestore["GCP Firestore\n(Vector Search)"]
        Firestore -- "Top-K Memories\n(Time-decay Ranked)" --> ChatAgent
        Gateway -- "needs_memory=true\n(Background Task)" --> MemParser["MemoryParser\n(摘要 + 標籤)"]
        MemParser --> Firestore
    end

    subgraph LLMLayer["🔌 LLM Provider Layer"]
        RouterLLM & CalAgent & ExpAgent & ChatAgent & MemParser --> Factory["factory.py\n(LLM_PROVIDER env)"]
        Factory -- "gemini" --> Gemini["GeminiProvider"]
        Factory -- "claude" --> Claude["ClaudeProvider"]
    end

    subgraph Skills["🛠️ Skills Layer (Deterministic)"]
        CalAgent -- "呼叫函式" --> CalSkill["⚙️ Calendar Skills"]
        ExpAgent -- "呼叫函式" --> ExpSkill["⚙️ Expense Skills"]
        CalSkill -- "CRUD" --> GCal["Google Calendar API"]
        ExpSkill -- "寫入" --> GSheet["Google Sheets"]
    end

    subgraph Cron["🔔 Scheduled Reporting (GitHub Actions)"]
        CronTrigger["⏱️ 排程觸發\n(daily / weekly)"] --> Scripts["🐍 Python Scripts\n(daily_report / weekly_report)"]
        Scripts -- "Query" --> CalSkill
        Scripts -- "Push Message" --> Line
    end

    ChatAgent -- "Reply" --> Gateway
    Gateway -- "Reply" --> Line
    Gateway -- "JSON Response" --> Curl
```

## 📂 專案結構

```
ai-butler/
├── backend/
│   ├── main.py                      # LINE Webhook 入口 (Cloud Function)
│   ├── app.py                       # FastAPI 入口 (本地開發 / curl 測試)
│   ├── requirements.txt             # Python 依賴
│   └── src/
│       ├── config.py                # 統一設定管理 (模型名稱、生成參數)
│       ├── agents/                  # Agents (AI Parsers & Controllers)
│       │   ├── calendar.py          # 行事曆意圖解析 + 參數清洗
│       │   ├── expense.py           # 費用記帳意圖解析
│       │   ├── chat.py              # 閒聊 Agent（含記憶注入）
│       │   └── memory_parser.py     # ✨ 記憶摘要提取 Agent
│       ├── services/                # Drivers & Adapters
│       │   ├── firestore_service.py # ✨ Firestore Vector Search (記憶存取 + Time-decay)
│       │   ├── gcal_service.py      # Google Calendar API 底層串接
│       │   └── llm/                 # LLM 抽象層 (可擴充新模型)
│       │       ├── base.py          # LLMProvider 抽象介面 (async)
│       │       ├── gemini.py        # Gemini 適配器 (google-genai SDK)
│       │       ├── claude.py        # Claude 適配器 (AsyncAnthropic)
│       │       ├── embedding.py     # ✨ Embedding Service (固定 Gemini)
│       │       └── factory.py       # Provider 工廠函式
│       ├── skills/                  # Skills (Pure Python Logic)
│       │   ├── calendar_skill.py    # Google Calendar CRUD (原子操作)
│       │   └── expense.py           # Google Sheets 記帳
│       ├── scripts/                 # Standalone Scripts (報表用腳本)
│       │   ├── daily_report.py      # 每日行程推播
│       │   └── weekly_report.py     # 每週行程推播
│       ├── prompts/                 # AI System Prompts
│       │   ├── system_prompt.txt    # Router Prompt (含 needs_memory 旗標)
│       │   ├── calendar_agent.txt   # Calendar Agent Prompt
│       │   ├── expense_agent.txt    # Expense Agent Prompt
│       │   └── chat_agent.txt       # Chat Agent Prompt (含記憶注入模板)
│       └── utils/                   # Helpers & UI
│           └── flex_templates.py    # LINE Flex Message 模板
├── docs/
│   └── docs/
│       └── ARCHITECTURE_FAQ.md      # 架構設計決策紀錄 (中英對照)
└── .github/workflows/
    ├── ci.yml                       # CI Pipeline (flake8 + pytest)
    ├── daily_notify.yml             # 每日推播 Cron Job
    └── weekly_notify.yml            # 每週推播 Cron Job
```

## 🚀 快速開始

### 1. 環境準備

- Python 3.11+
- Google Cloud Platform 帳號，啟用以下服務：
  - **Cloud Functions** / **Cloud Run**
  - **Cloud Build**
  - **Google Calendar API**
  - **Firestore** (Native Mode，需手動建立 `memories` collection 的向量索引，詳見下方說明)
- **Service Account**: 建立 GCP 服務帳號，下載 JSON 金鑰，並授予對 Calendar 的讀寫權限與 Firestore 的讀寫權限。
- LINE Developers Channel (Messaging API) — 僅 `main.py` 入口需要。
- **Gemini API Key** (`GOOGLE_GENAI_API_KEY`) — 無論 `LLM_PROVIDER` 設為何，Embedding 始終使用 Gemini，因此這個 Key **必填**。

### 2. 安裝依賴

```bash
git clone https://github.com/YenChengLai/ai-butler.git
cd ai-butler/backend

python3 -m venv venv
source venv/bin/activate    # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. 環境變數設定 (.env)

請在 `backend/` 目錄下建立 `.env` 檔案：

```ini
# LINE Bot (僅 main.py 需要)
CHANNEL_ACCESS_TOKEN=你的_LINE_Token
CHANNEL_SECRET=你的_LINE_Secret

# Google Calendar
CALENDAR_ID=你的_Google_Calendar_ID

# GCP Service Account (Firestore / Calendar 的認證)
GOOGLE_APPLICATION_CREDENTIALS=service_account.json

# AI Provider 設定 (二選一，但 GOOGLE_GENAI_API_KEY 無論如何都必填)
LLM_PROVIDER=gemini          # 或 claude
GOOGLE_GENAI_API_KEY=你的_Gemini_Key
# ANTHROPIC_API_KEY=你的_Claude_Key    # 若使用 Claude 才需要
```

### 4. Firestore 向量索引設定

記憶系統使用 GCP Firestore Native Vector Search。首次使用前，請至 GCP Console 手動建立 Composite Index：

- **Collection**: `memories`
- **Field**: `embedding` (Vector, dimension: `768`, distance: `COSINE`)
- **Field**: `user_id` (Ascending)

> 💡 部署後傳送第一條訊息，Cloud Functions Log 中會出現官方生成的「快速建立索引」連結，點擊即可跳轉至 Console 完成設定。

### 5. 本地開發與測試 (FastAPI)

```bash
cd backend
uvicorn app:app --reload --port 8000
```

用 curl 測試 — **不需要 LINE 帳號或 ngrok**：

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id": "dev_user", "message": "明天下午三點開會"}'
```

回應範例：

```json
{
  "reply": "✅ 已建立行程「開會」，時間：明天 15:00",
  "intent": "CALENDAR"
}
```

也可以打開 **Swagger UI** 進行互動式測試：[http://localhost:8000/docs](http://localhost:8000/docs)

### 6. 部署至 GCP

**Cloud Functions (Production，記憶體建議至少 512MiB)：**

```bash
gcloud functions deploy webhook \
  --gen2 \
  --runtime=python311 \
  --region=asia-east1 \
  --memory=512MiB \
  --source=backend/ \
  --entry-point=webhook \
  --trigger-http \
  --allow-unauthenticated \
  --set-env-vars="CHANNEL_ACCESS_TOKEN=...,CHANNEL_SECRET=...,LLM_PROVIDER=gemini,GOOGLE_GENAI_API_KEY=...,CALENDAR_ID=..."
```

> ⚠️ 本地測試需要有效的 `service_account.json` 在 `backend/` 目錄，並且設定 `GOOGLE_APPLICATION_CREDENTIALS` 環境變數。

### 7. 設定 GitHub Actions (自動報表)

若要啟用每日 / 每週報表推播，請至 GitHub Repo 的 **Settings > Secrets and variables > Actions** 新增以下 Secrets：

| Secret 名稱 | 說明 |
|-------------|------|
| `CHANNEL_ACCESS_TOKEN` | LINE Channel Access Token |
| `CALENDAR_ID` | 目標 Google Calendar ID |
| `TARGET_GROUP_ID` | 接收報表的群組 ID (`C...`) 或使用者 ID (`U...`) |
| `GCP_SA_KEY_BASE64` | 將 `service_account.json` 轉為 Base64 字串後填入 |

**產生 Base64 字串：**

```bash
base64 -i service_account.json -o sa_base64.txt
# 複製 sa_base64.txt 的內容貼上
```

> 💡 **常見問題：如何取得正確的 Group ID？** LINE 官方帳號後台網址上的 ID 不是 API 用的 Group ID。
>
> 1. 將機器人邀入群組。
> 2. 在群組中說話，前往 GCP Logs 查看該 Webhook 事件的 `source.groupId`。

## 🔌 切換 AI Provider

本專案支援在 Gemini 與 Claude 之間切換，**無需修改任何程式碼**，只需更改 `.env` 中的 `LLM_PROVIDER`：

| `LLM_PROVIDER` | 需要的 API Key | Router 模型 | Agent 模型 |
|---|---|---|---|
| `gemini`（預設） | `GOOGLE_GENAI_API_KEY` | `gemini-2.5-flash-lite` | `gemini-3-flash-preview` |
| `claude` | `ANTHROPIC_API_KEY` | `claude-haiku-4-5` | `claude-sonnet-4-5` |

> 📌 **注意**: `GOOGLE_GENAI_API_KEY` 無論使用哪個 Provider 都 **必填**，因為記憶向量化 (Embedding) 固定使用 `gemini-embedding-001`，以確保向量空間一致性。

> 模型名稱可在 `backend/src/config.py` 中調整。

## 📝 使用範例

**行事曆管理：**
- **新增行程**: 「管家，明天下午三點要帶兒子去打疫苗」
- **查詢行程**: 「管家，這禮拜有什麼行程？」
- **智慧改期**: 「管家，把明天的會議延後一小時」
- **模糊刪除**: 「管家，取消晚上的健身課」
- **批量建立**: 「管家，12/19（五）09:00-10:00、12/26（五）09:00-10:00，上英文會話」

**記帳追蹤：**
- **記錄支出**: 「管家，午餐花了 150 元」
- **計程車**: 「管家，計程車 300」

**記憶系統：**
- **記錄技術筆記**: 「今天排查了 FD leak 問題，根本原因是 eventlet hub 在 asyncio 環境下沒被正確關閉」
- **記錄個人事項**: 「我對海鮮過敏，訂餐廳時要注意」
- **召回記憶 (自動)**: 下次聊天時，管家會主動引用相關記憶提供更精準的回應。

**本地開發 (curl)：**

```bash
# 行事曆
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id": "dev_user", "message": "明天下午三點開會"}' | python3 -m json.tool

# 記帳
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id": "dev_user", "message": "午餐花了 150 元"}' | python3 -m json.tool

# 閒聊 (會自動搜尋相關記憶)
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id": "dev_user", "message": "之前那個 FD leak 問題後來怎麼解的？"}' | python3 -m json.tool
```

## 📖 延伸閱讀

- [Architecture FAQ](docs/docs/ARCHITECTURE_FAQ.md) — 為什麼自建 Router-Agent-Skill？為什麼不用 LangChain？如何處理 Gemini 參數幻覺？

## 👤 Author

Developed by [YenCheng Lai](https://github.com/YenChengLai)

## 📄 License

[MIT License](LICENSE) © 2026 YenChengLai
