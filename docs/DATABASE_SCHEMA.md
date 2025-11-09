✓ Connecting to production database...

================================================================================
PRODUCTION DATABASE SCHEMA
Total Tables: 32
================================================================================

TABLE: alembic_version
--------------------------------------------------------------------------------
  Columns:
    - version_num                    VARCHAR(32)          NOT NULL [PK]

TABLE: backfill_progress
--------------------------------------------------------------------------------
  Columns:
  
    - id                             INTEGER              NOT NULL [PK]
    - source                         VARCHAR(50)          NOT NULL
    - batch_id                       VARCHAR(100)         NOT NULL
    - start_date                     VARCHAR(20)          NOT NULL
    - end_date                       VARCHAR(20)          NOT NULL
    - status                         VARCHAR(20)          NOT NULL
    - total_items                    INTEGER              NULL
    - processed_items                INTEGER              NULL
    - ingested_items                 INTEGER              NULL
    - error_message                  TEXT                 NULL
    - started_at                     TIMESTAMP            NULL
    - completed_at                   TIMESTAMP            NULL
    - created_at                     TIMESTAMP            NOT NULL
    - updated_at                     TIMESTAMP            NOT NULL

TABLE: celery_taskmeta
--------------------------------------------------------------------------------
  Columns:
  
    - id                             INTEGER              NOT NULL [PK]
    - task_id                        VARCHAR(155)         NULL
    - status                         VARCHAR(50)          NULL
    - result                         BYTEA                NULL
    - date_done                      TIMESTAMP            NULL
    - traceback                      TEXT                 NULL
    - name                           VARCHAR(155)         NULL
    - args                           BYTEA                NULL
    - kwargs                         BYTEA                NULL
    - worker                         VARCHAR(155)         NULL
    - retries                        INTEGER              NULL
    - queue                          VARCHAR(155)         NULL

TABLE: celery_tasksetmeta
--------------------------------------------------------------------------------
  Columns:
  
    - id                             INTEGER              NOT NULL [PK]
    - taskset_id                     VARCHAR(155)         NULL
    - result                         BYTEA                NULL
    - date_done                      TIMESTAMP            NULL

TABLE: epic_baselines
--------------------------------------------------------------------------------
  Columns:
  
    - id                             INTEGER              NOT NULL [PK]
    - epic_category                  VARCHAR(200)         NOT NULL
    - median_hours                   DOUBLE PRECISION     NOT NULL
    - mean_hours                     DOUBLE PRECISION     NOT NULL
    - p75_hours                      DOUBLE PRECISION     NOT NULL
    - p90_hours                      DOUBLE PRECISION     NOT NULL
    - min_hours                      DOUBLE PRECISION     NOT NULL
    - max_hours                      DOUBLE PRECISION     NOT NULL
    - project_count                  INTEGER              NOT NULL
    - occurrence_count               INTEGER              NOT NULL
    - coefficient_of_variation       DOUBLE PRECISION     NOT NULL
    - variance_level                 VARCHAR(20)          NOT NULL
    - created_at                     TIMESTAMP            NOT NULL
    - updated_at                     TIMESTAMP            NOT NULL

TABLE: epic_forecasts
--------------------------------------------------------------------------------
  Columns:
  
    - id                             INTEGER              NOT NULL [PK]
    - project_key                    VARCHAR(50)          NOT NULL
    - epic_name                      VARCHAR(200)         NOT NULL
    - epic_description               TEXT                 NULL
    - be_integrations                BOOLEAN              NOT NULL
    - custom_theme                   BOOLEAN              NOT NULL
    - custom_designs                 BOOLEAN              NOT NULL
    - ux_research                    BOOLEAN              NOT NULL
    - estimated_months               INTEGER              NOT NULL
    - teams_selected                 JSON                 NOT NULL
    - forecast_data                  JSON                 NOT NULL
    - total_hours                    DOUBLE PRECISION     NOT NULL
    - created_by                     VARCHAR(100)         NULL
    - created_at                     TIMESTAMP            NULL
    - updated_at                     TIMESTAMP            NULL

TABLE: epic_hours
--------------------------------------------------------------------------------
  Columns:
  
    - id                             INTEGER              NOT NULL [PK]
    - project_key                    VARCHAR(50)          NOT NULL
    - epic_key                       VARCHAR(50)          NOT NULL
    - epic_summary                   VARCHAR(500)         NULL
    - month                          DATE                 NOT NULL
    - hours                          DOUBLE PRECISION     NOT NULL
    - created_at                     TIMESTAMP            NOT NULL
    - updated_at                     TIMESTAMP            NOT NULL
    - team                           VARCHAR(50)          NOT NULL

TABLE: escalation_history
--------------------------------------------------------------------------------
  Columns:
  
    - id                             INTEGER              NOT NULL [PK]
    - insight_id                     VARCHAR(36)          NOT NULL
    - escalation_type                VARCHAR(50)          NOT NULL
    - escalation_level               INTEGER              NOT NULL
    - target                         VARCHAR(255)         NOT NULL
    - message_sent                   TEXT                 NULL
    - success                        BOOLEAN              NOT NULL
    - error_message                  TEXT                 NULL
    - created_at                     TIMESTAMP            NOT NULL

  Foreign Keys:
    - insight_id → proactive_insights(id)

TABLE: escalation_preferences
--------------------------------------------------------------------------------
  Columns:
  
    - user_id                        INTEGER              NOT NULL [PK]
    - enable_auto_escalation         BOOLEAN              NOT NULL
    - enable_dm_escalation           BOOLEAN              NOT NULL
    - enable_channel_escalation      BOOLEAN              NOT NULL
    - enable_github_escalation       BOOLEAN              NOT NULL
    - dm_threshold_days              INTEGER              NOT NULL
    - channel_threshold_days         INTEGER              NOT NULL
    - critical_threshold_days        INTEGER              NOT NULL
    - created_at                     TIMESTAMP            NOT NULL
    - updated_at                     TIMESTAMP            NOT NULL

  Foreign Keys:
    - user_id → users(id)

TABLE: feedback_items
--------------------------------------------------------------------------------
  Columns:
  
    - id                             VARCHAR(36)          NOT NULL [PK]
    - user_id                        INTEGER              NOT NULL
    - recipient                      VARCHAR(255)         NULL
    - content                        TEXT                 NOT NULL
    - status                         VARCHAR(50)          NULL
    - created_at                     TIMESTAMP            NULL
    - updated_at                     TIMESTAMP            NULL

TABLE: learnings
--------------------------------------------------------------------------------
  Columns:
  
    - id                             INTEGER              NOT NULL [PK]
    - user_id                        INTEGER              NULL
    - title                          VARCHAR(255)         NOT NULL
    - description                    TEXT                 NULL
    - category                       VARCHAR(100)         NULL
    - tags                           TEXT                 NULL
    - source                         VARCHAR(255)         NULL
    - created_at                     TIMESTAMP            NULL
    - updated_at                     TIMESTAMP            NULL

  Foreign Keys:
    - user_id → users(id)

TABLE: meeting_metadata
--------------------------------------------------------------------------------
  Columns:
  
    - id                             INTEGER              NOT NULL [PK]
    - meeting_title                  VARCHAR(255)         NOT NULL
    - normalized_title               VARCHAR(255)         NOT NULL
    - meeting_type                   VARCHAR(50)          NULL
    - project_key                    VARCHAR(50)          NULL
    - recurrence_pattern             VARCHAR(50)          NULL
    - last_occurrence                TIMESTAMP            NOT NULL
    - next_expected                  TIMESTAMP            NULL
    - participants                   JSON                 NULL
    - created_at                     TIMESTAMP            NOT NULL
    - updated_at                     TIMESTAMP            NOT NULL

TABLE: meeting_project_connections
--------------------------------------------------------------------------------
  Columns:
  
    - id                             VARCHAR              NOT NULL [PK]
    - meeting_id                     VARCHAR              NOT NULL
    - meeting_title                  VARCHAR              NULL
    - meeting_date                   TIMESTAMP            NULL
    - project_key                    VARCHAR              NOT NULL
    - project_name                   VARCHAR              NULL
    - relevance_score                VARCHAR              NULL
    - confidence                     VARCHAR              NULL
    - matching_factors               JSON                 NULL
    - created_at                     TIMESTAMP            NULL
    - last_confirmed_at              TIMESTAMP            NULL
    - is_verified                    BOOLEAN              NULL

TABLE: proactive_insights
--------------------------------------------------------------------------------
  Columns:
  
    - id                             VARCHAR(36)          NOT NULL [PK]
    - user_id                        INTEGER              NOT NULL
    - project_key                    VARCHAR(50)          NULL
    - insight_type                   VARCHAR(50)          NOT NULL
    - title                          VARCHAR(255)         NOT NULL
    - description                    TEXT                 NOT NULL
    - severity                       VARCHAR(20)          NOT NULL
    - metadata_json                  JSON                 NULL
    - created_at                     TIMESTAMP            NOT NULL
    - dismissed_at                   TIMESTAMP            NULL
    - acted_on_at                    TIMESTAMP            NULL
    - action_taken                   VARCHAR(100)         NULL
    - delivered_via_slack            TIMESTAMP            NULL
    - delivered_via_email            TIMESTAMP            NULL
    - last_escalated_at              TIMESTAMP            NULL
    - escalation_count               INTEGER              NOT NULL
    - escalation_level               INTEGER              NOT NULL

  Foreign Keys:
    - user_id → users(id)

TABLE: processed_meetings
--------------------------------------------------------------------------------
  Columns:
  
    - id                             VARCHAR(36)          NOT NULL [PK]
    - title                          VARCHAR(255)         NOT NULL
    - fireflies_id                   VARCHAR(255)         NULL
    - date                           TIMESTAMP            NULL
    - duration                       INTEGER              NULL
    - summary                        TEXT                 NULL
    - action_items                   TEXT                 NULL
    - created_at                     TIMESTAMP            NULL
    - updated_at                     TIMESTAMP            NULL
    - key_decisions                  TEXT                 NULL
    - blockers                       TEXT                 NULL
    - analyzed_at                    TIMESTAMP            NULL
    - processed_at                   TIMESTAMP            NULL
    - tickets_created                TEXT                 NULL
    - todos_created                  TEXT                 NULL
    - success                        BOOLEAN              NULL
    - executive_summary              TEXT                 NULL
    - outcomes                       TEXT                 NULL
    - blockers_and_constraints       TEXT                 NULL
    - timeline_and_milestones        TEXT                 NULL
    - key_discussions                TEXT                 NULL
    - topics                         TEXT                 NULL
    - ai_provider                    VARCHAR(50)          NULL
    - ai_model                       VARCHAR(100)         NULL

TABLE: project_changes
--------------------------------------------------------------------------------
  Columns:
  
    - id                             VARCHAR              NOT NULL [PK]
    - project_key                    VARCHAR              NOT NULL
    - change_type                    VARCHAR              NOT NULL
    - ticket_key                     VARCHAR              NOT NULL
    - ticket_title                   VARCHAR              NULL
    - old_value                      VARCHAR              NULL
    - new_value                      VARCHAR              NULL
    - assignee                       VARCHAR              NULL
    - reporter                       VARCHAR              NULL
    - priority                       VARCHAR              NULL
    - status                         VARCHAR              NULL
    - change_timestamp               TIMESTAMP            NOT NULL
    - detected_at                    TIMESTAMP            NULL
    - change_details                 JSON                 NULL

TABLE: project_digest_cache
--------------------------------------------------------------------------------
  Columns:
  
    - id                             INTEGER              NOT NULL [PK]
    - project_key                    VARCHAR(50)          NOT NULL
    - days                           INTEGER              NOT NULL
    - digest_data                    TEXT                 NOT NULL
    - created_at                     TIMESTAMP            NOT NULL
    - include_context                BOOLEAN              NOT NULL

TABLE: project_keywords
--------------------------------------------------------------------------------
  Columns:
  
    - id                             INTEGER              NOT NULL [PK]
    - user_id                        INTEGER              NULL
    - keyword                        VARCHAR(100)         NOT NULL
    - project_key                    VARCHAR(50)          NOT NULL
    - created_at                     TIMESTAMP            NULL
    - updated_at                     TIMESTAMP            NULL

  Foreign Keys:
    - user_id → users(id)

TABLE: project_monthly_forecast
--------------------------------------------------------------------------------
  Columns:
  
    - id                             INTEGER              NOT NULL [PK]
    - project_key                    VARCHAR(50)          NOT NULL
    - month_year                     DATE                 NOT NULL
    - forecasted_hours               NUMERIC(10, 2)       NULL
    - actual_monthly_hours           NUMERIC(10, 2)       NULL
    - created_at                     TIMESTAMP            NULL
    - updated_at                     TIMESTAMP            NULL

  Foreign Keys:
    - project_key → projects(key)

TABLE: project_resource_mappings
--------------------------------------------------------------------------------
  Columns:
  
    - id                             INTEGER              NOT NULL [PK]
    - project_key                    TEXT                 NOT NULL
    - project_name                   TEXT                 NOT NULL
    - slack_channel_ids              TEXT                 NULL
    - notion_page_ids                TEXT                 NULL
    - github_repos                   TEXT                 NULL
    - created_at                     TIMESTAMP            NULL
    - updated_at                     TIMESTAMP            NULL
    - jira_project_keys              TEXT                 NULL
    - internal_slack_channels        TEXT                 NULL

TABLE: projects
--------------------------------------------------------------------------------
  Columns:
  
    - key                            VARCHAR(50)          NOT NULL [PK]
    - name                           VARCHAR(255)         NOT NULL
    - description                    TEXT                 NULL
    - lead                           VARCHAR(255)         NULL
    - is_active                      BOOLEAN              NULL
    - created_at                     TIMESTAMP            NULL
    - updated_at                     TIMESTAMP            NULL
    - total_hours                    NUMERIC(10, 2)       NULL
    - project_work_type              VARCHAR(50)          NULL
    - cumulative_hours               NUMERIC(10, 2)       NULL
    - weekly_meeting_day             TEXT                 NULL
    - retainer_hours                 NUMERIC(10, 2)       NULL
    - send_meeting_emails            BOOLEAN              NOT NULL

TABLE: query_expansions
--------------------------------------------------------------------------------
  Columns:
  
    - id                             INTEGER              NOT NULL [PK]
    - original_term                  VARCHAR(100)         NOT NULL
    - expanded_term                  VARCHAR(100)         NOT NULL
    - expansion_type                 VARCHAR(20)          NOT NULL
    - confidence_score               DOUBLE PRECISION     NOT NULL
    - usage_count                    INTEGER              NOT NULL
    - success_count                  INTEGER              NOT NULL
    - project_key                    VARCHAR(10)          NULL
    - domain                         VARCHAR(50)          NULL
    - is_active                      BOOLEAN              NOT NULL
    - created_at                     TIMESTAMP            NOT NULL
    - updated_at                     TIMESTAMP            NOT NULL

TABLE: search_feedback
--------------------------------------------------------------------------------
  Columns:
  
    - id                             INTEGER              NOT NULL [PK]
    - user_id                        INTEGER              NULL
    - slack_user_id                  VARCHAR(50)          NULL
    - query                          TEXT                 NOT NULL
    - rating                         INTEGER              NOT NULL
    - feedback_text                  TEXT                 NULL
    - result_count                   INTEGER              NULL
    - result_sources                 JSON                 NULL
    - top_result_source              VARCHAR(50)          NULL
    - detail_level                   VARCHAR(20)          NULL
    - project_key                    VARCHAR(10)          NULL
    - response_time_ms               INTEGER              NULL
    - summary_length                 INTEGER              NULL
    - created_at                     TIMESTAMP            NOT NULL

TABLE: slack_sessions
--------------------------------------------------------------------------------
  Columns:
  
    - session_id                     VARCHAR(32)          NOT NULL [PK]
    - data                           BYTEA                NOT NULL
    - created_at                     TIMESTAMP            NOT NULL
    - expires_at                     TIMESTAMP            NOT NULL

TABLE: system_settings
--------------------------------------------------------------------------------
  Columns:
  
    - id                             INTEGER              NOT NULL [PK]
    - ai_provider                    VARCHAR(50)          NOT NULL
    - ai_model                       VARCHAR(100)         NULL
    - ai_temperature                 DOUBLE PRECISION     NOT NULL
    - ai_max_tokens                  INTEGER              NOT NULL
    - openai_api_key_encrypted       TEXT                 NULL
    - anthropic_api_key_encrypted    TEXT                 NULL
    - google_api_key_encrypted       TEXT                 NULL
    - updated_at                     TIMESTAMP            NULL
    - updated_by_user_id             INTEGER              NULL

TABLE: todo_items
--------------------------------------------------------------------------------
  Columns:
  
    - id                             VARCHAR(36)          NOT NULL [PK]
    - title                          VARCHAR(255)         NOT NULL
    - description                    TEXT                 NULL
    - assignee                       VARCHAR(255)         NULL
    - priority                       VARCHAR(50)          NULL
    - status                         VARCHAR(50)          NULL
    - project_key                    VARCHAR(50)          NULL
    - user_id                        INTEGER              NULL
    - created_at                     TIMESTAMP            NULL
    - updated_at                     TIMESTAMP            NULL
    - due_date                       TIMESTAMP            NULL
    - ticket_key                     VARCHAR(50)          NULL
    - source_meeting_id              VARCHAR(36)          NULL
    - source                         VARCHAR(50)          NULL

TABLE: user_notification_preferences
--------------------------------------------------------------------------------
  Columns:
  
    - user_id                        INTEGER              NOT NULL [PK]
    - daily_brief_slack              BOOLEAN              NOT NULL
    - daily_brief_email              BOOLEAN              NOT NULL
    - enable_stale_pr_alerts         BOOLEAN              NOT NULL
    - enable_budget_alerts           BOOLEAN              NOT NULL
    - enable_missing_ticket_alerts   BOOLEAN              NOT NULL
    - enable_anomaly_alerts          BOOLEAN              NOT NULL
    - enable_meeting_prep            BOOLEAN              NOT NULL
    - daily_brief_time               VARCHAR(5)           NOT NULL
    - timezone                       VARCHAR(50)          NOT NULL

  Foreign Keys:
    - user_id → users(id)

TABLE: user_preferences
--------------------------------------------------------------------------------
  Columns:
  
    - id                             VARCHAR              NOT NULL [PK]
    - email                          VARCHAR              NOT NULL
    - slack_username                 VARCHAR              NULL
    - notification_cadence           VARCHAR              NULL
    - selected_projects              JSON                 NULL
    - created_at                     TIMESTAMP            NULL
    - updated_at                     TIMESTAMP            NULL
    - last_notification_sent         TIMESTAMP            NULL

TABLE: user_teams
--------------------------------------------------------------------------------
  Columns:
  
    - account_id                     VARCHAR(100)         NOT NULL [PK]
    - display_name                   VARCHAR(200)         NULL
    - team                           VARCHAR(50)          NOT NULL
    - updated_at                     TIMESTAMP            NOT NULL

TABLE: user_watched_projects
--------------------------------------------------------------------------------
  Columns:
  
    - id                             INTEGER              NOT NULL [PK]
    - user_id                        INTEGER              NULL
    - project_key                    VARCHAR(50)          NOT NULL
    - created_at                     TIMESTAMP            NULL
    - updated_at                     TIMESTAMP            NULL

  Foreign Keys:
    - user_id → users(id)

TABLE: users
--------------------------------------------------------------------------------
  Columns:
  
    - id                             INTEGER              NOT NULL [PK]
    - email                          VARCHAR(255)         NOT NULL
    - name                           VARCHAR(255)         NULL
    - google_id                      VARCHAR(255)         NULL
    - role                           VARCHAR(9)           NULL
    - created_at                     TIMESTAMP            NULL
    - updated_at                     TIMESTAMP            NULL
    - last_login                     TIMESTAMP            NULL
    - is_active                      BOOLEAN              NULL
    - fireflies_api_key_encrypted    TEXT                 NULL
    - google_oauth_token_encrypted   TEXT                 NULL
    - notion_api_key_encrypted       TEXT                 NULL
    - google_credentials_updated_at  TIMESTAMP            NULL
    - notion_credentials_updated_at  TIMESTAMP            NULL
    - slack_user_token_encrypted     TEXT                 NULL
    - slack_credentials_updated_at   TIMESTAMP            NULL
    - slack_user_id                  VARCHAR(50)          NULL
    - notify_daily_todo_digest       BOOLEAN              NOT NULL
    - notify_project_hours_forecast  BOOLEAN              NOT NULL

TABLE: vector-sync-status
--------------------------------------------------------------------------------
  Columns:
  
    - source                         TEXT                 NOT NULL [PK]
    - last_sync                      TEXT                 NOT NULL
    - created_at                     TIMESTAMP            NULL
    - updated_at                     TIMESTAMP            NULL

