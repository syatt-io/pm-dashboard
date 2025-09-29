// @ts-nocheck
import { fetchUtils } from 'react-admin';

const API_URL = process.env.REACT_APP_API_URL
  ? `${process.env.REACT_APP_API_URL}/api`
  : (window.location.hostname === 'localhost'
    ? 'http://localhost:4000/api'
    : 'https://agent-pm-tsbbb.ondigitalocean.app/api');

const httpClient = (url, options = {}) => {
    // Add auth token if available
    const token = localStorage.getItem('auth_token');
    if (token) {
        if (!options.headers) {
            options.headers = new Headers();
        } else if (!(options.headers instanceof Headers)) {
            options.headers = new Headers(options.headers);
        }
        options.headers.set('Authorization', `Bearer ${token}`);
    }

    // Don't add a catch here - let the individual methods handle errors
    return fetchUtils.fetchJson(url, options);
};

export const dataProvider: any = {
    getList: async (resource, params) => {
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
                if (!token) return [];

                const response = await fetch(`${API_URL}/watched-projects`, {
                    headers: {
                        'Authorization': `Bearer ${token}`,
                        'Content-Type': 'application/json',
                    },
                });

                if (response.ok) {
                    const data = await response.json();
                    return data.watched_projects || [];
                }
            } catch (error) {
                console.error('Error fetching watched projects:', error);
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
        }

        switch (resource) {
            case 'meetings':
                url = `${API_URL}/meetings`;
                // Pass context to indicate this is for the Meetings tab (show ALL meetings)
                queryParams.append('resource_context', 'meetings');
                break;
            case 'analysis':
                url = `${API_URL}/meetings`;
                // Pass context to indicate this is for the Analysis tab (filter by projects)
                queryParams.append('resource_context', 'analysis');
                // For analysis, always filter by watched projects
                const watchedProjectsForAnalysis = await getWatchedProjects();
                if (watchedProjectsForAnalysis.length > 0) {
                    queryParams.set('projects', watchedProjectsForAnalysis.join(','));
                } else {
                    // If no watched projects, set default projects to ensure we get some results
                    queryParams.set('projects', 'BEAU,RNWL,SUBS,IRIS');
                }
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
            // Debug logging for projects resource
            if (resource === 'projects') {
                console.log('Projects API response:', json);
                console.log('Projects array exists:', !!json.projects);
                console.log('Projects array length:', json.projects ? json.projects.length : 0);
            }

            // Handle the standard API response format with json.data
            if (json.data && Array.isArray(json.data)) {
                let data = json.data;

                // Special handling for analysis resource - transform all meetings
                if (resource === 'analysis') {
                    data = json.data.map((meeting: any) => {
                        // Ensure consistent ID handling
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
                            // Include all original meeting fields with consistent ID
                            meeting_id: meetingId,
                            title: meeting.title,
                            date: meeting.date,
                            confidence: meeting.confidence,
                            relevance_score: meeting.relevance_score,
                            action_items_count: meeting.action_items_count || 0,
                            ...meeting
                        };
                    });
                    console.log('Analysis data transformed:', data.length, 'records');
                }

                return {
                    data: data.map((item: any, index: number) => ({
                        id: item.id || item.meeting_id || item.key || index,
                        ...item
                    })),
                    total: json.total || data.length,
                };
            }

            // Fallback for legacy formats
            if (resource === 'meetings' && json.dashboard?.project_meetings) {
                const meetings = Object.values(json.dashboard.project_meetings).flat();
                return {
                    data: meetings.map((meeting: any, index: number) => ({
                        id: meeting.meeting_id || index,
                        ...meeting
                    })),
                    total: meetings.length,
                };
            } else if (resource === 'todos' && json.todos) {
                return {
                    data: json.todos.map((todo: any) => ({
                        id: todo.id,
                        ...todo
                    })),
                    total: json.todos.length,
                };
            } else if ((resource === 'projects' || resource === 'jira_projects') && json.projects) {
                return {
                    data: json.projects.map((project: any) => ({
                        id: project.key,
                        ...project
                    })),
                    total: json.projects.length,
                };
            } else if (resource === 'learnings' && json.learnings) {
                return {
                    data: json.learnings.map((learning: any) => ({
                        id: learning.id,
                        ...learning
                    })),
                    total: json.total || json.learnings.length,
                };
            }

            return {
                data: Array.isArray(json) ? json : [],
                total: Array.isArray(json) ? json.length : 0,
            };
        }).catch(error => {
            console.error(`Error fetching ${resource}:`, error);
            return Promise.reject(error);
        });
    },

    getOne: (resource, params) => {
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
            case 'learnings':
                url = `${API_URL}/learnings/${params.id}`;
                break;
            default:
                return Promise.reject(new Error(`Unknown resource: ${resource}`));
        }

        return httpClient(url).then(({ json }) => {
            if (resource === 'analysis') {
                // For analysis, transform the meeting data similarly to getList
                console.log('getOne analysis - Response:', json);
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
            return {
                data: { id: params.id, ...json },
            };
        }).catch(error => {
            console.error(`Error fetching single ${resource}:`, error);
            return Promise.reject(error);
        });
    },

    getMany: (resource, params) => {
        const queries = params.ids.map(id =>
            httpClient(`${API_URL}/${resource}/${id}`)
        );
        return Promise.all(queries).then(responses => ({
            data: responses.map(({ json }, index) => ({
                id: params.ids[index],
                ...json
            })),
        })).catch(error => {
            console.error('Error in getMany:', error);
            return Promise.reject(error);
        });
    },

    getManyReference: (resource, params) => {
        return dataProvider.getList(resource, {
            ...params,
            filter: {
                ...params.filter,
                [params.target]: params.id,
            },
        });
    },

    create: (resource, params) => {
        let url = '';
        let body = params.data;

        switch (resource) {
            case 'todos':
                url = `${API_URL}/todos`;
                console.log('Creating TODO with data:', body);
                break;
            case 'tickets':
                url = `${API_URL}/process`;
                break;
            case 'learnings':
                url = `${API_URL}/learnings`;
                break;
            default:
                return Promise.reject(new Error(`Create not supported for resource: ${resource}`));
        }

        return httpClient(url, {
            method: 'POST',
            body: JSON.stringify(body),
        }).then(({ json }) => {
            if (resource === 'todos') {
                console.log('TODO create response:', json);
            }
            if (resource === 'learnings' && json.learning) {
                return {
                    data: { id: json.learning.id, ...json.learning },
                };
            }
            return {
                data: { id: json.id || Date.now(), ...json },
            };
        }).catch(error => {
            console.error(`Error creating ${resource}:`, error);
            return Promise.reject(error);
        });
    },

    update: (resource, params) => {
        let url = '';

        switch (resource) {
            case 'todos':
                url = `${API_URL}/todos/${params.id}`;
                console.log('Updating TODO with data:', params.data);
                break;
            case 'jira_projects':
                url = `${API_URL}/jira/projects/${params.id}`;
                break;
            case 'learnings':
                url = `${API_URL}/learnings/${params.id}`;
                break;
            default:
                return Promise.reject(new Error(`Update not supported for resource: ${resource}`));
        }

        return httpClient(url, {
            method: 'PUT',
            body: JSON.stringify(params.data),
        }).then(({ json }) => {
            if (resource === 'todos') {
                console.log('TODO update response:', json);
            }
            return {
                data: { ...params.data, id: params.id } as any,
            };
        }).catch(error => {
            console.error(`Error updating ${resource}:`, error);
            return Promise.reject(error);
        });
    },

    updateMany: (resource, params) => {
        const queries = params.ids.map(id =>
            httpClient(`${API_URL}/${resource}/${id}`, {
                method: 'PUT',
                body: JSON.stringify(params.data),
            })
        );
        return Promise.all(queries).then(responses => ({
            data: params.ids,
        })).catch(error => {
            console.error('Error in updateMany:', error);
            return Promise.reject(error);
        });
    },

    delete: (resource, params) => {
        let url = '';

        switch (resource) {
            case 'todos':
                url = `${API_URL}/todos/${params.id}`;
                break;
            case 'learnings':
                url = `${API_URL}/learnings/${params.id}`;
                break;
            default:
                return Promise.reject(new Error(`Delete not supported for resource: ${resource}`));
        }

        return httpClient(url, {
            method: 'DELETE',
        }).then(() => ({
            data: params.previousData,
        })).catch(error => {
            console.error(`Error deleting ${resource}:`, error);
            return Promise.reject(error);
        });
    },

    deleteMany: (resource, params) => {
        const queries = params.ids.map(id =>
            httpClient(`${API_URL}/${resource}/${id}`, {
                method: 'DELETE',
            })
        );
        return Promise.all(queries).then(() => ({
            data: params.ids,
        })).catch(error => {
            console.error('Error in deleteMany:', error);
            return Promise.reject(error);
        });
    },
};