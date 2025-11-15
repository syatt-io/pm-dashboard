/**
 * API client for epic budget management endpoints.
 * Handles AI-powered forecast import and placeholder epic management.
 */

export interface ForecastEpic {
  epic: string;
  total_hours: number;
  percentage: number;
  reasoning: string;
}

export interface MatchedEpic {
  epic_key: string;
  epic_summary: string;
  allocated_hours: number;
  reasoning: string;
  confidence: number;
}

export interface EpicMapping {
  forecast_epic: string;
  forecast_hours: number;
  matched_epics: MatchedEpic[];
}

export interface PreviewImportResponse {
  mappings: EpicMapping[];
  unmapped_forecasts: string[];
  unmatched_existing: string[];
  overall_confidence: number;
  will_update: number;
  will_skip: number;
  will_create_placeholders: number;
  existing_epics_count: number;
  error?: string;
}

export interface ImportMapping {
  forecast_epic: string;
  forecast_hours: number;
  epic_allocations: Record<string, number>; // { "SUBS-123": 150, "SUBS-124": 95 }
}

export interface CreatePlaceholder {
  forecast_epic: string;
  hours: number;
}

export interface ImportFromForecastRequest {
  project_key: string;
  mappings: ImportMapping[];
  create_placeholders: CreatePlaceholder[];
}

export interface ImportDetail {
  epic_key: string;
  action: 'updated' | 'skipped' | 'created';
  hours?: number;
  previous_estimate?: number;
  forecast_source?: string;
  epic_summary?: string;
  is_placeholder?: boolean;
  reason?: string;
}

export interface ImportFromForecastResponse {
  success: boolean;
  summary: {
    updated: number;
    skipped: number;
    created_placeholders: number;
    total_hours_imported: number;
  };
  details: ImportDetail[];
  warnings: string[];
  error?: string;
}

export interface LinkToJiraRequest {
  jira_epic_key: string;
  jira_epic_summary?: string;
}

export interface LinkToJiraResponse {
  success: boolean;
  epic_budget_id: number;
  old_epic_key: string;
  new_epic_key: string;
  is_placeholder: boolean;
  epic_budget: any;
  error?: string;
}

/**
 * Epic Budgets API client
 */
export const epicBudgetsApi = {
  /**
   * Preview AI-suggested mappings without saving to database.
   * Called when user selects a project in the import dialog.
   */
  previewImport: async (
    projectKey: string,
    forecastEpics: ForecastEpic[]
  ): Promise<PreviewImportResponse> => {
    const response = await fetch('/api/epic-budgets/preview-import', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        project_key: projectKey,
        forecast_epics: forecastEpics,
      }),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'Failed to preview import');
    }

    return response.json();
  },

  /**
   * Execute import of forecast epics to project epic budgets.
   * Updates existing epics and creates placeholders as specified.
   */
  importFromForecast: async (
    data: ImportFromForecastRequest
  ): Promise<ImportFromForecastResponse> => {
    const response = await fetch('/api/epic-budgets/import-from-forecast', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'Failed to import forecast');
    }

    return response.json();
  },

  /**
   * Convert a placeholder epic budget to a real Jira epic.
   * Links SUBS-FORECAST-1 → SUBS-150.
   */
  linkPlaceholderToJira: async (
    epicBudgetId: number,
    data: LinkToJiraRequest
  ): Promise<LinkToJiraResponse> => {
    const response = await fetch(
      `/api/epic-budgets/${epicBudgetId}/link-to-jira`,
      {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(data),
      }
    );

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'Failed to link placeholder to Jira epic');
    }

    return response.json();
  },
};
