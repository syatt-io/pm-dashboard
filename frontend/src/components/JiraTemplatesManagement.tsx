import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Button,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  IconButton,
  Chip,
  CircularProgress,
  Alert,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  TextField,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  MenuItem,
  Select,
  FormControl,
  InputLabel,
  SelectChangeEvent,
} from '@mui/material';
import {
  ExpandMore,
  Edit,
  Delete,
  Add,
} from '@mui/icons-material';
import { getApiUrl } from '../config';
import { useNotify } from 'react-admin';
import { jiraApi, JiraIssueType } from '../api/jira';

interface TemplateTicket {
  id: number;
  template_epic_id: number;
  epic_name: string | null;
  issue_type: string;
  summary: string;
  description: string;
  sort_order: number;
}

interface TemplateEpic {
  id: number;
  epic_name: string;
  summary: string;
  description: string;
  epic_color: string;
  epic_category: string | null;
  sort_order: number;
  tickets: TemplateTicket[];
  ticket_count: number;
}

const JiraTemplatesManagement: React.FC = () => {
  const [epics, setEpics] = useState<TemplateEpic[]>([]);
  const [loading, setLoading] = useState(true);
  const [issueTypes, setIssueTypes] = useState<JiraIssueType[]>([]);
  const [loadingIssueTypes, setLoadingIssueTypes] = useState(false);

  // Epic editing state
  const [epicDialogOpen, setEpicDialogOpen] = useState(false);
  const [editingEpic, setEditingEpic] = useState<TemplateEpic | null>(null);
  const [epicForm, setEpicForm] = useState({
    epic_name: '',
    summary: '',
    description: '',
    epic_color: '#6554C0',
    epic_category: '',
  });

  // Ticket editing state
  const [ticketDialogOpen, setTicketDialogOpen] = useState(false);
  const [editingTicket, setEditingTicket] = useState<TemplateTicket | null>(null);
  const [ticketForm, setTicketForm] = useState({
    issue_type: 'Task',
    summary: '',
    description: '',
    template_epic_id: 0,
  });

  // Confirmation dialog state
  const [confirmDialogOpen, setConfirmDialogOpen] = useState(false);
  const [confirmAction, setConfirmAction] = useState<() => void>(() => {});
  const [confirmMessage, setConfirmMessage] = useState('');

  const notify = useNotify();

  const fetchEpics = async () => {
    try {
      setLoading(true);
      const token = localStorage.getItem('auth_token');
      const response = await fetch(`${getApiUrl()}/api/jira-templates/epics`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error('Failed to fetch templates');
      }

      const data = await response.json();
      setEpics(data.epics || []);
    } catch (error: any) {
      notify(`Error loading templates: ${error.message}`, { type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  const fetchIssueTypes = async () => {
    try {
      setLoadingIssueTypes(true);
      const types = await jiraApi.fetchIssueTypes();
      setIssueTypes(types);
    } catch (error: any) {
      notify(`Error loading issue types: ${error.message}`, { type: 'error' });
      // Set default fallback issue types if API fails
      setIssueTypes([
        { id: '1', name: 'Story' },
        { id: '2', name: 'Task' },
        { id: '3', name: 'Bug' },
        { id: '4', name: 'Epic' },
        { id: '5', name: 'Subtask' },
      ]);
    } finally {
      setLoadingIssueTypes(false);
    }
  };

  useEffect(() => {
    fetchEpics();
    fetchIssueTypes();
  }, []);

  // ========== EPIC CRUD HANDLERS ==========

  const handleCreateEpic = () => {
    setEditingEpic(null);
    setEpicForm({
      epic_name: '',
      summary: '',
      description: '',
      epic_color: '#6554C0',
      epic_category: '',
    });
    setEpicDialogOpen(true);
  };

  const handleEditEpic = (epic: TemplateEpic) => {
    setEditingEpic(epic);
    setEpicForm({
      epic_name: epic.epic_name,
      summary: epic.summary,
      description: epic.description,
      epic_color: epic.epic_color || '#6554C0',
      epic_category: epic.epic_category || '',
    });
    setEpicDialogOpen(true);
  };

  const handleSaveEpic = async () => {
    try {
      const token = localStorage.getItem('auth_token');
      const url = editingEpic
        ? `${getApiUrl()}/api/jira-templates/epics/${editingEpic.id}`
        : `${getApiUrl()}/api/jira-templates/epics`;

      const method = editingEpic ? 'PUT' : 'POST';

      const response = await fetch(url, {
        method,
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(epicForm),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Failed to save epic');
      }

      notify(editingEpic ? 'Epic updated successfully' : 'Epic created successfully', { type: 'success' });
      setEpicDialogOpen(false);
      fetchEpics();
    } catch (error: any) {
      notify(`Error saving epic: ${error.message}`, { type: 'error' });
    }
  };

  const handleDeleteEpic = (epic: TemplateEpic) => {
    setConfirmMessage(`Delete epic "${epic.epic_name}" and all its tickets (${epic.ticket_count})?`);
    setConfirmAction(() => async () => {
      try {
        const token = localStorage.getItem('auth_token');
        const response = await fetch(
          `${getApiUrl()}/api/jira-templates/epics/${epic.id}`,
          {
            method: 'DELETE',
            headers: {
              'Authorization': `Bearer ${token}`,
            },
          }
        );

        if (!response.ok) {
          throw new Error('Failed to delete epic');
        }

        notify('Epic deleted successfully', { type: 'success' });
        fetchEpics();
      } catch (error: any) {
        notify(`Error deleting epic: ${error.message}`, { type: 'error' });
      }
    });
    setConfirmDialogOpen(true);
  };

  // ========== TICKET CRUD HANDLERS ==========

  const handleCreateTicket = (epicId: number) => {
    setEditingTicket(null);
    setTicketForm({
      issue_type: 'Task',
      summary: '',
      description: '',
      template_epic_id: epicId,
    });
    setTicketDialogOpen(true);
  };

  const handleEditTicket = (ticket: TemplateTicket) => {
    setEditingTicket(ticket);
    setTicketForm({
      issue_type: ticket.issue_type,
      summary: ticket.summary,
      description: ticket.description,
      template_epic_id: ticket.template_epic_id,
    });
    setTicketDialogOpen(true);
  };

  const handleSaveTicket = async () => {
    try {
      const token = localStorage.getItem('auth_token');
      const url = editingTicket
        ? `${getApiUrl()}/api/jira-templates/tickets/${editingTicket.id}`
        : `${getApiUrl()}/api/jira-templates/tickets`;

      const method = editingTicket ? 'PUT' : 'POST';

      const response = await fetch(url, {
        method,
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(ticketForm),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Failed to save ticket');
      }

      notify(editingTicket ? 'Ticket updated successfully' : 'Ticket created successfully', { type: 'success' });
      setTicketDialogOpen(false);
      fetchEpics();
    } catch (error: any) {
      notify(`Error saving ticket: ${error.message}`, { type: 'error' });
    }
  };

  const handleDeleteTicket = (ticket: TemplateTicket) => {
    setConfirmMessage(`Delete ticket "${ticket.summary}"?`);
    setConfirmAction(() => async () => {
      try {
        const token = localStorage.getItem('auth_token');
        const response = await fetch(
          `${getApiUrl()}/api/jira-templates/tickets/${ticket.id}`,
          {
            method: 'DELETE',
            headers: {
              'Authorization': `Bearer ${token}`,
            },
          }
        );

        if (!response.ok) {
          throw new Error('Failed to delete ticket');
        }

        notify('Ticket deleted successfully', { type: 'success' });
        fetchEpics();
      } catch (error: any) {
        notify(`Error deleting ticket: ${error.message}`, { type: 'error' });
      }
    });
    setConfirmDialogOpen(true);
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" p={4}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h5" fontWeight={600}>
          Jira Starter Templates
        </Typography>
        <Box display="flex" alignItems="center" gap={2}>
          <Alert severity="info" sx={{ flexGrow: 1 }}>
            These templates will be used to create epics and tickets in new Jira projects.
            {epics.length > 0 && ` Currently ${epics.length} epics with ${epics.reduce((sum, e) => sum + e.ticket_count, 0)} tickets.`}
          </Alert>
          <Button
            variant="contained"
            startIcon={<Add />}
            onClick={handleCreateEpic}
          >
            Create Epic
          </Button>
        </Box>
      </Box>

      <Box>
        {epics.map((epic) => (
          <Accordion key={epic.id} sx={{ mb: 1 }}>
            <AccordionSummary expandIcon={<ExpandMore />}>
              <Box display="flex" alignItems="center" gap={2} width="100%">
                <Box
                  width={16}
                  height={16}
                  borderRadius="2px"
                  bgcolor={epic.epic_color}
                />
                <Typography fontWeight={600}>{epic.epic_name}</Typography>
                {epic.epic_category && (
                  <Chip
                    label={epic.epic_category}
                    size="small"
                    color="primary"
                    variant="outlined"
                  />
                )}
                <Chip
                  label={`${epic.ticket_count} tickets`}
                  size="small"
                  variant="outlined"
                />
                <Box sx={{ ml: 'auto', display: 'flex', gap: 1 }}>
                  <IconButton
                    size="small"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleEditEpic(epic);
                    }}
                  >
                    <Edit fontSize="small" />
                  </IconButton>
                  <IconButton
                    size="small"
                    color="error"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDeleteEpic(epic);
                    }}
                  >
                    <Delete fontSize="small" />
                  </IconButton>
                </Box>
              </Box>
            </AccordionSummary>
            <AccordionDetails>
              <Box>
                {epic.summary && (
                  <Typography variant="body2" color="text.secondary" mb={2}>
                    {epic.summary}
                  </Typography>
                )}

                <Box display="flex" justifyContent="space-between" alignItems="center" mb={1}>
                  <Typography variant="subtitle2" fontWeight={600}>
                    Tickets ({epic.ticket_count})
                  </Typography>
                  <Button
                    size="small"
                    startIcon={<Add />}
                    onClick={() => handleCreateTicket(epic.id)}
                  >
                    Add Ticket
                  </Button>
                </Box>

                <TableContainer component={Paper} variant="outlined">
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell>Issue Type</TableCell>
                        <TableCell>Summary</TableCell>
                        <TableCell>Description</TableCell>
                        <TableCell align="right">Actions</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {epic.tickets.map((ticket) => (
                        <TableRow key={ticket.id}>
                          <TableCell>
                            <Chip label={ticket.issue_type} size="small" />
                          </TableCell>
                          <TableCell>{ticket.summary}</TableCell>
                          <TableCell>
                            <Typography
                              variant="body2"
                              color="text.secondary"
                              sx={{
                                maxWidth: 400,
                                overflow: 'hidden',
                                textOverflow: 'ellipsis',
                                whiteSpace: 'nowrap',
                              }}
                            >
                              {ticket.description || '—'}
                            </Typography>
                          </TableCell>
                          <TableCell align="right">
                            <IconButton
                              size="small"
                              onClick={() => handleEditTicket(ticket)}
                            >
                              <Edit fontSize="small" />
                            </IconButton>
                            <IconButton
                              size="small"
                              color="error"
                              onClick={() => handleDeleteTicket(ticket)}
                            >
                              <Delete fontSize="small" />
                            </IconButton>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              </Box>
            </AccordionDetails>
          </Accordion>
        ))}
      </Box>

      {/* Epic Edit/Create Dialog */}
      <Dialog
        open={epicDialogOpen}
        onClose={() => setEpicDialogOpen(false)}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>{editingEpic ? 'Edit Epic Template' : 'Create Epic Template'}</DialogTitle>
        <DialogContent>
          <Box display="flex" flexDirection="column" gap={2} mt={1}>
            <TextField
              label="Epic Name"
              value={epicForm.epic_name}
              onChange={(e) =>
                setEpicForm({ ...epicForm, epic_name: e.target.value })
              }
              fullWidth
              required
            />
            <TextField
              label="Summary"
              value={epicForm.summary}
              onChange={(e) =>
                setEpicForm({ ...epicForm, summary: e.target.value })
              }
              fullWidth
            />
            <TextField
              label="Description"
              value={epicForm.description}
              onChange={(e) =>
                setEpicForm({ ...epicForm, description: e.target.value })
              }
              fullWidth
              multiline
              rows={4}
              helperText="Supports markdown formatting"
            />
            <Box display="flex" gap={2}>
              <TextField
                label="Epic Color"
                type="color"
                value={epicForm.epic_color}
                onChange={(e) =>
                  setEpicForm({ ...epicForm, epic_color: e.target.value })
                }
                sx={{ width: 150 }}
                InputLabelProps={{ shrink: true }}
              />
              <TextField
                label="Epic Category"
                value={epicForm.epic_category}
                onChange={(e) =>
                  setEpicForm({ ...epicForm, epic_category: e.target.value })
                }
                fullWidth
                helperText="Optional grouping category"
              />
            </Box>
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setEpicDialogOpen(false)}>Cancel</Button>
          <Button onClick={handleSaveEpic} variant="contained">
            {editingEpic ? 'Save' : 'Create'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Ticket Edit/Create Dialog */}
      <Dialog
        open={ticketDialogOpen}
        onClose={() => setTicketDialogOpen(false)}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>{editingTicket ? 'Edit Ticket Template' : 'Create Ticket Template'}</DialogTitle>
        <DialogContent>
          <Box display="flex" flexDirection="column" gap={2} mt={1}>
            <FormControl fullWidth disabled={loadingIssueTypes}>
              <InputLabel>Issue Type</InputLabel>
              <Select
                value={ticketForm.issue_type}
                label="Issue Type"
                onChange={(e: SelectChangeEvent) =>
                  setTicketForm({ ...ticketForm, issue_type: e.target.value })
                }
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
            <TextField
              label="Summary"
              value={ticketForm.summary}
              onChange={(e) =>
                setTicketForm({ ...ticketForm, summary: e.target.value })
              }
              fullWidth
              required
            />
            <TextField
              label="Description"
              value={ticketForm.description}
              onChange={(e) =>
                setTicketForm({ ...ticketForm, description: e.target.value })
              }
              fullWidth
              multiline
              rows={6}
              helperText="Supports markdown formatting"
            />
            <FormControl fullWidth>
              <InputLabel>Epic Assignment</InputLabel>
              <Select
                value={ticketForm.template_epic_id}
                label="Epic Assignment"
                onChange={(e: SelectChangeEvent<number>) =>
                  setTicketForm({ ...ticketForm, template_epic_id: Number(e.target.value) })
                }
              >
                {epics.map((epic) => (
                  <MenuItem key={epic.id} value={epic.id}>
                    {epic.epic_name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setTicketDialogOpen(false)}>Cancel</Button>
          <Button onClick={handleSaveTicket} variant="contained">
            {editingTicket ? 'Save' : 'Create'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Confirmation Dialog */}
      <Dialog
        open={confirmDialogOpen}
        onClose={() => setConfirmDialogOpen(false)}
      >
        <DialogTitle>Confirm Deletion</DialogTitle>
        <DialogContent>
          <Typography>{confirmMessage}</Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConfirmDialogOpen(false)}>Cancel</Button>
          <Button
            onClick={() => {
              confirmAction();
              setConfirmDialogOpen(false);
            }}
            color="error"
            variant="contained"
          >
            Delete
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default JiraTemplatesManagement;
