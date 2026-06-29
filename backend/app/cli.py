import argparse

from sqlalchemy import select

from app.database import Base, SessionLocal, engine
from app.models import User
from app.security import hash_password


def create_admin(username: str, password: str, real_name: str):
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


def main():
    parser = argparse.ArgumentParser(description="DAI backend management commands")
    subparsers = parser.add_subparsers(dest="command", required=True)
    admin_parser = subparsers.add_parser("create-admin")
    admin_parser.add_argument("--username", required=True)
    admin_parser.add_argument("--password", required=True)
    admin_parser.add_argument("--real-name", default="Administrator")
    args = parser.parse_args()
    if args.command == "create-admin":
        create_admin(args.username, args.password, args.real_name)


if __name__ == "__main__":
    main()
