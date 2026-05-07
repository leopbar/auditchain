"""Script to initialize the database schema.
Runs Base.metadata.create_all(engine) to ensure all tables exist.
Also enables the pgvector extension.
"""
from sqlalchemy import text
from auditchain.data.database import Base, engine
# Import all models to ensure they are registered with Base
import auditchain.data.models
import auditchain.auth.models

def init_db():
    print("Enabling pgvector extension...")
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
    
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("Database tables created successfully.")

if __name__ == "__main__":
    init_db()
