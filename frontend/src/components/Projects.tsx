// @ts-nocheck
import React, { useState, useEffect, useCallback } from 'react';
import {
  TextField,
  FunctionField,
  NumberField,
  BooleanField,
  useGetList,
  useNotify,
  useRefresh,
  useDataProvider,
  Button,
  SaveButton,
  TextInput,
  NumberInput,
  BooleanInput,
  SelectInput,
  SimpleForm,
  useRecordContext,
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
  IconButton,
  MenuItem,
  Select,
  InputLabel,
  FormControl,
  Grid,
  CardActions,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextareaAutosize,
  Divider,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Avatar,
  Skeleton,
  Button as MuiButton,
  TextField as MuiTextField,
} from '@mui/material';
import {
  Star,
  StarBorder,
  Edit as EditIcon,
  Save as SaveIcon,
  Cancel as CancelIcon,
  Sync as SyncIcon,
  Work as WorkIcon,
  AccessTime as TimeIcon,
  People as PeopleIcon,
  Schedule as ScheduleIcon,
  Forum as ForumIcon,
  Assignment as TaskIcon,
  CalendarToday as CalendarIcon,
  Refresh as RefreshIcon,
  Assessment as DigestIcon,
  GetApp as DownloadIcon,
} from '@mui/icons-material';

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
  const notify = useNotify();

  useEffect(() => {
    // Load watched projects from API
    loadWatchedProjectsFromAPI();
  }, [record.key]);

  const loadWatchedProjectsFromAPI = async () => {
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
        setWatched(data.watched_projects.includes(record.key));
      }
    } catch (error) {
      console.error('Error loading watched projects:', error);
    }
  };

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
      console.error('Error updating project watch status:', error);
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
      }
    } catch (error) {
      console.error('Error loading watched projects:', error);
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

const EditableProjectRow = ({ project, onSave }: { project: Project, onSave: (project: Project) => void }) => {
  const [editing, setEditing] = useState(false);
  const [editedProject, setEditedProject] = useState(project);

  const handleSave = () => {
    onSave(editedProject);
    setEditing(false);
  };

  const handleCancel = () => {
    setEditedProject(project);
    setEditing(false);
  };

  if (!editing) {
    return (
      <TableRow>
        <TableCell>{project.name}</TableCell>
        <TableCell>{project.key}</TableCell>
        <TableCell>{project.projectTypeKey || 'Unknown'}</TableCell>
        <TableCell>{project.project_work_type || 'project-based'}</TableCell>
        <TableCell>{project.forecasted_hours_month || 0}</TableCell>
        <TableCell>{project.total_hours || 0}</TableCell>
        <TableCell>
          <IconButton onClick={() => setEditing(true)} size="small">
            <EditIcon />
          </IconButton>
        </TableCell>
      </TableRow>
    );
  }

  return (
    <TableRow>
      <TableCell>{project.name}</TableCell>
      <TableCell>{project.key}</TableCell>
      <TableCell>{project.projectTypeKey || 'Unknown'}</TableCell>
      <TableCell>
        <FormControl size="small" fullWidth>
          <Select
            value={editedProject.project_work_type || 'project-based'}
            onChange={(e) => setEditedProject({ ...editedProject, project_work_type: e.target.value as 'project-based' | 'growth-support' | 'n-a' })}
          >
            <MenuItem value="project-based">Project-based</MenuItem>
            <MenuItem value="growth-support">Growth & Support</MenuItem>
            <MenuItem value="n-a">N/A</MenuItem>
          </Select>
        </FormControl>
      </TableCell>
      <TableCell>
        <input
          type="number"
          value={editedProject.forecasted_hours_month || 0}
          onChange={(e) => setEditedProject({ ...editedProject, forecasted_hours_month: parseFloat(e.target.value) || 0 })}
          style={{ width: '80px' }}
        />
      </TableCell>
      <TableCell>
        <input
          type="number"
          value={editedProject.total_hours || 0}
          onChange={(e) => setEditedProject({ ...editedProject, total_hours: parseFloat(e.target.value) || 0 })}
          style={{ width: '80px' }}
        />
      </TableCell>
      <TableCell>
        <IconButton onClick={handleSave} size="small" color="primary">
          <SaveIcon />
        </IconButton>
        <IconButton onClick={handleCancel} size="small">
          <CancelIcon />
        </IconButton>
      </TableCell>
    </TableRow>
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
        console.error('Failed to fetch project meetings:', response.statusText);
        setRecentMeetings([]);
      }
    } catch (error) {
      console.error('Error fetching project meetings:', error);
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
        console.log('All TODOs fetched:', data.data);
        // Filter TODOs for this project
        const projectTodos = data.data?.filter((todo: any) => {
          console.log(`Checking TODO: ${todo.title} - project_key: ${todo.project_key} vs ${projectKey}`);
          return todo.project_key === projectKey;
        }) || [];
        console.log(`Filtered TODOs for ${projectKey}:`, projectTodos);
        setRecentTodos(projectTodos);
      } else {
        console.error('Failed to fetch todos:', response.statusText);
        setRecentTodos([]);
      }
    } catch (error) {
      console.error('Error fetching todos:', error);
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
        console.log('Project digest generated:', data);
      } else {
        console.error('Failed to generate digest:', response.statusText);
        const errorData = await response.json().catch(() => ({ error: 'Unknown error' }));
        alert(`Error generating digest: ${errorData.error || response.statusText}`);
      }
    } catch (error) {
      console.error('Error generating digest:', error);
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
                    p: 2,
                    maxHeight: '400px',
                    overflow: 'auto',
                    fontFamily: 'monospace',
                    fontSize: '0.875rem',
                    lineHeight: 1.6,
                    whiteSpace: 'pre-wrap'
                  }}>
                    {digestData.formatted_agenda}
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

export const ProjectList = () => {
  const notify = useNotify();
  const refresh = useRefresh();
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
      }
    } catch (error) {
      console.error('Error loading watched projects:', error);
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
    } catch (error) {
      notify('Error fetching projects', { type: 'error' });
    } finally {
      setLoading(false);
    }
  }, [dataProvider, notify, loadWatchedProjects]);

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
      const response = await fetch('${API_BASE_URL}/api/sync-hours', {
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
              startIcon={<SyncIcon />}
              onClick={handleSyncHours}
              disabled={syncing}
              sx={{ textTransform: 'none' }}
            >
              {syncing ? 'Syncing Hours...' : 'Sync Hours'}
            </Button>
          </Box>

          <Tabs value={tabValue} onChange={handleTabChange}>
            <Tab label={`📌 My Projects (${watchedProjects.length})`} />
            <Tab label={`⚙️ Active Projects (${activeProjects.length})`} />
            <Tab label={`📋 All Projects (${allProjects.length})`} />
          </Tabs>

          <TabPanel value={tabValue} index={0}>
            {/* My Projects - Card View */}
            {watchedProjects.length === 0 ? (
              <Alert severity="info" sx={{ mb: 3 }}>
                <Typography variant="h6" gutterBottom>
                  No projects being watched yet! 👀
                </Typography>
                <Typography variant="body2">
                  Switch to the "Active Projects" tab and use the watch toggles to select projects you want to follow.
                  They'll appear here as beautiful project cards with detailed information.
                </Typography>
              </Alert>
            ) : (
              <Box>
                <Typography variant="h6" gutterBottom sx={{ color: 'primary.main', mb: 3 }}>
                  🎯 Your Project Dashboard
                </Typography>
                <Grid container spacing={3}>
                  {watchedProjects.map((project) => (
                    <Grid item xs={12} sm={6} md={4} key={project.key}>
                      <ProjectCard
                        project={project}
                        onCardClick={handleCardClick}
                      />
                    </Grid>
                  ))}
                </Grid>
              </Box>
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
                          {workType === 'project-based' && <TableCell>Forecasted Hours/Month</TableCell>}
                          {workType === 'growth-support' && <TableCell>Retainer Hours</TableCell>}
                          <TableCell>{currentMonth} Hours</TableCell>
                          {workType === 'project-based' && <TableCell>Total Hours</TableCell>}
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
                            {(workType === 'project-based' || workType === 'growth-support') && (
                              <TableCell>
                                {project.forecasted_hours_month !== undefined ? (
                                  <input
                                    type="number"
                                    value={getProjectValue(project, 'forecasted_hours_month')}
                                    onChange={(e) => {
                                      handleFieldChange(project.key, 'forecasted_hours_month', e.target.value);
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
                                ) : (
                                  <Typography variant="body2" color="text.secondary">-</Typography>
                                )}
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

export const ProjectShow = () => (
  <Card>
    <CardContent>
      <Typography variant="h5" gutterBottom>
        Project Details
      </Typography>
      <TextField source="name" label="Name" />
      <TextField source="key" label="Key" />
      <TextField source="projectTypeKey" label="Type" />
    </CardContent>
  </Card>
);