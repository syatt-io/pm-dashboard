// @ts-nocheck
import React, { useState, useEffect, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import {
  TextField,
  useNotify,
  useDataProvider,
  Button,
  useRedirect,
  Show,
  SimpleShowLayout,
  useRecordContext,
  Edit,
  SimpleForm,
  TextInput,
  SelectInput,
  NumberInput,
  EditButton,
  TopToolbar,
} from 'react-admin';
import {
  Card,
  CardContent,
  Typography,
  Box,
  Chip,
  Switch,
  FormControlLabel,
  Alert,
  Tabs,
  Tab,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  MenuItem,
  Select,
  InputLabel,
  FormControl,
  Grid,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  List,
  ListItem,
  ListItemText,
  Divider,
  IconButton,
  ListItemIcon,
  Skeleton,
  Button as MuiButton,
  TextField as MuiTextField,
  CircularProgress,
} from '@mui/material';
import {
  Star,
  StarBorder,
  Sync as SyncIcon,
  Work as WorkIcon,
  AccessTime as TimeIcon,
  People as PeopleIcon,
  Forum as ForumIcon,
  Assignment as TaskIcon,
  CalendarToday as CalendarIcon,
  Refresh as RefreshIcon,
  Assessment as DigestIcon,
  GetApp as DownloadIcon,
} from '@mui/icons-material';
import { ResourceMappingCell } from './ResourceMappingCell';

// API Configuration
const API_BASE_URL = process.env.REACT_APP_API_URL || '' + (window.location.hostname === 'localhost' ? 'http://localhost:4000' : 'https://agent-pm-tsbbb.ondigitalocean.app') + '';

interface Project {
  key: string;
  name: string;
  projectTypeKey?: string;
  is_active?: boolean;
  forecasted_hours_month?: number;
  project_work_type?: 'project-based' | 'growth-support' | 'n-a';
  total_hours?: number;
  description?: string;
  current_month_hours?: number;
  cumulative_hours?: number;
  slack_channel?: string;
  weekly_meeting_day?: string;
}

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

function TabPanel(props: TabPanelProps) {
  const { children, value, index, ...other } = props;

  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`simple-tabpanel-${index}`}
      aria-labelledby={`simple-tab-${index}`}
      {...other}
    >
      {value === index && (
        <Box sx={{ p: 3 }}>
          {children}
        </Box>
      )}
    </div>
  );
}

const WatchToggle = ({ record }: { record: any }) => {
  const [watched, setWatched] = useState(false);
  const [loading, setLoading] = useState(false);
  const notify = useNotify();

  useEffect(() => {
    // Load watched projects from API
    const loadWatchedProjectsFromAPI = async () => {
      if (loading) return; // Prevent multiple simultaneous requests

      try {
        setLoading(true);
        const token = localStorage.getItem('auth_token');
        if (!token) {
          setLoading(false);
          return;
        }

        const response = await fetch(`${API_BASE_URL}/api/watched-projects`, {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
        });

        if (response.ok) {
          const data = await response.json();
          setWatched(data.watched_projects.includes(record.key));
        } else if (response.status === 401) {
          // Silently handle auth errors - user may not be logged in yet
        }
      } catch (error) {
        // Silently handle errors to prevent infinite retry loop
      } finally {
        setLoading(false);
      }
    };

    loadWatchedProjectsFromAPI();
  }, [record.key, loading]); // Only re-run when record.key changes

  const handleToggle = async () => {
    try {
      const token = localStorage.getItem('auth_token');
      if (!token) {
        notify('Authentication required', { type: 'error' });
        return;
      }

      if (watched) {
        // Remove from watched list
        const response = await fetch(`${API_BASE_URL}/api/watched-projects/${record.key}`, {
          method: 'DELETE',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
        });

        if (response.ok) {
          setWatched(false);
          notify(`Stopped watching ${record.name}`, { type: 'info' });
          window.dispatchEvent(new Event('watchedProjectsChanged'));
        } else {
          throw new Error('Failed to unwatch project');
        }
      } else {
        // Add to watched list
        const response = await fetch(`${API_BASE_URL}/api/watched-projects/${record.key}`, {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
        });

        if (response.ok) {
          setWatched(true);
          notify(`Now watching ${record.name}`, { type: 'success' });
          window.dispatchEvent(new Event('watchedProjectsChanged'));
        } else {
          throw new Error('Failed to watch project');
        }
      }
    } catch (error) {
      notify('Error updating project watch status', { type: 'error' });
    }
  };

  return (
    <FormControlLabel
      control={
        <Switch
          checked={watched}
          onChange={handleToggle}
          color="primary"
          size="small"
        />
      }
      label={
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
          {watched ? <Star color="primary" fontSize="small" /> : <StarBorder fontSize="small" />}
          {watched ? 'Watching' : 'Watch'}
        </Box>
      }
    />
  );
};


const WatchedProjectsHeader = () => {
  const [watchedProjects, setWatchedProjects] = useState<string[]>([]);

  useEffect(() => {
    loadWatchedProjects();

    // Listen for watched projects changes
    const handleWatchedProjectsChange = () => {
      loadWatchedProjects();
    };

    window.addEventListener('watchedProjectsChanged', handleWatchedProjectsChange);

    return () => {
      window.removeEventListener('watchedProjectsChanged', handleWatchedProjectsChange);
    };
  }, []);

  const loadWatchedProjects = async () => {
    try {
      const token = localStorage.getItem('auth_token');
      if (!token) return;

      const response = await fetch(`${API_BASE_URL}/api/watched-projects`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (response.ok) {
        const data = await response.json();
        setWatchedProjects(data.watched_projects);
      } else if (response.status === 401) {
        // Silently handle auth errors - user may not be logged in yet
      } else {
        // Silently handle other errors to prevent retry loops
      }
    } catch (error) {
      // Silently handle errors to prevent infinite retry loop
    }
  };

  return (
    <Card sx={{ mb: 2, borderLeft: '4px solid', borderLeftColor: 'primary.main' }}>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          📌 Your Watched Projects ({watchedProjects.length})
        </Typography>
        {watchedProjects.length === 0 ? (
          <Alert severity="info">
            No projects selected yet. Use the watch toggles below to select projects you want to monitor for meeting analysis.
          </Alert>
        ) : (
          <Box>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
              These projects will be monitored for relevant meeting analysis:
            </Typography>
            <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
              {watchedProjects.map((projectKey) => (
                <Chip
                  key={projectKey}
                  label={projectKey}
                  color="primary"
                  variant="filled"
                  size="small"
                  sx={{ fontWeight: 'medium' }}
                />
              ))}
            </Box>
          </Box>
        )}
      </CardContent>
    </Card>
  );
};

const ActiveToggle = ({ record, onToggle }: { record: Project, onToggle: (record: Project) => void }) => {
  const handleToggle = () => {
    onToggle(record);
  };

  return (
    <FormControlLabel
      control={
        <Switch
          checked={record.is_active || false}
          onChange={handleToggle}
          color="primary"
          size="small"
        />
      }
      label={record.is_active ? 'Active' : 'Inactive'}
    />
  );
};

const ProjectCard = ({ project, onCardClick }: { project: Project, onCardClick: (project: Project) => void }) => {
  const watchedProjects = JSON.parse(localStorage.getItem('watchedProjects') || '[]');
  const isWatched = watchedProjects.includes(project.key);

  const getHoursColor = (currentHours: number, forecastedHours: number, projectType: string) => {
    if (projectType === 'n-a') return 'text.primary';
    if (!forecastedHours || forecastedHours === 0) return 'success.main';
    const percentage = (currentHours / forecastedHours) * 100;
    if (percentage > 100) return 'error.main';
    if (percentage > 80) return 'warning.main';
    return 'success.main';
  };

  return (
    <Card
      sx={{
        height: '100%',
        cursor: 'pointer',
        transition: 'all 0.2s ease-in-out',
        '&:hover': {
          transform: 'translateY(-2px)',
          boxShadow: 3
        },
        borderLeft: isWatched ? '4px solid' : 'none',
        borderLeftColor: isWatched ? 'primary.main' : 'transparent',
        backgroundColor: isWatched ? 'rgba(85, 77, 255, 0.08)' : 'background.paper'
      }}
      onClick={() => onCardClick(project)}
    >
      <CardContent>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 2 }}>
          <Typography variant="h6" component="div" sx={{ fontWeight: 'bold' }}>
            {project.name}
          </Typography>
          <Box>
            <Chip label={project.key} size="small" color="primary" variant="outlined" />
            {isWatched && (
              <Star color="primary" fontSize="small" sx={{ ml: 1 }} />
            )}
          </Box>
        </Box>

        <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
          {project.projectTypeKey || 'Unknown Type'}
        </Typography>

        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
          <WorkIcon fontSize="small" color="action" />
          <Typography variant="body2">
            {project.project_work_type === 'project-based' ? 'Project-based' :
             project.project_work_type === 'growth-support' ? 'Growth & Support' : 'N/A'}
          </Typography>
        </Box>

        {project.project_work_type !== 'n-a' && (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
            <TimeIcon fontSize="small" color="action" />
            <Typography
              variant="body2"
              sx={{
                fontWeight: 'bold',
                color: getHoursColor(
                  project.current_month_hours || 0,
                  project.forecasted_hours_month || 0,
                  project.project_work_type || 'project-based'
                )
              }}
            >
              {`${(project.current_month_hours || 0).toFixed(1)}h / ${project.forecasted_hours_month || 0}h this month`}
            </Typography>
          </Box>
        )}

        {project.slack_channel && (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
            <ForumIcon fontSize="small" color="action" />
            <Typography variant="body2">
              {project.slack_channel}
            </Typography>
          </Box>
        )}

        {project.weekly_meeting_day && (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <CalendarIcon fontSize="small" color="action" />
            <Typography variant="body2">
              Weekly meeting: {project.weekly_meeting_day}
            </Typography>
          </Box>
        )}
      </CardContent>
    </Card>
  );
};

const ProjectDetailDialog = ({
  project,
  open,
  onClose,
  onSave
}: {
  project: Project | null,
  open: boolean,
  onClose: () => void,
  onSave: (project: Project) => void
}) => {
  const [editedProject, setEditedProject] = useState<Project | null>(null);
  const [recentMeetings, setRecentMeetings] = useState([]);
  const [recentTodos, setRecentTodos] = useState([]);
  const [loadingMeetings, setLoadingMeetings] = useState(false);
  const [loadingTodos, setLoadingTodos] = useState(false);
  const [dateFilter, setDateFilter] = useState<'1' | '7' | '30'>('7');

  // Project digest state
  const [generatingDigest, setGeneratingDigest] = useState(false);
  const [digestData, setDigestData] = useState<any>(null);
  const [digestDays, setDigestDays] = useState<'7' | '30'>('7');

  // Function to fetch meetings for this project
  const fetchMeetings = async (projectKey: string, days: string) => {
    setLoadingMeetings(true);
    try {
      const token = localStorage.getItem('auth_token');
      const response = await fetch(`${API_BASE_URL}/api/meetings?resource_context=analysis&projects=${projectKey}&date_range=${days}&sort_field=analyzed_at&sort_order=DESC`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });
      if (response.ok) {
        const data = await response.json();
        setRecentMeetings(data.data || []);
      } else {
        setRecentMeetings([]);
      }
    } catch (error) {
      setRecentMeetings([]);
    } finally {
      setLoadingMeetings(false);
    }
  };

  // Function to fetch TODOs for this project
  const fetchTodos = async (projectKey: string) => {
    setLoadingTodos(true);
    try {
      const token = localStorage.getItem('auth_token');
      const response = await fetch(`${API_BASE_URL}/api/todos`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });
      if (response.ok) {
        const data = await response.json();
        // Filter TODOs for this project
        const projectTodos = data.data?.filter((todo: any) => {
          return todo.project_key === projectKey;
        }) || [];
        setRecentTodos(projectTodos);
      } else {
        setRecentTodos([]);
      }
    } catch (error) {
      setRecentTodos([]);
    } finally {
      setLoadingTodos(false);
    }
  };

  // Function to generate project digest
  const generateDigest = async () => {
    if (!project) return;

    setGeneratingDigest(true);
    try {
      const token = localStorage.getItem('auth_token');
      const response = await fetch(`${API_BASE_URL}/api/project-digest/${project.key}`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          days: parseInt(digestDays),
          project_name: project.name,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setDigestData(data);
      } else {
        const errorData = await response.json().catch(() => ({ error: 'Unknown error' }));
        alert(`Error generating digest: ${errorData.error || response.statusText}`);
      }
    } catch (error) {
      alert(`Error generating digest: ${error.message}`);
    } finally {
      setGeneratingDigest(false);
    }
  };

  // Function to download digest as markdown
  const downloadDigest = () => {
    if (!digestData || !digestData.formatted_agenda) return;

    const blob = new Blob([digestData.formatted_agenda], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${project?.key}_digest_${digestDays}days_${new Date().toISOString().split('T')[0]}.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  useEffect(() => {
    if (project) {
      setEditedProject({ ...project });

      // Fetch meetings for this project
      fetchMeetings(project.key, dateFilter);

      // Fetch TODOs for this project
      fetchTodos(project.key);
    }
  }, [project, dateFilter]);

  const handleSave = () => {
    if (editedProject) {
      onSave(editedProject);
      onClose();
    }
  };

  const weekdayOptions = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'];

  if (!project || !editedProject) return null;

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="md"
      fullWidth
      PaperProps={{
        sx: { maxHeight: '90vh' }
      }}
    >
      <DialogTitle>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <Typography variant="h5">{project.name}</Typography>
          <Chip label={project.key} color="primary" />
        </Box>
      </DialogTitle>

      <DialogContent dividers>
        <Grid container spacing={3}>
          {/* Project Settings */}
          <Grid item xs={12} md={6}>
            <Typography variant="h6" gutterBottom sx={{ color: 'primary.main', fontWeight: 'bold' }}>
              📋 Project Settings
            </Typography>

            <Box sx={{ mb: 3 }}>
              <FormControl fullWidth sx={{ mb: 2 }}>
                <InputLabel>Project Type</InputLabel>
                <Select
                  value={editedProject.project_work_type || 'project-based'}
                  onChange={(e) => setEditedProject({
                    ...editedProject,
                    project_work_type: e.target.value as 'project-based' | 'growth-support' | 'n-a'
                  })}
                >
                  <MenuItem value="project-based">Project-based</MenuItem>
                  <MenuItem value="growth-support">Growth & Support</MenuItem>
                  <MenuItem value="n-a">N/A</MenuItem>
                </Select>
              </FormControl>

              {editedProject.project_work_type !== 'n-a' && (
                <MuiTextField
                  fullWidth
                  label="Forecasted Hours/Month"
                  type="number"
                  value={editedProject.forecasted_hours_month || 0}
                  onChange={(e) => setEditedProject({
                    ...editedProject,
                    forecasted_hours_month: parseFloat(e.target.value) || 0
                  })}
                  sx={{ mb: 2 }}
                />
              )}

              <MuiTextField
                fullWidth
                label="Slack Channel"
                value={editedProject.slack_channel || ''}
                onChange={(e) => setEditedProject({
                  ...editedProject,
                  slack_channel: e.target.value
                })}
                placeholder="#project-channel"
                sx={{ mb: 2 }}
              />

              <FormControl fullWidth>
                <InputLabel>Weekly Meeting Day</InputLabel>
                <Select
                  value={editedProject.weekly_meeting_day || ''}
                  onChange={(e) => setEditedProject({
                    ...editedProject,
                    weekly_meeting_day: e.target.value
                  })}
                >
                  <MenuItem value="">None</MenuItem>
                  {weekdayOptions.map((day) => (
                    <MenuItem key={day} value={day}>{day}</MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Box>
          </Grid>

          {/* Project Stats */}
          <Grid item xs={12} md={6}>
            <Typography variant="h6" gutterBottom sx={{ color: 'primary.main', fontWeight: 'bold' }}>
              📊 Project Stats
            </Typography>

            <Box sx={{ mb: 3 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                <TimeIcon color="action" />
                <Typography variant="body1">
                  <strong>This Month:</strong> {(project.current_month_hours || 0).toFixed(1)}h
                </Typography>
              </Box>

              {project.project_work_type === 'project-based' && (
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                  <WorkIcon color="action" />
                  <Typography variant="body1">
                    <strong>Total Hours:</strong> {(project.cumulative_hours || 0).toFixed(1)}h
                  </Typography>
                </Box>
              )}

              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <PeopleIcon color="action" />
                <Typography variant="body1">
                  <strong>Type:</strong> {project.projectTypeKey || 'Unknown'}
                </Typography>
              </Box>
            </Box>
          </Grid>

          {/* Recent Meetings */}
          <Grid item xs={12} md={6}>
            <Box sx={{
              border: '1px solid',
              borderColor: 'divider',
              borderRadius: 2,
              p: 3,
              backgroundColor: 'background.paper',
              boxShadow: 1
            }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                <Typography variant="h6" sx={{ color: 'primary.main', fontWeight: 'bold' }}>
                  🎯 Recent Meetings
                </Typography>
                <FormControl size="small" sx={{ minWidth: 120 }}>
                  <InputLabel>Days</InputLabel>
                  <Select
                    value={dateFilter}
                    onChange={(e) => setDateFilter(e.target.value as '1' | '7' | '30')}
                    label="Days"
                  >
                    <MenuItem value="1">Last 1 day</MenuItem>
                    <MenuItem value="7">Last 7 days</MenuItem>
                    <MenuItem value="30">Last 30 days</MenuItem>
                  </Select>
                </FormControl>
              </Box>

            {loadingMeetings ? (
              <Box>
                {[...Array(3)].map((_, i) => (
                  <Skeleton key={i} variant="rectangular" height={40} sx={{ mb: 1 }} />
                ))}
              </Box>
            ) : recentMeetings.length === 0 ? (
              <Alert severity="info">
                No meetings found for this project in the last {dateFilter} day{dateFilter !== '1' ? 's' : ''}
              </Alert>
            ) : (
              <List dense>
                {recentMeetings.map((meeting: any, index) => (
                  <ListItem key={meeting.id || index}>
                    <ListItemIcon>
                      <TaskIcon fontSize="small" />
                    </ListItemIcon>
                    <ListItemText
                      primary={meeting.title || 'Untitled Meeting'}
                      secondary={
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          <Typography variant="body2" color="text.secondary">
                            {new Date(meeting.date).toLocaleDateString()}
                          </Typography>
                          {meeting.analyzed && (
                            <Chip label="Analyzed" size="small" color="success" />
                          )}
                        </Box>
                      }
                    />
                  </ListItem>
                ))}
              </List>
            )}
            </Box>
          </Grid>

          {/* Recent TODOs */}
          <Grid item xs={12} md={6}>
            <Box sx={{
              border: '1px solid',
              borderColor: 'divider',
              borderRadius: 2,
              p: 3,
              backgroundColor: 'background.paper',
              boxShadow: 1
            }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                <Typography variant="h6" sx={{ color: 'primary.main', fontWeight: 'bold' }}>
                  ✅ Recent TODOs
                </Typography>
                <MuiButton
                  size="small"
                  onClick={() => fetchTodos(project.key)}
                  disabled={loadingTodos}
                  startIcon={<RefreshIcon />}
                >
                  Refresh
                </MuiButton>
              </Box>

            {loadingTodos ? (
              <Box>
                {[...Array(3)].map((_, i) => (
                  <Skeleton key={i} variant="rectangular" height={40} sx={{ mb: 1 }} />
                ))}
              </Box>
            ) : recentTodos.length === 0 ? (
              <Alert severity="info">
                No recent TODOs found for this project
              </Alert>
            ) : (
              <List dense>
                {recentTodos.map((todo: any, index) => (
                  <ListItem key={todo.id || index}>
                    <ListItemIcon>
                      <TaskIcon fontSize="small" />
                    </ListItemIcon>
                    <ListItemText
                      primary={todo.title || 'Untitled TODO'}
                      secondary={
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          <Typography variant="body2" color="text.secondary">
                            Status: {todo.status || 'pending'}
                          </Typography>
                          {todo.due_date && (
                            <Typography variant="body2" color="text.secondary">
                              Due: {new Date(todo.due_date).toLocaleDateString()}
                            </Typography>
                          )}
                          {todo.ticket_key && (
                            <Chip label={todo.ticket_key} size="small" color="primary" />
                          )}
                        </Box>
                      }
                    />
                  </ListItem>
                ))}
              </List>
            )}
            </Box>
          </Grid>

          {/* Project Digest Generator */}
          <Grid item xs={12}>
            <Box sx={{
              border: '1px solid',
              borderColor: 'primary.main',
              borderRadius: 2,
              p: 3,
              backgroundColor: 'rgba(85, 77, 255, 0.08)',
              boxShadow: 2
            }}>
              <Typography variant="h6" sx={{ color: 'primary.main', fontWeight: 'bold', mb: 2 }}>
                📋 Client Meeting Digest Generator
              </Typography>

              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Generate a comprehensive project status report for client meetings, including progress summary,
                key achievements, blockers, and next steps.
              </Typography>

              <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', mb: 3 }}>
                <FormControl size="small" sx={{ minWidth: 120 }}>
                  <InputLabel>Time Period</InputLabel>
                  <Select
                    value={digestDays}
                    onChange={(e) => setDigestDays(e.target.value as '7' | '30')}
                    label="Time Period"
                  >
                    <MenuItem value="7">Last 7 days</MenuItem>
                    <MenuItem value="30">Last 30 days</MenuItem>
                  </Select>
                </FormControl>

                <MuiButton
                  variant="contained"
                  color="primary"
                  size="medium"
                  startIcon={<DigestIcon />}
                  onClick={generateDigest}
                  disabled={generatingDigest}
                  sx={{ textTransform: 'none' }}
                >
                  {generatingDigest ? 'Generating...' : 'Generate Digest'}
                </MuiButton>

                {digestData && (
                  <MuiButton
                    variant="outlined"
                    color="primary"
                    size="medium"
                    startIcon={<DownloadIcon />}
                    onClick={downloadDigest}
                    sx={{ textTransform: 'none' }}
                  >
                    Download as Markdown
                  </MuiButton>
                )}
              </Box>

              {/* Digest Results */}
              {digestData && (
                <Box sx={{
                  backgroundColor: 'background.paper',
                  border: '1px solid',
                  borderColor: 'divider',
                  borderRadius: 1,
                  p: 2,
                  mt: 2
                }}>
                  <Typography variant="h6" gutterBottom>
                    📊 Generated Digest Summary
                  </Typography>

                  <Grid container spacing={2}>
                    <Grid item xs={6} sm={3}>
                      <Box sx={{ textAlign: 'center', p: 1 }}>
                        <Typography variant="h4" color="primary.main">
                          {digestData.activity_data.meetings_count}
                        </Typography>
                        <Typography variant="caption">Meetings</Typography>
                      </Box>
                    </Grid>
                    <Grid item xs={6} sm={3}>
                      <Box sx={{ textAlign: 'center', p: 1 }}>
                        <Typography variant="h4" color="success.main">
                          {digestData.activity_data.tickets_completed}
                        </Typography>
                        <Typography variant="caption">Completed</Typography>
                      </Box>
                    </Grid>
                    <Grid item xs={6} sm={3}>
                      <Box sx={{ textAlign: 'center', p: 1 }}>
                        <Typography variant="h4" color="info.main">
                          {digestData.activity_data.tickets_created}
                        </Typography>
                        <Typography variant="caption">New Tickets</Typography>
                      </Box>
                    </Grid>
                    <Grid item xs={6} sm={3}>
                      <Box sx={{ textAlign: 'center', p: 1 }}>
                        <Typography variant="h4" color="warning.main">
                          {digestData.activity_data.hours_logged.toFixed(1)}h
                        </Typography>
                        <Typography variant="caption">Hours Logged</Typography>
                      </Box>
                    </Grid>
                  </Grid>

                  {digestData.activity_data.progress_summary && (
                    <Box sx={{ mt: 2 }}>
                      <Typography variant="body2" sx={{ fontStyle: 'italic' }}>
                        "{digestData.activity_data.progress_summary}"
                      </Typography>
                    </Box>
                  )}
                </Box>
              )}

              {/* Full Digest Content Display */}
              {digestData && digestData.formatted_agenda && (
                <Box sx={{
                  backgroundColor: 'background.paper',
                  border: '1px solid',
                  borderColor: 'divider',
                  borderRadius: 1,
                  p: 2,
                  mt: 3
                }}>
                  <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    📄 Complete Digest
                    <MuiButton
                      size="small"
                      variant="outlined"
                      startIcon={<DownloadIcon />}
                      onClick={downloadDigest}
                      sx={{ ml: 'auto', textTransform: 'none' }}
                    >
                      Download MD
                    </MuiButton>
                  </Typography>

                  <Box sx={{
                    backgroundColor: '#f8f9fa',
                    border: '1px solid #e9ecef',
                    borderRadius: 1,
                    p: 3,
                    maxHeight: '600px',
                    overflow: 'auto',
                    '& h1': { fontSize: '1.75rem', fontWeight: 600, mt: 2, mb: 2, color: '#2c3e50' },
                    '& h2': { fontSize: '1.5rem', fontWeight: 600, mt: 2, mb: 1.5, color: '#34495e', borderBottom: '2px solid #e9ecef', pb: 1 },
                    '& h3': { fontSize: '1.25rem', fontWeight: 600, mt: 2, mb: 1, color: '#34495e' },
                    '& h4': { fontSize: '1.1rem', fontWeight: 600, mt: 1.5, mb: 1, color: '#34495e' },
                    '& p': { mb: 1.5, lineHeight: 1.7, color: '#495057' },
                    '& ul, & ol': { pl: 3, mb: 2 },
                    '& li': { mb: 0.75, lineHeight: 1.6, color: '#495057' },
                    '& strong': { fontWeight: 600, color: '#2c3e50' },
                    '& em': { fontStyle: 'italic' },
                    '& code': {
                      backgroundColor: '#e9ecef',
                      padding: '2px 6px',
                      borderRadius: '3px',
                      fontSize: '0.9em',
                      fontFamily: 'monospace',
                      color: '#c7254e'
                    },
                    '& pre': {
                      backgroundColor: '#f5f5f5',
                      p: 2,
                      borderRadius: 1,
                      overflow: 'auto',
                      border: '1px solid #ddd'
                    },
                    '& blockquote': {
                      borderLeft: '4px solid #554DFF',
                      pl: 2,
                      ml: 0,
                      fontStyle: 'italic',
                      color: '#6c757d'
                    },
                    '& a': { color: '#554DFF', textDecoration: 'none', '&:hover': { textDecoration: 'underline' } },
                    '& hr': { border: 'none', borderTop: '1px solid #dee2e6', my: 2 }
                  }}>
                    <ReactMarkdown>{digestData.formatted_agenda}</ReactMarkdown>
                  </Box>
                </Box>
              )}
            </Box>
          </Grid>
        </Grid>
      </DialogContent>

      <DialogActions>
        <MuiButton onClick={onClose}>
          Cancel
        </MuiButton>
        <MuiButton onClick={handleSave} variant="contained" color="primary">
          Save Changes
        </MuiButton>
      </DialogActions>
    </Dialog>
  );
};

const MonthlyForecastsPanel = ({ activeProjects }: { activeProjects: Project[] }) => {
  const notify = useNotify();
  const [forecasts, setForecasts] = useState<{[projectKey: string]: any[]}>({});
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [editedForecasts, setEditedForecasts] = useState<{[projectKey: string]: any[]}>({});
  const [monthHeaders, setMonthHeaders] = useState<string[]>([]);

  // Load forecasts when tab becomes active
  useEffect(() => {
    if (activeProjects.length > 0) {
      loadForecasts();
    }
  }, [activeProjects]);

  const loadForecasts = async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem('auth_token');
      const projectKeys = activeProjects.map(p => p.key);

      // Batch request for all projects
      const response = await fetch(`${API_BASE_URL}/api/jira/project-forecasts/batch`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ project_keys: projectKeys }),
      });

      if (response.ok) {
        const data = await response.json();
        const forecastData = data.data.forecasts;

        // Get month headers from first project with data
        let headers: string[] = [];
        for (const projectKey of projectKeys) {
          if (forecastData[projectKey] && forecastData[projectKey].length > 0) {
            headers = forecastData[projectKey].map((f: any) => getMonthName(f.month_year));
            break;
          }
        }

        setMonthHeaders(headers);
        setForecasts(forecastData);
        setEditedForecasts(JSON.parse(JSON.stringify(forecastData))); // Deep copy
      } else {
        notify('Error loading forecasts', { type: 'error' });
      }
    } catch (error) {
      notify('Error loading forecasts', { type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  const handleForecastChange = (projectKey: string, monthIndex: number, value: string) => {
    const updated = { ...editedForecasts };
    if (!updated[projectKey]) return;

    updated[projectKey] = [...updated[projectKey]];
    updated[projectKey][monthIndex] = {
      ...updated[projectKey][monthIndex],
      forecasted_hours: parseFloat(value) || 0
    };

    setEditedForecasts(updated);
  };

  const hasAnyChanges = () => {
    return JSON.stringify(forecasts) !== JSON.stringify(editedForecasts);
  };

  const handleSaveAll = async () => {
    setSaving(true);
    try {
      const token = localStorage.getItem('auth_token');
      const promises = activeProjects.map(async (project) => {
        const response = await fetch(`${API_BASE_URL}/api/jira/project-forecasts/${project.key}`, {
          method: 'PUT',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            forecasts: editedForecasts[project.key]
          })
        });
        return response.ok;
      });

      const results = await Promise.all(promises);

      if (results.every(r => r)) {
        notify('All forecasts saved successfully', { type: 'success' });
        setForecasts(JSON.parse(JSON.stringify(editedForecasts)));
      } else {
        notify('Some forecasts failed to save', { type: 'error' });
      }
    } catch (error) {
      notify('Error saving forecasts', { type: 'error' });
    } finally {
      setSaving(false);
    }
  };

  const getMonthName = (monthYear: string) => {
    // Parse ISO date string (YYYY-MM-DD) without timezone issues
    const [year, month] = monthYear.split('-').map(Number);
    const date = new Date(year, month - 1, 1); // month is 0-indexed
    return date.toLocaleString('default', { month: 'short', year: 'numeric' });
  };

  if (loading) {
    return <CircularProgress />;
  }

  if (activeProjects.length === 0) {
    return (
      <Alert severity="info">
        No active projects found. Please activate projects in the "All Projects" tab to manage forecasts.
      </Alert>
    );
  }

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Alert severity="info" sx={{ flex: 1, mr: 2 }}>
          Manage forecasted hours for the next 6 months for active projects.
        </Alert>
        <MuiButton
          variant="contained"
          size="medium"
          color="primary"
          disabled={!hasAnyChanges() || saving}
          onClick={handleSaveAll}
          startIcon={saving ? <CircularProgress size={16} /> : null}
          sx={{ minWidth: '150px' }}
        >
          {saving ? 'Saving...' : 'Save All'}
        </MuiButton>
      </Box>

      <TableContainer component={Paper}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell sx={{ fontWeight: 'bold', minWidth: '200px' }}>Project</TableCell>
              {monthHeaders.map((month, idx) => (
                <TableCell key={idx} sx={{ fontWeight: 'bold', textAlign: 'center', minWidth: '120px' }}>
                  {month}
                </TableCell>
              ))}
            </TableRow>
          </TableHead>
          <TableBody>
            {activeProjects.map((project) => (
              <TableRow key={project.key}>
                <TableCell>
                  <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                    {project.name}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    {project.key}
                  </Typography>
                </TableCell>
                {editedForecasts[project.key]?.map((forecast, monthIndex) => (
                  <TableCell key={monthIndex} sx={{ textAlign: 'center' }}>
                    <input
                      type="number"
                      value={forecast.forecasted_hours}
                      onChange={(e) => handleForecastChange(project.key, monthIndex, e.target.value)}
                      style={{
                        width: '80px',
                        padding: '6px',
                        border: hasAnyChanges() ? '2px solid #ff9800' : '1px solid #ccc',
                        borderRadius: '4px',
                        backgroundColor: hasAnyChanges() ? '#fff3e0' : 'white',
                        textAlign: 'center'
                      }}
                      step="0.5"
                      min="0"
                    />
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </Box>
  );
};

export const ProjectList = () => {
  const notify = useNotify();
  const dataProvider = useDataProvider();
  const [tabValue, setTabValue] = useState(0);
  const [allProjects, setAllProjects] = useState<Project[]>([]);
  const [activeProjects, setActiveProjects] = useState<Project[]>([]);
  const [watchedProjects, setWatchedProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [selectedProject, setSelectedProject] = useState<Project | null>(null);
  const [projectDetailOpen, setProjectDetailOpen] = useState(false);
  const [pendingChanges, setPendingChanges] = useState<{[key: string]: Partial<Project>}>({});

  // Resource mappings state
  const [resourceMappings, setResourceMappings] = useState<{[projectKey: string]: {
    slack_channel_ids: string[];
    notion_page_ids: string[];
    github_repos: string[];
    jira_project_keys: string[];
  }}>({});

  // Todo counts state
  const [todoCounts, setTodoCounts] = useState<{[projectKey: string]: number}>({});

  // Monthly hours state
  const [monthlyHours, setMonthlyHours] = useState<{[projectKey: string]: number}>({});

  // Navigation
  const redirect = useRedirect();

  const loadWatchedProjects = useCallback(async (activeProjects: Project[]) => {
    try {
      const token = localStorage.getItem('auth_token');
      if (!token) return;

      const response = await fetch(`${API_BASE_URL}/api/watched-projects`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (response.ok) {
        const data = await response.json();
        const watchedProjectKeys = data.watched_projects;
        const watched = activeProjects.filter((p: Project) => watchedProjectKeys.includes(p.key));
        setWatchedProjects(watched);
      } else if (response.status === 401) {
        // Silently handle auth errors - user may not be logged in yet
      } else {
        // Silently handle other errors to prevent retry loops
      }
    } catch (error) {
      // Silently handle errors to prevent infinite retry loop
    }
  }, []);

  const fetchProjects = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await dataProvider.getList('jira_projects', {
        pagination: { page: 1, perPage: 200 },
        sort: { field: 'name', order: 'ASC' },
        filter: {},
      });
      setAllProjects(data);

      // Filter active projects from local DB
      const active = data.filter((p: Project) => p.is_active === true);
      setActiveProjects(active);

      // Load watched projects from API
      await loadWatchedProjects(active);

      // Load resource mappings, todo counts, and monthly hours
      await loadResourceMappings();
      await loadTodoCounts();
      await loadMonthlyHours();
    } catch (error) {
      notify('Error fetching projects', { type: 'error' });
    } finally {
      setLoading(false);
    }
  }, [dataProvider, notify, loadWatchedProjects]);

  const loadResourceMappings = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/project-resource-mappings`);
      if (response.ok) {
        const data = await response.json();
        if (data.success) {
          const mappingsMap: any = {};
          data.mappings.forEach((mapping: any) => {
            mappingsMap[mapping.project_key] = {
              slack_channel_ids: mapping.slack_channel_ids || [],
              notion_page_ids: mapping.notion_page_ids || [],
              github_repos: mapping.github_repos || [],
              jira_project_keys: mapping.jira_project_keys || []
            };
          });
          setResourceMappings(mappingsMap);
        }
      }
    } catch (error) {
      // Silently fail - mappings are optional
    }
  };

  const loadTodoCounts = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/projects/todo-counts`);
      if (response.ok) {
        const data = await response.json();
        if (data.success) {
          setTodoCounts(data.counts || {});
        }
      }
    } catch (error) {
      // Silently fail - todo counts are optional
    }
  };

  const loadMonthlyHours = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/projects/monthly-hours`);
      if (response.ok) {
        const data = await response.json();
        if (data.success) {
          setMonthlyHours(data.monthly_hours || {});
        }
      }
    } catch (error) {
      // Silently fail - monthly hours are optional
    }
  };

  const handleResourceMappingChange = async (
    projectKey: string,
    projectName: string,
    resourceType: 'slack' | 'notion' | 'github' | 'jira',
    newValues: string[]
  ) => {
    // Update local state immediately
    const updated = {
      ...resourceMappings,
      [projectKey]: {
        ...resourceMappings[projectKey],
        slack_channel_ids: resourceType === 'slack' ? newValues : (resourceMappings[projectKey]?.slack_channel_ids || []),
        notion_page_ids: resourceType === 'notion' ? newValues : (resourceMappings[projectKey]?.notion_page_ids || []),
        github_repos: resourceType === 'github' ? newValues : (resourceMappings[projectKey]?.github_repos || []),
        jira_project_keys: resourceType === 'jira' ? newValues : (resourceMappings[projectKey]?.jira_project_keys || [])
      }
    };
    setResourceMappings(updated);

    // Save to backend
    try {
      const response = await fetch(`${API_BASE_URL}/api/project-resource-mappings/${projectKey}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          project_name: projectName,
          ...updated[projectKey]
        })
      });

      if (response.ok) {
        notify('Resource mapping updated', { type: 'success' });
      } else {
        throw new Error('Failed to update resource mapping');
      }
    } catch (error) {
      notify('Error updating resource mapping', { type: 'error' });
      // Reload mappings to restore previous state
      loadResourceMappings();
    }
  };

  useEffect(() => {
    fetchProjects();
  }, [fetchProjects]);

  useEffect(() => {
    // Listen for changes to watched projects
    const handleWatchedProjectsChange = () => {
      if (activeProjects.length > 0) {
        loadWatchedProjects(activeProjects);
      }
    };

    window.addEventListener('watchedProjectsChanged', handleWatchedProjectsChange);
    return () => {
      window.removeEventListener('watchedProjectsChanged', handleWatchedProjectsChange);
    };
  }, [activeProjects, loadWatchedProjects]);

  const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
    setTabValue(newValue);
  };

  const handleCardClick = (project: Project) => {
    setSelectedProject(project);
    setProjectDetailOpen(true);
  };

  const handleProjectDetailSave = async (project: Project) => {
    try {
      await dataProvider.update('jira_projects', {
        id: project.key,
        data: project,
        previousData: project,
      });

      notify(`Project ${project.name} updated successfully`, { type: 'success' });
      fetchProjects(); // Refresh the data
    } catch (error) {
      notify('Error updating project', { type: 'error' });
    }
  };

  const handleActiveToggle = async (project: Project) => {
    try {
      const updatedProject = {
        ...project,
        is_active: !project.is_active,
      };

      // Update in database
      await dataProvider.update('jira_projects', {
        id: project.key,
        data: updatedProject,
        previousData: project,
      });

      notify(`Project ${project.name} is now ${updatedProject.is_active ? 'active' : 'inactive'}`, { type: 'success' });
      fetchProjects();
    } catch (error) {
      notify('Error updating project status', { type: 'error' });
    }
  };

  const handleProjectSave = async (project: Project) => {
    try {
      await dataProvider.update('jira_projects', {
        id: project.key,
        data: project,
        previousData: project,
      });

      notify(`Project ${project.name} updated successfully`, { type: 'success' });
      fetchProjects();
    } catch (error) {
      notify('Error updating project', { type: 'error' });
    }
  };

  const handleSyncHours = async () => {
    setSyncing(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/sync-hours`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (response.ok) {
        const result = await response.json();
        notify(`Hours synced successfully: ${result.projects_updated} projects updated`, { type: 'success' });
        fetchProjects(); // Refresh the data
      } else {
        throw new Error('Failed to sync hours');
      }
    } catch (error) {
      notify('Error syncing hours. Please try again.', { type: 'error' });
    } finally {
      setSyncing(false);
    }
  };

  // Helper functions for manual save functionality
  const handleFieldChange = (projectKey: string, field: string, value: string) => {
    setPendingChanges(prev => ({
      ...prev,
      [projectKey]: {
        ...prev[projectKey],
        [field]: value
      }
    }));
  };

  const handleRowSave = async (projectKey: string) => {
    const changes = pendingChanges[projectKey];
    if (!changes) return;

    const project = activeProjects.find(p => p.key === projectKey);
    if (!project) return;

    const updatedProject = { ...project, ...changes };
    await handleProjectSave(updatedProject);

    // Clear pending changes for this project
    setPendingChanges(prev => {
      const newState = { ...prev };
      delete newState[projectKey];
      return newState;
    });
  };

  const getProjectValue = (project: Project, field: string): string => {
    return pendingChanges[project.key]?.[field] || project[field] || '';
  };

  const hasUnsavedChanges = (projectKey: string): boolean => {
    return Boolean(pendingChanges[projectKey] && Object.keys(pendingChanges[projectKey]).length > 0);
  };

  return (
    <Box>
      <WatchedProjectsHeader />

      <Card>
        <CardContent>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
            <Typography variant="h5">
              🏢 Project Management
            </Typography>
            <Button
              variant="outlined"
              color="primary"
              size="small"
              startIcon={syncing ? <CircularProgress size={16} /> : <SyncIcon />}
              onClick={handleSyncHours}
              disabled={syncing}
              sx={{ textTransform: 'none' }}
            >
              {syncing ? 'Syncing Current Month...' : 'Sync Hours'}
            </Button>
          </Box>

          <Tabs value={tabValue} onChange={handleTabChange}>
            <Tab label={`📌 My Projects (${watchedProjects.length})`} />
            <Tab label={`⚙️ Active Projects (${activeProjects.length})`} />
            <Tab label={`📋 All Projects (${allProjects.length})`} />
            <Tab label="📊 Monthly Forecasts" />
          </Tabs>

          <TabPanel value={tabValue} index={0}>
            {/* My Projects - Table View */}
            {watchedProjects.length === 0 ? (
              <Alert severity="info" sx={{ mb: 3 }}>
                <Typography variant="h6" gutterBottom>
                  No projects being watched yet! 👀
                </Typography>
                <Typography variant="body2">
                  Switch to the "Active Projects" tab and use the watch toggles to select projects you want to follow.
                </Typography>
              </Alert>
            ) : (
              <TableContainer component={Paper}>
                <Table>
                  <TableHead>
                    <TableRow>
                      <TableCell>Name</TableCell>
                      <TableCell>Type</TableCell>
                      <TableCell>Hours</TableCell>
                      <TableCell>Meeting Day</TableCell>
                      <TableCell># of TODOs</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {watchedProjects.map((project) => {
                      const projectType = project.project_work_type || 'project-based';
                      const todoCount = todoCounts[project.key] || 0;

                      // Determine current and forecasted hours based on project type
                      let currentHours = 0;
                      let forecastedHours = 0;

                      if (projectType === 'growth-support') {
                        // Retainer projects: use monthly hours
                        currentHours = monthlyHours[project.key] || 0;
                        forecastedHours = project.retainer_hours || 0;
                      } else if (projectType === 'project-based') {
                        // Project-based: use cumulative hours
                        currentHours = project.cumulative_hours || 0;
                        forecastedHours = project.total_hours || 0;
                      }

                      // Helper function to get color based on usage percentage
                      const getHoursColor = () => {
                        if (projectType === 'n-a') return 'text.primary';
                        if (!forecastedHours || forecastedHours === 0) return 'success.main';
                        const percentage = (currentHours / forecastedHours) * 100;
                        if (percentage > 100) return 'error.main';
                        if (percentage > 80) return 'warning.main';
                        return 'success.main';
                      };

                      const getTypeLabel = (type: string) => {
                        switch (type) {
                          case 'project-based': return 'Project-based';
                          case 'growth-support': return 'Growth & Support';
                          case 'n-a': return 'N/A';
                          default: return 'Other';
                        }
                      };

                      return (
                        <TableRow
                          key={project.key}
                          sx={{
                            cursor: 'pointer',
                            '&:hover': {
                              backgroundColor: 'rgba(85, 77, 255, 0.08)'
                            }
                          }}
                          onClick={() => redirect('show', 'projects', project.key)}
                        >
                          <TableCell>
                            <Typography variant="body2" fontWeight="medium">
                              {project.name}
                            </Typography>
                            <Typography variant="caption" color="text.secondary">
                              {project.key}
                            </Typography>
                          </TableCell>
                          <TableCell>{getTypeLabel(projectType)}</TableCell>
                          <TableCell>
                            <Typography
                              variant="body2"
                              sx={{ color: getHoursColor(), fontWeight: 'medium' }}
                            >
                              {currentHours.toFixed(1)} / {forecastedHours.toFixed(1)}h
                            </Typography>
                            {forecastedHours > 0 && (
                              <Typography variant="caption" color="text.secondary">
                                ({((currentHours / forecastedHours) * 100).toFixed(0)}%)
                              </Typography>
                            )}
                          </TableCell>
                          <TableCell>
                            {project.weekly_meeting_day || '-'}
                          </TableCell>
                          <TableCell>
                            <Chip
                              label={todoCount}
                              size="small"
                              color={todoCount > 0 ? 'primary' : 'default'}
                            />
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </TableContainer>
            )}
          </TabPanel>

          <TabPanel value={tabValue} index={1}>
            {/* Group active projects by type */}
            {['project-based', 'growth-support', 'n-a'].map((workType) => {
              const projectsInType = activeProjects.filter(project =>
                (project.project_work_type || 'project-based') === workType
              );

              if (projectsInType.length === 0) return null;

              const getTypeLabel = (type: string) => {
                switch (type) {
                  case 'project-based': return 'Project-based Projects';
                  case 'growth-support': return 'Growth & Support Projects';
                  case 'n-a': return 'N/A Projects';
                  default: return 'Other Projects';
                }
              };

              // Get current month name
              const currentMonth = new Date().toLocaleString('default', { month: 'long' });

              // Helper function to get color based on usage percentage
              const getHoursColor = (currentHours: number, forecastedHours: number, projectType: string) => {
                // No color coding for N/A projects - use default text color
                if (projectType === 'n-a') return 'text.primary';

                if (!forecastedHours || forecastedHours === 0) return 'success.main'; // Green by default
                const percentage = (currentHours / forecastedHours) * 100;
                if (percentage > 100) return 'error.main'; // Red if over
                if (percentage > 80) return 'warning.main'; // Yellow if above 80%
                return 'success.main'; // Green by default
              };

              return (
                <Box key={workType} sx={{ mb: 4 }}>
                  <Typography
                    variant="h6"
                    sx={{
                      mb: 2,
                      pb: 1,
                      borderBottom: '2px solid',
                      borderBottomColor: 'primary.main',
                      color: 'primary.main',
                      fontWeight: 'bold'
                    }}
                  >
                    {getTypeLabel(workType)} ({projectsInType.length})
                  </Typography>

                  <TableContainer component={Paper}>
                    <Table>
                      <TableHead>
                        <TableRow>
                          <TableCell>Project Name</TableCell>
                          <TableCell>Key</TableCell>
                          <TableCell>Type</TableCell>
                          <TableCell>Project Type</TableCell>
                          <TableCell>Slack Channels</TableCell>
                          <TableCell>Notion Pages</TableCell>
                          <TableCell>GitHub Repos</TableCell>
                          <TableCell>Jira Projects</TableCell>
                          {workType === 'project-based' && <TableCell>{currentMonth} Forecast</TableCell>}
                          {workType === 'growth-support' && <TableCell>Retainer Hours</TableCell>}
                          <TableCell>{currentMonth} Hours</TableCell>
                          {workType === 'project-based' && <TableCell>Total Hours</TableCell>}
                          {workType === 'project-based' && <TableCell>Cumulative Hours</TableCell>}
                          <TableCell>Watch</TableCell>
                          <TableCell>Save</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {projectsInType.map((project) => {
                          // Check if this project is being watched
                          const watchedProjects = JSON.parse(localStorage.getItem('watchedProjects') || '[]');
                          const isWatched = watchedProjects.includes(project.key);

                          return (
                          <TableRow
                            key={project.key}
                            sx={{
                              backgroundColor: isWatched ? 'rgba(85, 77, 255, 0.08)' : 'inherit', // Light purple background for watched projects
                              '&:hover': {
                                backgroundColor: isWatched ? 'rgba(85, 77, 255, 0.12)' : 'rgba(0, 0, 0, 0.04)'
                              }
                            }}
                          >
                            <TableCell>{project.name}</TableCell>
                            <TableCell>
                              <Chip label={project.key} size="small" />
                            </TableCell>
                            <TableCell>{project.projectTypeKey || 'Unknown'}</TableCell>
                            <TableCell>
                              <FormControl size="small" fullWidth>
                                <Select
                                  value={project.project_work_type || 'project-based'}
                                  onChange={(e) => {
                                    const updatedProject = { ...project, project_work_type: e.target.value as 'project-based' | 'growth-support' | 'n-a' };
                                    handleProjectSave(updatedProject);
                                  }}
                                >
                                  <MenuItem value="project-based">Project-based</MenuItem>
                                  <MenuItem value="growth-support">Growth & Support</MenuItem>
                                  <MenuItem value="n-a">N/A</MenuItem>
                                </Select>
                              </FormControl>
                            </TableCell>
                            <TableCell sx={{ minWidth: 180 }}>
                              <ResourceMappingCell
                                projectKey={project.key}
                                resourceType="slack"
                                values={resourceMappings[project.key]?.slack_channel_ids || []}
                                onChange={(newValues) => handleResourceMappingChange(project.key, project.name, 'slack', newValues)}
                              />
                            </TableCell>
                            <TableCell sx={{ minWidth: 180 }}>
                              <ResourceMappingCell
                                projectKey={project.key}
                                resourceType="notion"
                                values={resourceMappings[project.key]?.notion_page_ids || []}
                                onChange={(newValues) => handleResourceMappingChange(project.key, project.name, 'notion', newValues)}
                              />
                            </TableCell>
                            <TableCell sx={{ minWidth: 180 }}>
                              <ResourceMappingCell
                                projectKey={project.key}
                                resourceType="github"
                                values={resourceMappings[project.key]?.github_repos || []}
                                onChange={(newValues) => handleResourceMappingChange(project.key, project.name, 'github', newValues)}
                              />
                            </TableCell>
                            <TableCell sx={{ minWidth: 180 }}>
                              <ResourceMappingCell
                                projectKey={project.key}
                                resourceType="jira"
                                values={resourceMappings[project.key]?.jira_project_keys || []}
                                onChange={(newValues) => handleResourceMappingChange(project.key, project.name, 'jira', newValues)}
                              />
                            </TableCell>
                            {(workType === 'project-based' || workType === 'growth-support') && (
                              <TableCell>
                                <Typography variant="body2" sx={{ fontWeight: 'medium' }}>
                                  {project.forecasted_hours_month !== undefined && project.forecasted_hours_month > 0
                                    ? `${project.forecasted_hours_month.toFixed(1)}h`
                                    : '-'}
                                </Typography>
                              </TableCell>
                            )}
                            <TableCell>
                              <Typography
                                variant="body2"
                                sx={{
                                  fontWeight: 'bold',
                                  color: getHoursColor(project.current_month_hours || 0, project.forecasted_hours_month || 0, workType)
                                }}
                              >
                                {`${(project.current_month_hours || 0).toFixed(1)}h`}
                              </Typography>
                            </TableCell>
                            {workType === 'project-based' && (
                              <TableCell>
                                <input
                                  type="number"
                                  value={getProjectValue(project, 'total_hours')}
                                  onChange={(e) => {
                                    handleFieldChange(project.key, 'total_hours', e.target.value);
                                  }}
                                  style={{
                                    width: '80px',
                                    padding: '4px',
                                    border: hasUnsavedChanges(project.key) ? '2px solid #ff9800' : '1px solid #ccc',
                                    borderRadius: '4px',
                                    backgroundColor: hasUnsavedChanges(project.key) ? '#fff3e0' : 'white'
                                  }}
                                  step="0.1"
                                  min="0"
                                />
                              </TableCell>
                            )}
                            {workType === 'project-based' && (
                              <TableCell>
                                <Typography variant="body2" sx={{ fontWeight: 'medium' }}>
                                  {`${(project.cumulative_hours || 0).toFixed(1)}h`}
                                </Typography>
                              </TableCell>
                            )}
                            <TableCell>
                              <WatchToggle record={project} />
                            </TableCell>
                            <TableCell>
                              <MuiButton
                                variant="contained"
                                size="small"
                                color="primary"
                                disabled={!hasUnsavedChanges(project.key)}
                                onClick={() => handleRowSave(project.key)}
                                sx={{
                                  minWidth: '60px',
                                  fontSize: '0.75rem',
                                  textTransform: 'none'
                                }}
                              >
                                Save
                              </MuiButton>
                            </TableCell>
                          </TableRow>
                          );
                        })}
                      </TableBody>
                    </Table>
                  </TableContainer>
                </Box>
              );
            })}
          </TabPanel>

          <TabPanel value={tabValue} index={2}>
            <Alert severity="info" sx={{ mb: 2 }}>
              Toggle the "Active" switch to sync projects to local database and enable additional fields.
            </Alert>

            <TableContainer component={Paper}>
              <Table>
                <TableHead>
                  <TableRow>
                    <TableCell>Project Name</TableCell>
                    <TableCell>Key</TableCell>
                    <TableCell>Type</TableCell>
                    <TableCell>Status</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {allProjects.map((project) => (
                    <TableRow key={project.key}>
                      <TableCell>{project.name}</TableCell>
                      <TableCell>
                        <Chip label={project.key} size="small" />
                      </TableCell>
                      <TableCell>{project.projectTypeKey || 'Unknown'}</TableCell>
                      <TableCell>
                        <ActiveToggle record={project} onToggle={handleActiveToggle} />
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </TabPanel>

          <TabPanel value={tabValue} index={3}>
            <MonthlyForecastsPanel activeProjects={activeProjects} />
          </TabPanel>
        </CardContent>
      </Card>

      <ProjectDetailDialog
        project={selectedProject}
        open={projectDetailOpen}
        onClose={() => setProjectDetailOpen(false)}
        onSave={handleProjectDetailSave}
      />
    </Box>
  );
};

const ProjectShowActions = () => (
  <TopToolbar>
    <EditButton />
  </TopToolbar>
);

const ProjectShowContent = () => {
  const record = useRecordContext();
  const notify = useNotify();
  const [keywords, setKeywords] = useState<string[]>([]);
  const [loadingKeywords, setLoadingKeywords] = useState(false);
  const [editingKeywords, setEditingKeywords] = useState(false);
  const [keywordInput, setKeywordInput] = useState('');

  // Load keywords when component mounts
  useEffect(() => {
    if (record?.key) {
      loadKeywords();
    }
  }, [record?.key]);

  const loadKeywords = async () => {
    if (!record?.key) return;

    setLoadingKeywords(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/projects/${record.key}/keywords`);
      if (response.ok) {
        const data = await response.json();
        setKeywords(data.keywords || []);
      }
    } catch (error) {
      // Silently fail
    } finally {
      setLoadingKeywords(false);
    }
  };

  const handleAddKeyword = () => {
    const trimmed = keywordInput.trim().toLowerCase();
    if (trimmed && !keywords.includes(trimmed)) {
      setKeywords([...keywords, trimmed]);
      setKeywordInput('');
    }
  };

  const handleRemoveKeyword = (keyword: string) => {
    setKeywords(keywords.filter(k => k !== keyword));
  };

  const handleSaveKeywords = async () => {
    setLoadingKeywords(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/projects/${record.key}/keywords`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ keywords })
      });

      if (response.ok) {
        notify('Keywords updated successfully', { type: 'success' });
        setEditingKeywords(false);
      } else {
        throw new Error('Failed to update keywords');
      }
    } catch (error) {
      notify('Error updating keywords', { type: 'error' });
    } finally {
      setLoadingKeywords(false);
    }
  };

  if (!record) return null;

  return (
    <Box sx={{ p: 3 }}>
        <Grid container spacing={3}>
          {/* Project Information */}
          <Grid item xs={12} md={6}>
            <Card sx={{ height: '100%' }}>
              <CardContent>
                <Typography variant="h6" sx={{ mb: 2, fontWeight: 600 }}>
                  Project Information
                </Typography>
                <Divider sx={{ mb: 2 }} />

                <Box sx={{ mb: 2 }}>
                  <Typography variant="caption" color="text.secondary">
                    Project Key
                  </Typography>
                  <Typography variant="body1" sx={{ fontWeight: 500 }}>
                    {record.key}
                  </Typography>
                </Box>

                <Box sx={{ mb: 2 }}>
                  <Typography variant="caption" color="text.secondary">
                    Project Name
                  </Typography>
                  <Typography variant="body1">
                    {record.name || 'N/A'}
                  </Typography>
                </Box>

                <Box sx={{ mb: 2 }}>
                  <Typography variant="caption" color="text.secondary">
                    Description
                  </Typography>
                  <Typography variant="body1">
                    {record.description || 'No description'}
                  </Typography>
                </Box>

                <Box sx={{ mb: 2 }}>
                  <Typography variant="caption" color="text.secondary">
                    Work Type
                  </Typography>
                  <Typography variant="body1">
                    {record.project_work_type || 'N/A'}
                  </Typography>
                </Box>

                <Box>
                  <Typography variant="caption" color="text.secondary">
                    Weekly Meeting Day
                  </Typography>
                  <Typography variant="body1">
                    {record.weekly_meeting_day || 'Not set'}
                  </Typography>
                </Box>
              </CardContent>
            </Card>
          </Grid>

          {/* Hours & Forecasting */}
          <Grid item xs={12} md={6}>
            <Card sx={{ height: '100%' }}>
              <CardContent>
                <Typography variant="h6" sx={{ mb: 2, fontWeight: 600 }}>
                  Hours & Forecasting
                </Typography>
                <Divider sx={{ mb: 2 }} />

                <Box sx={{ mb: 2 }}>
                  <Typography variant="caption" color="text.secondary">
                    Forecasted Hours/Month
                  </Typography>
                  <Typography variant="body1" sx={{ fontWeight: 500 }}>
                    {record.forecasted_hours_month || 0} hours
                  </Typography>
                </Box>

                <Box sx={{ mb: 2 }}>
                  <Typography variant="caption" color="text.secondary">
                    Total Hours
                  </Typography>
                  <Typography variant="body1">
                    {record.total_hours || 0} hours
                  </Typography>
                </Box>

                <Box sx={{ mb: 2 }}>
                  <Typography variant="caption" color="text.secondary">
                    Current Month Hours
                  </Typography>
                  <Typography variant="body1">
                    {record.current_month_hours || 0} hours
                  </Typography>
                </Box>

                <Box>
                  <Typography variant="caption" color="text.secondary">
                    Cumulative Hours
                  </Typography>
                  <Typography variant="body1">
                    {record.cumulative_hours || 0} hours
                  </Typography>
                </Box>
              </CardContent>
            </Card>
          </Grid>

          {/* Resource Mappings */}
          <Grid item xs={12}>
            <Card>
              <CardContent>
                <Typography variant="h6" sx={{ mb: 2, fontWeight: 600 }}>
                  Resource Mappings
                </Typography>
                <Divider sx={{ mb: 2 }} />

                <Grid container spacing={2}>
                  <Grid item xs={12} md={6}>
                    <Box sx={{ mb: 2 }}>
                      <Typography variant="caption" color="text.secondary">
                        Jira Projects
                      </Typography>
                      <Typography variant="body1">
                        {record.jira_project_keys ? (typeof record.jira_project_keys === 'string' ? JSON.parse(record.jira_project_keys).join(', ') : record.jira_project_keys.join(', ')) : 'None'}
                      </Typography>
                    </Box>

                    <Box sx={{ mb: 2 }}>
                      <Typography variant="caption" color="text.secondary">
                        Slack Channels
                      </Typography>
                      <Typography variant="body1">
                        {record.slack_channel_ids ? (typeof record.slack_channel_ids === 'string' ? JSON.parse(record.slack_channel_ids).join(', ') : record.slack_channel_ids.join(', ')) : 'None'}
                      </Typography>
                    </Box>
                  </Grid>

                  <Grid item xs={12} md={6}>
                    <Box sx={{ mb: 2 }}>
                      <Typography variant="caption" color="text.secondary">
                        Notion Pages
                      </Typography>
                      <Typography variant="body1">
                        {record.notion_page_ids ? (typeof record.notion_page_ids === 'string' ? JSON.parse(record.notion_page_ids).join(', ') : record.notion_page_ids.join(', ')) : 'None'}
                      </Typography>
                    </Box>

                    <Box>
                      <Typography variant="caption" color="text.secondary">
                        GitHub Repos
                      </Typography>
                      <Typography variant="body1">
                        {record.github_repos ? (typeof record.github_repos === 'string' ? JSON.parse(record.github_repos).join(', ') : record.github_repos.join(', ')) : 'None'}
                      </Typography>
                    </Box>
                  </Grid>
                </Grid>
              </CardContent>
            </Card>
          </Grid>

          {/* Project Keywords */}
          <Grid item xs={12}>
            <Card sx={{ borderLeft: '4px solid', borderLeftColor: 'warning.main' }}>
              <CardContent>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                  <Box>
                    <Typography variant="h6" sx={{ fontWeight: 600 }}>
                      🏷️ Project Keywords
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      Keywords used for Fireflies meeting filtering in /find-context command
                    </Typography>
                  </Box>
                  {!editingKeywords && (
                    <MuiButton
                      variant="outlined"
                      size="small"
                      onClick={() => setEditingKeywords(true)}
                      disabled={loadingKeywords}
                      sx={{ textTransform: 'none' }}
                    >
                      Edit Keywords
                    </MuiButton>
                  )}
                </Box>
                <Divider sx={{ mb: 2 }} />

                {loadingKeywords ? (
                  <CircularProgress size={24} />
                ) : editingKeywords ? (
                  <Box>
                    <Alert severity="info" sx={{ mb: 2 }}>
                      Keywords help filter Fireflies meetings for this project. Add words that commonly appear in meeting titles.
                    </Alert>

                    <Box sx={{ display: 'flex', gap: 1, mb: 2, flexWrap: 'wrap' }}>
                      {keywords.map((keyword, index) => (
                        <Chip
                          key={index}
                          label={keyword}
                          onDelete={() => handleRemoveKeyword(keyword)}
                          color="primary"
                          variant="outlined"
                        />
                      ))}
                    </Box>

                    <Box sx={{ display: 'flex', gap: 1, mb: 2 }}>
                      <MuiTextField
                        size="small"
                        placeholder="Add keyword..."
                        value={keywordInput}
                        onChange={(e) => setKeywordInput(e.target.value)}
                        onKeyPress={(e) => {
                          if (e.key === 'Enter') {
                            handleAddKeyword();
                          }
                        }}
                        fullWidth
                      />
                      <MuiButton
                        variant="contained"
                        size="small"
                        onClick={handleAddKeyword}
                        disabled={!keywordInput.trim()}
                        sx={{ textTransform: 'none' }}
                      >
                        Add
                      </MuiButton>
                    </Box>

                    <Box sx={{ display: 'flex', gap: 1, justifyContent: 'flex-end' }}>
                      <MuiButton
                        variant="outlined"
                        size="small"
                        onClick={() => {
                          loadKeywords();
                          setEditingKeywords(false);
                        }}
                        sx={{ textTransform: 'none' }}
                      >
                        Cancel
                      </MuiButton>
                      <MuiButton
                        variant="contained"
                        size="small"
                        color="primary"
                        onClick={handleSaveKeywords}
                        disabled={loadingKeywords}
                        sx={{ textTransform: 'none' }}
                      >
                        Save Keywords
                      </MuiButton>
                    </Box>
                  </Box>
                ) : (
                  <Box>
                    {keywords.length === 0 ? (
                      <Alert severity="warning">
                        <strong>No keywords configured!</strong> Without keywords, Fireflies meetings won't be included in project searches. Click "Edit Keywords" to add keywords.
                      </Alert>
                    ) : (
                      <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                        {keywords.map((keyword, index) => (
                          <Chip key={index} label={keyword} color="primary" />
                        ))}
                      </Box>
                    )}
                  </Box>
                )}
              </CardContent>
            </Card>
          </Grid>
        </Grid>
    </Box>
  );
};

export const ProjectShow = () => (
  <Show actions={<ProjectShowActions />}>
    <ProjectShowContent />
  </Show>
);

export const ProjectEdit = () => (
  <Edit>
    <SimpleForm>
      <Typography variant="h6" sx={{ mb: 2, fontWeight: 600 }}>
        Edit Project
      </Typography>

      <Box sx={{ display: 'flex', gap: 2, flexDirection: 'column', width: '100%' }}>
        <TextInput source="key" label="Project Key" disabled fullWidth />
        <TextInput source="name" label="Project Name" fullWidth />
        <TextInput source="description" label="Description" multiline rows={3} fullWidth />

        <SelectInput
          source="project_work_type"
          label="Work Type"
          choices={[
            { id: 'retainer', name: 'Retainer' },
            { id: 'project', name: 'Project' },
            { id: 'internal', name: 'Internal' },
          ]}
          fullWidth
        />

        <SelectInput
          source="weekly_meeting_day"
          label="Weekly Meeting Day"
          choices={[
            { id: 'Monday', name: 'Monday' },
            { id: 'Tuesday', name: 'Tuesday' },
            { id: 'Wednesday', name: 'Wednesday' },
            { id: 'Thursday', name: 'Thursday' },
            { id: 'Friday', name: 'Friday' },
          ]}
          fullWidth
        />

        <NumberInput source="forecasted_hours_month" label="Forecasted Hours/Month" fullWidth />
        <NumberInput source="total_hours" label="Total Hours" fullWidth />

        <Typography variant="subtitle2" sx={{ mt: 2, mb: 1, fontWeight: 600 }}>
          Resource Mappings (comma-separated)
        </Typography>

        <TextInput source="jira_project_keys" label="Jira Project Keys" fullWidth helperText="e.g., PROJ1, PROJ2" />
        <TextInput source="slack_channel_ids" label="Slack Channel IDs" fullWidth helperText="e.g., C123456, C789012" />
        <TextInput source="notion_page_ids" label="Notion Page IDs" fullWidth helperText="e.g., abc123, def456" />
        <TextInput source="github_repos" label="GitHub Repos" fullWidth helperText="e.g., org/repo1, org/repo2" />
      </Box>
    </SimpleForm>
  </Edit>
);