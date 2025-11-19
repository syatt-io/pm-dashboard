import React, { useState, useEffect } from 'react';
import {
  List,
  Datagrid,
  TextField,
  DateField,
  Show,
  SimpleShowLayout,
  useRecordContext,
  FunctionField,
  Button as AdminButton,
  useRedirect,
  useNotify,
  useListContext,
} from 'react-admin';
import { fetchCsrfToken } from '../dataProvider';
import { formatESTDateTime, formatESTDate, formatESTDateTimeShort } from '../utils/timezone';
import {
  Card,
  CardContent,
  Typography,
  Box,
  Chip,
  List as MuiList,
  ListItem,
  ListItemText,
  ListItemIcon,
  Divider,
  Paper,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField as MuiTextField,
  Autocomplete,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  CircularProgress,
  Alert,
  Tabs,
  Tab,
} from '@mui/material';
import {
  Assignment,
  CheckCircle,
  Warning,
  TrendingUp,
  Create,
  Download,
  Delete,
  Analytics,
  Launch,
} from '@mui/icons-material';
import { MeetingList } from './Meetings';
import { useAuth } from '../context/AuthContext';

// API Configuration
const API_BASE_URL = process.env.REACT_APP_API_URL || '' + (window.location.hostname === 'localhost' ? 'http://localhost:4000' : 'https://agent-pm-tsbbb.ondigitalocean.app') + '';

const CreateJiraTicketDialog = ({
  open,
  onClose,
  item,
  meetingTitle,
  onSuccess
}: {
  open: boolean;
  onClose: () => void;
  item: any;
  meetingTitle?: string;
  onSuccess: () => void;
}) => {
  const [assignees, setAssignees] = useState<any[]>([]);
  const [projects, setProjects] = useState<any[]>([]);
  const [issueTypes, setIssueTypes] = useState<any[]>([]);
  const [selectedAssignee, setSelectedAssignee] = useState<any>(null);
  const [selectedProject, setSelectedProject] = useState<string>('');
  const [selectedIssueType, setSelectedIssueType] = useState<string>('');
  const [title, setTitle] = useState<string>('');
  const [description, setDescription] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [loadingProjects, setLoadingProjects] = useState(false);
  const [loadingIssueTypes, setLoadingIssueTypes] = useState(false);
  const notify = useNotify();

  // Load initial data when dialog opens
  useEffect(() => {
    if (open) {
      loadProjects();
      loadUsers();
      // Initialize title and description from item
      setTitle(item?.title || '');
      setDescription(item?.description || '');
    }
  }, [open, item]);

  // Load issue types when project changes
  useEffect(() => {
    if (selectedProject) {
      loadIssueTypes(selectedProject);
    }
  }, [selectedProject]);

  // Auto-select project based on meeting title when dialog opens
  useEffect(() => {
    if (open && meetingTitle && projects.length > 0) {
      determineProjectFromMeeting(meetingTitle).then(projectKey => {
        if (projectKey) {
          console.log(`[INFO] Auto-selected project: ${projectKey} based on meeting title: "${meetingTitle}"`);
          setSelectedProject(projectKey);
        }
      });
    }
  }, [open, meetingTitle, projects]);

  // Function to determine Jira project from meeting title using resource mappings
  const determineProjectFromMeeting = async (meetingTitle: string): Promise<string | null> => {
    try {
      const token = localStorage.getItem('auth_token');
      if (!token) return null;

      // Step 1: Match meeting title against project keywords (already loaded in projects state)
      const titleLower = meetingTitle.toLowerCase();
      let matchedProjectKey = null;
      let bestMatchLength = 0;

      const KEYWORD_BLACKLIST = ['syatt'];

      const matchesKeyword = (text: string, keyword: string): boolean => {
        const escapedKeyword = keyword.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        const pattern = new RegExp(`\\b${escapedKeyword}\\b`, 'i');
        return pattern.test(text);
      };

      for (const project of projects) {
        if (project.is_active !== true) continue;

        if (project.keywords && Array.isArray(project.keywords)) {
          for (const keyword of project.keywords) {
            const keywordLower = keyword.toLowerCase();

            if (KEYWORD_BLACKLIST.includes(keywordLower)) {
              continue;
            }

            if (matchesKeyword(titleLower, keywordLower)) {
              if (keywordLower.length > bestMatchLength) {
                bestMatchLength = keywordLower.length;
                matchedProjectKey = project.key;
              }
            }
          }
        }
      }

      if (!matchedProjectKey) return null;

      // Step 2: Get resource mappings to find the correct Jira project key
      const mappingsResponse = await fetch(`${API_BASE_URL}/api/project-resource-mappings`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (!mappingsResponse.ok) return matchedProjectKey;

      const mappingsData = await mappingsResponse.json();
      const mappings = mappingsData.mappings || [];

      const mapping = mappings.find((m: any) => m.project_key === matchedProjectKey);

      if (mapping && mapping.jira_project_keys && mapping.jira_project_keys.length > 0) {
        return mapping.jira_project_keys[0];
      }

      return matchedProjectKey;
    } catch (error) {
      console.error('Error determining project from meeting:', error);
      return null;
    }
  };

  const loadUsers = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/jira/users`);

      if (!response.ok) {
        console.error('[ERROR] Users API failed:', response.status, response.statusText);
        return;
      }

      const data = await response.json();

      // Handle both response formats: {success: true, data: {users: []}} and {data: {users: []}}
      const users = data.success ? (data.users || data.data?.users || []) : (data.data?.users || []);
      setAssignees(users);
    } catch (error) {
      console.error('[ERROR] Failed to load users:', error);
    }
  };

  const loadProjects = async () => {
    setLoadingProjects(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/jira/projects`);

      if (!response.ok) {
        console.error('[ERROR] Projects API failed:', response.status, response.statusText);
        return;
      }

      const data = await response.json();

      // Handle both response formats: {success: true, data: {projects: []}} and {data: {projects: []}}
      const projects = data.success ? (data.projects || data.data?.projects || []) : (data.data?.projects || []);
      setProjects(projects);
    } catch (error) {
      console.error('[ERROR] Failed to load projects:', error);
    } finally {
      setLoadingProjects(false);
    }
  };

  const loadIssueTypes = async (projectKey: string) => {
    setLoadingIssueTypes(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/jira/issue-types?project=${projectKey}`);

      if (!response.ok) {
        console.error('[ERROR] Issue types API failed:', response.status, response.statusText);
        return;
      }

      const data = await response.json();

      // Handle both response formats: {success: true, data: {issue_types: []}} and {data: {issue_types: []}}
      const types = data.success
        ? (data.issue_types || data.issueTypes || data.data?.issue_types || data.data?.issueTypes || [])
        : (data.data?.issue_types || data.data?.issueTypes || []);
      setIssueTypes(types);
    } catch (error) {
      console.error('[ERROR] Failed to load issue types:', error);
    } finally {
      setLoadingIssueTypes(false);
    }
  };

  const handleSubmit = async () => {
    if (!title.trim()) {
      notify('Please enter a title', { type: 'warning' });
      return;
    }
    if (!selectedProject || !selectedIssueType) {
      notify('Please select project and issue type', { type: 'warning' });
      return;
    }

    setLoading(true);
    try {
      const token = localStorage.getItem('auth_token');
      const csrfToken = await fetchCsrfToken();

      const ticketData = {
        title: title,
        description: description,
        assignee: selectedAssignee ? selectedAssignee.emailAddress || selectedAssignee.name : '',
        project: selectedProject,
        issueType: selectedIssueType,
        priority: item.priority || 'Medium'
      };

      const response = await fetch(`${API_BASE_URL}/api/jira/tickets`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
          'X-CSRF-Token': csrfToken,
        },
        body: JSON.stringify(ticketData),
      });

      if (response.ok) {
        notify(`Created Jira ticket for: ${title}`, { type: 'success' });
        onSuccess();
        onClose();
      } else {
        const errorData = await response.json().catch(() => ({ error: 'Unknown error' }));
        throw new Error(errorData.error || 'Failed to create Jira ticket');
      }
    } catch (error) {
      notify(`Error creating Jira ticket: ${error}`, { type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>Create Jira Ticket</DialogTitle>
      <DialogContent>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3, pt: 2 }}>
          <MuiTextField
            label="Title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            fullWidth
            required
          />

          <MuiTextField
            label="Description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            multiline
            rows={3}
            fullWidth
          />

          <Autocomplete
            options={assignees}
            getOptionLabel={(option) => option.displayName || option.name || ''}
            value={selectedAssignee}
            onChange={(event, newValue) => setSelectedAssignee(newValue)}
            renderInput={(params) => (
              <MuiTextField {...params} label="Assignee" placeholder="Search for assignee..." />
            )}
            renderOption={(props, option) => (
              <Box component="li" {...props}>
                <Box>
                  <Typography variant="body2">{option.displayName || option.name}</Typography>
                  <Typography variant="caption" color="text.secondary">
                    {option.emailAddress}
                  </Typography>
                </Box>
              </Box>
            )}
          />

          <FormControl fullWidth>
            <InputLabel>Project</InputLabel>
            <Select
              value={selectedProject}
              onChange={(e) => setSelectedProject(e.target.value as string)}
              disabled={loadingProjects}
            >
              {projects.map((project) => (
                <MenuItem key={project.key} value={project.key}>
                  {project.key} - {project.name}
                </MenuItem>
              ))}
            </Select>
          </FormControl>

          <FormControl fullWidth disabled={!selectedProject || loadingIssueTypes}>
            <InputLabel>Issue Type</InputLabel>
            <Select
              value={selectedIssueType}
              onChange={(e) => setSelectedIssueType(e.target.value as string)}
            >
              {issueTypes.map((issueType) => (
                <MenuItem key={issueType.id} value={issueType.name}>
                  {issueType.name}
                </MenuItem>
              ))}
            </Select>
            {loadingIssueTypes && (
              <Box sx={{ display: 'flex', justifyContent: 'center', mt: 1 }}>
                <CircularProgress size={20} />
              </Box>
            )}
          </FormControl>
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={loading}>
          Cancel
        </Button>
        <Button
          onClick={handleSubmit}
          variant="contained"
          disabled={loading || !selectedProject || !selectedIssueType}
        >
          {loading ? <CircularProgress size={20} /> : 'Create Ticket'}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

const ActionItemsList = ({ actionItems, meetingTitle }: { actionItems: any[]; meetingTitle?: string }) => {
  const notify = useNotify();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [selectedItem, setSelectedItem] = useState<any>(null);

  // Function to determine Jira project from meeting title using resource mappings
  const determineProjectFromMeeting = async (meetingTitle: string): Promise<string | null> => {
    try {
      const token = localStorage.getItem('auth_token');
      if (!token) return null;

      // Step 1: Get all projects with keywords
      const projectsResponse = await fetch(`${API_BASE_URL}/api/jira/projects`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (!projectsResponse.ok) return null;

      const projectsData = await projectsResponse.json();
      const projects = projectsData.data?.projects || [];

      // Step 2: Match meeting title against project keywords to find the best matching project
      const titleLower = meetingTitle.toLowerCase();
      let matchedProjectKey = null;
      let bestMatchLength = 0;

      // Blacklist of common company terms that should be ignored for project matching
      // These terms appear in too many meetings to be useful discriminators
      const KEYWORD_BLACKLIST = ['syatt'];

      // Helper function to check if keyword matches as whole word (word boundary matching)
      const matchesKeyword = (text: string, keyword: string): boolean => {
        // Escape special regex characters
        const escapedKeyword = keyword.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        // Match whole words only using word boundaries
        const pattern = new RegExp(`\\b${escapedKeyword}\\b`, 'i');
        return pattern.test(text);
      };

      // Find all matching projects and choose the one with the longest/most specific keyword match
      // Only consider ACTIVE projects (must be explicitly true)
      for (const project of projects) {
        // Skip projects that are not explicitly marked as active
        if (project.is_active !== true) continue;

        if (project.keywords && Array.isArray(project.keywords)) {
          for (const keyword of project.keywords) {
            const keywordLower = keyword.toLowerCase();

            // Skip blacklisted keywords (common company terms)
            if (KEYWORD_BLACKLIST.includes(keywordLower)) {
              continue;
            }

            // Use word boundary matching instead of simple substring matching
            if (matchesKeyword(titleLower, keywordLower)) {
              // Prefer longer, more specific keyword matches
              if (keywordLower.length > bestMatchLength) {
                bestMatchLength = keywordLower.length;
                matchedProjectKey = project.key;
              }
            }
          }
        }
      }

      if (!matchedProjectKey) return null;

      // Step 3: Get resource mappings to find the correct Jira project key
      const mappingsResponse = await fetch(`${API_BASE_URL}/api/project-resource-mappings`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (!mappingsResponse.ok) return matchedProjectKey; // Fallback to matched project key

      const mappingsData = await mappingsResponse.json();
      const mappings = mappingsData.mappings || [];

      // Find the mapping for the matched project
      const mapping = mappings.find((m: any) => m.project_key === matchedProjectKey);

      if (mapping && mapping.jira_project_keys && mapping.jira_project_keys.length > 0) {
        // Return the first Jira project key from the mapping
        return mapping.jira_project_keys[0];
      }

      // Fallback to the matched project key if no mapping exists
      return matchedProjectKey;
    } catch (error) {
      console.error('Error determining project from meeting:', error);
      return null;
    }
  };

  const handleAddTodo = async (item: any, index: number) => {
    try {
      const token = localStorage.getItem('auth_token');
      const csrfToken = await fetchCsrfToken();

      // Determine project from meeting title if available
      let projectKey = null;
      if (meetingTitle) {
        projectKey = await determineProjectFromMeeting(meetingTitle);
      }

      const todoData = {
        title: item.title,
        description: item.description,
        assignee: item.assignee || '',
        priority: item.priority || 'Medium',
        ...(projectKey && { project_key: projectKey })
      };

      const response = await fetch(`${API_BASE_URL}/api/todos`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
          'X-CSRF-Token': csrfToken,
        },
        body: JSON.stringify(todoData),
      });

      if (response.ok) {
        const successMsg = projectKey
          ? `Added "${item.title}" to TODO list (Project: ${projectKey})`
          : `Added "${item.title}" to TODO list`;
        notify(successMsg, { type: 'success' });
      } else {
        const errorData = await response.json().catch(() => ({ error: 'Unknown error' }));
        throw new Error(errorData.error || 'Failed to create TODO');
      }
    } catch (error) {
      notify(`Error creating TODO: ${error}`, { type: 'error' });
    }
  };

  const handleCreateJiraTicket = (item: any, index: number) => {
    setSelectedItem(item);
    setDialogOpen(true);
  };

  const handleDialogSuccess = () => {
    // Optionally refresh data or show success message
  };

  if (!actionItems || actionItems.length === 0) {
    return (
      <Typography variant="body2" color="text.secondary">
        No action items found
      </Typography>
    );
  }

  return (
    <>
      <MuiList>
        {actionItems.map((item: any, index: number) => (
          <React.Fragment key={index}>
            <ListItem sx={{ alignItems: 'flex-start', py: 2 }}>
              <ListItemIcon sx={{ mt: 1 }}>
                <Assignment color="primary" />
              </ListItemIcon>
              <ListItemText
                primary={item.title}
                secondary={
                  <Box>
                    <Typography variant="body2" component="div" sx={{ mb: 1 }}>
                      {item.description}
                    </Typography>
                    <Box sx={{ mb: 2, display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
                      {item.assignee && (
                        <Chip label={item.assignee} size="small" variant="outlined" />
                      )}
                      <Chip
                        label={item.priority || 'Medium'}
                        size="small"
                        color={
                          item.priority === 'High'
                            ? 'error'
                            : item.priority === 'Low'
                            ? 'info'
                            : 'warning'
                        }
                      />
                      {item.due_date && (
                        <Chip
                          label={`Due: ${new Date(item.due_date).toLocaleDateString()}`}
                          size="small"
                          variant="outlined"
                        />
                      )}
                    </Box>
                    <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                      <Button
                        size="small"
                        variant="outlined"
                        color="info"
                        onClick={() => handleAddTodo(item, index)}
                        sx={{ textTransform: 'none' }}
                      >
                        Add TODO
                      </Button>
                      <Button
                        size="small"
                        variant="contained"
                        color="primary"
                        onClick={() => handleCreateJiraTicket(item, index)}
                        sx={{ textTransform: 'none' }}
                      >
                        Create Jira Ticket
                      </Button>
                    </Box>
                  </Box>
                }
              />
            </ListItem>
            {index < actionItems.length - 1 && <Divider />}
          </React.Fragment>
        ))}
      </MuiList>

      <CreateJiraTicketDialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        item={selectedItem}
        meetingTitle={meetingTitle}
        onSuccess={handleDialogSuccess}
      />
    </>
  );
};


const AnalysisDateRangeFilter = () => {
  const { filterValues, setFilters, refetch } = useListContext();
  const [dateRange, setDateRange] = useState(filterValues?.dateRange || '7');

  const handleDateRangeChange = (newRange: string) => {
    setDateRange(newRange);
    const newFilters = { ...filterValues, dateRange: newRange };
    setFilters(newFilters);
    // Force a refetch of the data
    setTimeout(() => refetch(), 100);
  };

  return (
    <Card sx={{ mb: 2, p: 2 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
        <Typography variant="h6">Filter by Date Range:</Typography>
        <FormControl size="small" sx={{ minWidth: 120 }}>
          <InputLabel>Date Range</InputLabel>
          <Select
            value={dateRange}
            onChange={(e) => handleDateRangeChange(e.target.value as string)}
            label="Date Range"
          >
            <MenuItem value="1">Last 1 day</MenuItem>
            <MenuItem value="7">Last 7 days</MenuItem>
            <MenuItem value="30">Last 30 days</MenuItem>
            <MenuItem value="all">All time</MenuItem>
          </Select>
        </FormControl>
      </Box>
    </Card>
  );
};

const WatchedProjectsNotice = () => {
  const [watchedProjects, setWatchedProjects] = useState<string[]>([]);

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
        setWatchedProjects(data.watched_projects || []);
      } else if (response.status === 401) {
        // Silently handle auth errors - user may not be logged in yet
      } else {
        // Silently handle other errors to prevent retry loops
      }
    } catch (error) {
      // Silently handle errors to prevent infinite retry loop
    }
  };

  useEffect(() => {
    loadWatchedProjects();

    const handleWatchedProjectsChange = () => {
      loadWatchedProjects();
    };

    window.addEventListener('watchedProjectsChanged', handleWatchedProjectsChange);

    return () => {
      window.removeEventListener('watchedProjectsChanged', handleWatchedProjectsChange);
    };
  }, []);

  if (watchedProjects.length === 0) {
    return (
      <Alert severity="warning" sx={{ mb: 2 }}>
        No projects selected for monitoring. Visit the <strong>All Projects</strong> tab to watch specific projects and see their related meetings here.
      </Alert>
    );
  }

  return (
    <Alert severity="info" sx={{ mb: 2 }}>
      <Box>
        <Typography variant="body2" sx={{ mb: 1 }}>
          <strong>Showing meetings for watched projects:</strong> Meetings with a green "Analyzed" badge have been processed, while others can be analyzed on-demand.
        </Typography>
        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
          {watchedProjects.map((projectKey) => (
            <Chip
              key={projectKey}
              label={projectKey}
              color="primary"
              variant="filled"
              size="small"
            />
          ))}
        </Box>
      </Box>
    </Alert>
  );
};

const AnalysisStatusChip = ({ record }: { record: any }) => {
  // A meeting has analysis if it has an analyzed_at timestamp
  const hasAnalysis = !!record.analyzed_at;

  if (hasAnalysis) {
    return (
      <Chip
        label="Analyzed"
        color="success"
        size="medium"
        variant="filled"
        icon={<CheckCircle />}
        sx={{
          fontWeight: 600,
          px: 1,
        }}
      />
    );
  }

  return (
    <Chip
      label="Not Analyzed"
      color="warning"
      size="medium"
      variant="outlined"
      sx={{
        fontWeight: 500,
        borderWidth: 2,
        px: 1,
      }}
    />
  );
};

const MeetingTitle = ({ record }: { record: any }) => {
  return (
    <Typography variant="body2">
      {record.meeting_title || record.title}
    </Typography>
  );
};

const MeetingActions = ({ record }: { record: any }) => {
  const redirect = useRedirect();
  const notify = useNotify();
  const hasAnalysis = !!record.analyzed_at;

  const handleAnalyze = (event: React.MouseEvent) => {
    event.stopPropagation();
    if (record?.meeting_id || record?.id) {
      const meetingId = record.meeting_id || record.id;
      notify('Opening analysis view...', { type: 'info' });
      redirect(`/analysis/${meetingId}/show`);
    }
  };

  const handleOpenFireflies = (event: React.MouseEvent) => {
    event.stopPropagation();
    if (record?.meeting_id || record?.id) {
      const meetingId = record.meeting_id || record.id;
      const firefliesUrl = `https://app.fireflies.ai/view/${meetingId}`;
      window.open(firefliesUrl, '_blank');
      notify('Opening Fireflies meeting...', { type: 'info' });
    } else {
      notify('Meeting ID not available', { type: 'warning' });
    }
  };

  return (
    <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
      <Button
        onClick={handleAnalyze}
        variant="contained"
        color="primary"
        size="small"
        startIcon={<Analytics />}
      >
        {hasAnalysis ? 'Re-analyze' : 'Analyze'}
      </Button>
      <Button
        onClick={handleOpenFireflies}
        variant="outlined"
        color="secondary"
        size="small"
        startIcon={<Launch />}
      >
        Fireflies
      </Button>
    </Box>
  );
};

export const AnalysisList = () => {
  const [tabValue, setTabValue] = useState(0);

  const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
    setTabValue(newValue);
  };

  return (
    <Box>
      <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 2 }}>
        <Tabs value={tabValue} onChange={handleTabChange} aria-label="meeting tabs">
          <Tab label="My Meetings" />
          <Tab label="All Meetings" />
        </Tabs>
      </Box>

      {tabValue === 0 && (
        <List
          title="💜 My Projects - Meeting Coverage"
          sort={{ field: 'date', order: 'DESC' }}
          perPage={25}
          actions={false}
          filters={[]} // Disable default filters since we have custom
        >
          <WatchedProjectsNotice />
          <AnalysisDateRangeFilter />
          <Datagrid rowClick="show" bulkActionButtons={false}>
            <FunctionField
              label="Status"
              render={(record: any) => <AnalysisStatusChip record={record} />}
              sortable={false}
            />
            <FunctionField
              label="Meeting"
              render={(record: any) => <MeetingTitle record={record} />}
            />
            <DateField
              source="date"
              label="Meeting Date"
              options={{
                year: 'numeric',
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit',
              }}
            />
            <FunctionField
              label="Action Items"
              render={(record: any) => record.action_items?.length || 0}
            />
            <FunctionField
              label="Actions"
              render={(record: any) => <MeetingActions record={record} />}
              sortable={false}
            />
          </Datagrid>
        </List>
      )}

      {tabValue === 1 && (
        <MeetingList />
      )}
    </Box>
  );
};

const AnalysisStatusBanner = () => {
  const record = useRecordContext();
  const notify = useNotify();
  const [isAnalyzing, setIsAnalyzing] = React.useState(false);

  if (!record) return null;

  // A meeting is analyzed if it has an analyzed_at timestamp, regardless of action items count
  const isAnalyzed = !!record.analyzed_at;
  const isRecent = isAnalyzed && new Date(record.analyzed_at) > new Date(Date.now() - 24 * 60 * 60 * 1000);

  const handleAnalyze = async () => {
    setIsAnalyzing(true);
    try {
      const token = localStorage.getItem('auth_token');
      const csrfToken = await fetchCsrfToken();

      const response = await fetch(`${API_BASE_URL}/api/meetings/${record.id}/analyze`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
          'X-CSRF-Token': csrfToken,
        },
      });

      if (response.ok) {
        notify('Meeting analysis completed successfully!', { type: 'success' });
        // Refresh the page to show updated analysis
        window.location.reload();
      } else {
        const error = await response.json();
        notify(`Analysis failed: ${error.error || error.message || 'Unknown error'}`, { type: 'error' });
      }
    } catch (error) {
      notify(`Analysis failed: ${error}`, { type: 'error' });
    } finally {
      setIsAnalyzing(false);
    }
  };

  if (!isAnalyzed) {
    // Not analyzed yet - show analyze button
    return (
      <Card sx={{ mb: 2, borderLeft: '4px solid', borderLeftColor: 'warning.main' }}>
        <CardContent sx={{ py: 1.5 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Chip
              label="Not Analyzed"
              color="warning"
              size="small"
              variant="filled"
            />
            <Typography variant="body2" color="text.secondary">
              This meeting has not been analyzed yet. Click "Analyze Meeting" to extract action items, decisions, and insights.
            </Typography>
            <Box sx={{ ml: 'auto' }}>
              <Button
                size="small"
                variant="contained"
                color="primary"
                sx={{ textTransform: 'none' }}
                onClick={handleAnalyze}
                disabled={isAnalyzing}
              >
                {isAnalyzing ? <CircularProgress size={16} sx={{ mr: 1 }} /> : null}
                {isAnalyzing ? 'Analyzing...' : 'Analyze Meeting'}
              </Button>
            </Box>
          </Box>
        </CardContent>
      </Card>
    );
  }

  // Already analyzed - show status and re-analyze option
  return (
    <Card sx={{ mb: 2, borderLeft: '4px solid', borderLeftColor: isRecent ? 'success.main' : 'info.main' }}>
      <CardContent sx={{ py: 1.5 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Chip
            label={isRecent ? "Recently Analyzed" : "Cached Analysis"}
            color={isRecent ? "success" : "info"}
            size="small"
            variant="filled"
          />
          <Typography variant="body2" color="text.secondary">
            Analyzed on {formatESTDateTime(record.analyzed_at)}
            {!isRecent && " (using cached results)"}
          </Typography>
          <Box sx={{ ml: 'auto' }}>
            <Button
              size="small"
              variant="outlined"
              color="secondary"
              sx={{ textTransform: 'none' }}
              onClick={handleAnalyze}
              disabled={isAnalyzing}
            >
              {isAnalyzing ? <CircularProgress size={16} sx={{ mr: 1 }} /> : null}
              {isAnalyzing ? 'Re-analyzing...' : 'Re-analyze'}
            </Button>
          </Box>
        </Box>
      </CardContent>
    </Card>
  );
};

const AnalysisShowErrorFallback = ({ error }: { error: any }) => {
  let errorMessage = 'An error occurred while loading the meeting';
  let helpText = 'Please try again later';

  if (error?.body?.error === 'no_api_key') {
    errorMessage = 'Fireflies API Key Not Configured';
    helpText = 'Please configure your Fireflies API key in Settings to view meeting details.';
  } else if (error?.body?.error === 'invalid_api_key') {
    errorMessage = 'Invalid Fireflies API Key';
    helpText = 'Please check your Fireflies API key in Settings.';
  } else if (error?.body?.error === 'Meeting not found') {
    errorMessage = 'Meeting Not Found';
    helpText = 'This meeting may not exist in your Fireflies account or may have been deleted.';
  } else if (error?.message?.includes('Authentication required')) {
    errorMessage = 'Authentication Required';
    helpText = 'Please log in to view meeting details.';
  }

  return (
    <Box sx={{ p: 4 }}>
      <Alert severity="error" sx={{ mb: 2 }}>
        <Typography variant="h6" gutterBottom>
          {errorMessage}
        </Typography>
        <Typography variant="body2">
          {helpText}
        </Typography>
        {error?.body?.message && (
          <Typography variant="caption" display="block" sx={{ mt: 1 }}>
            Details: {error.body.message}
          </Typography>
        )}
      </Alert>
      <Button
        variant="contained"
        color="primary"
        href="/#/settings"
        sx={{ mt: 2 }}
      >
        Go to Settings
      </Button>
      <Button
        variant="outlined"
        href="/#/analysis"
        sx={{ mt: 2, ml: 2 }}
      >
        Back to Analysis
      </Button>
    </Box>
  );
};

export const AnalysisShow = () => {
  const [error, setError] = React.useState<any>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = React.useState(false);
  const [isDeleting, setIsDeleting] = React.useState(false);
  const { isAdmin } = useAuth();
  const notify = useNotify();
  const redirect = useRedirect();

  const downloadAnalysisAsMarkdown = (record: any) => {
    if (!record) return;

    let markdown = `# ${record.meeting_title || record.title || 'Meeting Analysis'}\n\n`;
    markdown += `**Meeting Date:** ${record.date ? formatESTDateTime(record.date) : 'N/A'}\n`;
    markdown += `**Analyzed At:** ${record.analyzed_at ? formatESTDateTime(record.analyzed_at) : 'N/A'}\n\n`;
    markdown += '---\n\n';

    // Add topics if available (new format)
    if (record.topics && record.topics.length > 0) {
      record.topics.forEach((topic: any) => {
        markdown += `## ${topic.title}\n\n`;
        topic.content_items?.forEach((item: string) => {
          const isSubBullet = item.startsWith('  * ');
          let content = isSubBullet ? item.substring(4) : item;
          // Remove any leading asterisk and whitespace
          content = content.replace(/^\*\s*/, '').trim();
          markdown += isSubBullet ? `  * ${content}\n` : `* ${content}\n`;
        });
        markdown += '\n';
      });
    }

    // Add action items
    if (record.action_items && record.action_items.length > 0) {
      markdown += '## Action Items\n\n';
      record.action_items.forEach((item: any) => {
        markdown += `### ${item.title}\n\n`;
        if (item.description) markdown += `* **Description:** ${item.description}\n`;
        if (item.assignee) markdown += `* **Assignee:** ${item.assignee}\n`;
        if (item.priority) markdown += `* **Priority:** ${item.priority}\n`;
        if (item.due_date) markdown += `* **Due Date:** ${new Date(item.due_date).toLocaleDateString()}\n`;
        markdown += '\n';
      });
    }

    // Fallback to legacy format if no topics
    if ((!record.topics || record.topics.length === 0)) {
      if (record.executive_summary) {
        markdown += `## Executive Summary\n\n${record.executive_summary}\n\n`;
      }
      if (record.outcomes && record.outcomes.length > 0) {
        markdown += '## Outcomes\n\n';
        record.outcomes.forEach((outcome: string) => markdown += `* ${outcome}\n`);
        markdown += '\n';
      }
      if (record.blockers_and_constraints && record.blockers_and_constraints.length > 0) {
        markdown += '## Blockers & Constraints\n\n';
        record.blockers_and_constraints.forEach((blocker: string) => markdown += `* ${blocker}\n`);
        markdown += '\n';
      }
      if (record.timeline_and_milestones && record.timeline_and_milestones.length > 0) {
        markdown += '## Timeline & Milestones\n\n';
        record.timeline_and_milestones.forEach((item: string) => markdown += `* ${item}\n`);
        markdown += '\n';
      }
      if (record.key_discussions && record.key_discussions.length > 0) {
        markdown += '## Key Discussions\n\n';
        record.key_discussions.forEach((discussion: string) => markdown += `* ${discussion}\n`);
        markdown += '\n';
      }
    }

    // Create blob and trigger download
    const blob = new Blob([markdown], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${record.id || 'meeting'}_analysis_${new Date().toISOString().split('T')[0]}.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const handleDeleteMeeting = async (record: any) => {
    if (!record || !record.id) return;

    setIsDeleting(true);
    try {
      const token = localStorage.getItem('auth_token');
      const csrfToken = await fetchCsrfToken();

      const response = await fetch(`${API_BASE_URL}/api/meetings/${record.id}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`,
          'X-CSRF-Token': csrfToken,
        },
      });

      if (response.ok) {
        notify('Meeting analysis deleted successfully', { type: 'success' });
        // Redirect back to analysis list
        redirect('/analysis');
      } else {
        const error = await response.json();
        notify(`Failed to delete meeting: ${error.error || 'Unknown error'}`, { type: 'error' });
      }
    } catch (error) {
      notify(`Failed to delete meeting: ${error}`, { type: 'error' });
    } finally {
      setIsDeleting(false);
      setDeleteDialogOpen(false);
    }
  };

  return (
    <>
      {error ? (
        <AnalysisShowErrorFallback error={error} />
      ) : (
        <Show
          title="📊 Meeting Analysis"
          queryOptions={{
            onError: (err: any) => {
              console.error('Error loading meeting:', err);
              setError(err);
            },
          }}
        >
          <SimpleShowLayout>
            {/* Analysis Status Banner */}
            <FunctionField render={() => <AnalysisStatusBanner />} />

      {/* Two-Column Layout: Analysis (left) and Action Items (right) */}
      <Box sx={{ display: 'flex', gap: 3, alignItems: 'flex-start' }}>
        {/* Left Column: All Analysis Content */}
        <Box sx={{ flex: '1 1 65%', display: 'flex', flexDirection: 'column', gap: 3 }}>
          {/* Meeting Details Header */}
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                <Typography variant="h6">
                  Meeting Details
                </Typography>
                <FunctionField
                  render={(record: any) => (
                    <Box sx={{ display: 'flex', gap: 1 }}>
                      <Button
                        variant="outlined"
                        color="primary"
                        size="medium"
                        startIcon={<Download />}
                        onClick={() => downloadAnalysisAsMarkdown(record)}
                        sx={{ textTransform: 'none' }}
                      >
                        Download as Markdown
                      </Button>
                      {isAdmin && (
                        <Button
                          variant="outlined"
                          color="error"
                          size="medium"
                          startIcon={<Delete />}
                          onClick={() => setDeleteDialogOpen(true)}
                          sx={{ textTransform: 'none' }}
                        >
                          Delete
                        </Button>
                      )}
                    </Box>
                  )}
                />
              </Box>
              <TextField source="meeting_title" label="Title" />
              <FunctionField
                label="Meeting Date"
                render={(record: any) => formatESTDateTime(record.date)}
              />
              <FunctionField
                label="Analyzed At"
                render={(record: any) => formatESTDateTime(record.analyzed_at)}
              />
              <FunctionField
                label="AI Model"
                render={(record: any) => {
                  const provider = record.ai_provider || 'unknown';
                  const model = record.ai_model || 'unknown';
                  return (
                    <Typography variant="body2" color="text.secondary" fontStyle="italic">
                      {provider}/{model}
                    </Typography>
                  );
                }}
              />
            </CardContent>
          </Card>

          {/* Dynamic Topic-Based Sections */}
          <FunctionField
            render={(record: any) => {
              // Check if we have topics (new format)
              if (record.topics && record.topics.length > 0) {
                return (
                  <>
                    {record.topics.map((topic: any, topicIndex: number) => (
                      <Card key={topicIndex}>
                        <CardContent>
                          <Typography variant="h6" gutterBottom>
                            {topic.title}
                          </Typography>
                          <MuiList dense>
                            {topic.content_items?.map((item: string, itemIndex: number) => {
                              // Check if it's a sub-bullet (starts with "  * ")
                              const isSubBullet = item.startsWith('  * ');
                              // Strip the prefix AND any leading asterisk from the actual content
                              let content = isSubBullet ? item.substring(4) : item;
                              // Remove any leading asterisk and whitespace
                              content = content.replace(/^\*\s*/, '').trim();

                              return (
                                <ListItem
                                  key={itemIndex}
                                  sx={{
                                    pl: 2,
                                    ml: isSubBullet ? 4 : 0,
                                    py: 0.25,
                                    display: 'list-item',
                                    listStyleType: isSubBullet ? 'circle' : 'disc',
                                    listStylePosition: 'outside',
                                    lineHeight: 1.4
                                  }}
                                >
                                  <ListItemText
                                    primary={content}
                                    primaryTypographyProps={{
                                      variant: isSubBullet ? 'body2' : 'body1',
                                      component: 'span',
                                      sx: { lineHeight: 1.4 }
                                    }}
                                  />
                                </ListItem>
                              );
                            })}
                          </MuiList>
                        </CardContent>
                      </Card>
                    ))}
                  </>
                );
              }

              // Fallback to legacy format if no topics
              return (
                <>
                  {/* Executive Summary */}
                  {record.executive_summary && (
                    <Card>
                      <CardContent>
                        <Typography variant="h6" gutterBottom>
                          📝 Executive Summary
                        </Typography>
                        <Typography variant="body1">{record.executive_summary}</Typography>
                      </CardContent>
                    </Card>
                  )}

                  {/* Outcomes */}
                  {record.outcomes && record.outcomes.length > 0 && (
                    <Card>
                      <CardContent>
                        <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          <CheckCircle color="success" />
                          Outcomes
                        </Typography>
                        <MuiList dense>
                          {record.outcomes.map((outcome: string, index: number) => (
                            <ListItem key={index}>
                              <ListItemIcon sx={{ minWidth: 36 }}>
                                <CheckCircle color="success" />
                              </ListItemIcon>
                              <ListItemText primary={outcome} />
                            </ListItem>
                          ))}
                        </MuiList>
                      </CardContent>
                    </Card>
                  )}

                  {/* Blockers & Constraints */}
                  {record.blockers_and_constraints && record.blockers_and_constraints.length > 0 && (
                    <Card>
                      <CardContent>
                        <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          <Warning color="warning" />
                          Blockers & Constraints
                        </Typography>
                        <MuiList dense>
                          {record.blockers_and_constraints.map((blocker: string, index: number) => (
                            <ListItem key={index}>
                              <ListItemIcon sx={{ minWidth: 36 }}>
                                <Warning color="warning" />
                              </ListItemIcon>
                              <ListItemText primary={blocker} />
                            </ListItem>
                          ))}
                        </MuiList>
                      </CardContent>
                    </Card>
                  )}

                  {/* Timeline & Milestones */}
                  {record.timeline_and_milestones && record.timeline_and_milestones.length > 0 && (
                    <Card>
                      <CardContent>
                        <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          <TrendingUp color="info" />
                          Timeline & Milestones
                        </Typography>
                        <MuiList dense>
                          {record.timeline_and_milestones.map((item: string, index: number) => (
                            <ListItem key={index}>
                              <ListItemIcon sx={{ minWidth: 36 }}>
                                <TrendingUp color="info" />
                              </ListItemIcon>
                              <ListItemText primary={item} />
                            </ListItem>
                          ))}
                        </MuiList>
                      </CardContent>
                    </Card>
                  )}

                  {/* Key Discussions */}
                  {record.key_discussions && record.key_discussions.length > 0 && (
                    <Card>
                      <CardContent>
                        <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          <Assignment color="primary" />
                          Key Discussions
                        </Typography>
                        <MuiList dense>
                          {record.key_discussions.map((discussion: string, index: number) => (
                            <ListItem key={index}>
                              <ListItemIcon sx={{ minWidth: 36 }}>
                                <CheckCircle color="primary" />
                              </ListItemIcon>
                              <ListItemText primary={discussion} />
                            </ListItem>
                          ))}
                        </MuiList>
                      </CardContent>
                    </Card>
                  )}

                  {/* No analysis data */}
                  {!record.executive_summary &&
                   (!record.outcomes || record.outcomes.length === 0) &&
                   (!record.topics || record.topics.length === 0) && (
                    <Card>
                      <CardContent>
                        <Typography variant="body2" color="text.secondary">
                          No analysis data available. Click "Analyze Meeting" above to process this meeting.
                        </Typography>
                      </CardContent>
                    </Card>
                  )}
                </>
              );
            }}
          />
        </Box>

        {/* Right Column: Action Items */}
        <Box sx={{ flex: '1 1 35%', position: 'sticky', top: 16 }}>
          <Card>
            <CardContent>
              <Typography variant="h6" sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                <Assignment color="primary" />
                Action Items
              </Typography>
              <FunctionField
                render={(record: any) => (
                  <ActionItemsList
                    actionItems={record.action_items}
                    meetingTitle={record.title || record.meeting_title}
                  />
                )}
              />
            </CardContent>
          </Card>
        </Box>
      </Box>

          {/* Delete Confirmation Dialog */}
          <FunctionField
            render={(record: any) => (
              <Dialog open={deleteDialogOpen} onClose={() => setDeleteDialogOpen(false)}>
                <DialogTitle>Delete Meeting Analysis?</DialogTitle>
                <DialogContent>
                  <Typography>
                    Are you sure you want to delete the analysis for "{record?.meeting_title || record?.title}"?
                    This action cannot be undone.
                  </Typography>
                </DialogContent>
                <DialogActions>
                  <Button onClick={() => setDeleteDialogOpen(false)} disabled={isDeleting}>
                    Cancel
                  </Button>
                  <Button
                    onClick={() => handleDeleteMeeting(record)}
                    variant="contained"
                    color="error"
                    disabled={isDeleting}
                  >
                    {isDeleting ? <CircularProgress size={20} /> : 'Delete'}
                  </Button>
                </DialogActions>
              </Dialog>
            )}
          />
          </SimpleShowLayout>
        </Show>
      )}
    </>
  );
};