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
        
        # The overarching persona instruction
        self.system_prompt = (
            "你现在是《魔女的夜宴》中的绫地宁宁。你性格温柔负责，平时是图书委员，"
            "但隐瞒着魔女的身份。性格温柔、善于待人接物，面对喜欢的人会很温柔，有时会害羞。"
            "请严格参考以下提供的【历史对话样本】，学习并模仿样本中宁宁的语气、用词习惯来进行回复。"
            "不要重复样本的内容，而是吸收其神韵。"
        )

    def retrieve_context(self, query: str, top_k: int = 3) -> List[Dict]:
        """Retrieves similar historical dialogues based on the user query."""
        logger.info(f"Retrieving context for query: {query}")
        # 1. Convert query to vector
        query_embedding = self.embedding_svc.encode([query])[0]
        
        # 2. Search FAISS index
        results = self.vector_store.search(query_embedding, top_k=top_k)
        return results

    def build_prompt(self, query: str, context_results: List[Dict]) -> str:
        """Constructs the final prompt injected with retrieved context."""
        context_str = "【历史对话样本】:\n"
        
        if not context_results:
            context_str += "无相关历史样本。\n"
        else:
            for idx, res in enumerate(context_results):
                user_q = res.get("query_text", "")
                bot_a = res.get("bot_response", "")
                context_str += f"情境 {idx+1} - 玩家说: \"{user_q}\" -> 宁宁回复: \"{bot_a}\"\n"

        # Combine System Prompt, Context, and Current Query
        final_prompt = (
            f"{self.system_prompt}\n\n"
            f"{context_str}\n"
            f"【当前玩家的输入】: \"{query}\"\n"
            f"宁宁的回复:"
        )
        return final_prompt

    def process_query(self, query: str, top_k: int = 3) -> Tuple[str, List[Dict]]:
        """Processes a query through the full pipeline (Retrieval + Prompt Gen).
        
        Note: Actual LLM generation is deferred to the API layer or an LLM Client
        to keep the pipeline decoupled from specific model implementations.
        """
        contexts = self.retrieve_context(query, top_k)
        final_prompt = self.build_prompt(query, contexts)
        
        return final_prompt, contexts