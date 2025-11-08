import React, { useState, useEffect } from 'react';
import { Card, CardContent, Typography, Select, MenuItem, Switch, Box, TextField, Button, Dialog, DialogTitle, DialogContent, DialogActions, IconButton } from '@mui/material';
import DeleteIcon from '@mui/icons-material/Delete';
import AddIcon from '@mui/icons-material/Add';
import axios from 'axios';

const UserList = () => {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [newUser, setNewUser] = useState({
    email: '',
    name: '',
    google_id: '',
    role: 'member',
    is_active: true,
    team: '',
    project_team: '',
    jira_account_id: '',
    slack_user_id: '',
    weekly_hours_minimum: 32
  });

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

  const handleTeamSettingsChange = async (userId: number, field: string, value: any) => {
    try {
      const data: any = {};
      data[field] = value;
      await axios.put(`/api/auth/users/${userId}/team-settings`, data);
      fetchUsers();
    } catch (error: any) {
      setError(error.response?.data?.error || `Failed to update ${field}`);
    }
  };

  const handleCreateUser = async () => {
    try {
      await axios.post('/api/auth/users', newUser);
      setCreateDialogOpen(false);
      setNewUser({
        email: '',
        name: '',
        google_id: '',
        role: 'member',
        is_active: true,
        team: '',
        project_team: '',
        jira_account_id: '',
        slack_user_id: '',
        weekly_hours_minimum: 32
      });
      fetchUsers();
    } catch (error: any) {
      setError(error.response?.data?.error || 'Failed to create user');
    }
  };

  const handleDeleteUser = async (userId: number, userName: string) => {
    if (!window.confirm(`Are you sure you want to delete ${userName}?`)) {
      return;
    }

    try {
      await axios.delete(`/api/auth/users/${userId}`);
      fetchUsers();
    } catch (error: any) {
      setError(error.response?.data?.error || 'Failed to delete user');
    }
  };

  return (
    <Card sx={{ m: 2 }}>
      <CardContent>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
          <Typography variant="h5" component="h2">
            User Management
          </Typography>
          <Button
            variant="contained"
            color="primary"
            startIcon={<AddIcon />}
            onClick={() => setCreateDialogOpen(true)}
          >
            Create User
          </Button>
        </Box>

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
                  <th style={{ padding: '12px', textAlign: 'left' }}>Discipline</th>
                  <th style={{ padding: '12px', textAlign: 'left' }}>Team</th>
                  <th style={{ padding: '12px', textAlign: 'left' }}>Jira Account ID</th>
                  <th style={{ padding: '12px', textAlign: 'left' }}>Slack User ID</th>
                  <th style={{ padding: '12px', textAlign: 'left' }}>Min Hours/Week</th>
                  <th style={{ padding: '12px', textAlign: 'left' }}>Created</th>
                  <th style={{ padding: '12px', textAlign: 'left' }}>Last Login</th>
                  <th style={{ padding: '12px', textAlign: 'left' }}>Actions</th>
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
                    <Select
                      value={user.team || ''}
                      onChange={(e) => handleTeamSettingsChange(user.id, 'team', e.target.value)}
                      size="small"
                      displayEmpty
                      sx={{ minWidth: 120 }}
                    >
                      <MenuItem value="">
                        <em>None</em>
                      </MenuItem>
                      <MenuItem value="PMs">PMs</MenuItem>
                      <MenuItem value="Design">Design</MenuItem>
                      <MenuItem value="UX">UX</MenuItem>
                      <MenuItem value="FE Devs">FE Devs</MenuItem>
                      <MenuItem value="BE Devs">BE Devs</MenuItem>
                      <MenuItem value="Data">Data</MenuItem>
                    </Select>
                  </td>
                  <td style={{ padding: '12px' }}>
                    <Select
                      value={user.project_team || ''}
                      onChange={(e) => handleTeamSettingsChange(user.id, 'project_team', e.target.value)}
                      size="small"
                      displayEmpty
                      sx={{ minWidth: 140 }}
                    >
                      <MenuItem value="">
                        <em>None</em>
                      </MenuItem>
                      <MenuItem value="Waffle House">Waffle House</MenuItem>
                      <MenuItem value="Space Cowboiz">Space Cowboiz</MenuItem>
                      <MenuItem value="Other">Other</MenuItem>
                    </Select>
                  </td>
                  <td style={{ padding: '12px' }}>
                    <TextField
                      value={user.jira_account_id || ''}
                      onChange={(e) => handleTeamSettingsChange(user.id, 'jira_account_id', e.target.value)}
                      size="small"
                      placeholder="Enter Jira ID"
                      sx={{ minWidth: 150 }}
                    />
                  </td>
                  <td style={{ padding: '12px' }}>
                    <TextField
                      value={user.slack_user_id || ''}
                      onChange={(e) => handleTeamSettingsChange(user.id, 'slack_user_id', e.target.value)}
                      size="small"
                      placeholder="Enter Slack ID"
                      sx={{ minWidth: 150 }}
                    />
                  </td>
                  <td style={{ padding: '12px' }}>
                    <TextField
                      type="number"
                      value={user.weekly_hours_minimum || 32}
                      onChange={(e) => handleTeamSettingsChange(user.id, 'weekly_hours_minimum', parseFloat(e.target.value))}
                      size="small"
                      inputProps={{ min: 0, step: 0.5 }}
                      sx={{ width: 80 }}
                    />
                  </td>
                  <td style={{ padding: '12px' }}>
                    {new Date(user.created_at).toLocaleDateString()}
                  </td>
                  <td style={{ padding: '12px' }}>
                    {user.last_login ? new Date(user.last_login).toLocaleDateString() : 'Never'}
                  </td>
                  <td style={{ padding: '12px' }}>
                    <IconButton
                      color="error"
                      size="small"
                      onClick={() => handleDeleteUser(user.id, user.name)}
                      disabled={user.email === 'mike.samimi@syatt.io'}
                    >
                      <DeleteIcon />
                    </IconButton>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Box>
        )}

        {/* Create User Dialog */}
        <Dialog open={createDialogOpen} onClose={() => setCreateDialogOpen(false)} maxWidth="sm" fullWidth>
          <DialogTitle>Create New User</DialogTitle>
          <DialogContent>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 1 }}>
              <TextField
                label="Email *"
                type="email"
                value={newUser.email}
                onChange={(e) => setNewUser({ ...newUser, email: e.target.value })}
                fullWidth
                required
              />
              <TextField
                label="Name *"
                value={newUser.name}
                onChange={(e) => setNewUser({ ...newUser, name: e.target.value })}
                fullWidth
                required
              />
              <TextField
                label="Google ID *"
                value={newUser.google_id}
                onChange={(e) => setNewUser({ ...newUser, google_id: e.target.value })}
                fullWidth
                required
                helperText="Google OAuth user ID"
              />
              <Select
                value={newUser.role}
                onChange={(e) => setNewUser({ ...newUser, role: e.target.value })}
                fullWidth
              >
                <MenuItem value="no_access">No Access</MenuItem>
                <MenuItem value="member">Member</MenuItem>
                <MenuItem value="admin">Admin</MenuItem>
              </Select>
              <Select
                value={newUser.team}
                onChange={(e) => setNewUser({ ...newUser, team: e.target.value })}
                fullWidth
                displayEmpty
              >
                <MenuItem value="">
                  <em>Discipline (None)</em>
                </MenuItem>
                <MenuItem value="PMs">PMs</MenuItem>
                <MenuItem value="Design">Design</MenuItem>
                <MenuItem value="UX">UX</MenuItem>
                <MenuItem value="FE Devs">FE Devs</MenuItem>
                <MenuItem value="BE Devs">BE Devs</MenuItem>
                <MenuItem value="Data">Data</MenuItem>
              </Select>
              <Select
                value={newUser.project_team}
                onChange={(e) => setNewUser({ ...newUser, project_team: e.target.value })}
                fullWidth
                displayEmpty
              >
                <MenuItem value="">
                  <em>Team (None)</em>
                </MenuItem>
                <MenuItem value="Waffle House">Waffle House</MenuItem>
                <MenuItem value="Space Cowboiz">Space Cowboiz</MenuItem>
                <MenuItem value="Other">Other</MenuItem>
              </Select>
              <TextField
                label="Jira Account ID"
                value={newUser.jira_account_id}
                onChange={(e) => setNewUser({ ...newUser, jira_account_id: e.target.value })}
                fullWidth
              />
              <TextField
                label="Slack User ID"
                value={newUser.slack_user_id}
                onChange={(e) => setNewUser({ ...newUser, slack_user_id: e.target.value })}
                fullWidth
              />
              <TextField
                label="Weekly Hours Minimum"
                type="number"
                value={newUser.weekly_hours_minimum}
                onChange={(e) => setNewUser({ ...newUser, weekly_hours_minimum: parseFloat(e.target.value) })}
                fullWidth
                inputProps={{ min: 0, step: 0.5 }}
              />
            </Box>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setCreateDialogOpen(false)}>Cancel</Button>
            <Button
              onClick={handleCreateUser}
              variant="contained"
              color="primary"
              disabled={!newUser.email || !newUser.name || !newUser.google_id}
            >
              Create
            </Button>
          </DialogActions>
        </Dialog>
      </CardContent>
    </Card>
  );
};

export default UserList;