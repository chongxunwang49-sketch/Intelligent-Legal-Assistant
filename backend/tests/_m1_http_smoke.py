# -*- coding: utf-8 -*-
"""M1 HTTP 冒烟：auth / RBAC / notifications / 额度（临时开发脚本）。"""
import httpx

BASE = "http://127.0.0.1:28000/api/v1"


def main():
    c = httpx.Client(base_url=BASE, timeout=20)
    r = c.get("http://127.0.0.1:28000/health")
    assert r.status_code == 200 and r.json()["status"] == "healthy"
    print("[health] ok")

    # 三角色登录
    tokens = {}
    for u, p in [("admin", "admin123"), ("lawyer", "lawyer123"), ("user", "user123456")]:
        r = c.post("/auth/login", json={"username": u, "password": p})
        assert r.status_code == 200, (u, r.text)
        tokens[u] = r.json()["access_token"]
        print(f"[login] {u} ok roles=", [x["code"] for x in r.json()["user"]["roles"]])

    # /me
    h = {"Authorization": f"Bearer {tokens['admin']}"}
    r = c.get("/auth/me", headers=h)
    assert r.status_code == 200
    me = r.json()
    print("[me] admin ok superuser=", me["is_superuser"], "perms=", me.get("permission_codes"))

    # RBAC：user 不能访问 /users（仅超管）
    r = c.get("/users?page=1&page_size=5", headers={"Authorization": f"Bearer {tokens['user']}"})
    assert r.status_code == 403, r.text
    print("[rbac] user->/users 403 ok")

    r = c.get("/users?page=1&page_size=5", headers={"Authorization": f"Bearer {tokens['lawyer']}"})
    assert r.status_code == 403
    print("[rbac] lawyer->/users 403 ok")

    r = c.get("/users?page=1&page_size=5", headers=h)
    assert r.status_code == 200
    print("[rbac] admin->/users ok total=", r.json()["total"])

    # 无 token 401
    r = c.get("/auth/me")
    assert r.status_code == 401
    print("[auth] no-token 401 ok")

    # 弱密码注册被拒
    r = c.post("/auth/register", json={"username": "weakuser", "email": "weak@x.com", "password": "123456"})
    assert r.status_code in (400, 422), r.text
    print("[auth] weak-password rejected ok")

    # 通知
    for u in ("admin", "lawyer", "user"):
        r = c.get("/notifications/unread-count", headers={"Authorization": f"Bearer {tokens[u]}"})
        assert r.status_code == 200
        print(f"[notify] {u} unread=", r.json()["unread_count"])

    # 额度（user 限 50）
    r = c.get("/qa/quota", headers={"Authorization": f"Bearer {tokens['user']}"})
    # /qa/quota 尚未实现 → 先不 assert，M3 接入。跳过。
    print("[M1 HTTP SMOKE] ALL OK")


if __name__ == "__main__":
    main()
