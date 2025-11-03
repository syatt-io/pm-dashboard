"""SQL Safety utilities and best practices guide.

This module documents SQL injection prevention strategies used throughout the application.

SECURITY: The application uses SQLAlchemy's parameterized queries throughout, which provides
automatic protection against SQL injection attacks.

✅ SAFE PATTERNS (used throughout this codebase):
1. Parameterized queries with text() and named parameters:
   ```python
   conn.execute(text("SELECT * FROM users WHERE id = :user_id"), {"user_id": user_id})
   ```

2. SQLAlchemy ORM queries with filter_by():
   ```python
   session.query(User).filter_by(email=email).first()
   ```

3. Dynamic column selection with validated column names:
   ```python
   ALLOWED_COLUMNS = {'id', 'name', 'email'}
   if column_name in ALLOWED_COLUMNS:
       query = f"SELECT {column_name} FROM users WHERE id = :id"
       conn.execute(text(query), {"id": user_id})
   ```

❌ UNSAFE PATTERNS (never use these):
1. String concatenation or f-strings with user input:
   ```python
   # NEVER DO THIS:
   query = f"SELECT * FROM users WHERE email = '{email}'"
   conn.execute(text(query))
   ```

2. String formatting with user input:
   ```python
   # NEVER DO THIS:
   query = "SELECT * FROM users WHERE email = '%s'" % email
   conn.execute(text(query))
   ```

3. .format() with user input:
   ```python
   # NEVER DO THIS:
   query = "SELECT * FROM users WHERE email = '{}'".format(email)
   conn.execute(text(query))
   ```
"""

import re
import logging
from typing import Any, Dict, List, Set
from sqlalchemy import text

logger = logging.getLogger(__name__)


# Whitelists for dynamic query construction
ALLOWED_SORT_COLUMNS = {
    'id', 'created_at', 'updated_at', 'name', 'email', 'date', 'title', 'status'
}

ALLOWED_SORT_ORDERS = {'ASC', 'DESC'}

ALLOWED_TABLE_NAMES = {
    'users', 'projects', 'processed_meetings', 'project_keywords',
    'project_monthly_forecast', 'tempo_worklogs', 'user_watched_projects',
    'learnings', 'todo_items', 'project_digest_cache'
}


def validate_column_name(column: str, allowed_columns: Set[str] = ALLOWED_SORT_COLUMNS) -> bool:
    """Validate that a column name is in the allowed list.

    Use this when accepting column names from user input for sorting, filtering, etc.

    Args:
        column: Column name to validate
        allowed_columns: Set of allowed column names

    Returns:
        True if column is in allowed list, False otherwise

    Example:
        >>> if validate_column_name(user_sort_column):
        >>>     query = text(f"SELECT * FROM users ORDER BY {user_sort_column}")
    """
    return column in allowed_columns


def validate_sort_order(order: str) -> bool:
    """Validate that a sort order is either ASC or DESC.

    Args:
        order: Sort order to validate

    Returns:
        True if order is ASC or DESC (case-insensitive), False otherwise
    """
    return order.upper() in ALLOWED_SORT_ORDERS


def validate_table_name(table: str) -> bool:
    """Validate that a table name is in the allowed list.

    Use this when accepting table names from user input.

    Args:
        table: Table name to validate

    Returns:
        True if table is in allowed list, False otherwise
    """
    return table in ALLOWED_TABLE_NAMES


def build_safe_dynamic_query(
    table: str,
    columns: List[str],
    where_params: Dict[str, Any],
    sort_column: str = None,
    sort_order: str = 'DESC'
) -> tuple:
    """Build a safe dynamic query with validated components.

    This is a defensive utility that validates all dynamic parts of a query before construction.

    Args:
        table: Table name (must be in ALLOWED_TABLE_NAMES)
        columns: List of column names (must all be in ALLOWED_SORT_COLUMNS)
        where_params: Dictionary of WHERE clause parameters (will be parameterized)
        sort_column: Optional sort column (must be in ALLOWED_SORT_COLUMNS)
        sort_order: Optional sort order (must be ASC or DESC)

    Returns:
        Tuple of (query_string, params_dict) ready for text() + execute()

    Raises:
        ValueError: If any component fails validation

    Example:
        >>> query, params = build_safe_dynamic_query(
        ...     table='users',
        ...     columns=['id', 'name', 'email'],
        ...     where_params={'status': 'active'},
        ...     sort_column='created_at',
        ...     sort_order='DESC'
        ... )
        >>> conn.execute(text(query), params)
    """
    # Validate table name
    if not validate_table_name(table):
        raise ValueError(f"Invalid table name: {table}")

    # Validate column names
    for col in columns:
        if not validate_column_name(col):
            raise ValueError(f"Invalid column name: {col}")

    # Build SELECT clause
    columns_str = ', '.join(columns)
    query = f"SELECT {columns_str} FROM {table}"

    # Build WHERE clause with parameterized values
    if where_params:
        where_conditions = []
        for key in where_params.keys():
            if not validate_column_name(key):
                raise ValueError(f"Invalid WHERE column: {key}")
            where_conditions.append(f"{key} = :{key}")
        query += " WHERE " + " AND ".join(where_conditions)

    # Build ORDER BY clause
    if sort_column:
        if not validate_column_name(sort_column):
            raise ValueError(f"Invalid sort column: {sort_column}")
        if not validate_sort_order(sort_order):
            raise ValueError(f"Invalid sort order: {sort_order}")
        query += f" ORDER BY {sort_column} {sort_order.upper()}"

    return query, where_params


def is_safe_query_pattern(query_string: str) -> bool:
    """Check if a query string uses safe parameterized patterns.

    This is a heuristic check, not a guarantee of safety. Use for code review/linting.

    Args:
        query_string: SQL query string to check

    Returns:
        True if query appears to use parameterized patterns, False otherwise

    Warning:
        This is NOT a substitute for proper code review. It's a helper for catching
        obvious mistakes during development.
    """
    # Check for parameterized placeholder usage
    has_params = bool(re.search(r':[a-zA-Z_][a-zA-Z0-9_]*', query_string))

    # Check for potentially unsafe string formatting
    has_format_chars = bool(re.search(r'%s|%\([^)]+\)s|\{[^}]*\}', query_string))

    # Check for string concatenation patterns (very basic heuristic)
    # This won't catch everything, but helps during development
    has_concat_patterns = bool(re.search(r'\+\s*["\']|["\']\s*\+', query_string))

    if has_format_chars or has_concat_patterns:
        logger.warning(f"Query may use unsafe patterns: {query_string[:100]}")
        return False

    # Check for DDL statements (these don't need parameters)
    ddl_keywords = ['CREATE TABLE', 'CREATE INDEX', 'ALTER TABLE', 'DROP TABLE', 'CREATE VIEW']
    is_ddl = any(keyword in query_string.upper() for keyword in ddl_keywords)

    # Safe if: has parameters OR is DDL statement
    # Also allow queries without params if they don't have obvious injection points
    # (e.g., static queries with no user input)
    return has_params or is_ddl


# Example usage and documentation
def example_safe_queries():
    """Examples of safe query patterns used in this codebase."""
    from sqlalchemy import create_engine

    engine = create_engine('sqlite:///:memory:')

    with engine.connect() as conn:
        # ✅ SAFE: Parameterized query with text()
        result = conn.execute(
            text("SELECT * FROM users WHERE email = :email"),
            {"email": "user@example.com"}
        )

        # ✅ SAFE: Multiple parameters
        result = conn.execute(
            text("SELECT * FROM projects WHERE key = :key AND is_active = :active"),
            {"key": "PROJ", "active": True}
        )

        # ✅ SAFE: Dynamic column selection with validation
        sort_column = 'created_at'  # From user input
        if validate_column_name(sort_column):
            result = conn.execute(
                text(f"SELECT * FROM users ORDER BY {sort_column} DESC")
            )

        # ✅ SAFE: Dynamic query builder with validation
        query, params = build_safe_dynamic_query(
            table='users',
            columns=['id', 'name'],
            where_params={'status': 'active'},
            sort_column='created_at'
        )
        result = conn.execute(text(query), params)
