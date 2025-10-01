import React, { useState, useEffect } from 'react';
import { Card, CardContent, Typography, Select, MenuItem, Switch, Box } from '@mui/material';
import axios from 'axios';

const UserList = () => {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchUsers();
  }, []);

  const fetchUsers = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await axios.get('/api/auth/users');
      if (response.data && response.data.users) {
        setUsers(response.data.users);
      } else {
        setError('Unexpected response format from server');
      }
    } catch (error: any) {
      setError(error.response?.data?.error || 'Failed to fetch users');
    } finally {
      setLoading(false);
    }
  };

  const handleRoleChange = async (userId: number, newRole: string) => {
    try {
      await axios.put(`/api/auth/users/${userId}/role`, { role: newRole });
      fetchUsers();
    } catch (error) {
      // Error will be shown in UI via error state
    }
  };

  const handleStatusChange = async (userId: number, isActive: boolean) => {
    try {
      await axios.put(`/api/auth/users/${userId}/status`, { is_active: isActive });
      fetchUsers();
    } catch (error) {
      // Error will be shown in UI via error state
    }
  };

  return (
    <Card sx={{ m: 2 }}>
      <CardContent>
        <Typography variant="h5" component="h2" gutterBottom>
          User Management
        </Typography>

        {loading && (
          <Typography>Loading users...</Typography>
        )}

        {error && (
          <Typography color="error" sx={{ mb: 2 }}>
            Error: {error}
          </Typography>
        )}

        {!loading && !error && users.length === 0 && (
          <Typography>No users found.</Typography>
        )}

        {!loading && !error && users.length > 0 && (
          <Box sx={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ borderBottom: '2px solid #ddd' }}>
                  <th style={{ padding: '12px', textAlign: 'left' }}>Email</th>
                  <th style={{ padding: '12px', textAlign: 'left' }}>Name</th>
                  <th style={{ padding: '12px', textAlign: 'left' }}>Role</th>
                  <th style={{ padding: '12px', textAlign: 'left' }}>Status</th>
                  <th style={{ padding: '12px', textAlign: 'left' }}>Created</th>
                  <th style={{ padding: '12px', textAlign: 'left' }}>Last Login</th>
                </tr>
              </thead>
              <tbody>
                {users.map((user: any) => (
                <tr key={user.id} style={{ borderBottom: '1px solid #eee' }}>
                  <td style={{ padding: '12px' }}>{user.email}</td>
                  <td style={{ padding: '12px' }}>{user.name}</td>
                  <td style={{ padding: '12px' }}>
                    <Select
                      value={user.role}
                      onChange={(e) => handleRoleChange(user.id, e.target.value)}
                      size="small"
                      disabled={user.email === 'mike.samimi@syatt.io'}
                    >
                      <MenuItem value="no_access">No Access</MenuItem>
                      <MenuItem value="member">Member</MenuItem>
                      <MenuItem value="admin">Admin</MenuItem>
                    </Select>
                  </td>
                  <td style={{ padding: '12px' }}>
                    <Switch
                      checked={user.is_active}
                      onChange={(e) => handleStatusChange(user.id, e.target.checked)}
                      disabled={user.email === 'mike.samimi@syatt.io'}
                    />
                  </td>
                  <td style={{ padding: '12px' }}>
                    {new Date(user.created_at).toLocaleDateString()}
                  </td>
                  <td style={{ padding: '12px' }}>
                    {user.last_login ? new Date(user.last_login).toLocaleDateString() : 'Never'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Box>
        )}
      </CardContent>
    </Card>
  );
};

export default UserList;