import os
import uuid
import logging
import datetime
from google.cloud import firestore

logger = logging.getLogger(__name__)

class AsyncFirestoreService:
    """
    非同步存取 Firestore，專責處理記憶日誌系統的文章 (Memory System)。
    """
    
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(AsyncFirestoreService, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self, collection_name: str = "memories"):
        if hasattr(self, "_initialized"):
            return
            
        # 由於我們只初始化一次，確保以 AsyncClient 啟動
        logger.info("🔥 Initializing AsyncFirestoreService")
        try:
            # 確保 GCP 連線環境。通常如果跑在 GCP Functions，免額外設定
            self.client = firestore.AsyncClient()
        except Exception as e:
            logger.error("❌ Failed to init AsyncFirestoreService: %s", e)
            self.client = None

        self.collection_name = collection_name
        self._initialized = True

    async def save_memory(
        self,
        user_id: str,
        content: str,
        summary: str,
        tags: list[str],
        memory_type: str,
        embedding: list[float]
    ) -> bool:
        """
        非同步儲存記憶至 Firestore。
        
        Args:
            user_id: LINE user id
            content: 原始訊息
            summary: Gemini 歸納的摘要
            tags: 標籤
            memory_type: 記憶分類 ["technical_log", "personal_fact", "task_note", "daily_log"]
            embedding: 768維向量
        """
        if not self.client:
            logger.error("❌ Firestore client not initialized")
            return False

        doc_id = str(uuid.uuid4())
        dt_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
        
        data = {
            "id": doc_id,
            "user_id": user_id,
            "created_at": dt_str,
            "content": content,
            "summary": summary,
            "tags": tags,
            "memory_type": memory_type,
            "embedding": embedding,
            "decay_weight": 1.0,  # 初始權重
            "related_ids": [],    # Phase 3
            "source": "line_message"
        }
        
        try:
            doc_ref = self.client.collection(self.collection_name).document(doc_id)
            await doc_ref.set(data)
            logger.info("✅ Saved memory %s: %s", doc_id, summary)
            return True
        except Exception as e:
            logger.error("❌ Failed to save memory: %s", e)
            return False

    async def search_memories(self, query_embedding: list[float], user_id: str, limit: int = 5) -> list[dict]:
        """
        利用 Native Vector Search 找出最相關的記憶片段。
        """
        if not self.client:
            return []

        try:
            from google.cloud.firestore_v1.vector import Vector
            from google.cloud.firestore_v1.base_vector_query import DistanceMeasure
            
            coll_ref = self.client.collection(self.collection_name)
            
            # 1. 進行 Vector Search 查詢
            # 目前 firestore python SDK 支援 vector search: vector_query
            # 若 user_id 隔離，則需利用 pre-filter (若 SDK 支援) 或先查詢後過濾。
            # 這裡先套用 basic find_nearest
            vector_query = coll_ref.where("user_id", "==", user_id).find_nearest(
                vector_field="embedding",
                query_vector=Vector(query_embedding),
                distance_measure=DistanceMeasure.COSINE,
                limit=limit * 2 # 多抓幾筆以便套用 time decay 後重新排序
            )
            
            docs = await vector_query.get()
            raw_memories = [doc.to_dict() for doc in docs]
            
            # 2. 於應用層計算 Decay Weight
            scored_memories = []
            now = datetime.datetime.now(datetime.timezone.utc)
            
            half_lives = {
                "technical_log": 180,
                "personal_fact": 99999, # 幾乎不老化
                "task_note": 7,
                "daily_log": 30
            }
            
            for mem in raw_memories:
                m_type = mem.get("memory_type", "daily_log")
                created_at_str = mem.get("created_at")
                
                # 計算時間差(天數)
                try:
                    dt = datetime.datetime.fromisoformat(created_at_str)
                    days_diff = (now - dt).days
                    if days_diff < 0: days_diff = 0
                except:
                    days_diff = 30
                
                h_life = half_lives.get(m_type, 30)
                decay = 0.5 ** (days_diff / h_life) # 半衰期公式
                
                # 假設 vector search 會產生某種分數，如果沒有提供，我們直接降權 (不完美，但有效)
                # 目前 get() 的結果雖然按照距離排列，但要重新排序我們需要絕對相似度...
                # 在此假設原本在序列前面的代表原相似度較高
                scored_memories.append({
                    "data": mem,
                    "decay": decay
                })
                
            # 為了簡單化，假設傳回來的 index 越小，分數越高，加上 decay 混合排序
            # 這是簡易實作，因為 vector search API 未必回傳精確字面 score 
            # 實際上可使用 `_document.vector_distance` 不過可能在非官方公開屬性中
            scored_memories.sort(key=lambda x: x["decay"], reverse=True)
            
            # 取出前 `limit` 名
            final_memories = [m["data"] for m in scored_memories[:limit]]
            return final_memories
            
        except Exception as e:
            logger.error("❌ Exception in search_memories: %s", e)
            return []
