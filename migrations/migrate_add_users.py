"""Migration script to add user authentication tables and relationships."""
import os
import sys
from sqlalchemy import create_engine, text, Column, Integer, String, DateTime, Enum, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import enum

Base = declarative_base()


class UserRole(enum.Enum):
    """User role enumeration."""
    NO_ACCESS = "no_access"
    MEMBER = "member"
    ADMIN = "admin"


class User(Base):
    """User model for authentication and authorization."""
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    google_id = Column(String(255), unique=True, nullable=False)
    role = Column(Enum(UserRole), default=UserRole.NO_ACCESS, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime)
    is_active = Column(Boolean, default=True)

DATABASE_URL = "sqlite:///pm_agent.db"

def migrate():
    """Add user table and update existing tables with user_id."""
    engine = create_engine(DATABASE_URL)

    # Create new user table
    Base.metadata.create_all(engine)

    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # Create admin user
        admin_user = session.query(User).filter_by(email='mike.samimi@syatt.io').first()
        if not admin_user:
            admin_user = User(
                email='mike.samimi@syatt.io',
                name='Mike Samimi',
                google_id='pending_first_login',  # Will be updated on first login
                role=UserRole.ADMIN,
                created_at=datetime.utcnow(),
                is_active=True
            )
            session.add(admin_user)
            session.commit()
            print(f"Created admin user: {admin_user.email}")
        else:
            print(f"Admin user already exists: {admin_user.email}")

        # Add user_id column to existing tables
        with engine.connect() as conn:
            # Check and add user_id to todo_items
            result = conn.execute(text("PRAGMA table_info(todo_items)"))
            columns = [row[1] for row in result]
            if 'user_id' not in columns:
                conn.execute(text("ALTER TABLE todo_items ADD COLUMN user_id INTEGER"))
                conn.execute(text(f"UPDATE todo_items SET user_id = {admin_user.id}"))
                print("Added user_id to todo_items table")
            else:
                print("user_id already exists in todo_items")

            # Check and add user_id to processed_meetings
            result = conn.execute(text("PRAGMA table_info(processed_meetings)"))
            columns = [row[1] for row in result]
            if 'user_id' not in columns:
                conn.execute(text("ALTER TABLE processed_meetings ADD COLUMN user_id INTEGER"))
                conn.execute(text(f"UPDATE processed_meetings SET user_id = {admin_user.id}"))
                print("Added user_id to processed_meetings table")
            else:
                print("user_id already exists in processed_meetings")

            # Check and add user_id to user_preferences
            result = conn.execute(text("PRAGMA table_info(user_preferences)"))
            columns = [row[1] for row in result]
            if 'user_id' not in columns:
                conn.execute(text("ALTER TABLE user_preferences ADD COLUMN user_id INTEGER"))
                conn.execute(text(f"UPDATE user_preferences SET user_id = {admin_user.id}"))
                print("Added user_id to user_preferences table")
            else:
                print("user_id already exists in user_preferences")

            conn.commit()

        print("Migration completed successfully!")

    except Exception as e:
        session.rollback()
        print(f"Migration failed: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    migrate()