/**
 * Tests for the React Admin data provider.
 * These tests verify the standardized API response format handling.
 */

import { dataProvider } from './dataProvider';
import { fetchUtils } from 'react-admin';

// Mock fetchJson
jest.mock('react-admin', () => ({
    ...jest.requireActual('react-admin'),
    fetchUtils: {
        fetchJson: jest.fn(),
    },
}));

const mockFetchJson = fetchUtils.fetchJson as jest.MockedFunction<typeof fetchUtils.fetchJson>;

describe('dataProvider', () => {
    beforeEach(() => {
        jest.clearAllMocks();
        localStorage.clear();
    });

    describe('getList', () => {
        it('should fetch and return standardized meeting data', async () => {
            const mockResponse = {
                json: {
                    data: [
                        { id: 1, title: 'Meeting 1', date: '2025-09-30' },
                        { id: 2, title: 'Meeting 2', date: '2025-09-29' }
                    ],
                    total: 2
                },
                status: 200,
                headers: new Headers(),
                body: ''
            };

            mockFetchJson.mockResolvedValueOnce(mockResponse);

            const result = await dataProvider.getList('meetings', {
                pagination: { page: 1, perPage: 10 },
                sort: { field: 'date', order: 'DESC' },
                filter: {}
            });

            expect(result.data).toHaveLength(2);
            expect(result.total).toBe(2);
            expect(result.data[0].id).toBe(1);
        });

        it('should handle projects with nested data.projects structure', async () => {
            const mockResponse = {
                json: {
                    success: true,
                    data: {
                        projects: [
                            { key: 'TEST', name: 'Test Project' },
                            { key: 'DEMO', name: 'Demo Project' }
                        ]
                    },
                    total: 2
                },
                status: 200,
                headers: new Headers(),
                body: ''
            };

            mockFetchJson.mockResolvedValueOnce(mockResponse);

            const result = await dataProvider.getList('jira_projects', {
                pagination: { page: 1, perPage: 10 },
                sort: { field: 'name', order: 'ASC' },
                filter: {}
            });

            expect(result.data).toHaveLength(2);
            expect(result.data[0].key).toBe('TEST');
            expect(result.data[0].id).toBe('TEST');
        });

        it('should handle empty data array', async () => {
            const mockResponse = {
                json: { data: [], total: 0 },
                status: 200,
                headers: new Headers(),
                body: ''
            };

            mockFetchJson.mockResolvedValueOnce(mockResponse);

            const result = await dataProvider.getList('learnings', {
                pagination: { page: 1, perPage: 10 },
                sort: { field: 'created_at', order: 'DESC' },
                filter: {}
            });

            expect(result.data).toEqual([]);
            expect(result.total).toBe(0);
        });

        it('should transform analysis resource with action items', async () => {
            // Mock watched projects API call
            global.fetch = jest.fn()
                .mockResolvedValueOnce({
                    ok: true,
                    json: async () => ({ watched_projects: ['TEST', 'DEMO'] })
                });

            const mockResponse = {
                json: {
                    data: [
                        {
                            id: 1,
                            title: 'Sprint Planning',
                            date: '2025-09-30',
                            action_items: [{ title: 'Review PR' }],
                            key_decisions: ['Use React']
                        }
                    ],
                    total: 1
                },
                status: 200,
                headers: new Headers(),
                body: ''
            };

            mockFetchJson.mockResolvedValueOnce(mockResponse);

            const result = await dataProvider.getList('analysis', {
                pagination: { page: 1, perPage: 10 },
                sort: { field: 'date', order: 'DESC' },
                filter: { watchedProjects: true }
            });

            expect(result.data[0].meeting_title).toBe('Sprint Planning');
            expect(result.data[0].action_items).toHaveLength(1);
        });

        it('should handle settings resource', async () => {
            const result = await dataProvider.getList('settings', {
                pagination: { page: 1, perPage: 10 },
                sort: { field: 'name', order: 'ASC' },
                filter: {}
            });

            expect(result.data).toHaveLength(1);
            expect(result.total).toBe(1);
        });

        it('should add auth token to requests if available', async () => {
            localStorage.setItem('auth_token', 'test-token-123');

            const mockResponse = {
                json: { data: [], total: 0 },
                status: 200,
                headers: new Headers(),
                body: ''
            };

            mockFetchJson.mockResolvedValueOnce(mockResponse);

            await dataProvider.getList('learnings', {
                pagination: { page: 1, perPage: 10 },
                sort: { field: 'created_at', order: 'DESC' },
                filter: {}
            });

            const callOptions = mockFetchJson.mock.calls[0][1];
            expect(callOptions?.headers).toBeDefined();
        });

        it('should handle API errors gracefully', async () => {
            mockFetchJson.mockRejectedValueOnce(new Error('Network error'));

            await expect(dataProvider.getList('meetings', {
                pagination: { page: 1, perPage: 10 },
                sort: { field: 'date', order: 'DESC' },
                filter: {}
            })).rejects.toThrow('Network error');
        });
    });

    describe('getOne', () => {
        it('should fetch single meeting', async () => {
            const mockResponse = {
                json: {
                    id: 1,
                    title: 'Test Meeting',
                    date: '2025-09-30'
                },
                status: 200,
                headers: new Headers(),
                body: ''
            };

            mockFetchJson.mockResolvedValueOnce(mockResponse);

            const result = await dataProvider.getOne('meetings', { id: 1 });

            expect(result.data.id).toBe(1);
            expect(result.data.title).toBe('Test Meeting');
        });

        it('should transform analysis getOne response', async () => {
            const mockResponse = {
                json: {
                    id: 1,
                    title: 'Sprint Planning',
                    action_items: [{ title: 'Task 1' }],
                    key_decisions: ['Decision 1']
                },
                status: 200,
                headers: new Headers(),
                body: ''
            };

            mockFetchJson.mockResolvedValueOnce(mockResponse);

            const result = await dataProvider.getOne('analysis', { id: 1 });

            expect(result.data.meeting_title).toBe('Sprint Planning');
            expect(result.data.action_items).toHaveLength(1);
        });

        it('should handle learning with nested data', async () => {
            const mockResponse = {
                json: {
                    data: {
                        id: 1,
                        content: 'Test learning',
                        category: 'technical'
                    }
                },
                status: 200,
                headers: new Headers(),
                body: ''
            };

            mockFetchJson.mockResolvedValueOnce(mockResponse);

            const result = await dataProvider.getOne('learnings', { id: 1 });

            expect(result.data.id).toBe(1);
            expect(result.data.content).toBe('Test learning');
        });
    });

    describe('create', () => {
        it('should create a new todo', async () => {
            const mockResponse = {
                json: { id: 1, title: 'New Todo', status: 'pending' },
                status: 200,
                headers: new Headers(),
                body: ''
            };

            mockFetchJson.mockResolvedValueOnce(mockResponse);

            const result = await dataProvider.create('todos', {
                data: {
                    title: 'New Todo',
                    description: 'Test description'
                }
            });

            expect(result.data.id).toBe(1);
            expect(result.data.title).toBe('New Todo');
        });

        it('should create a learning with proper format', async () => {
            const mockResponse = {
                json: {
                    learning: {
                        id: 1,
                        content: 'New learning',
                        category: 'technical'
                    }
                },
                status: 200,
                headers: new Headers(),
                body: ''
            };

            mockFetchJson.mockResolvedValueOnce(mockResponse);

            const result = await dataProvider.create('learnings', {
                data: {
                    content: 'New learning',
                    category: 'technical'
                }
            });

            expect(result.data.id).toBe(1);
            expect(result.data.content).toBe('New learning');
        });
    });

    describe('update', () => {
        it('should update a todo', async () => {
            const mockResponse = {
                json: { success: true },
                status: 200,
                headers: new Headers(),
                body: ''
            };

            mockFetchJson.mockResolvedValueOnce(mockResponse);

            const result = await dataProvider.update('todos', {
                id: 1,
                data: { title: 'Updated Todo', status: 'done' },
                previousData: { title: 'Old Todo', status: 'pending' }
            });

            expect(result.data.id).toBe(1);
        });
    });

    describe('delete', () => {
        it('should delete a todo', async () => {
            const mockResponse = {
                json: {},
                status: 200,
                headers: new Headers(),
                body: ''
            };

            mockFetchJson.mockResolvedValueOnce(mockResponse);

            const result = await dataProvider.delete('todos', {
                id: 1,
                previousData: { id: 1, title: 'Test' }
            });

            expect(result.data).toEqual({ id: 1, title: 'Test' });
        });
    });
});
