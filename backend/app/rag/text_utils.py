# -*- coding: utf-8 -*-
"""
智法通 V2 —— 文本分块与统一向量元数据构造（单一路径，修复旧 metadata 双轨缺陷）

分块策略：
1. 法律/法规类文本按“第X条”条款切分，输出条款级 chunk（带 article_no/law_name），
   供引用校验、GraphRAG 实体链接、时间旅行使用；
2. 其他文本按滑窗(500/50)切分。
统一 metadata：document_id/chunk_index/doc_type/title/law_name/article_no/effectiveness/
effective_date(epoch int)/version。
"""
from __future__ import annotations

import re
from typing import Optional

from app.config import settings

_ARTICLE_HEAD = re.compile(r"第[零一二三四五六七八九十百千万〇0-9]{1,10}条")

LAW_DOC_TYPES = ("法律", "行政法规", "司法解释", "法规")


def _find_article_segments(text: str) -> list[tuple[int, int, str]]:
    """返回 [(start, end, article_no), ...]。头部无条款前缀文本并入首个条款。"""
    matches = list(_ARTICLE_HEAD.finditer(text))
    if not matches:
        return []
    segs: list[tuple[int, int, str]] = []
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        segs.append((start, end, m.group()))
    # 首个条款前的导言并入首个条款
    if segs and segs[0][0] > 0:
        s0, e0, a0 = segs[0]
        segs[0] = (0, e0, a0)
    return segs


def _window_split(text: str, chunk_size: int, overlap: int) -> list[str]:
    if len(text) <= chunk_size:
        return [text.strip()] if text.strip() else []
    parts: list[str] = []
    step = chunk_size - overlap
    start = 0
    n = len(text)
    while start < n:
        end = min(start + chunk_size, n)
        parts.append(text[start:end])
        if end == n:
            break
        start += step
    return [p.strip() for p in parts if p.strip()]


def split_document_text(
    title: str,
    doc_type: str,
    content: str,
    *,
    effectiveness: str = "有效",
    effective_epoch: Optional[int] = None,
    version: str = "",
    chunk_size: Optional[int] = None,
    overlap: Optional[int] = None,
) -> list[dict]:
    """按文档切分为统一 chunk 字典（含向量元数据字段）。"""
    cs = chunk_size or settings.RAG_CHUNK_SIZE
    ov = overlap if overlap is not None else settings.RAG_CHUNK_OVERLAP
    content = (content or "").strip()
    if not content:
        return []

    chunks: list[dict] = []
    use_articles = doc_type in LAW_DOC_TYPES and bool(_ARTICLE_HEAD.search(content))
    if use_articles:
        for start, end, article_no in _find_article_segments(content):
            seg = content[start:end].strip()
            if not seg:
                continue
            if len(seg) <= cs * 2:
                pieces = [seg]
            else:
                pieces = _window_split(seg, cs, ov)
            for p in pieces:
                chunks.append(
                    {
                        "text": p,
                        "law_name": title,
                        "article_no": article_no,
                        "effectiveness": effectiveness,
                        "effective_epoch": effective_epoch,
                        "version": version,
                        "is_article": True,
                    }
                )
    else:
        for p in _window_split(content, cs, ov):
            chunks.append(
                {
                    "text": p,
                    "law_name": title,
                    "article_no": None,
                    "effectiveness": effectiveness,
                    "effective_epoch": effective_epoch,
                    "version": version,
                    "is_article": False,
                }
            )
    return chunks
