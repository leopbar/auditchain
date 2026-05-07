"""Script to create the initial admin user.
"""
from auditchain.data.database import get_session
from auditchain.auth.models import UserORM
from passlib.context import CryptContext

# Use pbkdf2_sha256 to avoid bcrypt 72-char bug in some environments
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

def create_admin():
    email = "admin@auditchain.com"
    password = "AuditChainSecure2026!"
    
    with get_session() as session:
        # Check if user exists
        user = session.query(UserORM).filter(UserORM.email == email).first()
        if user:
            print(f"User {email} already exists. Updating password...")
            user.hashed_password = pwd_context.hash(password)
            session.commit()
            return
            
        user = UserORM(
            email=email,
            full_name="System Administrator",
            hashed_password=pwd_context.hash(password),
            is_active=True,
            role="admin"
        )
        session.add(user)
        print(f"Admin user {email} created successfully.")

if __name__ == "__main__":
    create_admin()
