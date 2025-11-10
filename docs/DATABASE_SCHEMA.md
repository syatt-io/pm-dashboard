✓ Connecting to production database...

================================================================================
PRODUCTION DATABASE SCHEMA
Total Tables: 37
Generated: 2025-11-10 08:25:54
================================================================================

TABLE: alembic_version
--------------------------------------------------------------------------------
  Columns:
  
    - version_num                    CHARACTER VARYING    NOT NULL [PK]

TABLE: backfill_progress
--------------------------------------------------------------------------------
  Columns:
  
    - id                             INTEGER              NOT NULL [PK]
    - source                         CHARACTER VARYING    NOT NULL
    - batch_id                       CHARACTER VARYING    NOT NULL
    - start_date                     CHARACTER VARYING    NOT NULL
    - end_date                       CHARACTER VARYING    NOT NULL
    - status                         CHARACTER VARYING    NOT NULL
    - total_items                    INTEGER              NULL    
    - processed_items                INTEGER              NULL    
    - ingested_items                 INTEGER              NULL    
    - error_message                  TEXT                 NULL    
    - started_at                     TIMESTAMP WITHOUT TIME ZONE NULL    
    - completed_at                   TIMESTAMP WITHOUT TIME ZONE NULL    
    - created_at                     TIMESTAMP WITHOUT TIME ZONE NOT NULL
    - updated_at                     TIMESTAMP WITHOUT TIME ZONE NOT NULL

TABLE: celery_taskmeta
--------------------------------------------------------------------------------
  Columns:
  
    - id                             INTEGER              NOT NULL [PK]
    - task_id                        CHARACTER VARYING    NULL    
    - status                         CHARACTER VARYING    NULL    
    - result                         BYTEA                NULL    
    - date_done                      TIMESTAMP WITHOUT TIME ZONE NULL    
    - traceback                      TEXT                 NULL    
    - name                           CHARACTER VARYING    NULL    
    - args                           BYTEA                NULL    
    - kwargs                         BYTEA                NULL    
    - worker                         CHARACTER VARYING    NULL    
    - retries                        INTEGER              NULL    
    - queue                          CHARACTER VARYING    NULL    

TABLE: celery_tasksetmeta
--------------------------------------------------------------------------------
  Columns:
  
    - id                             INTEGER              NOT NULL [PK]
    - taskset_id                     CHARACTER VARYING    NULL    
    - result                         BYTEA                NULL    
    - date_done                      TIMESTAMP WITHOUT TIME ZONE NULL    

TABLE: epic_baselines
--------------------------------------------------------------------------------
  Columns:
  
    - id                             INTEGER              NOT NULL [PK]
    - epic_category                  CHARACTER VARYING    NOT NULL
    - median_hours                   DOUBLE PRECISION     NOT NULL
    - mean_hours                     DOUBLE PRECISION     NOT NULL
    - p75_hours                      DOUBLE PRECISION     NOT NULL
    - p90_hours                      DOUBLE PRECISION     NOT NULL
    - min_hours                      DOUBLE PRECISION     NOT NULL
    - max_hours                      DOUBLE PRECISION     NOT NULL
    - project_count                  INTEGER              NOT NULL
    - occurrence_count               INTEGER              NOT NULL
    - coefficient_of_variation       DOUBLE PRECISION     NOT NULL
    - variance_level                 CHARACTER VARYING    NOT NULL
    - created_at                     TIMESTAMP WITHOUT TIME ZONE NOT NULL
    - updated_at                     TIMESTAMP WITHOUT TIME ZONE NOT NULL

TABLE: epic_budgets
--------------------------------------------------------------------------------
  Columns:
  
    - id                             INTEGER              NOT NULL [PK]
    - project_key                    CHARACTER VARYING    NOT NULL
    - epic_key                       CHARACTER VARYING    NOT NULL
    - epic_summary                   CHARACTER VARYING    NULL    
    - estimated_hours                NUMERIC              NOT NULL
    - created_at                     TIMESTAMP WITH TIME ZONE NOT NULL
    - updated_at                     TIMESTAMP WITH TIME ZONE NOT NULL

TABLE: epic_forecasts
--------------------------------------------------------------------------------
  Columns:
  
    - id                             INTEGER              NOT NULL [PK]
    - project_key                    CHARACTER VARYING    NOT NULL
    - epic_name                      CHARACTER VARYING    NOT NULL
    - epic_description               TEXT                 NULL    
    - be_integrations                BOOLEAN              NOT NULL
    - custom_theme                   BOOLEAN              NOT NULL
    - custom_designs                 BOOLEAN              NOT NULL
    - ux_research                    BOOLEAN              NOT NULL
    - estimated_months               INTEGER              NOT NULL
    - teams_selected                 JSON                 NOT NULL
    - forecast_data                  JSON                 NOT NULL
    - total_hours                    DOUBLE PRECISION     NOT NULL
    - created_by                     CHARACTER VARYING    NULL    
    - created_at                     TIMESTAMP WITH TIME ZONE NULL    
    - updated_at                     TIMESTAMP WITH TIME ZONE NULL    

TABLE: epic_hours
--------------------------------------------------------------------------------
  Columns:
  
    - id                             INTEGER              NOT NULL [PK]
    - project_key                    CHARACTER VARYING    NOT NULL
    - epic_key                       CHARACTER VARYING    NOT NULL
    - epic_summary                   CHARACTER VARYING    NULL    
    - month                          DATE                 NOT NULL
    - hours                          DOUBLE PRECISION     NOT NULL
    - created_at                     TIMESTAMP WITHOUT TIME ZONE NOT NULL
    - updated_at                     TIMESTAMP WITHOUT TIME ZONE NOT NULL
    - team                           CHARACTER VARYING    NOT NULL

TABLE: escalation_history
--------------------------------------------------------------------------------
  Columns:
  
    - id                             INTEGER              NOT NULL [PK]
    - insight_id                     CHARACTER VARYING    NOT NULL
    - escalation_type                CHARACTER VARYING    NOT NULL
    - escalation_level               INTEGER              NOT NULL
    - target                         CHARACTER VARYING    NOT NULL
    - message_sent                   TEXT                 NULL    
    - success                        BOOLEAN              NOT NULL
    - error_message                  TEXT                 NULL    
    - created_at                     TIMESTAMP WITHOUT TIME ZONE NOT NULL

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
    - created_at                     TIMESTAMP WITHOUT TIME ZONE NOT NULL
    - updated_at                     TIMESTAMP WITHOUT TIME ZONE NOT NULL

  Foreign Keys:
    - user_id → users(id)

TABLE: feedback_items
--------------------------------------------------------------------------------
  Columns:
  
    - id                             CHARACTER VARYING    NOT NULL [PK]
    - user_id                        INTEGER              NOT NULL
    - recipient                      CHARACTER VARYING    NULL    
    - content                        TEXT                 NOT NULL
    - status                         CHARACTER VARYING    NULL    
    - created_at                     TIMESTAMP WITHOUT TIME ZONE NULL    
    - updated_at                     TIMESTAMP WITHOUT TIME ZONE NULL    

TABLE: learnings
--------------------------------------------------------------------------------
  Columns:
  
    - id                             INTEGER              NOT NULL [PK]
    - user_id                        INTEGER              NULL    
    - title                          CHARACTER VARYING    NOT NULL
    - description                    TEXT                 NULL    
    - category                       CHARACTER VARYING    NULL    
    - tags                           TEXT                 NULL    
    - source                         CHARACTER VARYING    NULL    
    - created_at                     TIMESTAMP WITHOUT TIME ZONE NULL    
    - updated_at                     TIMESTAMP WITHOUT TIME ZONE NULL    

  Foreign Keys:
    - user_id → users(id)

TABLE: meeting_metadata
--------------------------------------------------------------------------------
  Columns:
  
    - id                             INTEGER              NOT NULL [PK]
    - meeting_title                  CHARACTER VARYING    NOT NULL
    - normalized_title               CHARACTER VARYING    NOT NULL
    - meeting_type                   CHARACTER VARYING    NULL    
    - project_key                    CHARACTER VARYING    NULL    
    - recurrence_pattern             CHARACTER VARYING    NULL    
    - last_occurrence                TIMESTAMP WITHOUT TIME ZONE NOT NULL
    - next_expected                  TIMESTAMP WITHOUT TIME ZONE NULL    
    - participants                   JSON                 NULL    
    - created_at                     TIMESTAMP WITHOUT TIME ZONE NOT NULL
    - updated_at                     TIMESTAMP WITHOUT TIME ZONE NOT NULL

TABLE: meeting_project_connections
--------------------------------------------------------------------------------
  Columns:
  
    - id                             CHARACTER VARYING    NOT NULL [PK]
    - meeting_id                     CHARACTER VARYING    NOT NULL
    - meeting_title                  CHARACTER VARYING    NULL    
    - meeting_date                   TIMESTAMP WITHOUT TIME ZONE NULL    
    - project_key                    CHARACTER VARYING    NOT NULL
    - project_name                   CHARACTER VARYING    NULL    
    - relevance_score                CHARACTER VARYING    NULL    
    - confidence                     CHARACTER VARYING    NULL    
    - matching_factors               JSON                 NULL    
    - created_at                     TIMESTAMP WITHOUT TIME ZONE NULL    
    - last_confirmed_at              TIMESTAMP WITHOUT TIME ZONE NULL    
    - is_verified                    BOOLEAN              NULL    

TABLE: monthly_reconciliation_reports
--------------------------------------------------------------------------------
  Columns:
  
    - id                             INTEGER              NOT NULL [PK]
    - month                          CHARACTER VARYING    NOT NULL
    - generated_at                   TIMESTAMP WITH TIME ZONE NOT NULL
    - file_path                      CHARACTER VARYING    NULL    
    - total_projects                 INTEGER              NOT NULL
    - total_epics                    INTEGER              NOT NULL
    - total_variance_pct             DOUBLE PRECISION     NULL    
    - sent_to                        JSON                 NULL    
    - report_metadata                JSON                 NULL    

TABLE: proactive_insights
--------------------------------------------------------------------------------
  Columns:
  
    - id                             CHARACTER VARYING    NOT NULL [PK]
    - user_id                        INTEGER              NOT NULL
    - project_key                    CHARACTER VARYING    NULL    
    - insight_type                   CHARACTER VARYING    NOT NULL
    - title                          CHARACTER VARYING    NOT NULL
    - description                    TEXT                 NOT NULL
    - severity                       CHARACTER VARYING    NOT NULL
    - metadata_json                  JSON                 NULL    
    - created_at                     TIMESTAMP WITHOUT TIME ZONE NOT NULL
    - dismissed_at                   TIMESTAMP WITHOUT TIME ZONE NULL    
    - acted_on_at                    TIMESTAMP WITHOUT TIME ZONE NULL    
    - action_taken                   CHARACTER VARYING    NULL    
    - delivered_via_slack            TIMESTAMP WITHOUT TIME ZONE NULL    
    - delivered_via_email            TIMESTAMP WITHOUT TIME ZONE NULL    
    - last_escalated_at              TIMESTAMP WITHOUT TIME ZONE NULL    
    - escalation_count               INTEGER              NOT NULL
    - escalation_level               INTEGER              NOT NULL

  Foreign Keys:
    - user_id → users(id)

TABLE: processed_meetings
--------------------------------------------------------------------------------
  Columns:
  
    - id                             CHARACTER VARYING    NOT NULL [PK]
    - title                          CHARACTER VARYING    NOT NULL
    - fireflies_id                   CHARACTER VARYING    NULL    
    - date                           TIMESTAMP WITHOUT TIME ZONE NULL    
    - duration                       INTEGER              NULL    
    - summary                        TEXT                 NULL    
    - action_items                   TEXT                 NULL    
    - created_at                     TIMESTAMP WITHOUT TIME ZONE NULL    
    - updated_at                     TIMESTAMP WITHOUT TIME ZONE NULL    
    - key_decisions                  TEXT                 NULL    
    - blockers                       TEXT                 NULL    
    - analyzed_at                    TIMESTAMP WITHOUT TIME ZONE NULL    
    - processed_at                   TIMESTAMP WITHOUT TIME ZONE NULL    
    - tickets_created                TEXT                 NULL    
    - todos_created                  TEXT                 NULL    
    - success                        BOOLEAN              NULL    
    - executive_summary              TEXT                 NULL    
    - outcomes                       TEXT                 NULL    
    - blockers_and_constraints       TEXT                 NULL    
    - timeline_and_milestones        TEXT                 NULL    
    - key_discussions                TEXT                 NULL    
    - topics                         TEXT                 NULL    
    - ai_provider                    CHARACTER VARYING    NULL    
    - ai_model                       CHARACTER VARYING    NULL    

TABLE: project_changes
--------------------------------------------------------------------------------
  Columns:
  
    - id                             CHARACTER VARYING    NOT NULL [PK]
    - project_key                    CHARACTER VARYING    NOT NULL
    - change_type                    CHARACTER VARYING    NOT NULL
    - ticket_key                     CHARACTER VARYING    NOT NULL
    - ticket_title                   CHARACTER VARYING    NULL    
    - old_value                      CHARACTER VARYING    NULL    
    - new_value                      CHARACTER VARYING    NULL    
    - assignee                       CHARACTER VARYING    NULL    
    - reporter                       CHARACTER VARYING    NULL    
    - priority                       CHARACTER VARYING    NULL    
    - status                         CHARACTER VARYING    NULL    
    - change_timestamp               TIMESTAMP WITHOUT TIME ZONE NOT NULL
    - detected_at                    TIMESTAMP WITHOUT TIME ZONE NULL    
    - change_details                 JSON                 NULL    

TABLE: project_characteristics
--------------------------------------------------------------------------------
  Columns:
  
    - id                             INTEGER              NOT NULL [PK]
    - project_key                    CHARACTER VARYING    NOT NULL
    - be_integrations                INTEGER              NOT NULL
    - custom_theme                   INTEGER              NOT NULL
    - custom_designs                 INTEGER              NOT NULL
    - ux_research                    INTEGER              NOT NULL
    - extensive_customizations       INTEGER              NOT NULL
    - project_oversight              INTEGER              NOT NULL
    - created_at                     TIMESTAMP WITHOUT TIME ZONE NOT NULL
    - updated_at                     TIMESTAMP WITHOUT TIME ZONE NOT NULL

  Foreign Keys:
    - project_key → projects(key)

TABLE: project_digest_cache
--------------------------------------------------------------------------------
  Columns:
  
    - id                             INTEGER              NOT NULL [PK]
    - project_key                    CHARACTER VARYING    NOT NULL
    - days                           INTEGER              NOT NULL
    - digest_data                    TEXT                 NOT NULL
    - created_at                     TIMESTAMP WITHOUT TIME ZONE NOT NULL
    - include_context                BOOLEAN              NOT NULL

TABLE: project_keywords
--------------------------------------------------------------------------------
  Columns:
  
    - id                             INTEGER              NOT NULL [PK]
    - project_key                    CHARACTER VARYING    NOT NULL
    - keyword                        CHARACTER VARYING    NOT NULL
    - created_at                     TIMESTAMP WITHOUT TIME ZONE NOT NULL

  Foreign Keys:
    - project_key → projects(key)

TABLE: project_monthly_forecast
--------------------------------------------------------------------------------
  Columns:
  
    - id                             INTEGER              NOT NULL [PK]
    - project_key                    CHARACTER VARYING    NOT NULL
    - month_year                     DATE                 NOT NULL
    - forecasted_hours               NUMERIC              NULL    
    - actual_monthly_hours           NUMERIC              NULL    
    - created_at                     TIMESTAMP WITHOUT TIME ZONE NULL    
    - updated_at                     TIMESTAMP WITHOUT TIME ZONE NULL    

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
    - jira_project_keys              TEXT                 NULL    
    - created_at                     TIMESTAMP WITHOUT TIME ZONE NULL    
    - updated_at                     TIMESTAMP WITHOUT TIME ZONE NULL    
    - internal_slack_channels        TEXT                 NULL    

TABLE: projects
--------------------------------------------------------------------------------
  Columns:
  
    - key                            CHARACTER VARYING    NOT NULL [PK]
    - name                           CHARACTER VARYING    NOT NULL
    - is_active                      BOOLEAN              NOT NULL
    - created_at                     TIMESTAMP WITHOUT TIME ZONE NOT NULL
    - updated_at                     TIMESTAMP WITHOUT TIME ZONE NOT NULL
    - project_work_type              CHARACTER VARYING    NULL    
    - total_hours                    NUMERIC              NULL    
    - retainer_hours                 NUMERIC              NULL    
    - weekly_meeting_day             TEXT                 NULL    
    - send_meeting_emails            BOOLEAN              NULL    
    - description                    TEXT                 NULL    
    - start_date                     DATE                 NULL    
    - launch_date                    DATE                 NULL    
    - cumulative_hours               NUMERIC              NULL    

TABLE: query_expansions
--------------------------------------------------------------------------------
  Columns:
  
    - id                             INTEGER              NOT NULL [PK]
    - original_term                  CHARACTER VARYING    NOT NULL
    - expanded_term                  CHARACTER VARYING    NOT NULL
    - expansion_type                 CHARACTER VARYING    NOT NULL
    - confidence_score               DOUBLE PRECISION     NOT NULL
    - usage_count                    INTEGER              NOT NULL
    - success_count                  INTEGER              NOT NULL
    - project_key                    CHARACTER VARYING    NULL    
    - domain                         CHARACTER VARYING    NULL    
    - is_active                      BOOLEAN              NOT NULL
    - created_at                     TIMESTAMP WITH TIME ZONE NOT NULL
    - updated_at                     TIMESTAMP WITH TIME ZONE NOT NULL

TABLE: search_feedback
--------------------------------------------------------------------------------
  Columns:
  
    - id                             INTEGER              NOT NULL [PK]
    - user_id                        INTEGER              NULL    
    - slack_user_id                  CHARACTER VARYING    NULL    
    - query                          TEXT                 NOT NULL
    - rating                         INTEGER              NOT NULL
    - feedback_text                  TEXT                 NULL    
    - result_count                   INTEGER              NULL    
    - result_sources                 JSON                 NULL    
    - top_result_source              CHARACTER VARYING    NULL    
    - detail_level                   CHARACTER VARYING    NULL    
    - project_key                    CHARACTER VARYING    NULL    
    - response_time_ms               INTEGER              NULL    
    - summary_length                 INTEGER              NULL    
    - created_at                     TIMESTAMP WITH TIME ZONE NOT NULL

TABLE: slack_sessions
--------------------------------------------------------------------------------
  Columns:
  
    - session_id                     CHARACTER VARYING    NOT NULL [PK]
    - data                           BYTEA                NOT NULL
    - created_at                     TIMESTAMP WITHOUT TIME ZONE NOT NULL
    - expires_at                     TIMESTAMP WITHOUT TIME ZONE NOT NULL

TABLE: standard_epic_templates
--------------------------------------------------------------------------------
  Columns:
  
    - id                             INTEGER              NOT NULL [PK]
    - name                           CHARACTER VARYING    NOT NULL
    - description                    TEXT                 NULL    
    - typical_hours_min              INTEGER              NULL    
    - typical_hours_max              INTEGER              NULL    
    - order                          INTEGER              NOT NULL
    - created_at                     TIMESTAMP WITHOUT TIME ZONE NOT NULL
    - updated_at                     TIMESTAMP WITHOUT TIME ZONE NOT NULL

TABLE: system_settings
--------------------------------------------------------------------------------
  Columns:
  
    - id                             INTEGER              NOT NULL [PK]
    - ai_provider                    CHARACTER VARYING    NOT NULL
    - ai_model                       CHARACTER VARYING    NULL    
    - ai_temperature                 DOUBLE PRECISION     NOT NULL
    - ai_max_tokens                  INTEGER              NOT NULL
    - openai_api_key_encrypted       TEXT                 NULL    
    - anthropic_api_key_encrypted    TEXT                 NULL    
    - google_api_key_encrypted       TEXT                 NULL    
    - updated_at                     TIMESTAMP WITHOUT TIME ZONE NULL    
    - updated_by_user_id             INTEGER              NULL    
    - epic_auto_update_enabled       BOOLEAN              NOT NULL

TABLE: time_tracking_compliance
--------------------------------------------------------------------------------
  Columns:
  
    - user_account_id                CHARACTER VARYING    NOT NULL [PK]
    - week_start_date                DATE                 NOT NULL [PK]
    - hours_logged                   DOUBLE PRECISION     NOT NULL
    - is_compliant                   BOOLEAN              NOT NULL
    - notification_sent              BOOLEAN              NOT NULL
    - pm_notified                    BOOLEAN              NOT NULL
    - created_at                     TIMESTAMP WITH TIME ZONE NOT NULL

TABLE: todo_items
--------------------------------------------------------------------------------
  Columns:
  
    - id                             CHARACTER VARYING    NOT NULL [PK]
    - title                          CHARACTER VARYING    NOT NULL
    - description                    TEXT                 NULL    
    - assignee                       CHARACTER VARYING    NULL    
    - priority                       CHARACTER VARYING    NULL    
    - status                         CHARACTER VARYING    NULL    
    - project_key                    CHARACTER VARYING    NULL    
    - user_id                        INTEGER              NULL    
    - created_at                     TIMESTAMP WITHOUT TIME ZONE NULL    
    - updated_at                     TIMESTAMP WITHOUT TIME ZONE NULL    
    - due_date                       TIMESTAMP WITHOUT TIME ZONE NULL    
    - ticket_key                     CHARACTER VARYING    NULL    
    - source_meeting_id              CHARACTER VARYING    NULL    
    - source                         CHARACTER VARYING    NULL    

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
    - daily_brief_time               CHARACTER VARYING    NOT NULL
    - timezone                       CHARACTER VARYING    NOT NULL

  Foreign Keys:
    - user_id → users(id)

TABLE: user_preferences
--------------------------------------------------------------------------------
  Columns:
  
    - id                             CHARACTER VARYING    NOT NULL [PK]
    - email                          CHARACTER VARYING    NOT NULL
    - slack_username                 CHARACTER VARYING    NULL    
    - notification_cadence           CHARACTER VARYING    NULL    
    - selected_projects              JSON                 NULL    
    - created_at                     TIMESTAMP WITHOUT TIME ZONE NULL    
    - updated_at                     TIMESTAMP WITHOUT TIME ZONE NULL    
    - last_notification_sent         TIMESTAMP WITHOUT TIME ZONE NULL    

TABLE: user_teams
--------------------------------------------------------------------------------
  Columns:
  
    - account_id                     CHARACTER VARYING    NOT NULL [PK]
    - display_name                   CHARACTER VARYING    NULL    
    - team                           CHARACTER VARYING    NOT NULL
    - updated_at                     TIMESTAMP WITH TIME ZONE NULL    

TABLE: user_watched_projects
--------------------------------------------------------------------------------
  Columns:
  
    - id                             INTEGER              NOT NULL [PK]
    - user_id                        INTEGER              NOT NULL
    - project_key                    CHARACTER VARYING    NOT NULL
    - created_at                     TIMESTAMP WITHOUT TIME ZONE NULL    

  Foreign Keys:
    - user_id → users(id)

TABLE: users
--------------------------------------------------------------------------------
  Columns:
  
    - id                             INTEGER              NOT NULL [PK]
    - email                          CHARACTER VARYING    NOT NULL
    - name                           CHARACTER VARYING    NOT NULL
    - google_id                      CHARACTER VARYING    NOT NULL
    - role                           USER-DEFINED         NOT NULL
    - created_at                     TIMESTAMP WITHOUT TIME ZONE NULL    
    - updated_at                     TIMESTAMP WITHOUT TIME ZONE NULL    
    - last_login                     TIMESTAMP WITHOUT TIME ZONE NULL    
    - is_active                      BOOLEAN              NULL    
    - fireflies_api_key_encrypted    TEXT                 NULL    
    - google_oauth_token_encrypted   TEXT                 NULL    
    - notion_api_key_encrypted       TEXT                 NULL    
    - google_credentials_updated_at  TIMESTAMP WITHOUT TIME ZONE NULL    
    - notion_credentials_updated_at  TIMESTAMP WITHOUT TIME ZONE NULL    
    - slack_user_token_encrypted     TEXT                 NULL    
    - slack_credentials_updated_at   TIMESTAMP WITHOUT TIME ZONE NULL    
    - slack_user_id                  CHARACTER VARYING    NULL    
    - notify_daily_todo_digest       BOOLEAN              NOT NULL
    - notify_project_hours_forecast  BOOLEAN              NOT NULL
    - jira_account_id                CHARACTER VARYING    NULL    
    - team                           CHARACTER VARYING    NULL    
    - weekly_hours_minimum           DOUBLE PRECISION     NOT NULL
    - project_team                   CHARACTER VARYING    NULL    

TABLE: vector-sync-status
--------------------------------------------------------------------------------
  Columns:
  
    - source                         TEXT                 NOT NULL [PK]
    - last_sync                      TEXT                 NOT NULL
    - created_at                     TIMESTAMP WITHOUT TIME ZONE NULL    
    - updated_at                     TIMESTAMP WITHOUT TIME ZONE NULL    

