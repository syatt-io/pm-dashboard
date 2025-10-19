"""Migration script to add search_feedback and query_expansions tables."""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.database import get_engine
from src.models.search_feedback import SearchFeedback, QueryExpansion
from src.models.base import Base


def migrate():
    """Create search_feedback and query_expansions tables."""
    print("Creating search_feedback and query_expansions tables...")

    engine = get_engine()

    # Create tables
    SearchFeedback.__table__.create(engine, checkfirst=True)
    QueryExpansion.__table__.create(engine, checkfirst=True)

    print("✅ Tables created successfully")

    # Seed some common query expansions
    from sqlalchemy.orm import Session

    with Session(engine) as session:
        # Check if we already have expansions
        existing_count = session.query(QueryExpansion).count()

        if existing_count == 0:
            print("Seeding common query expansions...")

            # Common synonyms
            synonyms = [
                ("cart", "shopping cart", "synonym"),
                ("cart", "checkout", "related"),
                ("cart", "basket", "synonym"),
                ("bug", "issue", "synonym"),
                ("bug", "problem", "synonym"),
                ("bug", "error", "related"),
                ("fix", "resolve", "synonym"),
                ("fix", "patch", "related"),
                ("deploy", "deployment", "synonym"),
                ("deploy", "release", "related"),
                ("build", "compilation", "synonym"),
                ("build", "ci", "related"),
                ("test", "testing", "synonym"),
                ("test", "qa", "related"),
                ("pr", "pull request", "acronym"),
                ("pr", "merge request", "synonym"),
                ("wip", "work in progress", "acronym"),
                ("asap", "as soon as possible", "acronym"),
                ("api", "application programming interface", "acronym"),
                ("ui", "user interface", "acronym"),
                ("ux", "user experience", "acronym"),
                ("db", "database", "acronym"),
                ("repo", "repository", "synonym"),
                ("docs", "documentation", "synonym"),
                ("config", "configuration", "synonym"),
                ("auth", "authentication", "synonym"),
                ("cred", "credential", "synonym"),
                ("env", "environment", "synonym"),
                ("prod", "production", "synonym"),
                ("dev", "development", "synonym"),
                ("qa", "quality assurance", "acronym"),
                ("ci/cd", "continuous integration", "acronym"),
            ]

            expansions = []
            for original, expanded, exp_type in synonyms:
                expansions.append(QueryExpansion(
                    original_term=original.lower(),
                    expanded_term=expanded.lower(),
                    expansion_type=exp_type,
                    confidence_score=1.0,
                    is_active=True
                ))

            session.add_all(expansions)
            session.commit()

            print(f"✅ Seeded {len(expansions)} query expansions")
        else:
            print(f"⏭️ Skipped seeding - {existing_count} expansions already exist")


if __name__ == "__main__":
    migrate()
