# -*- coding: utf-8 -*-
"""
智法通 V2 —— 端到端验收（部署后执行，对齐 V6 级口径）

用法：python tests/e2e_v2.py [base_url]   默认 http://localhost:28000
输出：tests/e2e_results.json（passed/failed/total/pass_rate + 明细 + 性能）
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:28000"
P = f"{BASE}/api/v1"
RESULTS: list[dict] = []


def check(name: str, ok: bool, detail: str = "", ms: int = 0):
    RESULTS.append({"name": name, "passed": bool(ok), "detail": detail, "ms": ms})
    mark = "PASS" if ok else "FAIL"
    print(f"[{mark}] {name}" + (f"  ({ms}ms)" if ms else "") + (f"  :: {detail}" if detail and not ok else ""))


def main():
    c = httpx.Client(base_url=BASE, timeout=300)

    # 1 健康
    t0 = time.perf_counter()
    try:
        r = c.get("/health")
        check("系统健康 /health", r.status_code == 200 and r.json().get("status") == "healthy",
              ms=int((time.perf_counter() - t0) * 1000))
    except Exception as e:
        check("系统健康 /health", False, str(e))

    def login(u, p):
        rr = c.post(f"{P}/auth/login", json={"username": u, "password": p})
        return rr.json()["access_token"], rr.json()["user"]

    # 2 认证与 RBAC
    tokens = {}
    for u, p in [("admin", "admin123"), ("lawyer", "lawyer123"), ("user", "user123456")]:
        try:
            tok, user = login(u, p)
            tokens[u] = tok
            roles = [x["code"] for x in user["roles"]]
            check(f"登录 {u}", tok and user.get("id"), f"roles={roles}")
        except Exception as e:
            check(f"登录 {u}", False, str(e))

    def hd(u):
        return {"Authorization": f"Bearer {tokens[u]}"}

    try:
        me = c.get(f"{P}/auth/me", headers=hd("admin")).json()
        check("GET /auth/me 权限码", "analysis:view" in me.get("permission_codes", []),
              f"perms={me.get('permission_codes')}")
    except Exception as e:
        check("GET /auth/me 权限码", False, str(e))
    check("RBAC: user 访问 /users 拒绝", c.get(f"{P}/users", headers=hd("user")).status_code == 403)
    check("RBAC: lawyer 访问 /users 拒绝", c.get(f"{P}/users", headers=hd("lawyer")).status_code == 403)
    check("RBAC: admin 访问 /users 放行", c.get(f"{P}/users", headers=hd("admin")).status_code == 200)
    check("RBAC: user 访问 /analysis 拒绝", c.get(f"{P}/analysis/overview", headers=hd("user")).status_code == 403)
    check("RBAC: lawyer 访问 /analysis 放行", c.get(f"{P}/analysis/overview", headers=hd("lawyer")).status_code == 200)
    check("弱密码注册拒绝", c.post(f"{P}/auth/register", json={"username": "weak1", "email": "w1@x.com", "password": "123456"}).status_code in (400, 422))
    check("无 token 401", c.get(f"{P}/auth/me").status_code == 401)

    # 3 知识库 / 两阶段检索
    st = c.get(f"{P}/knowledge/stats", headers=hd("user")).json()
    check("知识库统计(文档>0)", st.get("total_documents", 0) > 0, f"docs={st.get('total_documents')} chunks={st.get('total_chunks')}")
    r = c.post(f"{P}/knowledge/search", headers=hd("user"), json={"query": "试用期最长多久", "top_k": 5}).json()
    check("知识库语义检索命中", len(r.get("items", [])) > 0, f"hits={len(r.get('items', []))}")

    # 4 图谱 + 时间旅行
    gs = c.get(f"{P}/graph/stats", headers=hd("user")).json()
    check("Neo4j 图谱可用(节点>0)", gs.get("available") and gs.get("total", 0) > 0, f"total={gs.get('total')}")
    gk = c.get(f"{P}/graph/knowledge", headers=hd("user")).json()
    check("图谱可视化数据(nodes>0)", len(gk.get("nodes", [])) > 0)
    v0 = c.get(f"{P}/graph/law-versions", headers=hd("user"), params={"at_date": "2020-06-01"}).json()
    v1 = c.get(f"{P}/graph/law-versions", headers=hd("user"), params={"at_date": "2021-06-01"}).json()
    t0n = [i["title"] for i in v0["items"]]
    t1n = [i["title"] for i in v1["items"]]
    check("时间旅行 2020 含合同法", "中华人民共和国合同法" in t0n)
    check("时间旅行 2021 剔除合同法", "中华人民共和国合同法" not in t1n)

    # 5 分析 / 仪表盘 / 通知
    ht = c.get(f"{P}/analysis/hot-topics", headers=hd("lawyer"), params={"days": 30}).json()
    check("热点分析返回", len(ht.get("items", [])) > 0)
    ov = c.get(f"{P}/dashboard/overview", headers=hd("lawyer")).json()
    check("仪表盘概览", "today_queries" in ov)
    un = c.get(f"{P}/notifications/unread-count", headers=hd("user")).json()
    check("通知未读数接口", "unread_count" in un)

    # 6 合同（含种子 REVIEWED 演示合同取报告）
    hist = c.get(f"{P}/contract/history", headers=hd("admin")).json()["items"]
    check("合同历史(含演示)", len(hist) > 0, f"count={len(hist)}")
    reviewed = [x for x in hist if x.get("status") == "reviewed"]
    if reviewed:
        rep = c.get(f"{P}/contract/report/{reviewed[0]['id']}", headers=hd("admin")).json()
        check("合同报告返回风险条款", "risk_level" in rep, f"score={rep.get('overall_score')} risk={rep.get('risk_level')}")
    else:
        check("合同报告返回风险条款", False, "无已审查合同")

    # 7 问答（非流式，含 GraphRAG/自评估/引用；记录性能）
    t0 = time.perf_counter()
    try:
        ans = c.post(f"{P}/qa/ask", headers=hd("user"), json={"question": "签三年劳动合同试用期约定六个月合法吗？"}).json()
        ms = int((time.perf_counter() - t0) * 1000)
        check("智能问答(非流式)", bool(ans.get("answer")) and "conversation_id" in ans, f"conf={ans.get('confidence')}", ms=ms)
    except Exception as e:
        check("智能问答(非流式)", False, str(e))

    # 汇总
    passed = sum(1 for x in RESULTS if x["passed"])
    failed = sum(1 for x in RESULTS if not x["passed"])
    total = len(RESULTS)
    out = {
        "summary": {"passed": passed, "failed": failed, "skipped": 0, "total": total,
                    "pass_rate": round(passed * 100.0 / total, 2) if total else 0},
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "results": RESULTS,
    }
    Path("tests/e2e_results.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("=" * 40)
    print(f"SUMMARY: {passed}/{total} passed, rate={out['summary']['pass_rate']}%")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
