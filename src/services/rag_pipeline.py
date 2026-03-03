"""Core RAG pipeline service orchestrating retrieval and prompt generation."""

import logging
from typing import Dict, List, Tuple

from src.infrastructure.vector_store.faiss_impl import FaissVectorStore
from src.services.embedding_svc import EmbeddingService

logger = logging.getLogger(__name__)


class RAGPipeline:
    """Orchestrates the Retrieval-Augmented Generation process."""

    def __init__(self, vector_store: FaissVectorStore, embedding_svc: EmbeddingService):
        """Initializes the RAG Pipeline with necessary services."""
        self.vector_store = vector_store
        self.embedding_svc = embedding_svc
        
        # INDUSTRIAL STANDARD: Define a distance threshold.
        # Since we use L2 distance in FAISS:
        # - Close to 0: Nearly identical
        # - 0.3 to 0.6: Very similar
        # - 0.7 to 0.9: Loosely related
        # - > 1.0: Likely irrelevant
        self.match_threshold = 0.8  # Adjust this based on testing results

        # Refined system prompt with clearer instructions on context usage
        self.system_prompt = (
            "你现在是《魔女的夜宴》中的绫地宁宁。你性格温柔负责，平时是图书委员，但隐瞒着魔女身份。"
            "性格温柔、善于待人接物，面对喜欢的人会很温柔，有时会害羞，说话常带'……'。\n"
            "【回复准则】：\n"
            "1. 模仿提供的【参考样本】中的语气和用词习惯（如语气词）。\n"
            "2. 如果样本与当前玩家的话题无关，请忽略样本内容，仅保持性格设定进行自由回答。\n"
            "3. 绝对不要直接复述或搬运样本中的对话内容。"
        )

    def retrieve_context(self, query: str, top_k: int = 3) -> List[Dict]:
        """Retrieves similar historical dialogues based on the user query."""
        logger.info(f"Retrieving context for query: {query}")
        query_embedding = self.embedding_svc.encode([query])[0]
        return self.vector_store.search(query_embedding, top_k=top_k)

    def build_prompt(self, query: str, context_results: List[Dict]) -> str:
        """Constructs the final prompt injected with filtered context."""
        context_str = "【参考样本】:\n"
        
        # If no results passed the threshold, we provide a fallback instruction
        if not context_results:
            context_str += "(无相关历史记忆，请根据性格设定自由发挥)\n"
            logger.info("No contexts passed the similarity threshold.")
        else:
            for idx, res in enumerate(context_results):
                user_q = res.get("query_text", "")
                bot_a = res.get("bot_response", "")
                score = res.get("distance_score", 0.0)
                context_str += f"样本 {idx+1} [相似度:{score:.4f}] - 玩家说: \"{user_q}\" -> 宁宁回: \"{bot_a}\"\n"

        final_prompt = (
            f"{self.system_prompt}\n\n"
            f"{context_str}\n"
            f"【当前玩家的输入】: \"{query}\"\n"
            f"宁宁的回复:"
        )
        return final_prompt

    def process_query(self, query: str, top_k: int = 3) -> Tuple[str, List[Dict]]:
        """Processes a query with similarity threshold filtering."""
        # 1. Get raw search results
        raw_contexts = self.retrieve_context(query, top_k)
        
        # 2. FILTERING LOGIC: Only keep results within the threshold
        # This is the key fix for the "donkey's head on a horse" problem
        filtered_contexts = [
            ctx for ctx in raw_contexts 
            if ctx.get("distance_score", 1.0) < self.match_threshold
        ]
        
        # 3. Build prompt with filtered results
        final_prompt = self.build_prompt(query, filtered_contexts)
        
        return final_prompt, filtered_contexts