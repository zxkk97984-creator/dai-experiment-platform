# -*- coding: utf-8 -*-
"""用户 / 学期 / 教学班 / 选课。

复用 app.security.hash_password（按角色缓存一次，避免 bcrypt 拖慢种子）
与 app.services.roster_service.sync_course_class_enrollments（教学班到选课的
真实业务规则物化）。
"""
from __future__ import annotations

import logging
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    AcademicTerm,
    Course,
    CourseTeachingClass,
    TeachingClass,
    TeachingClassStudent,
    User,
)
from app.security import hash_password
from app.services.roster_service import sync_course_class_enrollments

from .constants import (
    ADMIN_REAL_NAME,
    ADMIN_USERNAME,
    BACKGROUND_CLASS_MEMBERSHIP,
    CLASS_PREFIXES,
    CLASS_SIZE,
    CLOSED_TERM,
    ACTIVE_TERM,
    FIXED_STUDENT_DEFS,
    TEACHER_DEFS,
    background_usernames,
    demo_password,
)
from .marks import mark
from .rng import make_rng
from .timeline import DemoClock

logger = logging.getLogger("dai.seed_demo.users")

# 固定中文姓名素材（背景学生用；画像学生姓名固定）
_GIVEN = list("伟芳娜秀英敏静丽强磊军洋勇艳杰娟涛明超兰霞平刚桂华慧巧美健峰文鹏飞鑫玲丹倩雪宁婷欢宇浩然子涵梓轩雨桐思远清禾明远知行若安嘉言景行书瑶沐阳星河芷晴安然可欣亦凡向晨语嫣昊天心怡博文佳宁晨曦逸凡念慈舒雅承泽锦程乐言予安一诺")

# 常用汉字姓氏（背景学生姓名生成，避免与画像冲突）
_SURNAME_POOL = list("赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华金魏陶姜戚谢邹喻柏水窦章云苏潘葛奚范彭郎鲁韦昌马苗凤花方俞任袁柳鲍史唐费廉岑薛雷贺倪汤滕殷罗毕郝邬安常乐于时傅皮卞齐康伍余元卜顾孟平黄和穆萧尹姚邵湛汪祁毛禹狄米贝明臧计伏成戴谈宋茅庞熊纪舒屈项祝董梁杜阮蓝闵席季麻强贾路娄危江童颜郭梅盛林刁钟徐邱骆高夏蔡田樊胡凌霍虞万支柯昝管卢莫经房裘缪解应宗丁宣邓杭洪包诸左石崔吉龚程邢裴陆荣翁荀羊惠甄曲家封芮羿储靳汲邴糜松井段富巫乌焦巴弓牧隗山谷车侯宓蓬全郗班仰秋仲伊宫宁仇栾暴甘钭厉戎祖武符刘景詹束龙叶幸司韶郜黎蓟薄印宿白怀蒲邰从鄂索咸籍赖卓蔺屠蒙池乔阴郁胥能苍双闻莘党翟谭贡劳逄姬申扶堵冉宰郦雍郤璩桑桂濮牛寿通边扈燕冀郏浦尚农温别庄晏柴瞿阎充慕连茹习宦艾鱼容向古易慎戈廖庾终暨居衡步都耿满弘匡国文寇广禄阙东欧殳沃利蔚越夔隆师巩厍聂晁勾敖融冷訾辛阚那简饶空曾毋沙乜养鞠须丰巢关蒯相查后荆红游竺权逯盖益桓公万俟司马上官欧阳夏侯诸葛闻人东方赫连皇甫尉迟公羊澹台公冶宗政濮阳淳于单于太叔申屠公孙仲孙轩辕令狐钟离宇文长孙慕容鲜于闾丘司徒司空亓官司寇仉督子车颛孙端木巫马公西漆雕乐正壤驷公良拓跋夹谷宰父谷梁晋楚闫法汝鄢涂钦段干百里东郭南门呼延归海羊舌微生岳帅缑亢况后有琴梁丘左丘东门西门商牟佘佴伯赏南宫墨哈谯笪年爱阳佟第五言福")

_NAME_BLACKLIST = {"林书瑶", "周子涵", "王雨桐", "赵晨曦", "张明远", "陈思远", "赵清禾"}


def _unique_student_names(count: int) -> list[str]:
    """背景学生姓名：以 make_rng('names', 'background') 派生，固定且不重复。"""
    rng = make_rng("names", "background")
    names: list[str] = []
    used: set[str] = set()
    while len(names) < count:
        name = rng.choice(_SURNAME_POOL) + rng.choice(_GIVEN)
        if name in used or name in _NAME_BLACKLIST:
            continue
        used.add(name)
        names.append(name)
    return names


def create_users(db: Session, clock: DemoClock) -> dict:
    """创建用户并返回 {username: User} 与 {'students': [User, ...]}。"""
    password = demo_password()
    # bcrypt 成本高：同一角色共享一次 hash（旧种子同款优化）
    admin_hash = hash_password(password)
    teacher_hash = hash_password(password)
    student_hash = hash_password(password)

    users: dict = {}

    # admin（demo_admin；不触碰 admin/teacher/student 用户名）
    admin = db.scalar(select(User).where(User.username == ADMIN_USERNAME))
    if admin is None:
        admin = User(
            username=ADMIN_USERNAME, real_name=ADMIN_REAL_NAME, role="admin",
            status="active", password_hash=admin_hash,
        )
        db.add(admin)
        db.flush()
        logger.info("[创建] admin 用户 %s", ADMIN_USERNAME)
    else:
        admin.real_name = ADMIN_REAL_NAME
        admin.role = "admin"
        admin.status = "active"
        db.flush()
        logger.info("[更新] admin 用户 %s（同步角色/状态）", ADMIN_USERNAME)
    mark(db, "users", admin.id)
    users[ADMIN_USERNAME] = admin

    # 教师
    for username, real_name in TEACHER_DEFS:
        user = db.scalar(select(User).where(User.username == username))
        if user is None:
            user = User(
                username=username, real_name=real_name, role="teacher",
                department="计算机学院", status="active", password_hash=teacher_hash,
            )
            db.add(user)
            db.flush()
            logger.info("[创建] 教师 %s", username)
        else:
            user.real_name = real_name
            user.role = "teacher"
            user.department = "计算机学院"
            user.status = "active"
            db.flush()
            logger.info("[更新] 教师 %s（同步角色/状态）", username)
        mark(db, "users", user.id)
        users[username] = user

    # 固定画像学生
    students: list[User] = []
    for username, real_name, _archetype in FIXED_STUDENT_DEFS:
        user = db.scalar(select(User).where(User.username == username))
        if user is None:
            student_no = username.replace("demo_student_", "")
            user = User(
                username=username, real_name=real_name, role="student",
                status="active", password_hash=student_hash, student_no=student_no,
            )
            db.add(user)
            db.flush()
            logger.info("[创建] 画像学生 %s", username)
        else:
            user.real_name = real_name
            user.role = "student"
            user.status = "active"
            db.flush()
            logger.info("[更新] 画像学生 %s", username)
        mark(db, "users", user.id)
        users[username] = user
        students.append(user)

    # 背景学生（56 人，固定种子姓名）
    bg_usernames = background_usernames()
    bg_names = _unique_student_names(len(bg_usernames))
    for username, real_name in zip(bg_usernames, bg_names):
        user = db.scalar(select(User).where(User.username == username))
        if user is None:
            student_no = username.replace("student_", "")
            user = User(
                username=username, real_name=real_name, role="student",
                status="active", password_hash=student_hash, student_no=student_no,
            )
            db.add(user)
            db.flush()
            logger.info("[创建] 背景学生 %s", username)
        else:
            user.real_name = real_name
            user.role = "student"
            user.status = "active"
            db.flush()
            logger.info("[更新] 背景学生 %s", username)
        mark(db, "users", user.id)
        users[username] = user
        students.append(user)

    db.flush()
    return {**users, "students": students}


def create_academics(db: Session, clock: DemoClock, users: dict) -> dict:
    """创建学期 + 教学班 + 班级成员。返回 {'term': AcademicTerm, 'classes': [TeachingClass, ...]}。"""
    # 当前学期
    term = db.scalar(select(AcademicTerm).where(AcademicTerm.code == ACTIVE_TERM["code"]))
    if term is None:
        term = AcademicTerm(
            code=ACTIVE_TERM["code"], name=ACTIVE_TERM["name"],
            start_date=clock.term_start_date(), end_date=clock.term_end_date(),
            status=ACTIVE_TERM["status"],
        )
        db.add(term)
        db.flush()
        logger.info("[创建] 学期 %s", ACTIVE_TERM["code"])
    else:
        term.name = ACTIVE_TERM["name"]
        term.start_date = clock.term_start_date()
        term.end_date = clock.term_end_date()
        term.status = ACTIVE_TERM["status"]
        db.flush()
        logger.info("[更新] 学期 %s", ACTIVE_TERM["code"])
    mark(db, "academic_terms", term.id)

    # 历史学期（仅学期行，无业务数据）
    closed = db.scalar(select(AcademicTerm).where(AcademicTerm.code == CLOSED_TERM["code"]))
    if closed is None:
        closed = AcademicTerm(
            code=CLOSED_TERM["code"], name=CLOSED_TERM["name"],
            start_date=clock.term_start_date() - timedelta(days=196),
            end_date=clock.term_start_date() - timedelta(days=66),
            status=CLOSED_TERM["status"],
        )
        db.add(closed)
        db.flush()
        logger.info("[创建] 历史学期 %s", CLOSED_TERM["code"])
        mark(db, "academic_terms", closed.id)

    # 教学班 + 成员
    classes: list[TeachingClass] = []
    fixed_by_class: dict[int, User] = {
        i: users[username]
        for i, (username, _name, _archetype) in enumerate(FIXED_STUDENT_DEFS)
    }
    bg_iter = iter([u for u in users["students"] if u.username.startswith("student_")])
    bg_by_class: dict[int, list[User]] = {}
    for class_index, prefix in enumerate(CLASS_PREFIXES):
        # 画像学生（班1..班4 的序号1）
        members: list[User] = []
        if class_index in fixed_by_class:
            members.append(fixed_by_class[class_index])
        # 背景学生补齐
        need = CLASS_SIZE - len(members)
        bg_by_class[class_index] = [next(bg_iter) for _ in range(need)]
        members.extend(bg_by_class[class_index])

        code = f"{prefix}班"
        tc = db.scalar(
            select(TeachingClass).where(
                TeachingClass.academic_term_id == term.id,
                TeachingClass.code == code,
            )
        )
        if tc is None:
            tc = TeachingClass(
                academic_term_id=term.id, code=code,
                name=f"{ACTIVE_TERM['name']} {code}", status="active",
            )
            db.add(tc)
            db.flush()
            logger.info("[创建] 教学班 %s", code)
        else:
            tc.status = "active"
            db.flush()
            logger.info("[更新] 教学班 %s", code)
        mark(db, "teaching_classes", tc.id)
        classes.append(tc)

        # 班级成员（get_or_create by unique (class, student)）
        for student in members:
            member = db.scalar(
                select(TeachingClassStudent).where(
                    TeachingClassStudent.teaching_class_id == tc.id,
                    TeachingClassStudent.student_id == student.id,
                )
            )
            if member is None:
                member = TeachingClassStudent(
                    teaching_class_id=tc.id, student_id=student.id, status="active",
                )
                db.add(member)
                db.flush()
                logger.info("[创建] 班级成员 %s -> %s", code, student.username)
            else:
                member.status = "active"
                db.flush()
            mark(db, "teaching_class_students", member.id)

    db.flush()
    return {"term": term, "classes": classes}


def link_courses_to_classes(
    db: Session, courses: dict[str, Course], classes: list[TeachingClass],
) -> None:
    """课程 x 教学班绑定（course_teaching_classes），随后调用真实 roster sync 物化选课。

    幂等：唯一键 (course_id, teaching_class_id) 存在则跳过。
    """
    from .constants import COURSE_CLASSES

    for title, course in courses.items():
        class_indices = COURSE_CLASSES.get(title, [])
        for index in class_indices:
            tc = classes[index]
            link = db.scalar(
                select(CourseTeachingClass).where(
                    CourseTeachingClass.course_id == course.id,
                    CourseTeachingClass.teaching_class_id == tc.id,
                )
            )
            if link is None:
                link = CourseTeachingClass(course_id=course.id, teaching_class_id=tc.id)
                db.add(link)
                db.flush()
                logger.info("[创建] 课程教学班 %s -> %s", title, tc.code)
            mark(db, "course_teaching_classes", link.id)
        # 真实业务规则物化选课（class 来源；不覆盖 manual）
        sync_course_class_enrollments(db, course)
        # 会话 autoflush=False：必须先 flush 才能查询到刚物化的选课行
        db.flush()
        # 登记物化出的选课行（仅 class 来源且当前 enrolled 的）
        from app.models import CourseEnrollment

        for row in db.scalars(
            select(CourseEnrollment).where(
                CourseEnrollment.course_id == course.id,
                CourseEnrollment.origin == "class",
                CourseEnrollment.status == "enrolled",
            )
        ).all():
            mark(db, "course_enrollments", row.id)
    db.flush()
