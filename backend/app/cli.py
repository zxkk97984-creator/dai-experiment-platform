import argparse

from sqlalchemy import select

from app.database import Base, SessionLocal, engine
from app.models import User
from app.security import hash_password, validate_password_rules


def create_admin(username: str, password: str, real_name: str):
    try:
        validate_password_rules(password, username)
    except ValueError as exc:
        raise SystemExit(f"密码不符合要求：{exc}") from exc
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        existing = db.scalar(select(User).where(User.username == username))
        if existing:
            existing.password_hash = hash_password(password)
            existing.real_name = real_name
            existing.role = "admin"
            existing.status = "active"
            db.commit()
            print(f"Updated admin user: {username}")
            return
        user = User(
            username=username,
            real_name=real_name,
            role="admin",
            status="active",
            password_hash=hash_password(password),
        )
        db.add(user)
        db.commit()
        print(f"Created admin user: {username}")


def seed_environments(enqueue: bool):
    """初始化环境档位种子（幂等）——数据全部来自内置常量，无任意输入面。

    --enqueue 时同时把 draft/failed 版本入队构建（Redis 只负责唤醒，DB 是事实源）。
    """
    from app.config import get_settings
    from app.services.environment_seed import seed_environment_catalog

    settings = get_settings()
    redis_client = None
    if enqueue:
        import redis as _redis

        redis_client = _redis.Redis.from_url(settings.redis_url, decode_responses=True)
    with SessionLocal() as db:
        result = seed_environment_catalog(db, settings, enqueue=enqueue, redis_client=redis_client)
        print(f"Profiles created: {result.profiles_created}")
        print(f"Packages created: {result.packages_created}")
        print(f"Versions created: {result.versions_created}")
        print(f"Enqueued: {result.enqueued}")
        print(f"Already available: {result.already_available}")
        print(f"Skipped: {result.skipped}")


def main():
    parser = argparse.ArgumentParser(description="DAI backend management commands")
    subparsers = parser.add_subparsers(dest="command", required=True)
    admin_parser = subparsers.add_parser("create-admin")
    admin_parser.add_argument("--username", required=True)
    admin_parser.add_argument("--password", required=True)
    admin_parser.add_argument("--real-name", default="Administrator")
    seed_parser = subparsers.add_parser("seed-environments", help="初始化环境档位种子（幂等）")
    seed_parser.add_argument("--enqueue", action="store_true", help="同时入队构建任务")
    args = parser.parse_args()
    if args.command == "create-admin":
        create_admin(args.username, args.password, args.real_name)
    elif args.command == "seed-environments":
        seed_environments(args.enqueue)


if __name__ == "__main__":
    main()
