/**
 * Tests for the authentication provider.
 */

import { authProvider } from './authProvider';
import axios from 'axios';

// Mock axios
jest.mock('axios');
const mockedAxios = axios as jest.Mocked<typeof axios>;

describe('authProvider', () => {
    beforeEach(() => {
        jest.clearAllMocks();
        localStorage.clear();
    });

    describe('login', () => {
        it('should resolve successfully (handled by Google OAuth component)', async () => {
            // Login is handled externally by Google OAuth, so this just resolves
            await expect(authProvider.login({} as any)).resolves.toBeUndefined();
        });
    });

    describe('logout', () => {
        it('should clear localStorage and call logout endpoint', async () => {
            localStorage.setItem('auth_token', 'test-token');
            localStorage.setItem('rememberMe', 'true');

            mockedAxios.post.mockResolvedValueOnce({
                data: { success: true },
                status: 200,
                statusText: 'OK',
                headers: {},
                config: {} as any
            });

            await authProvider.logout({});

            expect(localStorage.getItem('auth_token')).toBeNull();
            expect(localStorage.getItem('rememberMe')).toBeNull();
            expect(mockedAxios.post).toHaveBeenCalledWith('/api/auth/logout');
        });

        it('should handle logout errors gracefully', async () => {
            localStorage.setItem('auth_token', 'test-token');

            mockedAxios.post.mockRejectedValueOnce(new Error('Network error'));

            await authProvider.logout({});

            // Should still clear local storage even if API call fails
            expect(localStorage.getItem('auth_token')).toBeNull();
        });
    });

    describe('checkAuth', () => {
        it('should resolve if auth token exists', async () => {
            localStorage.setItem('auth_token', 'test-token');

            await expect(authProvider.checkAuth({} as any)).resolves.toBeUndefined();
        });

        it('should reject if no auth token', async () => {
            await expect(authProvider.checkAuth({} as any)).rejects.toBeUndefined();
        });
    });

    describe('checkError', () => {
        it('should reject and clear token on 401 error', async () => {
            localStorage.setItem('auth_token', 'test-token');
            const error = { status: 401 };

            await expect(authProvider.checkError(error)).rejects.toBeUndefined();
            expect(localStorage.getItem('auth_token')).toBeNull();
        });

        it('should reject and clear token on 403 error', async () => {
            localStorage.setItem('auth_token', 'test-token');
            const error = { status: 403 };

            await expect(authProvider.checkError(error)).rejects.toBeUndefined();
            expect(localStorage.getItem('auth_token')).toBeNull();
        });

        it('should resolve on other errors', async () => {
            const error = { status: 500 };

            await expect(authProvider.checkError(error)).resolves.toBeUndefined();
        });

        it('should resolve if no error status', async () => {
            const error = { message: 'Some error' };

            await expect(authProvider.checkError(error as any)).resolves.toBeUndefined();
        });
    });

    describe('getIdentity', () => {
        it('should return user identity from API', async () => {
            const mockUser = {
                id: 1,
                email: 'test@example.com',
                name: 'Test User',
                picture: 'https://example.com/avatar.jpg'
            };

            mockedAxios.get.mockResolvedValueOnce({
                data: { user: mockUser },
                status: 200,
                statusText: 'OK',
                headers: {},
                config: {} as any
            });

            const identity = await authProvider.getIdentity();

            expect(identity).toEqual({
                id: mockUser.id,
                fullName: mockUser.name,
                avatar: mockUser.picture
            });
            expect(mockedAxios.get).toHaveBeenCalledWith('/api/auth/user');
        });

        it('should reject on API error', async () => {
            mockedAxios.get.mockRejectedValueOnce(new Error('Unauthorized'));

            await expect(authProvider.getIdentity()).rejects.toBeUndefined();
        });
    });

    describe('getPermissions', () => {
        it('should return user role from API', async () => {
            const mockUser = {
                id: 1,
                email: 'test@example.com',
                role: 'admin'
            };

            mockedAxios.get.mockResolvedValueOnce({
                data: { user: mockUser },
                status: 200,
                statusText: 'OK',
                headers: {},
                config: {} as any
            });

            const permissions = await authProvider.getPermissions({});

            expect(permissions).toBe('admin');
            expect(mockedAxios.get).toHaveBeenCalledWith('/api/auth/user');
        });

        it('should return user role for regular user', async () => {
            const mockUser = {
                id: 1,
                email: 'test@example.com',
                role: 'member'
            };

            mockedAxios.get.mockResolvedValueOnce({
                data: { user: mockUser },
                status: 200,
                statusText: 'OK',
                headers: {},
                config: {} as any
            });

            const permissions = await authProvider.getPermissions({});

            expect(permissions).toBe('member');
        });

        it('should reject on API error', async () => {
            mockedAxios.get.mockRejectedValueOnce(new Error('Unauthorized'));

            await expect(authProvider.getPermissions({})).rejects.toBeUndefined();
        });
    });
});
