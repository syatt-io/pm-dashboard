"""SQLAlchemy base declaration for all models."""
from sqlalchemy.orm import declarative_base

# Single Base for all models - consolidates metadata registry
Base = declarative_base()
