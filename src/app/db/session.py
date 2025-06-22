import os
from dotenv import load_dotenv
from sqlmodel import create_engine, Session, SQLModel
from sqlalchemy.orm import sessionmaker

# Load .env file from the project root to ensure consistency.
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set in .env file")

# Create a single, reusable engine instance for the entire application.
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,  # Test connections before they are used from the pool.
    connect_args={"sslmode": "require"},  # Enforce SSL connection.
    echo=False  # Set to True to log SQL statements for debugging.
)

# Create a configured "Session" class, which will serve as a factory for new Session objects.
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    class_=Session
)

# FastAPI dependency to get a DB session per request.
def get_db():
    """
    This dependency creates a new SQLAlchemy Session for each request,
    and ensures it's closed once the request is completed.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# A function to create all tables. This is useful for initial setup.
def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

