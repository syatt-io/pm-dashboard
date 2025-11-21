import React, { useState, useEffect, useRef } from 'react';
import { Card, CardContent, Typography, Select, MenuItem, Switch, Box, TextField, Button, Dialog, DialogTitle, DialogContent, DialogActions, IconButton, Collapse, useMediaQuery, useTheme, TableContainer, Table, TableHead, TableBody, TableRow, TableCell, Grid, Divider } from '@mui/material';
import DeleteIcon from '@mui/icons-material/Delete';
import EditIcon from '@mui/icons-material/Edit';
import AddIcon from '@mui/icons-material/Add';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import axios from 'axios';
import InlineNotificationPreferences from './InlineNotificationPreferences';

const UserList = () => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
  const isTablet = useMediaQuery(theme.breakpoints.down('md'));
  const isLaptop = useMediaQuery(theme.breakpoints.down('lg'));

  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [expandedUserId, setExpandedUserId] = useState<number | null>(null);
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

  // Debounce timers for auto-save fields
  const debounceTimers = useRef<{[key: string]: NodeJS.Timeout}>({});

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

  // Debounced team settings update - waits 1 second after user stops typing
  const handleTeamSettingsChange = (userId: number, field: string, value: any) => {
    // Update local state immediately for responsive UI
    setUsers(prevUsers =>
      prevUsers.map((u: any) =>
        u.id === userId ? { ...u, [field]: value } : u
      )
    );

    // Clear existing timer for this user-field combination
    const timerKey = `${userId}-${field}`;
    if (debounceTimers.current[timerKey]) {
      clearTimeout(debounceTimers.current[timerKey]);
    }

    // Set new timer to save after 1 second of inactivity
    debounceTimers.current[timerKey] = setTimeout(async () => {
      try {
        const data: any = {};
        data[field] = value;
        await axios.put(`/api/auth/users/${userId}/team-settings`, data);
        // Don't refetch - local state is already updated
      } catch (error: any) {
        setError(error.response?.data?.error || `Failed to update ${field}`);
        // On error, refetch to restore correct value
        fetchUsers();
      }
    }, 1000);
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

  const handleToggleExpand = (userId: number) => {
    setExpandedUserId(expandedUserId === userId ? null : userId);
  };

  const handleBasicInfoChange = (userId: number, field: string, value: any) => {
    // Update local state immediately
    setUsers(users.map((u: any) =>
      u.id === userId ? { ...u, [field]: value } : u
    ));

    // Find current user data to send both name and email
    const currentUser = users.find((u: any) => u.id === userId);
    if (!currentUser) return;

    // Clear existing timer for this field
    const timerKey = `user-${userId}-basic-info`;
    if (debounceTimers.current[timerKey]) {
      clearTimeout(debounceTimers.current[timerKey]);
    }

    // Debounce API call
    debounceTimers.current[timerKey] = setTimeout(async () => {
      try {
        // Send name, email, and google_id since endpoint requires all three
        const payload = {
          name: field === 'name' ? value : currentUser.name,
          email: field === 'email' ? value : currentUser.email,
          google_id: field === 'google_id' ? value : currentUser.google_id
        };
        await axios.put(`/api/auth/users/${userId}/basic-info`, payload);
      } catch (error: any) {
        setError(error.response?.data?.error || 'Failed to update user information');
        fetchUsers(); // Refetch to restore correct values
      }
    }, 1000);
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
            <TableContainer sx={{ overflowX: 'auto' }}>
              <Table size={isMobile ? 'small' : 'medium'}>
                <TableHead>
                  <TableRow>
                    <TableCell sx={{ width: 40, p: { xs: 1, sm: 1.5 } }}></TableCell>
                    <TableCell sx={{ p: { xs: 1, sm: 1.5 } }}>Name</TableCell>
                    <TableCell sx={{ p: { xs: 1, sm: 1.5 } }}>Role</TableCell>
                    <TableCell sx={{ p: { xs: 1, sm: 1.5 } }}>Status</TableCell>
                    {!isMobile && <TableCell sx={{ p: { xs: 1, sm: 1.5 } }}>Discipline</TableCell>}
                    {!isMobile && <TableCell sx={{ p: { xs: 1, sm: 1.5 } }}>Team</TableCell>}
                    {!isLaptop && <TableCell sx={{ p: { xs: 0.5, sm: 1 } }}>Last Login</TableCell>}
                    <TableCell sx={{ p: { xs: 0.5, sm: 1 } }}>Actions</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {users.map((user: any) => (
                    <React.Fragment key={user.id}>
                      <TableRow>
                        <TableCell sx={{ p: { xs: 1, sm: 1.5 } }}>
                          <IconButton
                            size="small"
                            onClick={() => handleToggleExpand(user.id)}
                          >
                            {expandedUserId === user.id ? <ExpandLessIcon /> : <ExpandMoreIcon />}
                          </IconButton>
                        </TableCell>
                        <TableCell sx={{ p: { xs: 1, sm: 1.5 } }}>
                          <Box
                            sx={{
                              cursor: 'pointer',
                              '&:hover': { textDecoration: 'underline' },
                              fontSize: { xs: '0.75rem', sm: '0.875rem' }
                            }}
                            onClick={() => handleToggleExpand(user.id)}
                          >
                            {user.name}
                          </Box>
                        </TableCell>
                        <TableCell sx={{ p: { xs: 1, sm: 1.5 } }}>
                          <Select
                            value={user.role}
                            onChange={(e) => handleRoleChange(user.id, e.target.value)}
                            size="small"
                            disabled={user.email === 'mike.samimi@syatt.io'}
                            sx={{ fontSize: { xs: '0.75rem', sm: '0.875rem' } }}
                          >
                            <MenuItem value="NO_ACCESS">No Access</MenuItem>
                            <MenuItem value="MEMBER">Member</MenuItem>
                            <MenuItem value="PM">PM</MenuItem>
                            <MenuItem value="ADMIN">Admin</MenuItem>
                          </Select>
                        </TableCell>
                        <TableCell sx={{ p: { xs: 1, sm: 1.5 } }}>
                          <Switch
                            checked={user.is_active}
                            onChange={(e) => handleStatusChange(user.id, e.target.checked)}
                            disabled={user.email === 'mike.samimi@syatt.io'}
                            size={isMobile ? 'small' : 'medium'}
                          />
                        </TableCell>
                        {!isMobile && (
                          <TableCell sx={{ p: { xs: 1, sm: 1.5 } }}>
                            <Select
                              value={user.team || ''}
                              onChange={(e) => handleTeamSettingsChange(user.id, 'team', e.target.value)}
                              size="small"
                              displayEmpty
                              sx={{ minWidth: { xs: 100, sm: 120 }, fontSize: { xs: '0.75rem', sm: '0.875rem' } }}
                            >
                              <MenuItem value=""><em>None</em></MenuItem>
                              <MenuItem value="PMs">PMs</MenuItem>
                              <MenuItem value="Design">Design</MenuItem>
                              <MenuItem value="UX">UX</MenuItem>
                              <MenuItem value="FE Devs">FE Devs</MenuItem>
                              <MenuItem value="BE Devs">BE Devs</MenuItem>
                              <MenuItem value="Data">Data</MenuItem>
                            </Select>
                          </TableCell>
                        )}
                        {!isMobile && (
                          <TableCell sx={{ p: { xs: 1, sm: 1.5 } }}>
                            <Select
                              value={user.project_team === 'N/A' ? '' : (user.project_team || '')}
                              onChange={(e) => handleTeamSettingsChange(user.id, 'project_team', e.target.value)}
                              size="small"
                              displayEmpty
                              sx={{ minWidth: { xs: 100, sm: 140 }, fontSize: { xs: '0.75rem', sm: '0.875rem' } }}
                            >
                              <MenuItem value=""><em>None</em></MenuItem>
                              <MenuItem value="Waffle House">Waffle House</MenuItem>
                              <MenuItem value="Space Cowboiz">Space Cowboiz</MenuItem>
                              <MenuItem value="Other">Other</MenuItem>
                            </Select>
                          </TableCell>
                        )}
                        {!isLaptop && (
                          <TableCell sx={{ p: { xs: 0.5, sm: 1 }, fontSize: { xs: '0.65rem', sm: '0.875rem' } }}>
                            {user.last_login ? new Date(user.last_login).toLocaleDateString() : 'Never'}
                          </TableCell>
                        )}
                        <TableCell sx={{ p: { xs: 0.5, sm: 1 } }}>
                          <Box sx={{ display: 'flex', gap: 0.5 }}>
                            <IconButton
                              color="primary"
                              size="small"
                              onClick={() => handleToggleExpand(user.id)}
                            >
                              <EditIcon />
                            </IconButton>
                            <IconButton
                              color="error"
                              size="small"
                              onClick={() => handleDeleteUser(user.id, user.name)}
                              disabled={user.email === 'mike.samimi@syatt.io'}
                            >
                              <DeleteIcon />
                            </IconButton>
                          </Box>
                        </TableCell>
                      </TableRow>
                      {/* Expandable row for user details and notification preferences */}
                      <TableRow>
                        <TableCell colSpan={8} sx={{ p: 0, borderBottom: 0 }}>
                          <Collapse in={expandedUserId === user.id} timeout="auto" unmountOnExit>
                            <Box sx={{ backgroundColor: 'rgba(85, 77, 255, 0.08)', p: 3 }}>
                              {/* User Information Section */}
                              <Typography variant="h6" fontWeight={600} mb={2}>
                                User Information
                              </Typography>
                              <Grid container spacing={2} mb={3}>
                                <Grid item xs={12} md={6}>
                                  <TextField
                                    label="Name"
                                    value={user.name || ''}
                                    onChange={(e) => handleBasicInfoChange(user.id, 'name', e.target.value)}
                                    fullWidth
                                    size="small"
                                  />
                                </Grid>
                                <Grid item xs={12} md={6}>
                                  <TextField
                                    label="Email"
                                    value={user.email || ''}
                                    onChange={(e) => handleBasicInfoChange(user.id, 'email', e.target.value)}
                                    fullWidth
                                    size="small"
                                  />
                                </Grid>
                                <Grid item xs={12} md={6}>
                                  <TextField
                                    label="Google ID"
                                    value={user.google_id || ''}
                                    onChange={(e) => handleBasicInfoChange(user.id, 'google_id', e.target.value)}
                                    fullWidth
                                    size="small"
                                    placeholder="Enter Google Account ID"
                                  />
                                </Grid>
                                <Grid item xs={12} md={6}>
                                  <TextField
                                    label="Jira ID"
                                    value={user.jira_account_id || ''}
                                    onChange={(e) => handleTeamSettingsChange(user.id, 'jira_account_id', e.target.value)}
                                    fullWidth
                                    size="small"
                                    placeholder="Enter Jira Account ID"
                                  />
                                </Grid>
                                <Grid item xs={12} md={6}>
                                  <TextField
                                    label="Slack ID"
                                    value={user.slack_user_id || ''}
                                    onChange={(e) => handleTeamSettingsChange(user.id, 'slack_user_id', e.target.value)}
                                    fullWidth
                                    size="small"
                                    placeholder="Enter Slack User ID"
                                  />
                                </Grid>
                                <Grid item xs={12} md={6}>
                                  <TextField
                                    label="Hrs/week"
                                    type="number"
                                    value={user.weekly_hours_minimum ?? 32}
                                    onChange={(e) => handleTeamSettingsChange(user.id, 'weekly_hours_minimum', parseFloat(e.target.value))}
                                    fullWidth
                                    size="small"
                                    inputProps={{ min: 0, step: 0.5 }}
                                  />
                                </Grid>
                              </Grid>

                              <Divider sx={{ my: 3 }} />

                              {/* Notification Preferences Section */}
                              <InlineNotificationPreferences userId={user.id} />
                            </Box>
                          </Collapse>
                        </TableCell>
                      </TableRow>
                    </React.Fragment>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}

        {/* Create User Dialog */}
        <Dialog open={createDialogOpen} onClose={() => setCreateDialogOpen(false)} maxWidth="sm" fullWidth>
          <DialogTitle>Create New User</DialogTitle>
          <DialogContent>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 2 }}>
              <TextField
                label="Email"
                type="email"
                value={newUser.email}
                onChange={(e) => setNewUser({ ...newUser, email: e.target.value })}
                fullWidth
                required
              />
              <TextField
                label="Name"
                value={newUser.name}
                onChange={(e) => setNewUser({ ...newUser, name: e.target.value })}
                fullWidth
                required
              />
              <TextField
                label="Google ID"
                value={newUser.google_id}
                onChange={(e) => setNewUser({ ...newUser, google_id: e.target.value })}
                fullWidth
                required
              />
              <Select
                label="Role"
                value={newUser.role}
                onChange={(e) => setNewUser({ ...newUser, role: e.target.value })}
                fullWidth
              >
                <MenuItem value="NO_ACCESS">No Access</MenuItem>
                <MenuItem value="MEMBER">Member</MenuItem>
                <MenuItem value="PM">PM</MenuItem>
                <MenuItem value="ADMIN">Admin</MenuItem>
              </Select>
              <Select
                label="Discipline"
                value={newUser.team}
                onChange={(e) => setNewUser({ ...newUser, team: e.target.value })}
                fullWidth
                displayEmpty
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
              <Select
                label="Team"
                value={newUser.project_team}
                onChange={(e) => setNewUser({ ...newUser, project_team: e.target.value })}
                fullWidth
                displayEmpty
              >
                <MenuItem value="">
                  <em>None</em>
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
                label="Min Hours/Week"
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
