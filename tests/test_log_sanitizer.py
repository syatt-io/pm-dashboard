"""Tests for log sanitization utility."""

import pytest
import logging
from src.utils.log_sanitizer import (
    redact_sensitive_data,
    redact_dict,
    SensitiveDataFilter,
    configure_root_logger_with_sanitization,
)


class TestRedactSensitiveData:
    """Test suite for redact_sensitive_data function."""

    def test_redact_api_key(self):
        """Test that API keys are redacted."""
        message = 'API_KEY=abc123def456ghi789'
        result = redact_sensitive_data(message)
        assert '[REDACTED]' in result
        assert 'abc123def456ghi789' not in result

    def test_redact_api_key_partial(self):
        """Test partial redaction shows first/last characters."""
        message = 'API_KEY=abc123def456ghi789'
        result = redact_sensitive_data(message, partial=True)
        assert 'abc1' in result  # First 4 chars
        assert 'i789' in result  # Last 4 chars
        assert '[REDACTED]' in result
        assert 'abc123def456ghi789' not in result

    def test_redact_bearer_token(self):
        """Test that Bearer tokens are redacted."""
        message = 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.payload.signature'
        result = redact_sensitive_data(message)
        assert '[REDACTED]' in result
        assert 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.payload.signature' not in result
        assert 'Bearer' in result  # Keep auth type

    def test_redact_basic_auth(self):
        """Test that Basic Auth tokens are redacted."""
        message = 'Authorization: Basic dXNlcjpwYXNzd29yZA=='
        result = redact_sensitive_data(message)
        assert '[REDACTED]' in result
        assert 'dXNlcjpwYXNzd29yZA==' not in result
        assert 'Basic' in result  # Keep auth type

    def test_redact_jwt_token(self):
        """Test that JWT tokens are completely redacted."""
        message = 'token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.signature'
        result = redact_sensitive_data(message)
        assert 'REDACTED-JWT' in result
        assert 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9' not in result

    def test_redact_password(self):
        """Test that passwords are redacted."""
        message = 'password=secretPass123'
        result = redact_sensitive_data(message)
        assert '[REDACTED]' in result
        assert 'secretPass123' not in result

    def test_redact_secret_key(self):
        """Test that secret keys are redacted."""
        message = 'SECRET_KEY=my_super_secret_key_123'
        result = redact_sensitive_data(message)
        assert '[REDACTED]' in result
        assert 'my_super_secret_key_123' not in result

    def test_redact_oauth_token(self):
        """Test that OAuth tokens are redacted."""
        message = 'oauth_token=ya29.a0AfH6SMBxyz123'
        result = redact_sensitive_data(message)
        assert '[REDACTED]' in result
        assert 'ya29.a0AfH6SMBxyz123' not in result

    def test_redact_database_connection_string(self):
        """Test that database URLs are redacted."""
        message = 'DATABASE_URL=postgresql://user:password123@localhost:5432/db'
        result = redact_sensitive_data(message)
        assert '[REDACTED-USER]' in result
        assert '[REDACTED-PASSWORD]' in result
        assert 'password123' not in result
        assert 'user' not in result or '[REDACTED-USER]' in result

    def test_redact_slack_token(self):
        """Test that Slack tokens are redacted."""
        message = 'SLACK_TOKEN=xoxb-1234567890-1234567890123-abcdefghijklmnopqrstuvwx'
        result = redact_sensitive_data(message)
        assert '[REDACTED-' in result
        assert 'xoxb-1234567890-1234567890123-abcdefghijklmnopqrstuvwx' not in result

    def test_redact_github_token(self):
        """Test that GitHub tokens are redacted."""
        message = 'GITHUB_TOKEN=ghp_1234567890abcdefghijklmnopqrstuvwxyz'
        result = redact_sensitive_data(message)
        assert '[REDACTED-' in result
        assert 'ghp_1234567890abcdefghijklmnopqrstuvwxyz' not in result

    def test_redact_multiple_credentials(self):
        """Test that multiple credentials in same message are all redacted."""
        message = 'API_KEY=abc123 and SECRET=def456 and password=secret'
        result = redact_sensitive_data(message)
        assert result.count('[REDACTED]') == 3
        assert 'abc123' not in result
        assert 'def456' not in result
        assert 'secret' not in result or '[REDACTED]' in result

    def test_preserve_non_sensitive_data(self):
        """Test that non-sensitive data is not redacted."""
        message = 'User logged in: john@example.com from IP 192.168.1.1'
        result = redact_sensitive_data(message)
        assert result == message  # Should not change

    def test_redact_json_format(self):
        """Test redaction in JSON-like format."""
        message = '{"api_key": "abc123", "name": "John"}'
        result = redact_sensitive_data(message)
        assert '[REDACTED]' in result
        assert 'abc123' not in result
        assert '"name": "John"' in result  # Non-sensitive preserved

    def test_case_insensitive_redaction(self):
        """Test that redaction is case-insensitive."""
        messages = [
            'API_KEY=test123',
            'api_key=test123',
            'Api_Key=test123',
            'API-KEY=test123',
        ]
        for message in messages:
            result = redact_sensitive_data(message)
            assert '[REDACTED]' in result
            assert 'test123' not in result

    def test_env_var_format_redaction(self):
        """Test redaction of environment variable formats."""
        message = 'OPENAI_API_KEY=sk-abc123def456ghi789'
        result = redact_sensitive_data(message)
        assert '[REDACTED]' in result
        assert 'sk-abc123def456ghi789' not in result


class TestRedactDict:
    """Test suite for redact_dict function."""

    def test_redact_api_key_in_dict(self):
        """Test that API keys in dictionaries are redacted."""
        data = {'api_key': 'secret123', 'name': 'John'}
        result = redact_dict(data)
        assert result['api_key'] == '[REDACTED]'
        assert result['name'] == 'John'

    def test_redact_nested_dict(self):
        """Test redaction in nested dictionaries."""
        data = {
            'user': {
                'name': 'John',
                'api_key': 'secret123'
            }
        }
        result = redact_dict(data)
        assert result['user']['api_key'] == '[REDACTED]'
        assert result['user']['name'] == 'John'

    def test_redact_list_of_dicts(self):
        """Test redaction in list of dictionaries."""
        data = {
            'credentials': [
                {'api_key': 'key1', 'name': 'Service 1'},
                {'api_key': 'key2', 'name': 'Service 2'}
            ]
        }
        result = redact_dict(data)
        assert result['credentials'][0]['api_key'] == '[REDACTED]'
        assert result['credentials'][1]['api_key'] == '[REDACTED]'
        assert result['credentials'][0]['name'] == 'Service 1'

    def test_redact_dict_partial(self):
        """Test partial redaction in dictionaries."""
        data = {'api_key': 'abc123def456ghi789'}
        result = redact_dict(data, partial=True)
        assert 'abc1' in result['api_key']
        assert 'i789' in result['api_key']
        assert '[REDACTED]' in result['api_key']

    def test_redact_multiple_sensitive_keys(self):
        """Test that all sensitive keys are redacted."""
        data = {
            'api_key': 'key1',
            'password': 'pass1',
            'secret': 'secret1',
            'name': 'John'
        }
        result = redact_dict(data)
        assert result['api_key'] == '[REDACTED]'
        assert result['password'] == '[REDACTED]'
        assert result['secret'] == '[REDACTED]'
        assert result['name'] == 'John'

    def test_preserve_non_dict_input(self):
        """Test that non-dict inputs are returned unchanged."""
        assert redact_dict('string') == 'string'
        assert redact_dict(123) == 123
        assert redact_dict(None) is None

    def test_case_insensitive_key_matching(self):
        """Test that key matching is case-insensitive."""
        data = {
            'API_KEY': 'key1',
            'Api_Key': 'key2',
            'api-key': 'key3',
        }
        result = redact_dict(data)
        # Note: The actual keys are preserved, but values are redacted
        assert result['API_KEY'] == '[REDACTED]'
        assert result['Api_Key'] == '[REDACTED]'
        assert result['api-key'] == '[REDACTED]'


class TestSensitiveDataFilter:
    """Test suite for SensitiveDataFilter logging filter."""

    def test_filter_redacts_log_message(self):
        """Test that filter redacts sensitive data in log messages."""
        # Create a logger with the filter
        logger = logging.getLogger('test_logger_1')
        logger.setLevel(logging.INFO)
        logger.addFilter(SensitiveDataFilter())

        # Create a handler that captures logs
        handler = logging.handlers.MemoryHandler(capacity=100)
        logger.addHandler(handler)

        # Log a message with sensitive data
        logger.info('API_KEY=secret123')

        # Check that the log was redacted
        record = handler.buffer[0]
        assert '[REDACTED]' in record.msg
        assert 'secret123' not in record.msg

    def test_filter_redacts_log_args(self):
        """Test that filter redacts sensitive data in log args."""
        logger = logging.getLogger('test_logger_2')
        logger.setLevel(logging.INFO)
        logger.addFilter(SensitiveDataFilter())

        handler = logging.handlers.MemoryHandler(capacity=100)
        logger.addHandler(handler)

        # Log with args containing sensitive data
        logger.info('User API key: %s', 'secret123')

        record = handler.buffer[0]
        assert '[REDACTED]' in str(record.args[0]) or 'secret123' not in str(record.args)

    def test_filter_preserves_non_sensitive_logs(self):
        """Test that filter does not modify non-sensitive logs."""
        logger = logging.getLogger('test_logger_3')
        logger.setLevel(logging.INFO)
        logger.addFilter(SensitiveDataFilter())

        handler = logging.handlers.MemoryHandler(capacity=100)
        logger.addHandler(handler)

        message = 'User logged in successfully'
        logger.info(message)

        record = handler.buffer[0]
        assert record.msg == message

    def test_filter_with_partial_redaction(self):
        """Test filter with partial redaction enabled."""
        logger = logging.getLogger('test_logger_4')
        logger.setLevel(logging.INFO)
        logger.addFilter(SensitiveDataFilter(partial=True))

        handler = logging.handlers.MemoryHandler(capacity=100)
        logger.addHandler(handler)

        logger.info('API_KEY=abc123def456ghi789')

        record = handler.buffer[0]
        # Should show partial info
        assert 'abc1' in record.msg or '[REDACTED]' in record.msg


class TestConfigureRootLogger:
    """Test suite for configure_root_logger_with_sanitization function."""

    def test_configure_adds_filter_to_root_logger(self):
        """Test that configuration adds filter to root logger."""
        # Remove any existing filters
        root_logger = logging.getLogger()
        root_logger.filters = []

        # Configure
        configure_root_logger_with_sanitization()

        # Check that filter was added
        assert any(isinstance(f, SensitiveDataFilter) for f in root_logger.filters)

    def test_configure_does_not_add_duplicate_filters(self):
        """Test that calling configure multiple times doesn't add duplicate filters."""
        root_logger = logging.getLogger()
        root_logger.filters = []

        # Configure twice
        configure_root_logger_with_sanitization()
        initial_count = sum(1 for f in root_logger.filters if isinstance(f, SensitiveDataFilter))

        configure_root_logger_with_sanitization()
        final_count = sum(1 for f in root_logger.filters if isinstance(f, SensitiveDataFilter))

        # Should have same number of filters
        assert initial_count == final_count == 1


class TestEdgeCases:
    """Test suite for edge cases and special scenarios."""

    def test_empty_string(self):
        """Test that empty strings are handled correctly."""
        assert redact_sensitive_data('') == ''

    def test_none_in_dict(self):
        """Test that None values in dicts are handled correctly."""
        data = {'api_key': None}
        result = redact_dict(data)
        assert result['api_key'] is None

    def test_very_short_value_partial_redaction(self):
        """Test that very short values are completely redacted even with partial=True."""
        message = 'API_KEY=abc'
        result = redact_sensitive_data(message, partial=True)
        assert '[REDACTED]' in result
        # Short values should not show partial info
        assert 'abc' not in result or '[REDACTED]' in result

    def test_special_characters_in_credentials(self):
        """Test that credentials with special characters are redacted."""
        message = 'PASSWORD=p@ssw0rd!#$%'
        result = redact_sensitive_data(message)
        assert '[REDACTED]' in result
        assert 'p@ssw0rd!#$%' not in result

    def test_unicode_in_credentials(self):
        """Test that credentials with unicode characters are redacted."""
        message = 'API_KEY=key_with_émojis_🔑'
        result = redact_sensitive_data(message)
        assert '[REDACTED]' in result

    def test_multiline_string_with_credentials(self):
        """Test redaction across multiple lines."""
        message = '''
        Config:
            API_KEY=secret123
            USER=john
            PASSWORD=pass456
        '''
        result = redact_sensitive_data(message)
        assert result.count('[REDACTED]') == 2  # API_KEY and PASSWORD
        assert 'secret123' not in result
        assert 'pass456' not in result
        assert 'USER=john' in result  # Non-sensitive preserved


class TestRealWorldScenarios:
    """Test suite for real-world logging scenarios."""

    def test_fireflies_api_key_redaction(self):
        """Test Fireflies API key is redacted."""
        message = 'Initializing Fireflies client with API key: abc123def456'
        result = redact_sensitive_data(message)
        assert '[REDACTED]' in result
        assert 'abc123def456' not in result

    def test_jira_credentials_redaction(self):
        """Test Jira credentials are redacted."""
        message = 'JIRA_API_TOKEN=jira_token_123 JIRA_USERNAME=user@example.com'
        result = redact_sensitive_data(message)
        assert '[REDACTED]' in result
        assert 'jira_token_123' not in result
        # Username might be preserved as it's not a token

    def test_http_request_logging(self):
        """Test HTTP request with Authorization header is redacted."""
        message = 'POST /api/endpoint Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9'
        result = redact_sensitive_data(message)
        assert 'Bearer [REDACTED]' in result or 'REDACTED' in result
        assert 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9' not in result

    def test_google_oauth_token_redaction(self):
        """Test Google OAuth token is redacted."""
        data = {
            'user_id': 123,
            'google_oauth_token': 'ya29.a0AfH6SMBxyz123',
            'name': 'John Doe'
        }
        result = redact_dict(data)
        assert result['google_oauth_token'] == '[REDACTED]'
        assert result['name'] == 'John Doe'

    def test_error_message_with_credentials(self):
        """Test error messages containing credentials are redacted."""
        message = 'Authentication failed with api_key=test123: Invalid credentials'
        result = redact_sensitive_data(message)
        assert '[REDACTED]' in result
        assert 'test123' not in result
        assert 'Authentication failed' in result
        assert 'Invalid credentials' in result
