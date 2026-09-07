# -*- coding: utf-8 -*-
"""智法通 V2 —— 文件解析（PDF / Word / TXT 多编码）。"""
from __future__ import annotations

import os
from typing import Optional

_TXT_ENCODINGS = ("utf-8", "gb18030", "gbk", "utf-16")


class FileParseError(Exception):
    pass


def _parse_pdf(path: str) -> str:
    text_parts: list[str] = []
    # 首选 PyMuPDF（快），失败回退 pdfplumber（更稳的表格文本）
    try:
        import fitz  # PyMuPDF

        doc = fitz.open(path)
        for page in doc:
            text_parts.append(page.get_text())
        doc.close()
    except Exception:
        try:
            import pdfplumber

            with pdfplumber.open(path) as pdf:
                for page in pdf.pages:
                    text_parts.append(page.extract_text() or "")
        except Exception as exc:
            raise FileParseError(f"PDF 解析失败: {exc}") from exc
    return "\n".join(text_parts)


def _parse_docx(path: str) -> str:
    try:
        import docx

        d = docx.Document(path)
        return "\n".join(p.text for p in d.paragraphs)
    except Exception as exc:
        raise FileParseError(f"Word 解析失败: {exc}") from exc


def _parse_txt(path: str) -> str:
    raw = open(path, "rb").read()
    for enc in _TXT_ENCODINGS:
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("utf-8", errors="replace")


def _parse_doc(path: str) -> str:
    """.doc 老格式无法直接读；尝试 txt/word 二进制无法解析时抛错。"""
    raise FileParseError("暂不支持旧版 .doc 二进制格式，请转换为 .docx / .txt 后上传")


def parse_document(path: str, file_type: str) -> str:
    """按扩展名解析文档正文，返回文本。失败抛 FileParseError。"""
    if not os.path.exists(path):
        raise FileParseError("文件不存在或已被移动")
    ext = (file_type or "").lower().lstrip(".")
    if ext == "pdf":
        return _parse_pdf(path)
    if ext == "docx":
        return _parse_docx(path)
    if ext == "txt":
        return _parse_txt(path)
    if ext == "doc":
        return _parse_doc(path)
    # 未知类型按文本尝试
    return _parse_txt(path)
