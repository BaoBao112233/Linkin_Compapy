# ==============================
# LinkedIn Company Scraper
# File: keyword_generator.py
# Dùng Groq LLM để sinh từ khóa tìm kiếm LinkedIn
# ==============================
"""
Ví dụ sử dụng độc lập:

    from keyword_generator import KeywordGenerator
    gen = KeywordGenerator()
    keywords = gen.generate("fintech ")
    # ["fintech", "neobank", "digital payments", "mobile banking", ...]
"""

from __future__ import annotations

from loguru import logger
from pydantic import BaseModel, Field

import config


class KeywordList(BaseModel):
    keywords: list[str] = Field(
        description=(
            "Danh sách các từ khóa tìm kiếm LinkedIn liên quan đến lĩnh vực/chủ đề đầu vào. "
            "Mỗi từ khóa ngắn gọn (1-4 từ), phù hợp tìm kiếm công ty trên LinkedIn."
        )
    )
    reasoning: str = Field(
        default="",
        description="Giải thích ngắn tại sao chọn các từ khóa này.",
    )


class KeywordGenerator:
    """
    Dùng Groq LLM để mở rộng 1 chủ đề → nhiều từ khóa LinkedIn.

    Ví dụ:
        "fintech" → ["fintech", "neobank", "digital payments", "mobile wallet",
                     "payment gateway", "insurtech", "wealthtech", "regtech", ...]
    """

    def __init__(self):
        self._chain = None  # lazy init

    def _get_chain(self):
        if self._chain is not None:
            return self._chain

        from langchain_groq import ChatGroq
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_core.output_parsers import JsonOutputParser

        llm = ChatGroq(
            model=config.GROQ_MODEL,
            temperature=0.4,          # càng cao → càng sáng tạo
            api_key=config.GROQ_API_KEY,
        )
        parser = JsonOutputParser(pydantic_object=KeywordList)

        prompt = ChatPromptTemplate.from_messages([
            (
                "system",
                """You are an expert LinkedIn company researcher. Your task is to expand a given topic or industry 
into a comprehensive list of search keywords that can be used to find relevant companies on LinkedIn.

Guidelines:
- Generate {n} diverse, specific keywords covering all sub-niches of the topic.
- Include: industry names, technology terms, business models, product types, common job titles as identifiers.
- Mix English and the language of any location mentioned in the topic.
- Keep each keyword short (1-4 words), suitable for LinkedIn company search.
- Avoid duplicates and overly generic terms like "software" or "company".
- Return JSON strictly matching this schema:
{format_instructions}""",
            ),
            (
                "user",
                "Generate LinkedIn search keywords for this topic/industry: {topic}",
            ),
        ]).partial(format_instructions=parser.get_format_instructions())

        self._chain = prompt | llm | parser
        return self._chain

    def generate(self, topic: str, n: int = 20) -> list[str]:
        """
        Sinh danh sách từ khóa liên quan đến `topic`.

        Args:
            topic: Chủ đề / ngành (vd: "fintech ", "healthcare AI", "SaaS B2B")
            n:     Số lượng từ khóa muốn sinh (gợi ý LLM, không phải giới hạn cứng)

        Returns:
            list[str] – danh sách từ khóa, đã loại trùng lặp.
        """
        if not config.GROQ_API_KEY:
            logger.warning("GROQ_API_KEY chưa cấu hình – trả về từ khóa gốc.")
            return [topic]

        logger.info(f"[KeywordGen] Đang sinh từ khóa cho: '{topic}' (yêu cầu ~{n} keywords)...")
        try:
            chain = self._get_chain()
            result = chain.invoke({"topic": topic, "n": n})

            if isinstance(result, dict):
                keywords: list[str] = result.get("keywords", [])
                reasoning: str = result.get("reasoning", "")
            else:
                keywords = getattr(result, "keywords", [])
                reasoning = getattr(result, "reasoning", "")

            # Loại trùng, giữ thứ tự, normalize
            seen: set[str] = set()
            clean: list[str] = []
            for kw in keywords:
                kw_lower = kw.strip().lower()
                if kw_lower and kw_lower not in seen:
                    seen.add(kw_lower)
                    clean.append(kw.strip())

            if reasoning:
                logger.debug(f"[KeywordGen] Lý do: {reasoning}")

            logger.success(f"[KeywordGen] Sinh được {len(clean)} từ khóa: {clean}")
            return clean

        except Exception as exc:
            logger.warning(f"[KeywordGen] LLM lỗi: {exc} – trả về từ khóa gốc.")
            return [topic]
