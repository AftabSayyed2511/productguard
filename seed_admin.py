"""Seed or create an initial administrator account for ProductGuard."""
import sys
import argparse
from app import create_app, db
from app.models.user import User


def create_admin(fullname, username, email, password):
    app = create_app("development")
    with app.app_context():
        db.create_all()

        email = email.strip().lower()
        username = username.strip()

        existing_user = User.query.filter(
            (User.email == email) | (User.username == username)
        ).first()

        if existing_user:
            if existing_user.email == email:
                print(f"[!] User with email '{email}' already exists.")
            if existing_user.username == username:
                print(f"[!] User with username '{username}' already exists.")
            return False

        admin = User(
            full_name=fullname.strip(),
            username=username,
            email=email,
            role="admin",
            is_active=True,
        )
        admin.set_password(password)
        db.session.add(admin)
        db.session.commit()
        print(f"[+] Administrator '{username}' ({email}) created successfully!")
        return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create ProductGuard Admin")
    parser.add_argument("--fullname", default="Security Administrator", help="Admin full name")
    parser.add_argument("--username", required=True, help="Admin username")
    parser.add_argument("--email", required=True, help="Admin email")
    parser.add_argument("--password", required=True, help="Admin password (min 8 chars)")

    args = parser.parse_args()
    if len(args.password) < 8:
        print("[!] Password must be at least 8 characters long.")
        sys.exit(1)

    success = create_admin(args.fullname, args.username, args.email, args.password)
    sys.exit(0 if success else 1)
