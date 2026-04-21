import os

# --- LLM Provider Switch ---
# 設定使用哪個 AI 模型供應商。
# 可選值: "gemini" | "claude"
# 透過 .env 設定，預設為 "gemini" 以維持向後相容。
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini")

# --- Gemini Model Configuration ---
# Router: 求快，使用 Flash 系列
GEMINI_ROUTER_MODEL_NAME = "gemini-2.5-flash-lite"
# Agent: 求準，解析使用者語意，可用更強的模型
GEMINI_AGENT_MODEL_NAME = "gemini-3-flash-preview"

# Gemini 生成參數（統一管理，保持回應風格一致）
GEMINI_GENERATION_CONFIG = {
    "temperature": 0.7,  # 0.0 ~ 1.0，越低越精確，越高越有創意
    "top_p": 0.95,
    "top_k": 40,
    "max_output_tokens": 8192,
}

# --- Claude Model Configuration ---
# Router: 求快，使用 Haiku 系列（成本最低）
CLAUDE_ROUTER_MODEL_NAME = "claude-haiku-4-5"
# Agent: 求準，使用 Sonnet 系列（平衡效能與成本）
CLAUDE_AGENT_MODEL_NAME = "claude-sonnet-4-5"

# Claude max_tokens（必填參數，Gemini 無此限制）
CLAUDE_MAX_TOKENS = 8192
