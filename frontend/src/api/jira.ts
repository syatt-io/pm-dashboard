/**
 * API client for Jira metadata endpoints.
 * Handles fetching issue types, projects, users, and other Jira configuration.
 */

import API_BASE_URL from '../config';

export interface JiraIssueType {
  id: string;
  name: string;
  description?: string;
  iconUrl?: string;
  subtask?: boolean;
}

export interface JiraIssueTypesResponse {
  success: boolean;
  issue_types?: JiraIssueType[];
  issueTypes?: JiraIssueType[];
  data?: {
    issue_types?: JiraIssueType[];
    issueTypes?: JiraIssueType[];
  };
}

/**
 * Jira API client
 */
export const jiraApi = {
  /**
   * Fetch available issue types for a Jira project.
   * If projectKey is not provided, returns all issue types from Jira.
   *
   * @param projectKey - Optional project key to filter issue types by project
   * @returns Array of issue types with id and name
   */
  fetchIssueTypes: async (projectKey?: string): Promise<JiraIssueType[]> => {
    try {
      const url = projectKey
        ? `${API_BASE_URL}/api/jira/issue-types?project=${projectKey}`
        : `${API_BASE_URL}/api/jira/issue-types`;

      const response = await fetch(url);

      if (!response.ok) {
        console.error(
          '[ERROR] Issue types API failed:',
          response.status,
          response.statusText
        );
        throw new Error(`Failed to fetch issue types: ${response.statusText}`);
      }

      const data: JiraIssueTypesResponse = await response.json();

      // Handle multiple response formats for backwards compatibility
      const types =
        data.success
          ? (data.issue_types ||
             data.issueTypes ||
             data.data?.issue_types ||
             data.data?.issueTypes ||
             [])
          : (data.data?.issue_types || data.data?.issueTypes || []);

      return types;
    } catch (error) {
      console.error('[ERROR] Failed to load issue types:', error);
      throw error;
    }
  },
};
