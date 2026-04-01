# 📚 Architecture FAQ & Design Decisions

# 架構常見問答與設計決策

This document records key technical decisions and design philosophies during the development of AI Butler.

這份文件記錄了 AI Butler 開發過程中的關鍵技術決策與設計思維。

---

## Q1: Why build a custom Router-Agent-Skill architecture instead of using LangChain?

## Q1: 為什麼不採用 LangChain 或現成的 Framework，而是自建 Router-Agent-Skill 架構？

**Context / 背景:**
In the early stages, we faced high code coupling, making it difficult to extend features or debug logic errors.

專案初期我們面臨程式碼耦合度過高，導致擴充功能困難，且難以釐清錯誤發生的層級。

**Decision / 決策:**
We adopted a 3-layer **Router-Agent-Skill** architecture:

我們採用了三層式的 **Router-Agent-Skill** 架構：

1.  **Router (Gateway)**: Handles **Intent Classification** only. No parameter parsing.

    (只負責分類意圖，不處理參數。)

2.  **Agent (Controller)**: Manages prompts, **normalizes parameters**, and controls flow.

    (負責該領域的 Prompt 管理、參數清洗與流程控制。)

3.  **Skill (Atomic Tool)**: Pure Python logic. Interacts with external APIs (e.g., Google Calendar) to ensure **deterministic execution**.

    (純 Python 邏輯，負責與外部 API 交互，確保執行的「確定性」。)

**Benefit / 效益:**
Debugging becomes trivial. Router errors = Classification issues; Agent errors = Parsing issues; Skill errors = API issues.

這樣的設計讓除錯變得非常容易。如果分類錯了是 Router 的問題；參數解析錯了是 Agent 的問題；API 報錯則是 Skill 的問題。

---

## Q2: Why define "Skills" as executable functions instead of text instructions (Anthropic AgentSkills)?

## Q2: 關於 "Skill" 的定義，為什麼不採用 Anthropic (AgentSkills.io) 的純文字定義？

**Context / 背景:**
There are two schools of thought for Agents:

- **Cognitive**: Skills are "instructions" teaching AI how to write code (e.g., Anthropic).
- **Action**: Skills are "tools" that AI calls to perform tasks (e.g., OpenAI Functions).

  目前 AI 趨勢中，有一派 (Cognitive) 認為 Skill 應該是「教 AI 寫程式的說明書」；另一派 (Action) 認為 Skill 應該是「可執行的工具」。

**Decision / 決策:**
As a **Butler Bot**, the user needs "stable services," not "code generation." Therefore, we define **Skills as atomic Python functions**.

作為一個 **Line Bot (管家)**，使用者需要的是「穩定的服務」而非「看 AI 寫程式」。因此我們定義 **Skill 為原子化的 Python 函式**。

We do not let AI generate code to delete an event; we let AI decide _when_ to call our pre-written, tested `delete_event` function. This minimizes data corruption caused by AI hallucinations.

我們不讓 AI 現場生成刪除行程的程式碼，而是讓 AI 決定「何時呼叫」我們寫好的 `delete_event` 函式。這能最大程度避免 AI 幻覺導致的資料損毀。

---

## Q3: Why not use a database for Conversation Context?

## Q3: 為什麼不引入資料庫來做對話 Context (上下文) 管理？

**Context / 背景:**
Users might use ambiguous references (e.g., "Reschedule _this_ meeting"). Without history, the bot cannot resolve "_this_".

使用者可能會說「把**這個**行程改期」，如果沒有儲存對話歷史，Bot 會不知道「這個」是指哪一個。

**Decision / 決策:**
We decided to keep the system **Stateless**.

目前的決策是 **保持 Stateless (無狀態)**。

1.  **Performance & Cost**: Introducing Firestore/Redis increases cold-start time and architectural complexity for a Serverless app.

    (引入資料庫會大幅增加 Serverless 的冷啟動時間與架構複雜度。)

2.  **Atomic Design**: We encourage users to give explicit instructions (e.g., "Reschedule tomorrow's meeting") rather than ambiguous ones.

    (我們傾向引導使用者下達完整指令，而非依賴模糊的代名詞。)

3.  **Solution**: We use **Prompt Caching** (loading in `__init__`) to optimize single-request performance instead.

    (透過快取 Prompt 來優化單次請求效能，暫不處理跨請求的記憶。)

---

## Q4: How do we handle Gemini's parameter hallucinations?

## Q4: 如何解決 Gemini 偶爾產生的「參數幻覺」 (Hallucination)？

**Context / 背景:**
During development, we found Gemini 3.0 Flash sometimes ignores the Prompt and returns `summary` (standard Google API field) instead of `title` (our defined field), causing crashes.

在開發 Calendar Agent 時，發現 Gemini 3.0 Flash 偶爾會忽略 Prompt 規定，回傳 `summary` (Google API 欄位) 而非 `title` (我們定義的欄位)，導致程式崩潰。

**Decision / 決策:**
We implemented a **`_normalize_args`** mechanism in the Agent layer.

我們在 Agent 層實作了 **`_normalize_args` (參數清洗)** 機制。

This acts as an **Adapter**, converting various hallucinated parameter names (e.g., `startTime` vs `start_time`) into the standard format accepted by our Skills. This significantly improves system **Robustness**.

這是一個轉接頭 (Adapter)，負責將 AI 可能產生的各種異名參數統一轉換為 Skill 能接受的標準格式，大幅提升了系統的 **容錯率 (Robustness)**。
