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
} from '@mui/icons-material';
import { MeetingList } from './Meetings';

// API Configuration
const API_BASE_URL = process.env.REACT_APP_API_URL || '' + (window.location.hostname === 'localhost' ? 'http://localhost:4000' : 'https://agent-pm-tsbbb.ondigitalocean.app') + '';

const CreateJiraTicketDialog = ({
  open,
  onClose,
  item,
  onSuccess
}: {
  open: boolean;
  onClose: () => void;
  item: any;
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
      const ticketData = {
        title: title,
        description: description,
        assignee: selectedAssignee ? selectedAssignee.emailAddress || selectedAssignee.name : '',
        project: selectedProject,
        issueType: selectedIssueType,
        priority: item.priority || 'Medium'
      };

      const response = await fetch(`${API_BASE_URL}/api/process`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(ticketData),
      });

      if (response.ok) {
        notify(`Created Jira ticket for: ${title}`, { type: 'success' });
        onSuccess();
        onClose();
      } else {
        throw new Error('Failed to create Jira ticket');
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

const ActionItemsList = ({ actionItems }: { actionItems: any[] }) => {
  const notify = useNotify();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [selectedItem, setSelectedItem] = useState<any>(null);

  const handleAddTodo = async (item: any, index: number) => {
    try {
      const token = localStorage.getItem('auth_token');
      const csrfToken = await fetchCsrfToken();

      const todoData = {
        title: item.title,
        description: item.description,
        assignee: item.assignee || '',
        priority: item.priority || 'Medium'
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
        notify(`Added "${item.title}" to TODO list`, { type: 'success' });
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
              label="Outcomes"
              render={(record: any) => record.outcomes?.length || 0}
            />
            <FunctionField
              label="Constraints"
              render={(record: any) => record.blockers_and_constraints?.length || 0}
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
            Analyzed on {new Date(record.analyzed_at).toLocaleString()}
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

  const downloadAnalysisAsMarkdown = (record: any) => {
    if (!record) return;

    let markdown = `# ${record.meeting_title || record.title || 'Meeting Analysis'}\n\n`;
    markdown += `**Meeting Date:** ${record.date ? new Date(record.date).toLocaleString() : 'N/A'}\n`;
    markdown += `**Analyzed At:** ${record.analyzed_at ? new Date(record.analyzed_at).toLocaleString() : 'N/A'}\n\n`;
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
                  )}
                />
              </Box>
              <TextField source="meeting_title" label="Title" />
              <DateField
                source="analyzed_at"
                label="Analyzed At"
                options={{
                  year: 'numeric',
                  month: 'long',
                  day: 'numeric',
                  hour: '2-digit',
                  minute: '2-digit',
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
                render={(record: any) => <ActionItemsList actionItems={record.action_items} />}
              />
            </CardContent>
          </Card>
        </Box>
      </Box>
          </SimpleShowLayout>
        </Show>
      )}
    </>
  );
};