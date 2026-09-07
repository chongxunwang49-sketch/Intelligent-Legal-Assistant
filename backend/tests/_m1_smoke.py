# -*- coding: utf-8 -*-
"""M1 冒烟：建表 + 种子 + 认证服务（临时开发脚本）。"""
import asyncio

import app.models  # noqa: F401  注册全部表
from app.database import Base, AsyncSessionLocal, engine
from app.init_data import init_seed_data
from app.services import auth_service
from app.utils.deps import _load_current_user
from app.services.quota_service import quota_service


async def main() -> None:
    # 1. 建表
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("[1] 建表完成")

    # 2. 种子（连续两次验证幂等）
    async with AsyncSessionLocal() as db:
        r1 = await init_seed_data(db)
        print("[2] 种子完成:", r1)
    async with AsyncSessionLocal() as db:
        r2 = await init_seed_data(db)
        print("    再次种子完成(幂等):", r2)

    # 3. 三角色登录
    async with AsyncSessionLocal() as db:
        for u, p, expect in [
            ("admin", "admin123", "superuser"),
            ("lawyer", "lawyer123", "legal_admin"),
            ("user", "user123456", "user"),
        ]:
            res = await auth_service.login(db, u, p)
            roles = [x["code"] for x in res["user"]["roles"]]
            print(f"    login {u} OK roles={roles} super={res['user']['is_superuser']}")

    # 4. 注册新用户
    async with AsyncSessionLocal() as db:
        import random

        uname = f"tester{random.randint(1000, 9999)}"
        reg = await auth_service.register(db, uname, f"{uname}@x.com", "Test123456")
        print(f"[4] 注册 {uname} OK roles=", [x["code"] for x in reg["user"]["roles"]])

    # 5. 用户缓存权限计算 + 额度
    async with AsyncSessionLocal() as db:
        cu = await _load_current_user(reg["user"]["id"], db)
        print("[5] tester 权限码:", cu.permission_codes, "| legal_admin:", cu.is_legal_admin)
        q = await quota_service.get_quota(cu, "qa")
        print("     tester qa 额度:", q)
    print("SMOKE OK")


if __name__ == "__main__":
    asyncio.run(main())
