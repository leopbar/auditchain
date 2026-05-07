"""Script to create or update the initial admin user.
"""
import argparse
from auditchain.data.database import get_session
from auditchain.auth.models import UserORM
from passlib.context import CryptContext

# Use pbkdf2_sha256 for consistent hashing across environments
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

def create_admin(email, password):
    with get_session() as session:
        # Check if user exists
        user = session.query(UserORM).filter(UserORM.email == email).first()
        if user:
            print(f"User {email} already exists. Updating password...")
            user.hashed_password = pwd_context.hash(password)
            session.commit()
            print("Password updated successfully.")
            return
            
        user = UserORM(
            email=email,
            full_name="System Administrator",
            hashed_password=pwd_context.hash(password),
            is_active=True,
            role="admin"
        )
        session.add(user)
        session.commit()
        print(f"Admin user {email} created successfully.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create or update an admin user.")
    parser.add_argument("--email", default="admin@auditchain.com", help="Admin email")
    parser.add_argument("--password", default="AuditChainSecure2026!", help="Admin password")
    
    args = parser.parse_args()
    create_admin(args.email, args.password)
