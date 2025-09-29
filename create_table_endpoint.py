#!/usr/bin/env python3
"""Temporary script to create users table via API endpoint."""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent))

from flask import Flask, jsonify
from sqlalchemy import create_engine, text
from src.utils.config import ConfigManager

app = Flask(__name__)

@app.route('/create-users-table', methods=['POST', 'GET'])
def create_users_table():
    """Create users table in the database."""
    try:
        # Get database URL from environment
        settings = ConfigManager()
        database_url = settings.agent.database_url

        if not database_url:
            return jsonify({'error': 'DATABASE_URL not configured'}), 500

        # Connect to database
        engine = create_engine(database_url)

        with engine.connect() as conn:
            trans = conn.begin()
            try:
                # Create enum type first
                conn.execute(text("""
                    DO $$
                    BEGIN
                        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'userrole') THEN
                            CREATE TYPE userrole AS ENUM ('NO_ACCESS', 'MEMBER', 'ADMIN');
                        END IF;
                    END$$;
                """))

                # Create users table
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS users (
                        id SERIAL PRIMARY KEY,
                        email VARCHAR(255) UNIQUE NOT NULL,
                        name VARCHAR(255),
                        google_id VARCHAR(255) UNIQUE,
                        role userrole DEFAULT 'MEMBER',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_login TIMESTAMP,
                        is_active BOOLEAN DEFAULT TRUE,
                        fireflies_api_key_encrypted TEXT
                    );
                """))

                trans.commit()

                # Verify table exists
                result = conn.execute(text("SELECT COUNT(*) FROM users"))
                count = result.scalar()

                return jsonify({
                    'success': True,
                    'message': 'Users table created successfully',
                    'table_exists': True,
                    'row_count': count
                })

            except Exception as e:
                trans.rollback()
                return jsonify({
                    'success': False,
                    'error': f'Failed to create table: {str(e)}'
                }), 500

    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Database connection failed: {str(e)}'
        }), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5555, debug=True)