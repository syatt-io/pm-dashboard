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
} from '@mui/material';
import {
  Assignment,
  CheckCircle,
  Warning,
  TrendingUp,
  Create,
} from '@mui/icons-material';

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
  const [loading, setLoading] = useState(false);
  const [loadingProjects, setLoadingProjects] = useState(false);
  const [loadingIssueTypes, setLoadingIssueTypes] = useState(false);
  const notify = useNotify();

  // Load initial data when dialog opens
  useEffect(() => {
    if (open) {
      loadProjects();
      loadUsers();
    }
  }, [open]);

  // Load issue types when project changes
  useEffect(() => {
    if (selectedProject) {
      loadIssueTypes(selectedProject);
    }
  }, [selectedProject]);

  const loadUsers = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/jira/users`);
      const data = await response.json();
      if (data.success) {
        setAssignees(data.users || []);
      }
    } catch (error) {
      // Failed to load users - will be handled by UI
    }
  };

  const loadProjects = async () => {
    setLoadingProjects(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/jira/projects`);
      const data = await response.json();
      if (data.success) {
        setProjects(data.projects || []);
      }
    } catch (error) {
      // Failed to load projects - will be handled by UI
    } finally {
      setLoadingProjects(false);
    }
  };

  const loadIssueTypes = async (projectKey: string) => {
    setLoadingIssueTypes(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/jira/issue-types?project=${projectKey}`);
      const data = await response.json();
      if (data.success) {
        setIssueTypes(data.issue_types || data.issueTypes || []);
      }
    } catch (error) {
      // Failed to load issue types - will be handled by UI
    } finally {
      setLoadingIssueTypes(false);
    }
  };

  const handleSubmit = async () => {
    if (!selectedProject || !selectedIssueType) {
      notify('Please select project and issue type', { type: 'warning' });
      return;
    }

    setLoading(true);
    try {
      const ticketData = {
        title: item.title,
        description: item.description,
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
        notify(`Created Jira ticket for: ${item.title}`, { type: 'success' });
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
            value={item?.title || ''}
            disabled
            fullWidth
          />

          <MuiTextField
            label="Description"
            value={item?.description || ''}
            disabled
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
        },
        body: JSON.stringify(todoData),
      });

      if (response.ok) {
        notify(`Added "${item.title}" to TODO list`, { type: 'success' });
      } else {
        throw new Error('Failed to create TODO');
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

const CreateTicketsButton = () => {
  const record = useRecordContext();
  const redirect = useRedirect();
  const notify = useNotify();

  const handleCreateTickets = () => {
    if (record?.action_items && record.action_items.length > 0) {
      notify('Redirecting to ticket creation...', { type: 'info' });
      // This would redirect to the ticket creation workflow
      redirect('/review');
    } else {
      notify('No action items to create tickets for', { type: 'warning' });
    }
  };

  return (
    <AdminButton
      onClick={handleCreateTickets}
      label="Create Jira Tickets"
      variant="contained"
      color="primary"
    >
      <Create sx={{ mr: 1 }} />
      Create Tickets
    </AdminButton>
  );
};

const AnalysisSummary = () => {
  const record = useRecordContext();
  if (!record) return null;

  const actionItemsCount = record.action_items?.length || 0;
  const decisionsCount = record.key_decisions?.length || 0;
  const blockersCount = record.blockers?.length || 0;
  const followUpsCount = record.follow_ups?.length || 0;

  return (
    <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
      <Box sx={{ flex: '1 1 auto', minWidth: 120 }}>
        <Paper sx={{ p: 2, textAlign: 'center' }}>
          <Typography variant="h4" color="primary">
            {actionItemsCount}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            Action Items
          </Typography>
        </Paper>
      </Box>
      <Box sx={{ flex: '1 1 auto', minWidth: 120 }}>
        <Paper sx={{ p: 2, textAlign: 'center' }}>
          <Typography variant="h4" color="success.main">
            {decisionsCount}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            Decisions
          </Typography>
        </Paper>
      </Box>
      <Box sx={{ flex: '1 1 auto', minWidth: 120 }}>
        <Paper sx={{ p: 2, textAlign: 'center' }}>
          <Typography variant="h4" color="warning.main">
            {blockersCount}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            Blockers
          </Typography>
        </Paper>
      </Box>
      <Box sx={{ flex: '1 1 auto', minWidth: 120 }}>
        <Paper sx={{ p: 2, textAlign: 'center' }}>
          <Typography variant="h4" color="info.main">
            {followUpsCount}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            Follow-ups
          </Typography>
        </Paper>
      </Box>
    </Box>
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

export const AnalysisList = () => (
  <Box>
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
          label="Decisions"
          render={(record: any) => record.key_decisions?.length || 0}
        />
        <FunctionField
          label="Blockers"
          render={(record: any) => record.blockers?.length || 0}
        />
      </Datagrid>
    </List>
  </Box>
);

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
      const response = await fetch(`${API_BASE_URL}/api/meetings/${record.id}/analyze`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
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

            {/* Summary Metrics */}
            <Card sx={{ mb: 3 }}>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Analysis Overview
                </Typography>
                <FunctionField render={() => <AnalysisSummary />} />
              </CardContent>
            </Card>

      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
        {/* Meeting Summary and Key Decisions Row */}
        <Box sx={{ display: 'flex', gap: 3, flexWrap: 'wrap' }}>
          <Box sx={{ flex: '1 1 400px' }}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  📝 Meeting Summary
                </Typography>
                <TextField source="summary" label="" multiline />
                <Box sx={{ mt: 2 }}>
                  <Typography variant="subtitle2" gutterBottom>
                    Meeting Details
                  </Typography>
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
                </Box>
              </CardContent>
            </Card>
          </Box>

          <Box sx={{ flex: '1 1 400px' }}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <CheckCircle color="success" />
                  Key Decisions
                </Typography>
                <FunctionField
                  render={(record: any) => (
                    <MuiList>
                      {record.key_decisions?.map((decision: string, index: number) => (
                        <ListItem key={index}>
                          <ListItemIcon>
                            <CheckCircle color="success" />
                          </ListItemIcon>
                          <ListItemText primary={decision} />
                        </ListItem>
                      )) || (
                        <Typography variant="body2" color="text.secondary">
                          No key decisions recorded
                        </Typography>
                      )}
                    </MuiList>
                  )}
                />
              </CardContent>
            </Card>
          </Box>
        </Box>

        {/* Action Items */}
        <Card>
          <CardContent>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
              <Typography variant="h6" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <Assignment color="primary" />
                Action Items
              </Typography>
              <CreateTicketsButton />
            </Box>
            <FunctionField
              render={(record: any) => <ActionItemsList actionItems={record.action_items} />}
            />
          </CardContent>
        </Card>

        {/* Blockers & Follow-ups Row */}
        <Box sx={{ display: 'flex', gap: 3, flexWrap: 'wrap' }}>
          <Box sx={{ flex: '1 1 400px' }}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Warning color="warning" />
                  Blockers & Risks
                </Typography>
                <FunctionField
                  render={(record: any) => (
                    <MuiList>
                      {record.blockers?.map((blocker: string, index: number) => (
                        <ListItem key={index}>
                          <ListItemIcon>
                            <Warning color="warning" />
                          </ListItemIcon>
                          <ListItemText primary={blocker} />
                        </ListItem>
                      )) || (
                        <Typography variant="body2" color="text.secondary">
                          No blockers identified
                        </Typography>
                      )}
                    </MuiList>
                  )}
                />
              </CardContent>
            </Card>
          </Box>

          <Box sx={{ flex: '1 1 400px' }}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <TrendingUp color="info" />
                  Follow-up Topics
                </Typography>
                <FunctionField
                  render={(record: any) => (
                    <MuiList>
                      {record.follow_ups?.map((followUp: string, index: number) => (
                        <ListItem key={index}>
                          <ListItemIcon>
                            <TrendingUp color="info" />
                          </ListItemIcon>
                          <ListItemText primary={followUp} />
                        </ListItem>
                      )) || (
                        <Typography variant="body2" color="text.secondary">
                          No follow-up topics identified
                        </Typography>
                      )}
                    </MuiList>
                  )}
                />
              </CardContent>
            </Card>
          </Box>
        </Box>
      </Box>
          </SimpleShowLayout>
        </Show>
      )}
    </>
  );
};