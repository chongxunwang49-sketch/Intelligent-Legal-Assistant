# -*- coding: utf-8 -*-
"""智法通 V2 —— 幂等种子数据（仅启动时由 main 调用，每步可重复执行）。

内容：三角色/内置账号/示例法律文档(含时间旅行样本)/演示合同与报告/欢迎通知/模拟分析数据。
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import naive_utcnow
from app.models.analysis import CitationStat, QueryLog
from app.models.contract import Contract, ReviewReport, RiskClause
from app.models.enums import (
    ContractStatus,
    DocumentSource,
    DocumentStatus,
    NotificationType,
    RiskLevel,
)
from app.models.knowledge import LegalDocument
from app.models.notification import Notification
from app.models.qa import Conversation, Message
from app.models.user import Permission, Role, User
from app.utils.security import hash_password

logger = logging.getLogger(__name__)

# ---------------- 角色/权限 ----------------
ROLE_SEED = [
    ("超级管理员", "admin", "拥有全部权限，可管理用户与系统", False),
    ("法务负责人", "legal_admin", "业务功能 + 数据分析 + 知识库管理", False),
    ("普通用户", "user", "法律问答 / 合同审查 / 法规检索", True),
]
PERMISSION_SEED = [
    ("查看数据分析", "analysis:view", "analysis", "view", "仪表盘与数据分析"),
    ("管理知识库", "knowledge:manage", "knowledge", "manage", "知识库上传/删除"),
]
BUILTIN_USERS = [
    ("admin", "admin@zhifatong.local", "admin123", True, ["admin"]),
    ("lawyer", "lawyer@zhifatong.local", "lawyer123", False, ["legal_admin"]),
    ("user", "user@zhifatong.local", "user123456", False, ["user"]),
]


# ---------------- 示例法律文档（含时间旅行样本） ----------------
def _law_doc(title, content, tags, effective, abolished=None, version="", summary=""):
    return {
        "title": title,
        "content": content,
        "tags": tags,
        "effective": effective,
        "abolished": abolished,
        "version": version,
        "summary": summary,
    }


SAMPLE_LEGAL_DOCS = [
    _law_doc(
        "中华人民共和国劳动合同法",
        """第一章 总则
第一条 为了完善劳动合同制度，明确劳动合同双方当事人的权利和义务，保护劳动者的合法权益，构建和发展和谐稳定的劳动关系，制定本法。
第二章 劳动合同的订立
第十七条 劳动合同应当具备以下条款：（一）用人单位的名称、住所和法定代表人或者主要负责人；（二）劳动者的姓名、住址和居民身份证或者其他有效身份证件号码；（三）劳动合同期限；（四）工作内容和工作地点；（五）工作时间和休息休假；（六）劳动报酬；（七）社会保险；（八）劳动保护、劳动条件和职业危害防护；（九）法律、法规规定应当纳入劳动合同的其他事项。
第十九条 劳动合同期限三个月以上不满一年的，试用期不得超过一个月；劳动合同期限一年以上不满三年的，试用期不得超过二个月；三年以上固定期限和无固定期限的劳动合同，试用期不得超过六个月。同一用人单位与同一劳动者只能约定一次试用期。
第三十九条 劳动者有下列情形之一的，用人单位可以解除劳动合同：（一）在试用期间被证明不符合录用条件的；（二）严重违反用人单位的规章制度的；（三）严重失职，营私舞弊，给用人单位造成重大损害的；（四）劳动者同时与其他用人单位建立劳动关系，对完成本单位的工作任务造成严重影响，或者经用人单位提出，拒不改正的；（五）因本法第二十六条第一款第一项规定的情形致使劳动合同无效的；（六）被依法追究刑事责任的。
第四十七条 经济补偿按劳动者在本单位工作的年限，每满一年支付一个月工资的标准向劳动者支付。六个月以上不满一年的，按一年计算；不满六个月的，向劳动者支付半个月工资的经济补偿。
第四十八条 用人单位违反本法规定解除或者终止劳动合同，劳动者要求继续履行劳动合同的，用人单位应当继续履行；劳动者不要求继续履行劳动合同或者劳动合同已经不能继续履行的，用人单位应当依照本法第八十七条规定支付赔偿金。
第八十七条 用人单位违反本法规定解除或者终止劳动合同的，应当依照本法第四十七条规定的经济补偿标准的二倍向劳动者支付赔偿金。""",
        ["劳动合同", "劳动法"],
        datetime(2008, 1, 1),
        None,
        "2012修正",
        "规范劳动合同订立、履行、变更、解除与终止的基本法律",
    ),
    _law_doc(
        "中华人民共和国民法典（合同编摘录）",
        """第四百九十六条 格式条款是当事人为了重复使用而预先拟定，并在订立合同时未与对方协商的条款。采用格式条款订立合同的，提供格式条款的一方应当遵循公平原则确定当事人之间的权利和义务，并采取合理的方式提示对方注意免除或者减轻其责任等与对方有重大利害关系的条款，按照对方的要求，对该条款予以说明。
第四百九十七条 有下列情形之一的，该格式条款无效：（一）具有本法第一编第六章第三节和本法第五百零六条规定的无效情形；（二）提供格式条款一方不合理地免除或者减轻其责任、加重对方责任、限制对方主要权利；（三）提供格式条款一方排除对方主要权利。
第五百三十三条 合同成立后，合同的基础条件发生了当事人在订立合同时无法预见的、不属于商业风险的重大变化，继续履行合同对于当事人一方明显不公平的，受不利影响的当事人可以与对方重新协商；在合理期限内协商不成的，当事人可以请求人民法院或者仲裁机构变更或者解除合同。
第五百八十五条 当事人可以约定一方违约时应当根据违约情况向对方支付一定数额的违约金，也可以约定因违约产生的损失赔偿额的计算方法。约定的违约金低于造成的损失的，人民法院或者仲裁机构可以根据当事人的请求予以增加；约定的违约金过分高于造成的损失的，人民法院或者仲裁机构可以根据当事人的请求予以适当减少。""",
        ["民法典", "合同", "格式条款"],
        datetime(2021, 1, 1),
        None,
        "2020年通过",
        "合同编关键条款（格式条款提示义务、情势变更、违约金调整）",
    ),
    _law_doc(
        "中华人民共和国消费者权益保护法",
        """第二十四条 经营者提供的商品或者服务不符合质量要求的，消费者可以依照国家规定、当事人约定退货，或者要求经营者履行更换、修理等义务。没有国家规定和当事人约定的，消费者可以自收到商品之日起七日内退货；七日后符合法定解除合同条件的，消费者可以及时退货，不符合法定解除合同条件的，可以要求经营者履行更换、修理等义务。
第五十五条 经营者提供商品或者服务有欺诈行为的，应当按照消费者的要求增加赔偿其受到的损失，增加赔偿的金额为消费者购买商品的价款或者接受服务的费用的三倍；增加赔偿的金额不足五百元的，为五百元。法律另有规定的，依照其规定。""",
        ["消费者", "消保法"],
        datetime(2014, 3, 15),
        None,
        "2013修正",
        "消费者权益保护与惩罚性赔偿条款",
    ),
    _law_doc(
        "最高人民法院关于审理民间借贷案件适用法律若干问题的规定",
        """第二十五条 出借人请求借款人按照合同约定利率支付利息的，人民法院应予支持，但是双方约定的利率超过合同成立时一年期贷款市场报价利率四倍的除外。
第二十六条 借据、收据、欠条等债权凭证载明的借款金额，一般认定为本金。预先在本金中扣除利息的，人民法院应当将实际出借的金额认定为本金。
第三十一条 本规定施行后，人民法院新受理的一审民间借贷纠纷案件，适用本规定。2020年8月20日之后新受理的一审民间借贷纠纷案件，借贷双方约定的利率不得超过合同成立时一年期贷款市场报价利率（LPR）四倍。""",
        ["民间借贷", "利率", "LPR"],
        datetime(2020, 8, 20),
        None,
        "2020修正",
        "民间借贷利率保护上限（LPR 四倍）规则",
    ),
    # 时间旅行样本：已被废止的旧法（合同法），供按日期查询旧版本
    _law_doc(
        "中华人民共和国合同法",
        """第九十四条 有下列情形之一的，当事人可以解除合同：（一）因不可抗力致使不能实现合同目的；（二）在履行期限届满之前，当事人一方明确表示或者以自己的行为表明不履行主要债务；（三）当事人一方迟延履行主要债务，经催告后在合理期限内仍未履行；（四）当事人一方迟延履行债务或者有其他违约行为致使不能实现合同目的；（五）法律规定的其他情形。
第一百一十四条 当事人可以约定一方违约时应当根据违约情况向对方支付一定数额的违约金，也可以约定因违约产生的损失赔偿额的计算方法。约定的违约金低于造成的损失的，当事人可以请求人民法院或者仲裁机构予以增加；约定的违约金过分高于造成的损失的，当事人可以请求人民法院或者仲裁机构予以适当减少。""",
        ["合同法", "历史版本"],
        datetime(1999, 10, 1),
        datetime(2020, 12, 31),
        "1999年",
        "旧《合同法》（2021年民法典施行后废止），用于时间旅行版本查询",
    ),
]

SAMPLE_CASE_DOCS = [
    {
        "title": "某科技公司违法解除劳动合同案",
        "content": "基本案情：张某在某科技公司工作两年八个月，公司以‘业绩不达标’为由解除劳动合同，但未举证证明其符合劳动合同法第三十九条规定的过失性解除情形，亦未支付经济补偿。法院认为，用人单位以不能胜任工作为由解除劳动合同，应当履行培训或者调整工作岗位的前置程序，且需支付经济补偿金。依据《中华人民共和国劳动合同法》第四十六条、第四十七条、第八十七条之规定，判决公司支付违法解除赔偿金（经济补偿标准二倍）。",
        "tags": ["案例", "劳动争议"],
    },
    {
        "title": "某买卖合同约定过高违约金案",
        "content": "基本案情：甲公司与乙公司签订设备买卖合同，约定逾期付款按日千分之五支付违约金。乙公司逾期付款90日，甲公司诉请高额违约金。法院依据《中华人民共和国民法典》第五百八十五条，认为约定违约金过分高于实际损失（以银行间同业拆借利率四倍为参照），酌情调减至年利率24%标准。",
        "tags": ["案例", "合同纠纷"],
    },
    {
        "title": "某公司高管竞业限制补偿纠纷案",
        "content": "基本案情：某公司技术总监离职后入职竞争对手，公司依竞业限制协议主张违约金。法院认为，用人单位应当在竞业限制期限内按月给予劳动者经济补偿；若约定的竞业限制经济补偿明显过低或无证据证明支付补偿，劳动者可主张协议对其不具约束力。依据《劳动合同法》第二十三条、第二十四条判决驳回公司过高违约金请求。",
        "tags": ["案例", "竞业限制"],
    },
]


# ---------------- 演示合同 ----------------
def _build_demo_contract_text(case_title: str) -> str:
    return (
        f"{case_title}\n"
        "甲方（采购方）：某某科技有限公司\n乙方（供应方）：某某设备制造有限公司\n\n"
        "第一条 合同目的：乙方依约向甲方供应生产设备及配套服务。\n"
        "第二条 合同金额：本合同总价款人民币壹佰万元整。\n"
        "第三条 付款方式：甲方应于合同签订后十日内支付合同总价款的百分之八十；余款于设备验收合格后支付。\n"
        "第四条 质量标准与验收：乙方交付之设备应符合国家相关质量标准，甲方有权在到货后十五日内组织验收。\n"
        "第五条 违约责任：任何一方违约，应向守约方支付合同总价款百分之三十的违约金。\n"
        "第六条 单方变更权：甲方有权根据市场情况单方调整供货价格或交付时间，乙方对此无异议。\n"
        "第七条 争议解决：本合同履行过程中发生争议，双方应友好协商解决；协商不成的，任何一方均可在甲方所在地人民法院提起诉讼。\n"
        "第八条 合同的最终解释权归甲方所有。\n"
        "第九条 本合同自双方盖章之日起生效，一式两份，双方各执一份。"
    )


async def _get_or_create_role(db, name, code, description, is_default) -> Role:
    result = await db.execute(
        select(Role).options(selectinload(Role.permissions)).where(Role.code == code)
    )
    role = result.scalar_one_or_none()
    if role is None:
        role = Role(name=name, code=code, description=description, is_default=is_default)
        role.permissions = []  # 显式初始化，避免 async 懒加载
        db.add(role)
        await db.flush()
    return role


async def _get_or_create_permission(db, name, code, resource, action, desc) -> Permission:
    result = await db.execute(select(Permission).where(Permission.code == code))
    p = result.scalar_one_or_none()
    if p is None:
        p = Permission(name=name, code=code, resource=resource, action=action, description=desc)
        db.add(p)
        await db.flush()
    return p


async def ensure_roles_permissions(db: AsyncSession) -> dict[str, Role]:
    roles: dict[str, Role] = {}
    for name, code, desc, is_default in ROLE_SEED:
        roles[code] = await _get_or_create_role(db, name, code, desc, is_default)
    # 权限码分配给 admin + legal_admin
    perms: dict[str, Permission] = {}
    for (name, code, resource, action, desc) in PERMISSION_SEED:
        perms[code] = await _get_or_create_permission(db, name, code, resource, action, desc)
    for code in ("admin", "legal_admin"):
        role = roles[code]
        for perm in perms.values():
            if perm not in role.permissions:
                role.permissions.append(perm)
    await db.flush()
    return roles


async def ensure_builtin_users(db: AsyncSession, roles: dict[str, Role]) -> dict[str, User]:
    users: dict[str, User] = {}
    for username, email, pwd, superuser, role_codes in BUILTIN_USERS:
        result = await db.execute(
            select(User).options(selectinload(User.roles)).where(User.username == username)
        )
        user = result.scalar_one_or_none()
        if user is None:
            user = User(
                username=username,
                email=email,
                hashed_password=hash_password(pwd),
                is_active=True,
                is_superuser=superuser,
            )
            user.roles = []  # 显式初始化，避免 async 懒加载
            db.add(user)
            await db.flush()
            for code in role_codes:
                if code in roles:
                    user.roles.append(roles[code])
        # 无论新建或已存在，都登记进映射，供演示数据使用
        users[username] = user
    await db.flush()
    return users


async def ensure_sample_legal_docs(db: AsyncSession) -> list[LegalDocument]:
    docs: list[LegalDocument] = []
    for item in SAMPLE_LEGAL_DOCS:
        exists = await db.scalar(
            select(LegalDocument.id).where(LegalDocument.title == item["title"])
        )
        if exists:
            continue
        doc = LegalDocument(
            title=item["title"],
            doc_type="法律",
            source=DocumentSource.MANUAL,
            content=item["content"],
            summary=item.get("summary", ""),
            tags=json.dumps(item["tags"], ensure_ascii=False),
            status=DocumentStatus.COMPLETED,
            indexing_progress=100,
            chunk_count=0,
            is_effective=item["abolished"] is None,
            effectiveness="已废止" if item["abolished"] else "有效",
            effective_date=item["effective"],
            abolished_date=item["abolished"],
            version=item.get("version", ""),
            publish_date=item["effective"],
        )
        db.add(doc)
        await db.flush()
        docs.append(doc)
    await db.flush()
    return docs


async def ensure_sample_case_docs(db: AsyncSession) -> list[LegalDocument]:
    docs: list[LegalDocument] = []
    for item in SAMPLE_CASE_DOCS:
        exists = await db.scalar(
            select(LegalDocument.id).where(LegalDocument.title == item["title"])
        )
        if exists:
            continue
        doc = LegalDocument(
            title=item["title"],
            doc_type="案例",
            source=DocumentSource.MANUAL,
            content=item["content"],
            summary=item["content"][:100],
            tags=json.dumps(item["tags"], ensure_ascii=False),
            status=DocumentStatus.COMPLETED,
            indexing_progress=100,
            chunk_count=0,
            is_effective=True,
            effectiveness="有效",
        )
        db.add(doc)
        await db.flush()
        docs.append(doc)
    await db.flush()
    return docs


async def ensure_welcome_notifications(db: AsyncSession, users: dict[str, User]) -> None:
    for username, user in users.items():
        exists = await db.scalar(
            select(Notification.id).where(
                Notification.user_id == user.id,
                Notification.title.like("%欢迎%"),
            )
        )
        if exists:
            continue
        db.add(
            Notification(
                user_id=user.id,
                type=NotificationType.SYSTEM,
                title="欢迎使用智法通 V2",
                content="平台已就绪。您可以开始法律问答、合同风险审查与法规检索；演示账号与密码见 README。",
            )
        )
    await db.flush()


async def ensure_demo_contracts(db: AsyncSession, users: dict[str, User]) -> None:
    demo_specs = [
        ("admin", "设备采购合同（演示）"),
        ("lawyer", "货物买卖合同（演示）"),
        ("user", "技术开发合同（演示）"),
    ]
    for username, title in demo_specs:
        user = users.get(username)
        if user is None:
            continue
        exists = await db.scalar(
            select(Contract.id).where(Contract.title == title)
        )
        if exists:
            continue
        content = _build_demo_contract_text(title)
        c = Contract(
            user_id=user.id,
            title=title,
            file_name=f"demo_{title}.txt",
            file_path="",
            file_size=len(content.encode("utf-8")),
            file_type="txt",
            content=content,
            status=ContractStatus.REVIEWED,
            contract_type="买卖",
        )
        db.add(c)
        await db.flush()
        report = ReviewReport(
            contract_id=c.id,
            overall_score=62.5,
            risk_level=RiskLevel.MEDIUM,
            risk_clause_count=3,
            summary="存在单方变更权、格式条款风险提示缺失、违约金比例过高、最终解释权归甲方等典型风险条款，建议重点修改。",
            completeness=70.0,
            compliance=55.0,
            consistency=60.0,
            suggestions=json.dumps(
                [
                    "第六条‘甲方有权单方调整价格’涉嫌加重乙方责任，建议删除或改为协商一致变更并给予合理对价。",
                    "第五条违约金百分之三十明显过高，建议调整为以实际损失为限并参照LPR四倍上限。",
                    "第八条‘最终解释权归甲方’违反格式条款规定，应删除。",
                ],
                ensure_ascii=False,
            ),
            primary_risks=json.dumps(
                [
                    {"clause": 6, "risk": "单方调价/单方变更权", "level": "high"},
                    {"clause": 5, "risk": "违约金过高", "level": "medium"},
                    {"clause": 8, "risk": "最终解释权", "level": "medium"},
                ],
                ensure_ascii=False,
            ),
            adverse_opinions=json.dumps(
                [
                    {
                        "clause": 6,
                        "opinion": "从乙方（弱势方）立场，单方调价条款使乙方处于不确定状态，主张删除或要求甲方就调价给予补偿。",
                    }
                ],
                ensure_ascii=False,
            ),
            debate_log=json.dumps(
                [
                    {
                        "round": 1,
                        "issue": "第六条约定的单方调价权是否有效",
                        "main_audit": "属于意思自治范畴但应受格式条款限制",
                        "adversary": "无效，加重乙方责任且未尽提示说明义务",
                        "arbiter": "维持高风险提示，建议删除并协商变更",
                    }
                ],
                ensure_ascii=False,
            ),
            unresolved_issues=json.dumps(["违约金基数应以实际损失为计算基准"]),
            adverse_opinion_count=1,
            unresolved_count=1,
        )
        db.add(report)
        await db.flush()
        demo_risks = [
            (6, "单方变更权条款", "high", 0.85,
             "甲方单方调整供货价格/交付时间，未给乙方协商与补偿机制，涉嫌构成民法典第四百九十七条格式条款无效情形。",
             "删除该单方变更权，改为双方协商一致并以补充协议确认；如需保留调价，约定公允调价机制与上限。",
             "《民法典》第四百九十六条、第四百九十七条"),
            (5, "违约金比例过高", "medium", 0.7,
             "约定违约金为合同总价款30%，可能被认定为过分高于实际损失。",
             "调整为以实际损失为基础，并参照一年期LPR四倍为上限，或约定损失计算方式。",
             "《民法典》第五百八十五条"),
            (8, "最终解释权条款", "medium", 0.62,
             "约定‘最终解释权归甲方’，属排除对方主要权利的格式条款。",
             "删除该条款，改为‘本合同未尽事宜由双方协商一致后以书面补充协议确定’。",
             "《民法典》第四百九十七条"),
        ]
        for idx, risk_type, level, score, desc, sug, basis in demo_risks:
            db.add(
                RiskClause(
                    report_id=report.id,
                    clause_index=idx,
                    original_text=content,
                    risk_type=risk_type,
                    risk_level=RiskLevel(level),
                    risk_score=score,
                    risk_description=desc,
                    suggestion=sug,
                    legal_basis=basis,
                )
            )
    await db.flush()


async def ensure_demo_analytics(db: AsyncSession, users: dict[str, User]) -> None:
    """模拟近 30 天问答/分析数据（仅在 query_logs 为空时生成）。"""
    count = await db.scalar(select(func.count(QueryLog.id)))
    if count:
        return
    now = datetime.now()
    # 类别偏好
    profiles = {
        "admin": ["劳动争议", "合同纠纷", "公司治理", "知识产权", "合同纠纷", "劳动争议"],
        "lawyer": ["合同纠纷", "公司法", "合同纠纷", "劳动争议", "知识产权"],
        "user": ["劳动争议", "婚姻家庭", "劳动争议", "消费维权", "民间借贷"],
    }
    n = 0
    for username, prefs in profiles.items():
        user = users.get(username)
        if user is None:
            continue
        for day in range(30):
            # 每人每日 0-4 条
            day_n = (hash((username, day)) % 4)
            for _ in range(day_n):
                ts = now - timedelta(days=day, hours=(n % 12), minutes=(n * 7) % 60)
                category = prefs[n % len(prefs)]
                db.add(
                    QueryLog(
                        user_id=user.id,
                        query_text=f"关于{category}的法律咨询问题示例 {n}",
                        rewritten_query=f"关于{category}的法律咨询问题示例 {n}",
                        category=category,
                        retrieved_count=3 + n % 5,
                        confidence=0.6 + (n % 4) * 0.1,
                        self_eval_score=0.65 + (n % 3) * 0.1,
                        is_streaming=1 if n % 2 else 0,
                        latency_ms=1200 + (n * 37) % 6000,
                        feedback_score=(1 if n % 3 == 0 else (-1 if n % 5 == 0 else 0)),
                        client_ip="127.0.0.1",
                        user_agent="seed",
                        created_at=ts,
                    )
                )
                n += 1
    # 引用统计：每文档按天少量
    docs = (await db.execute(select(LegalDocument.id).limit(5))).scalars().all()
    for did in docs:
        for day in range(7):
            ts = now - timedelta(days=day)
            db.add(
                CitationStat(
                    document_id=did,
                    stat_date=ts.replace(hour=0, minute=0, second=0, microsecond=0),
                    citation_count=2 + day,
                    positive_feedback_count=1,
                    negative_feedback_count=0 if day % 3 else 1,
                    avg_confidence=0.7,
                )
            )
    # 内置演示对话（user）
    user = users.get("user")
    if user is not None:
        conv_exists = await db.scalar(
            select(Conversation.id).where(Conversation.user_id == user.id).limit(1)
        )
        if not conv_exists:
            conv = Conversation(
                user_id=user.id,
                title="试用期约定是否合法（示例）",
                message_count=2,
            )
            db.add(conv)
            await db.flush()
            db.add(
                Message(
                    conversation_id=conv.id,
                    role="user",
                    content="我和公司签三年合同，公司说试用期六个月合法吗？",
                )
            )
            db.add(
                Message(
                    conversation_id=conv.id,
                    role="assistant",
                    content="根据《劳动合同法》第十九条，三年以上固定期限劳动合同试用期不得超过六个月，故六个月约定处于法定上限之内、合法；但同一用人单位与同一劳动者只能约定一次试用期。",
                    citations=json.dumps(
                        [{"name": "中华人民共和国劳动合同法", "article": "第十九条"}],
                        ensure_ascii=False,
                    ),
                    confidence=0.9,
                )
            )
    await db.flush()


async def init_seed_data(db: AsyncSession) -> dict:
    """幂等种子总入口。逐段 flush，任一步失败可重试。"""
    roles = await ensure_roles_permissions(db)
    users = await ensure_builtin_users(db, roles)
    await ensure_sample_legal_docs(db)
    await ensure_sample_case_docs(db)
    await ensure_demo_contracts(db, users)
    await ensure_welcome_notifications(db, users)
    await ensure_demo_analytics(db, users)
    await db.commit()
    return {"roles": list(roles.keys()), "users": list(users.keys())}
