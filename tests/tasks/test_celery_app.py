"""Tests for Celery application configuration and GCP credentials handling."""

import pytest
import os
import tempfile
import atexit
from unittest.mock import patch, MagicMock, mock_open, call
from pathlib import Path


class TestGCPCredentialsHandling:
    """Test suite for GCP credentials secure tempfile handling."""

    def test_gcp_credentials_uses_secure_tempfile(self):
        """Test that GCP credentials use secure tempfile instead of predictable path."""
        mock_creds_json = '{"type": "service_account", "project_id": "test"}'

        with patch.dict(os.environ, {'GOOGLE_APPLICATION_CREDENTIALS_JSON': mock_creds_json}, clear=False):
            with patch('tempfile.mkstemp') as mock_mkstemp:
                with patch('os.chmod') as mock_chmod:
                    with patch('os.fdopen', mock_open()) as mock_fdopen:
                        with patch('atexit.register') as mock_atexit:
                            # Mock mkstemp to return fake file descriptor and path
                            mock_fd = 123
                            mock_path = '/tmp/gcp-creds-random123.json'
                            mock_mkstemp.return_value = (mock_fd, mock_path)

                            # Import module (triggers credential setup)
                            import importlib
                            import src.tasks.celery_app
                            importlib.reload(src.tasks.celery_app)

                            # Verify secure tempfile was created (may be called multiple times during test setup)
                            assert mock_mkstemp.called
                            assert mock_mkstemp.call_args[1] == {'suffix': '.json', 'prefix': 'gcp-creds-'}

                            # Verify restrictive permissions were set (0o600 = owner read/write only)
                            assert mock_chmod.called
                            assert any(call[0][1] == 0o600 for call in mock_chmod.call_args_list)

                            # Verify file was opened with the file descriptor
                            assert mock_fdopen.called

                            # Verify cleanup function was registered
                            assert mock_atexit.called
                            assert any('cleanup_gcp_credentials' in str(call) for call in mock_atexit.call_args_list)

    def test_gcp_credentials_cleanup_on_exit(self):
        """Test that GCP credentials file is cleaned up on exit."""
        mock_creds_json = '{"type": "service_account", "project_id": "test"}'
        mock_path = '/tmp/gcp-creds-test.json'

        with patch.dict(os.environ, {'GOOGLE_APPLICATION_CREDENTIALS_JSON': mock_creds_json}, clear=False):
            with patch('tempfile.mkstemp') as mock_mkstemp:
                with patch('os.chmod'):
                    with patch('os.fdopen', mock_open()):
                        with patch('atexit.register') as mock_atexit:
                            with patch('os.path.exists') as mock_exists:
                                with patch('os.unlink') as mock_unlink:
                                    mock_mkstemp.return_value = (123, mock_path)
                                    mock_exists.return_value = True

                                    # Import module
                                    import importlib
                                    import src.tasks.celery_app
                                    importlib.reload(src.tasks.celery_app)

                                    # Get the cleanup function that was registered
                                    cleanup_func = mock_atexit.call_args[0][0]

                                    # Call the cleanup function
                                    cleanup_func()

                                    # Verify file existence was checked
                                    mock_exists.assert_called_once_with(mock_path)

                                    # Verify file was deleted
                                    mock_unlink.assert_called_once_with(mock_path)

    def test_gcp_credentials_cleanup_handles_missing_file(self):
        """Test that cleanup handles case where file doesn't exist."""
        mock_creds_json = '{"type": "service_account", "project_id": "test"}'
        mock_path = '/tmp/gcp-creds-test.json'

        with patch.dict(os.environ, {'GOOGLE_APPLICATION_CREDENTIALS_JSON': mock_creds_json}, clear=False):
            with patch('tempfile.mkstemp') as mock_mkstemp:
                with patch('os.chmod'):
                    with patch('os.fdopen', mock_open()):
                        with patch('atexit.register') as mock_atexit:
                            with patch('os.path.exists') as mock_exists:
                                with patch('os.unlink') as mock_unlink:
                                    mock_mkstemp.return_value = (123, mock_path)
                                    mock_exists.return_value = False

                                    # Import module
                                    import importlib
                                    import src.tasks.celery_app
                                    importlib.reload(src.tasks.celery_app)

                                    # Get and call cleanup function
                                    cleanup_func = mock_atexit.call_args[0][0]
                                    cleanup_func()

                                    # Verify unlink was NOT called since file doesn't exist
                                    mock_unlink.assert_not_called()

    def test_gcp_credentials_cleanup_handles_errors_silently(self):
        """Test that cleanup handles errors gracefully without raising."""
        mock_creds_json = '{"type": "service_account", "project_id": "test"}'
        mock_path = '/tmp/gcp-creds-test.json'

        with patch.dict(os.environ, {'GOOGLE_APPLICATION_CREDENTIALS_JSON': mock_creds_json}, clear=False):
            with patch('tempfile.mkstemp') as mock_mkstemp:
                with patch('os.chmod'):
                    with patch('os.fdopen', mock_open()):
                        with patch('atexit.register') as mock_atexit:
                            with patch('os.path.exists') as mock_exists:
                                with patch('os.unlink') as mock_unlink:
                                    mock_mkstemp.return_value = (123, mock_path)
                                    mock_exists.return_value = True
                                    mock_unlink.side_effect = OSError("Permission denied")

                                    # Import module
                                    import importlib
                                    import src.tasks.celery_app
                                    importlib.reload(src.tasks.celery_app)

                                    # Get and call cleanup function - should not raise
                                    cleanup_func = mock_atexit.call_args[0][0]
                                    try:
                                        cleanup_func()
                                    except Exception as e:
                                        pytest.fail(f"Cleanup should handle errors silently, but raised: {e}")

    def test_gcp_credentials_not_configured_when_env_var_missing(self):
        """Test that GCP credentials setup is skipped when env var not set."""
        # Ensure GOOGLE_APPLICATION_CREDENTIALS_JSON is not set
        env = os.environ.copy()
        if 'GOOGLE_APPLICATION_CREDENTIALS_JSON' in env:
            del env['GOOGLE_APPLICATION_CREDENTIALS_JSON']

        with patch.dict(os.environ, env, clear=True):
            with patch('tempfile.mkstemp') as mock_mkstemp:
                with patch('os.chmod') as mock_chmod:
                    with patch('atexit.register') as mock_atexit:
                        # Import module
                        import importlib
                        import src.tasks.celery_app
                        importlib.reload(src.tasks.celery_app)

                        # Verify tempfile was NOT created
                        mock_mkstemp.assert_not_called()
                        mock_chmod.assert_not_called()

    def test_gcp_credentials_file_permissions_are_restrictive(self):
        """Test that file permissions are set to 0o600 (owner read/write only)."""
        mock_creds_json = '{"type": "service_account", "project_id": "test"}'

        with patch.dict(os.environ, {'GOOGLE_APPLICATION_CREDENTIALS_JSON': mock_creds_json}, clear=False):
            with patch('tempfile.mkstemp') as mock_mkstemp:
                with patch('os.chmod') as mock_chmod:
                    with patch('os.fdopen', mock_open()):
                        with patch('atexit.register'):
                            mock_mkstemp.return_value = (123, '/tmp/gcp-creds-test.json')

                            # Import module
                            import importlib
                            import src.tasks.celery_app
                            importlib.reload(src.tasks.celery_app)

                            # Verify chmod was called with restrictive permissions
                            # 0o600 = 384 in decimal = owner read/write only
                            mock_chmod.assert_called_once()
                            call_args = mock_chmod.call_args
                            assert call_args[0][1] == 0o600, f"Expected 0o600 permissions, got {oct(call_args[0][1])}"

    def test_gcp_credentials_json_written_correctly(self):
        """Test that credentials JSON is written to the temp file correctly."""
        mock_creds_json = '{"type": "service_account", "project_id": "test-project"}'

        with patch.dict(os.environ, {'GOOGLE_APPLICATION_CREDENTIALS_JSON': mock_creds_json}, clear=False):
            with patch('tempfile.mkstemp') as mock_mkstemp:
                with patch('os.chmod'):
                    mock_file = MagicMock()
                    with patch('os.fdopen', return_value=mock_file):
                        with patch('atexit.register'):
                            mock_mkstemp.return_value = (123, '/tmp/gcp-creds-test.json')

                            # Import module
                            import importlib
                            import src.tasks.celery_app
                            importlib.reload(src.tasks.celery_app)

                            # Verify credentials were written
                            mock_file.__enter__.return_value.write.assert_called_once_with(mock_creds_json)

    def test_environment_variable_set_correctly(self):
        """Test that GOOGLE_APPLICATION_CREDENTIALS env var is set to temp file path."""
        mock_creds_json = '{"type": "service_account", "project_id": "test"}'
        mock_path = '/tmp/gcp-creds-random456.json'

        with patch.dict(os.environ, {'GOOGLE_APPLICATION_CREDENTIALS_JSON': mock_creds_json}, clear=False):
            with patch('tempfile.mkstemp') as mock_mkstemp:
                with patch('os.chmod'):
                    with patch('os.fdopen', mock_open()):
                        with patch('atexit.register'):
                            mock_mkstemp.return_value = (123, mock_path)

                            # Import module
                            import importlib
                            import src.tasks.celery_app
                            importlib.reload(src.tasks.celery_app)

                            # Verify environment variable was set
                            assert os.environ.get('GOOGLE_APPLICATION_CREDENTIALS') == mock_path


class TestCeleryConfiguration:
    """Test suite for Celery configuration."""

    def test_celery_app_includes_correct_tasks(self):
        """Test that Celery app includes expected task modules."""
        from src.tasks.celery_app import celery_app

        expected_includes = ['src.tasks.vector_tasks', 'src.tasks.notification_tasks', 'src.tasks.backfill_tasks', 'src.webhooks.fireflies_webhook']
        assert celery_app.conf.include == expected_includes

    def test_celery_task_time_limit_configured(self):
        """Test that task time limit is configured correctly."""
        from src.tasks.celery_app import celery_app

        # Should be 120 minutes (7200 seconds) for large backfills
        assert celery_app.conf.task_time_limit == 120 * 60

    def test_backfill_tasks_inherit_global_time_limit(self):
        """Test that backfill tasks don't override global time limit."""
        from src.tasks.vector_tasks import backfill_jira, backfill_tempo

        # Neither backfill task should have time_limit override in decorator
        # They should inherit the global 2-hour limit
        # Check if time_limit was explicitly set in decorator (not None)
        assert backfill_jira.time_limit is None, "backfill_jira should not override time_limit (should be None to inherit global)"
        assert backfill_tempo.time_limit is None, "backfill_tempo should not override time_limit (should be None to inherit global)"

    def test_celery_late_ack_enabled(self):
        """Test that late acknowledgment is enabled (resilience fix)."""
        from src.tasks.celery_app import celery_app

        # Late ack should be True to prevent task loss on restart
        assert celery_app.conf.task_acks_late is True

    def test_celery_reject_on_worker_lost_enabled(self):
        """Test that reject_on_worker_lost is enabled (resilience fix)."""
        from src.tasks.celery_app import celery_app

        # Should requeue tasks if worker crashes
        assert celery_app.conf.task_reject_on_worker_lost is True

    def test_celery_prefetch_multiplier_set(self):
        """Test that prefetch multiplier is set to 1 (prevents task loss)."""
        from src.tasks.celery_app import celery_app

        # Should only fetch 1 task at a time
        assert celery_app.conf.worker_prefetch_multiplier == 1

    def test_celery_result_expires_configured(self):
        """Test that result expiration is configured (prevents database bloat)."""
        from src.tasks.celery_app import celery_app

        # Should expire after 1 hour (3600 seconds)
        assert celery_app.conf.result_expires == 3600


class TestBrokerConfiguration:
    """Test suite for GCP Pub/Sub broker configuration."""

    def test_broker_url_uses_gcp_pubsub(self):
        """Test that broker URL is configured for GCP Pub/Sub."""
        with patch.dict(os.environ, {'GCP_PROJECT_ID': 'test-project'}, clear=False):
            import importlib
            import src.tasks.celery_app
            importlib.reload(src.tasks.celery_app)

            from src.tasks.celery_app import celery_app

            assert celery_app.conf.broker_url.startswith('gcpubsub://projects/')

    def test_broker_ack_deadline_configured(self):
        """Test that broker acknowledgment deadline is configured."""
        from src.tasks.celery_app import celery_app

        # Should have 10 minutes (600 seconds) ack deadline
        assert 'ack_deadline' in celery_app.conf.broker_transport_options
        assert celery_app.conf.broker_transport_options['ack_deadline'] == 600

    def test_broker_message_retention_configured(self):
        """Test that message retention is configured for 7 days."""
        from src.tasks.celery_app import celery_app

        # Should keep unacked messages for 7 days (604800 seconds)
        assert 'message_retention_duration' in celery_app.conf.broker_transport_options
        assert celery_app.conf.broker_transport_options['message_retention_duration'] == 604800
