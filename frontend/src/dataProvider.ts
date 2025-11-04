import { fetchUtils, DataProvider, GetListParams, GetOneParams, CreateParams, UpdateParams, DeleteParams } from 'react-admin';

const API_URL = process.env.REACT_APP_API_URL
  ? `${process.env.REACT_APP_API_URL}/api`
  : (window.location.hostname === 'localhost'
    ? 'http://localhost:4000/api'
    : 'https://agent-pm-tsbbb.ondigitalocean.app/api');

// CSRF token storage (in-memory for security)
let csrfToken: string | null = null;

// Fetch CSRF token from backend
const fetchCsrfToken = async (): Promise<string> => {
    if (csrfToken) {
        return csrfToken;
    }

    try {
        const response = await fetch(`${API_URL}/csrf-token`, {
            credentials: 'include', // Include cookies for session
        });

        if (response.ok) {
            const data = await response.json();
            csrfToken = data.csrf_token;
            return csrfToken as string;
        }
    } catch (error) {
        console.error('Failed to fetch CSRF token:', error);
    }

    return '';
};

// Export for use in other components
export { fetchCsrfToken };

const httpClient = async (url: string, options: fetchUtils.Options = {}) => {
    // Add auth token if available
    const token = localStorage.getItem('auth_token');
    if (!options.headers) {
        options.headers = new Headers();
    } else if (!(options.headers instanceof Headers)) {
        options.headers = new Headers(options.headers);
    }

    if (token) {
        options.headers.set('Authorization', `Bearer ${token}`);
    }

    // Add CSRF token for state-changing operations
    const method = options.method || 'GET';
    if (['POST', 'PUT', 'DELETE', 'PATCH'].includes(method.toUpperCase())) {
        const csrf = await fetchCsrfToken();
        if (csrf) {
            options.headers.set('X-CSRF-Token', csrf);
        }
    }

    // Don't add a catch here - let the individual methods handle errors
    return fetchUtils.fetchJson(url, options);
};

export const dataProvider: DataProvider = {
    getList: async (resource: string, params: GetListParams) => {
        const { page, perPage } = params.pagination;
        const { field, order } = params.sort;
        const { filter } = params;

        let url = '';
        const queryParams = new URLSearchParams();

        // Add pagination params
        if (page) queryParams.append('page', page.toString());
        if (perPage) queryParams.append('per_page', perPage.toString());

        // Add sort params
        if (field) queryParams.append('sort_field', field);
        if (order) queryParams.append('sort_order', order);

        // Helper function to get watched projects from API
        const getWatchedProjects = async () => {
            try {
                const token = localStorage.getItem('auth_token');

                if (!token) {
                    return [];
                }

                const url = `${API_URL}/watched-projects`;

                const response = await fetch(url, {
                    headers: {
                        'Authorization': `Bearer ${token}`,
                        'Content-Type': 'application/json',
                    },
                });

                if (response.ok) {
                    const data = await response.json();
                    return data.watched_projects || [];
                }
                // Silently handle errors - user may not be logged in yet or have no watched projects
            } catch (error) {
                // Silently handle errors to prevent infinite retry loop
            }
            return [];
        };

        // Add filter params
        if (filter) {
            if (filter.dateRange) queryParams.append('date_range', filter.dateRange);
            if (filter.watchedProjects) {
                const watchedProjects = await getWatchedProjects();
                if (watchedProjects.length > 0) {
                    queryParams.append('projects', watchedProjects.join(','));
                }
            }
            // Pass through explicit projects filter (for project-specific views)
            if (filter.projects) {
                queryParams.append('projects', filter.projects);
            }
            // Pass through explicit resource_context if provided
            if (filter.resource_context) {
                queryParams.append('resource_context', filter.resource_context);
            }
        }

        switch (resource) {
            case 'meetings':
                url = `${API_URL}/meetings`;
                // Only set default context if not already specified in filter
                if (!filter?.resource_context) {
                    // Pass context to indicate this is for the Meetings tab (show ALL meetings)
                    queryParams.append('resource_context', 'meetings');
                }
                break;
            case 'analysis':
                url = `${API_URL}/meetings`;
                // Only set default context if not already specified in filter
                if (!filter?.resource_context) {
                    // Pass context to indicate this is for the Analysis tab (filter by projects)
                    queryParams.append('resource_context', 'analysis');
                }
                // For analysis, always filter by watched projects unless explicit projects provided
                if (!filter?.projects) {
                    const watchedProjectsForAnalysis = await getWatchedProjects();
                    if (watchedProjectsForAnalysis.length > 0) {
                        queryParams.set('projects', watchedProjectsForAnalysis.join(','));
                    }
                }
                // No fallback - if user has no watched projects, show nothing
                break;
            case 'todos':
                url = `${API_URL}/todos`;
                break;
            case 'projects':
                url = `${API_URL}/jira/projects`;
                break;
            case 'jira_projects':
                url = `${API_URL}/jira/projects`;
                break;
            case 'learnings':
                url = `${API_URL}/learnings`;
                // Add filter params for learnings
                if (filter.category) queryParams.append('category', filter.category);
                if (filter.q) queryParams.append('q', filter.q);
                // Add pagination for learnings
                queryParams.append('limit', perPage.toString());
                queryParams.append('offset', ((page - 1) * perPage).toString());
                break;
            case 'feedback':
                url = `${API_URL}/feedback`;
                // Add filter params for feedback
                if (filter.status) queryParams.append('status', filter.status);
                if (filter.recipient) queryParams.append('recipient', filter.recipient);
                break;
            case 'settings':
                // Settings is not really a list, but React Admin expects list data
                // We'll return a single item representing user settings
                return Promise.resolve({
                    data: [{ id: 1, name: 'User Settings' }],
                    total: 1
                });
            default:
                return Promise.reject(new Error(`Unknown resource: ${resource}`));
        }

        // Append query parameters to URL
        const queryString = queryParams.toString();
        if (queryString) {
            url += `?${queryString}`;
        }

        return httpClient(url).then(({ json }) => {
            // Standard format: {data: [...], total: number}
            // Handle nested data from success_response wrapper: {success: true, data: {...}}
            let responseData = json.data;

            // If data is wrapped in success response with nested data.projects, unwrap it
            if (responseData && typeof responseData === 'object' && 'projects' in responseData) {
                responseData = responseData.projects;
            }

            // Ensure we have an array
            if (!Array.isArray(responseData)) {
                responseData = [];
            }

            // Special handling for analysis resource - transform all meetings
            if (resource === 'analysis' && responseData.length > 0) {
                responseData = responseData.map((meeting: any) => {
                    const meetingId = meeting.meeting_id || meeting.id;
                    return {
                        id: meetingId,
                        meeting_title: meeting.title || 'Untitled Meeting',
                        analyzed_at: meeting.analyzed_at || meeting.date,
                        action_items: meeting.action_items || [],
                        key_decisions: meeting.key_decisions || [],
                        blockers: meeting.blockers || [],
                        follow_ups: meeting.follow_ups || [],
                        summary: meeting.summary || (meeting.action_items && meeting.action_items.length > 0 ? 'Meeting analysis completed' : 'Not analyzed yet'),
                        meeting_id: meetingId,
                        title: meeting.title,
                        date: meeting.date,
                        confidence: meeting.confidence,
                        relevance_score: meeting.relevance_score,
                        action_items_count: meeting.action_items_count || 0,
                        ...meeting
                    };
                });
            }

            return {
                data: responseData.map((item: any, index: number) => ({
                    id: item.id || item.meeting_id || item.key || index,
                    ...item
                })),
                total: json.total || responseData.length,
            };
        }).catch(error => {
            // Re-throw error for react-admin to handle
            return Promise.reject(error);
        });
    },

    getOne: (resource: string, params: GetOneParams) => {
        let url = '';

        switch (resource) {
            case 'meetings':
                url = `${API_URL}/meetings/${params.id}`;
                break;
            case 'analysis':
                // For getOne analysis, bypass filtering and go directly to meetings endpoint
                // This ensures we can always find the meeting regardless of project filtering
                url = `${API_URL}/meetings/${params.id}`;
                break;
            case 'todos':
                url = `${API_URL}/todos/${params.id}`;
                break;
            case 'projects':
                url = `${API_URL}/jira/projects/${params.id}`;
                break;
            case 'jira_projects':
                url = `${API_URL}/jira/projects/${params.id}`;
                break;
            case 'learnings':
                url = `${API_URL}/learnings/${params.id}`;
                break;
            case 'feedback':
                url = `${API_URL}/feedback/${params.id}`;
                break;
            default:
                return Promise.reject(new Error(`Unknown resource: ${resource}`));
        }

        return httpClient(url).then(({ json }) => {
            if (resource === 'analysis') {
                // For analysis, transform the meeting data similarly to getList
                const meetingId = json.meeting_id || json.id || params.id;
                return {
                    data: {
                        id: meetingId,
                        meeting_title: json.title || 'Untitled Meeting',
                        analyzed_at: json.analyzed_at || json.date,
                        action_items: json.action_items || [],
                        key_decisions: json.key_decisions || [],
                        blockers: json.blockers || [],
                        follow_ups: json.follow_ups || [],
                        summary: json.summary || (json.action_items && json.action_items.length > 0 ? 'Meeting analysis completed' : 'Not analyzed yet'),
                        // Include all original meeting fields
                        meeting_id: meetingId,
                        title: json.title,
                        date: json.date,
                        confidence: json.confidence,
                        relevance_score: json.relevance_score,
                        action_items_count: json.action_items_count || 0,
                        ...json
                    }
                };
            }
            // Handle learnings response format
            if (resource === 'learnings' && json.data) {
                return {
                    data: { id: json.data.id || params.id, ...json.data },
                };
            }
            // Handle projects response format (wrapped in success_response)
            if ((resource === 'projects' || resource === 'jira_projects') && json.data) {
                return {
                    data: { ...json.data, id: json.data.key || json.data.id || params.id },
                };
            }
            return {
                data: { id: params.id, ...json },
            };
        }).catch(error => {
            return Promise.reject(error);
        });
    },

    getMany: (resource: string, params: { ids: any[] }) => {
        const queries = params.ids.map(id =>
            httpClient(`${API_URL}/${resource}/${id}`)
        );
        return Promise.all(queries).then(responses => ({
            data: responses.map(({ json }, index) => ({
                id: params.ids[index],
                ...json
            })),
        })).catch(error => {
            return Promise.reject(error);
        });
    },

    getManyReference: (resource: string, params: any) => {
        return dataProvider.getList(resource, {
            ...params,
            filter: {
                ...params.filter,
                [params.target]: params.id,
            },
        });
    },

    create: (resource: string, params: CreateParams) => {
        let url = '';
        let body = params.data;

        switch (resource) {
            case 'todos':
                url = `${API_URL}/todos`;
                break;
            case 'tickets':
                url = `${API_URL}/process`;
                break;
            case 'learnings':
                url = `${API_URL}/learnings`;
                break;
            case 'feedback':
                url = `${API_URL}/feedback`;
                break;
            default:
                return Promise.reject(new Error(`Create not supported for resource: ${resource}`));
        }

        return httpClient(url, {
            method: 'POST',
            body: JSON.stringify(body),
        }).then(({ json }) => {
            if (resource === 'learnings' && json.learning) {
                return {
                    data: { id: json.learning.id, ...json.learning },
                };
            }
            if (resource === 'feedback' && json.data) {
                return {
                    data: { id: json.data.id, ...json.data },
                };
            }
            return {
                data: { id: json.id || Date.now(), ...json },
            };
        }).catch(error => {
            return Promise.reject(error);
        });
    },

    update: (resource: string, params: UpdateParams) => {
        let url = '';

        switch (resource) {
            case 'todos':
                url = `${API_URL}/todos/${params.id}`;
                break;
            case 'projects':
            case 'jira_projects':
                url = `${API_URL}/jira/projects/${params.id}`;
                break;
            case 'learnings':
                url = `${API_URL}/learnings/${params.id}`;
                break;
            case 'feedback':
                url = `${API_URL}/feedback/${params.id}`;
                break;
            default:
                return Promise.reject(new Error(`Update not supported for resource: ${resource}`));
        }

        return httpClient(url, {
            method: 'PUT',
            body: JSON.stringify(params.data),
        }).then(({ json }) => {
            // Use server response if available, otherwise fallback to params.data
            const responseData = json.data || params.data;
            return {
                data: { ...responseData, id: responseData.key || responseData.id || params.id } as any,
            };
        }).catch(error => {
            console.error('[dataProvider] Error:', error);
            return Promise.reject(error);
        });
    },

    updateMany: (resource: string, params: { ids: any[]; data: any }) => {
        const queries = params.ids.map(id =>
            httpClient(`${API_URL}/${resource}/${id}`, {
                method: 'PUT',
                body: JSON.stringify(params.data),
            })
        );
        return Promise.all(queries).then(responses => ({
            data: params.ids,
        })).catch(error => {
            return Promise.reject(error);
        });
    },

    delete: (resource: string, params: DeleteParams) => {
        let url = '';

        switch (resource) {
            case 'todos':
                url = `${API_URL}/todos/${params.id}`;
                break;
            case 'learnings':
                url = `${API_URL}/learnings/${params.id}`;
                break;
            case 'feedback':
                url = `${API_URL}/feedback/${params.id}`;
                break;
            default:
                return Promise.reject(new Error(`Delete not supported for resource: ${resource}`));
        }

        return httpClient(url, {
            method: 'DELETE',
        }).then(() => ({
            data: params.previousData,
        })).catch(error => {
            return Promise.reject(error);
        });
    },

    deleteMany: (resource: string, params: { ids: any[] }) => {
        const queries = params.ids.map(id =>
            httpClient(`${API_URL}/${resource}/${id}`, {
                method: 'DELETE',
            })
        );
        return Promise.all(queries).then(() => ({
            data: params.ids,
        })).catch(error => {
            return Promise.reject(error);
        });
    },
};