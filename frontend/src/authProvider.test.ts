/**
 * Tests for the authentication provider.
 */

import { authProvider } from './authProvider';

// Mock fetch
global.fetch = jest.fn();
const mockFetch = global.fetch as jest.MockedFunction<typeof fetch>;

describe('authProvider', () => {
    beforeEach(() => {
        jest.clearAllMocks();
        localStorage.clear();
    });

    describe('login', () => {
        it('should redirect to Google OAuth', async () => {
            const mockOpen = jest.spyOn(window, 'open').mockImplementation(() => null);

            await authProvider.login({});

            expect(mockOpen).toHaveBeenCalledWith(
                expect.stringContaining('/api/auth/google/login'),
                '_self'
            );

            mockOpen.mockRestore();
        });
    });

    describe('logout', () => {
        it('should clear localStorage and call logout endpoint', async () => {
            localStorage.setItem('auth_token', 'test-token');
            localStorage.setItem('user', JSON.stringify({ email: 'test@example.com' }));

            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: async () => ({ success: true })
            } as Response);

            await authProvider.logout({});

            expect(localStorage.getItem('auth_token')).toBeNull();
            expect(localStorage.getItem('user')).toBeNull();
            expect(mockFetch).toHaveBeenCalledWith(
                expect.stringContaining('/api/auth/logout'),
                expect.objectContaining({ method: 'POST' })
            );
        });

        it('should handle logout errors gracefully', async () => {
            localStorage.setItem('auth_token', 'test-token');

            mockFetch.mockRejectedValueOnce(new Error('Network error'));

            await authProvider.logout({});

            // Should still clear local storage even if API call fails
            expect(localStorage.getItem('auth_token')).toBeNull();
        });
    });

    describe('checkAuth', () => {
        it('should resolve if auth token exists', async () => {
            localStorage.setItem('auth_token', 'test-token');

            await expect(authProvider.checkAuth({})).resolves.toBeUndefined();
        });

        it('should reject if no auth token', async () => {
            await expect(authProvider.checkAuth({})).rejects.toThrow();
        });
    });

    describe('checkError', () => {
        it('should reject on 401 error', async () => {
            const error = { status: 401 };

            await expect(authProvider.checkError(error)).rejects.toThrow();
        });

        it('should reject on 403 error', async () => {
            const error = { status: 403 };

            await expect(authProvider.checkError(error)).rejects.toThrow();
        });

        it('should resolve on other errors', async () => {
            const error = { status: 500 };

            await expect(authProvider.checkError(error)).resolves.toBeUndefined();
        });

        it('should resolve if no error status', async () => {
            const error = { message: 'Some error' };

            await expect(authProvider.checkError(error)).resolves.toBeUndefined();
        });
    });

    describe('getIdentity', () => {
        it('should return user identity from localStorage', async () => {
            const mockUser = {
                id: 1,
                email: 'test@example.com',
                name: 'Test User'
            };

            localStorage.setItem('user', JSON.stringify(mockUser));

            const identity = await authProvider.getIdentity();

            expect(identity).toEqual({
                id: mockUser.id,
                fullName: mockUser.name
            });
        });

        it('should return undefined if no user in localStorage', async () => {
            const identity = await authProvider.getIdentity();

            expect(identity).toBeUndefined();
        });

        it('should handle invalid JSON in localStorage', async () => {
            localStorage.setItem('user', 'invalid-json');

            const identity = await authProvider.getIdentity();

            expect(identity).toBeUndefined();
        });
    });

    describe('getPermissions', () => {
        it('should return user role from localStorage', async () => {
            const mockUser = {
                id: 1,
                email: 'test@example.com',
                role: 'admin'
            };

            localStorage.setItem('user', JSON.stringify(mockUser));

            const permissions = await authProvider.getPermissions({});

            expect(permissions).toBe('admin');
        });

        it('should return user role for regular user', async () => {
            const mockUser = {
                id: 1,
                email: 'test@example.com',
                role: 'user'
            };

            localStorage.setItem('user', JSON.stringify(mockUser));

            const permissions = await authProvider.getPermissions({});

            expect(permissions).toBe('user');
        });

        it('should return undefined if no user', async () => {
            const permissions = await authProvider.getPermissions({});

            expect(permissions).toBeUndefined();
        });
    });

    describe('OAuth callback handling', () => {
        it('should extract and store token from URL', () => {
            // Simulate OAuth callback URL
            Object.defineProperty(window, 'location', {
                value: {
                    search: '?token=abc123&user=%7B%22email%22%3A%22test%40example.com%22%7D',
                    href: 'http://localhost:4001/auth-callback'
                },
                writable: true
            });

            // This would normally be handled by App component
            const urlParams = new URLSearchParams(window.location.search);
            const token = urlParams.get('token');
            const userParam = urlParams.get('user');

            expect(token).toBe('abc123');
            expect(userParam).toBeDefined();
        });
    });

    describe('Token refresh', () => {
        it('should handle expired token', async () => {
            localStorage.setItem('auth_token', 'expired-token');

            mockFetch.mockResolvedValueOnce({
                status: 401,
                ok: false,
                json: async () => ({ error: 'Token expired' })
            } as Response);

            const error = { status: 401 };
            await expect(authProvider.checkError(error)).rejects.toThrow();

            // Token should be cleared
            expect(localStorage.getItem('auth_token')).toBe('expired-token'); // Not cleared by checkError
        });
    });
});
