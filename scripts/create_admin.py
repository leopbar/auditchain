"""Standalone script to create the initial administrative user in AuditChain."""

import sys
from getpass import getpass

from dotenv import load_dotenv
from sqlalchemy import select

from auditchain.auth.models import UserORM
from auditchain.auth.service import hash_password
from auditchain.data.database import get_session

# Load environment variables
load_dotenv()


def create_admin():
    """Interactive CLI to create an admin user."""
    print("\n--- AuditChain: Create Admin User ---")

    email = input("Email: ").strip()
    if not email:
        print("Error: Email is required.")
        sys.exit(1)

    full_name = input("Full Name: ").strip()
    password = getpass("Password: ")
    if not password:
        print("Error: Password is required.")
        sys.exit(1)

    with get_session() as session:
        # Check if user already exists
        stmt = select(UserORM).where(UserORM.email == email)
        existing_user = session.execute(stmt).scalar_one_or_none()

        if existing_user:
            print(f"Warning: User with email '{email}' already exists. Operation aborted.")
            sys.exit(0)

        # Create admin user
        hashed = hash_password(password)
        admin = UserORM(
            email=email,
            hashed_password=hashed,
            full_name=full_name,
            role="admin",
            is_active=True,
        )

        session.add(admin)
        print(f"\nSuccess! Admin user '{email}' created successfully.")


if __name__ == "__main__":
    try:
        create_admin()
    except KeyboardInterrupt:
        print("\nOperation cancelled.")
        sys.exit(0)
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
        sys.exit(1)
