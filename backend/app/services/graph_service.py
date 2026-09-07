# -*- coding: utf-8 -*-
"""
智法通 V2 —— Neo4j 法律知识图谱服务（语义化 schema）
节点：Law / Article / Case / Concept / PartyType
关系：HAS_ARTICLE / MENTIONS / REFERENCES{role} / INVOLVES / RELATES{type} / INVOLVES_PARTY
"""
from __future__ import annotations

import logging
import re
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings

logger = logging.getLogger(__name__)

_ARTICLE_SPLIT = re.compile(r"(?=第[零一二三四五六七八九十百千0-9]+条)")
_LAW_CITE = re.compile(r"《([^》]{2,40}?)》")
_CONCEPT_DOMAIN: dict[str, list[str]] = {
    "劳动": ["劳动", "劳动者", "用人单位", "工资", "工伤", "劳动合同", "解除"],
    "合同": ["合同", "买卖", "格式条款", "违约金", "履约", "催告"],
    "公司": ["公司", "股东", "董事", "注册资本", "法人"],
    "消费者": ["消费者", "消费", "退货", "三倍赔偿", "欺诈"],
    "民间借贷": ["民间借贷", "借款", "利率", "LPR", "利息"],
    "知识产权": ["知识产权", "著作权", "商标", "专利", "竞业限制", "商业秘密"],
    "婚姻家庭": ["婚姻", "离婚", "抚养", "继承", "赡养"],
    "侵权": ["侵权", "损害赔偿", "人身损害", "过错"],
}
_PARTY_TYPES = {
    "用人单位": ["用人单位", "公司", "企业"],
    "劳动者": ["劳动者", "员工", "职工"],
    "经营消费者": ["消费者"],
    "个人主体": ["个人", "自然人"],
}


def _short_name(name: str) -> str:
    return re.sub(r"(中华人民共和国|最高人民法院关于|规定|若干问题|（.*?）)", "", name).strip() or name


class GraphService:
    def __init__(self) -> None:
        self._driver: Any = None

    async def driver(self):
        if self._driver is None:
            from neo4j import AsyncGraphDatabase

            self._driver = AsyncGraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
            )
        return self._driver

    async def close_driver(self) -> None:
        if self._driver is not None:
            try:
                await self._driver.close()
            except Exception:
                pass
            self._driver = None

    async def verify_connectivity(self) -> bool:
        try:
            d = await self.driver()
            await d.verify_connectivity()
            return True
        except Exception as exc:
            logger.warning("Neo4j 连接失败: %s", exc)
            return False

    async def _run(self, query: str, **params) -> list[dict]:
        d = await self.driver()
        async with d.session(database=settings.NEO4J_DATABASE) as session:
            result = await session.run(query, **params)
            return [dict(r) for r in await result.data()]

    async def ensure_constraints(self) -> None:
        for stmt in [
            "CREATE CONSTRAINT law_name IF NOT EXISTS FOR (n:Law) REQUIRE n.name IS UNIQUE",
            "CREATE CONSTRAINT article_id IF NOT EXISTS FOR (n:Article) REQUIRE n.node_id IS UNIQUE",
            "CREATE CONSTRAINT case_id IF NOT EXISTS FOR (n:Case) REQUIRE n.node_id IS UNIQUE",
            "CREATE CONSTRAINT concept_name IF NOT EXISTS FOR (n:Concept) REQUIRE n.name IS UNIQUE",
            "CREATE CONSTRAINT party_name IF NOT EXISTS FOR (n:PartyType) REQUIRE n.name IS UNIQUE",
        ]:
            try:
                await self._run(stmt)
            except Exception as exc:
                logger.debug("约束创建跳过: %s", exc)

    # ---------------- 建图 ----------------
    async def build_graph(self, db: AsyncSession) -> dict:
        if not await self.verify_connectivity():
            return {"ok": False, "reason": "neo4j_unavailable"}
        await self.ensure_constraints()
        await self._run("MATCH (n) DETACH DELETE n")
        from app.models.knowledge import LegalDocument

        docs = (await db.execute(select(LegalDocument))).scalars().all()
        law_docs = [d for d in docs if d.doc_type == "法律"]
        case_docs = [d for d in docs if d.doc_type == "案例"]
        stats = {"laws": 0, "articles": 0, "cases": 0, "concepts": 0, "edges": 0}

        concept_ids: set[str] = set()
        for cname, _kw in _CONCEPT_DOMAIN.items():
            concept_ids.add(cname)
        for cname in concept_ids:
            await self._merge("Concept", cname, {"domain": next((d for d, k in _CONCEPT_DOMAIN.items() if cname in k), "其他")})
        # PartyType 节点
        for pname in _PARTY_TYPES:
            await self._merge("PartyType", pname, {})

        for doc in law_docs:
            lname = _short_name(doc.title)
            await self._merge("Law", lname, {"effective_date": str(doc.effective_date or "")})
            stats["laws"] += 1
            segments = self._split_articles(doc.content or "")
            for i, (ano, ac) in enumerate(segments):
                node_id = f"law_{doc.id}_art_{ano or i}"
                await self._merge(
                    "Article",
                    node_id,
                    {"law_name": lname, "article_no": ano or "", "content": ac[:2000], "order": i},
                )
                await self._rel(
                    "Law", lname, "Article", node_id, "HAS_ARTICLE", {"order": i}
                )
                stats["articles"] += 1
                # Article → Concept（关键词最长匹配）
                for cname, kws in _CONCEPT_DOMAIN.items():
                    if any(k in ac for k in kws):
                        await self._rel("Article", node_id, "Concept", cname, "MENTIONS", {})
                        stats["edges"] += 1
                        break

        law_names = {_short_name(d.title) for d in law_docs}
        # 汇总 法名 -> Article 节点列表，供案例 REFERENCES 关联
        article_by_law: dict[str, list[dict]] = {}
        arts_rows = await self._run(
            "MATCH (a:Article) RETURN a.node_id AS nid, a.law_name AS ln, a.article_no AS ano, a.content AS c"
        )
        for a in arts_rows:
            article_by_law.setdefault(a.get("ln", ""), []).append(
                {"nid": a["nid"], "ano": a.get("ano") or "", "content": a.get("c") or ""}
            )

        for cdoc in case_docs:
            node_id = f"case_{cdoc.id}"
            cname = _short_name(cdoc.title)
            await self._merge("Case", node_id, {"name": cname, "summary": (cdoc.content or "")[:600]})
            stats["cases"] += 1
            content = cdoc.content or ""
            # REFERENCES：案例所引法条关联到对应 Law 的 Article 节点
            for cite in set(_LAW_CITE.findall(content)):
                target_law = self._match_law(cite, law_names)
                if not target_law:
                    continue
                candidates = article_by_law.get(target_law, [])
                target_art = None
                if candidates:
                    nearest = self._nearest_article(cite, content)
                    target_art = next(
                        (a for a in candidates if a["ano"] and f"第{a['ano']}条" in nearest), None
                    ) or candidates[0]
                if target_art:
                    role = "APPLIES"
                    if any(k in content for k in ["无效", "违法", "不支持"]):
                        role = "OVERRULES"
                    elif "判决" in content or "法院认为" in content:
                        role = "CITES"
                    await self._rel("Case", node_id, "Article", target_art["nid"], "REFERENCES", {"role": role})
                    stats["edges"] += 1
                else:
                    await self._rel("Case", node_id, "Law", target_law, "INVOLVES", {})
                    stats["edges"] += 1
            for cname2, kws in _CONCEPT_DOMAIN.items():
                if any(k in content for k in kws):
                    await self._rel("Case", node_id, "Concept", cname2, "INVOLVES", {})
                    stats["edges"] += 1
            for pname, kws in _PARTY_TYPES.items():
                if any(k in content for k in kws):
                    await self._rel("Case", node_id, "PartyType", pname, "INVOLVES_PARTY", {})
                    stats["edges"] += 1

        # Article→Article RELATES{type}（同法引“第X条”）
        arts = await self._run("MATCH (a:Article) RETURN a.node_id AS nid, a.law_name AS ln, a.content AS c")
        by_law: dict[str, list[dict]] = {}
        for a in arts:
            by_law.setdefault(a.get("ln", ""), []).append(a)
        for ln, items in by_law.items():
            for a in items:
                refs = set(re.findall(r"第([零一二三四五六七八九十百千0-9]+)条", a.get("c") or ""))
                for ref in refs:
                    for b in items:
                        if b.get("nid") != a.get("nid") and ref and ref in (b.get("c") or "")[:40]:
                            await self._rel("Article", a.get("nid"), "Article", b.get("nid"), "RELATES", {"type": "引用"})
                            stats["edges"] += 1
                            break
        return {"ok": True, "stats": stats}

    async def _merge(self, label: str, name: str, props: dict) -> None:
        key = "name" if label in ("Law", "Concept", "PartyType") else "node_id"
        await self._run(
            f"MERGE (n:{label} {{{key}: $key}}) SET n += $props",
            key=name,
            props={k: (v if v is not None else "") for k, v in props.items()},
        )

    async def _rel(self, a_label, a_name, b_label, b_name, rel, props=None) -> None:
        a_key = "name" if a_label in ("Law", "Concept", "PartyType") else "node_id"
        b_key = "name" if b_label in ("Law", "Concept", "PartyType") else "node_id"
        await self._run(
            f"MATCH (a:{a_label} {{{a_key}: $a}}), (b:{b_label} {{{b_key}: $b}}) "
            f"MERGE (a)-[r:{rel}]->(b) SET r += $props",
            a=a_name,
            b=b_name,
            props=props or {},
        )

    def _split_articles(self, content: str) -> list[tuple[Optional[str], str]]:
        parts = _ARTICLE_SPLIT.split(content or "")
        out = []
        for p in parts:
            p = p.strip()
            if not p:
                continue
            m = re.match(r"第([零一二三四五六七八九十百千0-9]+)条", p)
            ano = m.group(1) if m else None
            out.append((ano, p))
        return out[:200]

    def _match_law(self, cite: str, law_names: set[str]) -> Optional[str]:
        c = _short_name(cite)
        for ln in law_names:
            if c and (c in ln or ln in c or c in cite or (len(c) >= 2 and c in ln)):
                return ln
        return None

    def _nearest_article(self, cite: str, content: str) -> str:
        m = re.search(re.escape(cite) + r".{0,60}?第([零一二三四五六七八九十百千0-9]+)条", content)
        return f"第{m.group(1)}条" if m else ""

    # ---------------- 查询 ----------------
    async def query_graph(self, max_nodes: Optional[int] = None) -> dict:
        if not await self.verify_connectivity():
            return {"source": "unavailable", "nodes": [], "links": [], "categories": []}
        limit = max_nodes or settings.NEO4J_MAX_QUERY_NODES
        nodes = await self._run(
            "MATCH (n) WITH n, size([(n)--()|1]) AS deg "
            "RETURN labels(n)[0] AS label, coalesce(n.name, n.node_id) AS id, deg "
            "ORDER BY deg DESC LIMIT $limit",
            limit=limit,
        )
        ids = [n["id"] for n in nodes]
        labels = {n["id"]: n["label"] for n in nodes}
        cats = ["法律", "法条", "案例", "概念", "当事人类型"]
        links = []
        if ids:
            links = await self._run(
                "MATCH (a)-[r]->(b) WHERE coalesce(a.name,a.node_id) IN $ids "
                "AND coalesce(b.name,b.node_id) IN $ids RETURN "
                "coalesce(a.name,a.node_id) AS s, type(r) AS t, coalesce(b.name,b.node_id) AS e",
                ids=ids,
            )
        node_list = []
        for n in nodes:
            label = n["label"]
            cat = {"Law": 0, "Article": 1, "Case": 2, "Concept": 3, "PartyType": 4}.get(label, 0)
            node_list.append(
                {
                    "id": n["id"],
                    "name": n["id"],
                    "category": cat,
                    "symbolSize": min(20 + int(n.get("deg", 0)) * 3, 60),
                    "degree": int(n.get("deg", 0)),
                }
            )
        return {
            "source": "neo4j",
            "nodes": node_list,
            "links": [
                {"source": l["s"], "target": l["e"], "relation": l["t"]}
                for l in links
            ],
            "categories": [{"name": c} for c in cats],
        }

    async def get_stats(self) -> dict:
        if not await self.verify_connectivity():
            return {"available": False}
        counts = await self._run(
            "MATCH (n) RETURN labels(n)[0] AS label, count(*) AS c"
        )
        total = sum(int(x["c"]) for x in counts)
        return {
            "available": True,
            "total": total,
            "by_label": {x["label"]: int(x["c"]) for x in counts},
        }

    async def graph_query_text(self, question: str, top_n: int = 5) -> list[dict]:
        """GraphRAG：从图谱返回与问题相关的法条/案例文本候选。"""
        if not await self.verify_connectivity():
            return []
        # 概念匹配：找出问题命中的领域概念
        concept = next((c for c, kws in _CONCEPT_DOMAIN.items() if any(k in question for k in kws)), None)
        results: list[dict] = []
        if concept:
            rows = await self._run(
                "MATCH (c:Concept {name:$name})<-[:MENTIONS]-(a:Article) "
                "RETURN a.node_id AS id, a.content AS content, a.law_name AS law, a.article_no AS art LIMIT $n",
                name=concept,
                n=top_n,
            )
            results.extend(
                [
                    {"id": r.get("id"), "text": r.get("content", ""), "law_name": r.get("law"), "article_no": r.get("art")}
                    for r in rows
                ]
            )
        # 命中的法名 → 关联案例
        for cite in set(_LAW_CITE.findall(question)):
            rows = await self._run(
                "MATCH (l:Law)<-[:INVOLVES]-(ca:Case) WHERE l.name CONTAINS $n "
                "RETURN ca.node_id AS id, ca.summary AS content LIMIT 3",
                n=cite,
            )
            results.extend([{"id": r.get("id"), "text": r.get("content", ""), "law_name": cite, "article_no": ""} for r in rows])
        return results[:top_n]


graph_service = GraphService()
