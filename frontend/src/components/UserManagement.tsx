import React, { useState, useEffect } from 'react';
import {
  List,
  Edit,
  Create,
  SimpleList,
  Datagrid,
  TextField,
  EmailField,
  DateField,
  BooleanField,
  SelectInput,
  BooleanInput,
  SimpleForm,
  TextInput,
  EditButton,
  SaveButton,
  Toolbar,
  useRecordContext,
  useNotify,
  useRefresh
} from 'react-admin';
import { Card, CardContent, Typography, Select, MenuItem, Switch, FormControlLabel, Box } from '@mui/material';
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
      console.log('Fetching users from /api/auth/users...');
      const response = await axios.get('/api/auth/users');
      console.log('Users response:', response);
      console.log('Users data:', response.data);
      if (response.data && response.data.users) {
        setUsers(response.data.users);
        console.log('Users set:', response.data.users);
      } else {
        console.error('Unexpected response format:', response.data);
        setError('Unexpected response format from server');
      }
    } catch (error: any) {
      console.error('Failed to fetch users:', error);
      console.error('Error response:', error.response);
      console.error('Error data:', error.response?.data);
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
      console.error('Failed to update role:', error);
    }
  };

  const handleStatusChange = async (userId: number, isActive: boolean) => {
    try {
      await axios.put(`/api/auth/users/${userId}/status`, { is_active: isActive });
      fetchUsers();
    } catch (error) {
      console.error('Failed to update status:', error);
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