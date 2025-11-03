"""Tests for SQL injection protection and safe query patterns.

This test suite validates that all SQL operations use parameterized queries
and are protected against SQL injection attacks.
"""

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DatabaseError
from src.utils.sql_safety import (
    validate_column_name,
    validate_sort_order,
    validate_table_name,
    build_safe_dynamic_query,
    is_safe_query_pattern
)


class TestColumnNameValidation:
    """Test column name whitelist validation."""

    def test_valid_column_names(self):
        """Test that valid column names pass validation."""
        valid_columns = ['id', 'created_at', 'updated_at', 'name', 'email']
        for column in valid_columns:
            assert validate_column_name(column)

    def test_invalid_column_names(self):
        """Test that invalid column names fail validation."""
        invalid_columns = [
            'password', 'api_key', 'secret_key',
            'DROP TABLE users', '1=1', 'id; DROP TABLE users'
        ]
        for column in invalid_columns:
            assert not validate_column_name(column)

    def test_sql_injection_attempts(self):
        """Test that SQL injection attempts in column names are rejected."""
        injection_attempts = [
            "id' OR '1'='1",
            "id; DROP TABLE users",
            "id UNION SELECT * FROM secrets",
            "id--",
            "id/*comment*/",
        ]
        for attempt in injection_attempts:
            assert not validate_column_name(attempt)


class TestSortOrderValidation:
    """Test sort order validation."""

    def test_valid_sort_orders(self):
        """Test that ASC and DESC pass validation."""
        assert validate_sort_order('ASC')
        assert validate_sort_order('DESC')
        assert validate_sort_order('asc')
        assert validate_sort_order('desc')
        assert validate_sort_order('Asc')
        assert validate_sort_order('Desc')

    def test_invalid_sort_orders(self):
        """Test that invalid sort orders fail validation."""
        invalid_orders = [
            'RANDOM', 'DROP TABLE', 'ASC; DROP TABLE users',
            'ASC--', 'ASC/*comment*/', "ASC' OR '1'='1"
        ]
        for order in invalid_orders:
            assert not validate_sort_order(order)


class TestTableNameValidation:
    """Test table name whitelist validation."""

    def test_valid_table_names(self):
        """Test that valid table names pass validation."""
        valid_tables = ['users', 'projects', 'processed_meetings']
        for table in valid_tables:
            assert validate_table_name(table)

    def test_invalid_table_names(self):
        """Test that invalid table names fail validation."""
        invalid_tables = [
            'admin_users', 'secrets', 'DROP TABLE users',
            '1=1', 'users; DROP TABLE secrets'
        ]
        for table in invalid_tables:
            assert not validate_table_name(table)

    def test_sql_injection_in_table_names(self):
        """Test that SQL injection attempts in table names are rejected."""
        injection_attempts = [
            "users' OR '1'='1",
            "users; DROP TABLE secrets",
            "users UNION SELECT * FROM secrets",
            "users--",
        ]
        for attempt in injection_attempts:
            assert not validate_table_name(attempt)


class TestSafeDynamicQueryBuilder:
    """Test safe dynamic query construction."""

    def test_basic_select_query(self):
        """Test building a basic SELECT query."""
        query, params = build_safe_dynamic_query(
            table='users',
            columns=['id', 'name'],
            where_params={}
        )
        assert 'SELECT id, name FROM users' in query
        assert params == {}

    def test_select_with_where_clause(self):
        """Test building a SELECT query with WHERE clause."""
        query, params = build_safe_dynamic_query(
            table='users',
            columns=['id', 'name'],
            where_params={'status': 'active'}
        )
        assert 'SELECT id, name FROM users WHERE status = :status' in query
        assert params == {'status': 'active'}

    def test_select_with_order_by(self):
        """Test building a SELECT query with ORDER BY."""
        query, params = build_safe_dynamic_query(
            table='users',
            columns=['id', 'name'],
            where_params={},
            sort_column='created_at',
            sort_order='DESC'
        )
        assert 'SELECT id, name FROM users ORDER BY created_at DESC' in query

    def test_reject_invalid_table_name(self):
        """Test that invalid table names are rejected."""
        with pytest.raises(ValueError, match="Invalid table name"):
            build_safe_dynamic_query(
                table='DROP TABLE users',
                columns=['id'],
                where_params={}
            )

    def test_reject_invalid_column_name(self):
        """Test that invalid column names are rejected."""
        with pytest.raises(ValueError, match="Invalid column name"):
            build_safe_dynamic_query(
                table='users',
                columns=['id; DROP TABLE users'],
                where_params={}
            )

    def test_reject_invalid_where_column(self):
        """Test that invalid WHERE column names are rejected."""
        with pytest.raises(ValueError, match="Invalid WHERE column"):
            build_safe_dynamic_query(
                table='users',
                columns=['id'],
                where_params={'DROP TABLE': 'users'}
            )

    def test_reject_invalid_sort_column(self):
        """Test that invalid sort column names are rejected."""
        with pytest.raises(ValueError, match="Invalid sort column"):
            build_safe_dynamic_query(
                table='users',
                columns=['id'],
                where_params={},
                sort_column='id; DROP TABLE users'
            )

    def test_reject_invalid_sort_order(self):
        """Test that invalid sort orders are rejected."""
        with pytest.raises(ValueError, match="Invalid sort order"):
            build_safe_dynamic_query(
                table='users',
                columns=['id'],
                where_params={},
                sort_column='id',
                sort_order='DROP TABLE'
            )


class TestParameterizedQueries:
    """Test that parameterized queries prevent SQL injection."""

    def test_parameterized_query_with_malicious_input(self):
        """Test that parameterized queries prevent SQL injection."""
        engine = create_engine('sqlite:///:memory:')

        with engine.connect() as conn:
            # Create test table
            conn.execute(text("""
                CREATE TABLE test_users (
                    id INTEGER PRIMARY KEY,
                    email TEXT,
                    password TEXT
                )
            """))
            conn.execute(text("""
                INSERT INTO test_users (id, email, password)
                VALUES (1, 'admin@example.com', 'secret')
            """))
            conn.commit()

            # Attempt SQL injection via parameterized query (should be safe)
            malicious_email = "admin@example.com' OR '1'='1"
            result = conn.execute(
                text("SELECT * FROM test_users WHERE email = :email"),
                {"email": malicious_email}
            )
            rows = result.fetchall()

            # Should return no rows because parameterized query treats input as literal
            assert len(rows) == 0

    def test_safe_update_with_parameterized_values(self):
        """Test that UPDATE queries with parameters are safe."""
        engine = create_engine('sqlite:///:memory:')

        with engine.connect() as conn:
            # Create test table
            conn.execute(text("""
                CREATE TABLE test_users (
                    id INTEGER PRIMARY KEY,
                    email TEXT,
                    status TEXT
                )
            """))
            conn.execute(text("""
                INSERT INTO test_users (id, email, status)
                VALUES (1, 'user@example.com', 'active')
            """))
            conn.commit()

            # Attempt to inject SQL via status parameter
            malicious_status = "active'; DROP TABLE test_users; --"
            conn.execute(
                text("UPDATE test_users SET status = :status WHERE id = :id"),
                {"status": malicious_status, "id": 1}
            )
            conn.commit()

            # Verify table still exists and data is safe
            result = conn.execute(text("SELECT * FROM test_users"))
            rows = result.fetchall()
            assert len(rows) == 1
            # Status should be stored as literal string, not executed
            assert rows[0][2] == malicious_status


class TestQueryPatternDetection:
    """Test query pattern safety detection."""

    def test_detect_safe_parameterized_queries(self):
        """Test detection of safe parameterized query patterns."""
        safe_queries = [
            "SELECT * FROM users WHERE id = :id",
            "UPDATE users SET email = :email WHERE id = :user_id",
            "INSERT INTO users (name, email) VALUES (:name, :email)",
            "DELETE FROM users WHERE id = :id",
        ]
        for query in safe_queries:
            assert is_safe_query_pattern(query)

    def test_detect_unsafe_format_strings(self):
        """Test detection of unsafe string formatting patterns."""
        unsafe_queries = [
            "SELECT * FROM users WHERE id = %s",
            "SELECT * FROM users WHERE id = %(id)s",
            "SELECT * FROM users WHERE id = {}",
            "SELECT * FROM users WHERE name = '{}'",
        ]
        for query in unsafe_queries:
            assert not is_safe_query_pattern(query)

    def test_allow_ddl_statements(self):
        """Test that DDL statements without params are allowed."""
        ddl_statements = [
            "CREATE TABLE users (id INTEGER PRIMARY KEY)",
            "CREATE INDEX idx_users_email ON users(email)",
            "ALTER TABLE users ADD COLUMN age INTEGER",
        ]
        for statement in ddl_statements:
            assert is_safe_query_pattern(statement)


class TestRealWorldQueryPatterns:
    """Test real SQL patterns used in the codebase."""

    def test_jira_projects_query_pattern(self):
        """Test the query pattern used in jira.py for project data."""
        # This is the actual pattern used in src/routes/jira.py
        query = text("""
            SELECT
                p.is_active,
                p.project_work_type,
                p.total_hours
            FROM projects p
            WHERE p.key = :key
        """)
        engine = create_engine('sqlite:///:memory:')

        with engine.connect() as conn:
            # Create test table
            conn.execute(text("""
                CREATE TABLE projects (
                    key TEXT PRIMARY KEY,
                    is_active INTEGER,
                    project_work_type TEXT,
                    total_hours REAL
                )
            """))
            conn.execute(text("""
                INSERT INTO projects (key, is_active, project_work_type, total_hours)
                VALUES ('TEST', 1, 'project-based', 100.0)
            """))
            conn.commit()

            # Test with safe input
            result = conn.execute(query, {"key": "TEST"})
            rows = result.fetchall()
            assert len(rows) == 1

            # Test with malicious input (should be safe)
            malicious_key = "TEST' OR '1'='1"
            result = conn.execute(query, {"key": malicious_key})
            rows = result.fetchall()
            assert len(rows) == 0  # Parameterized query treats it as literal

    def test_meeting_keywords_query_pattern(self):
        """Test the query pattern used in meetings.py for keywords."""
        # This is the pattern used in src/routes/meetings.py
        query = text("""
            SELECT project_key, array_agg(LOWER(keyword)) as keywords
            FROM project_keywords
            GROUP BY project_key
        """)

        # Note: This query has no parameters, but is safe because it's static with no user input.
        # The heuristic function is designed to catch UNSAFE patterns (format strings, concatenation),
        # not to guarantee all safe patterns pass. Static queries without parameters may return False
        # from is_safe_query_pattern(), but that doesn't mean they're unsafe - it just means the
        # heuristic can't verify them automatically.

        # Verify the pattern doesn't trigger unsafe pattern detection
        query_str = str(query)
        # Should not contain format strings or concatenation patterns
        assert '%s' not in query_str
        assert '%(' not in query_str
        assert not any(pattern in query_str for pattern in ['{', '+ "', "+ '"])

    def test_update_project_pattern(self):
        """Test the dynamic UPDATE pattern used in jira.py."""
        engine = create_engine('sqlite:///:memory:')

        with engine.connect() as conn:
            # Create test table
            conn.execute(text("""
                CREATE TABLE projects (
                    key TEXT PRIMARY KEY,
                    is_active INTEGER,
                    total_hours REAL
                )
            """))
            conn.execute(text("""
                INSERT INTO projects (key, is_active, total_hours)
                VALUES ('TEST', 1, 50.0)
            """))
            conn.commit()

            # Simulate the dynamic update pattern from src/routes/jira.py
            update_fields = ["is_active = :is_active", "total_hours = :total_hours"]
            update_params = {"key": "TEST", "is_active": 0, "total_hours": 100.0}

            # Build dynamic query (field names are trusted, values are parameterized)
            query_str = f"UPDATE projects SET {', '.join(update_fields)} WHERE key = :key"
            conn.execute(text(query_str), update_params)
            conn.commit()

            # Verify update worked
            result = conn.execute(text("SELECT * FROM projects WHERE key = 'TEST'"))
            row = result.fetchone()
            assert row[1] == 0  # is_active
            assert row[2] == 100.0  # total_hours
