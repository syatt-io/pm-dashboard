import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
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
} from '@mui/material';
import {
  ExpandMore,
  Edit,
  Folder as EpicIcon,
  Task as TaskIcon,
  CheckCircle,
} from '@mui/icons-material';
import { getApiUrl } from '../config';
import { useNotify } from 'react-admin';

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
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [editingEpic, setEditingEpic] = useState<TemplateEpic | null>(null);
  const [editForm, setEditForm] = useState({
    epic_name: '',
    summary: '',
    description: '',
  });
  const notify = useNotify();

  const fetchEpics = async () => {
    try {
      setLoading(true);
      const token = localStorage.getItem('token');
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

  useEffect(() => {
    fetchEpics();
  }, []);

  const handleEditEpic = (epic: TemplateEpic) => {
    setEditingEpic(epic);
    setEditForm({
      epic_name: epic.epic_name,
      summary: epic.summary,
      description: epic.description,
    });
    setEditDialogOpen(true);
  };

  const handleSaveEpic = async () => {
    if (!editingEpic) return;

    try {
      const token = localStorage.getItem('token');
      const response = await fetch(
        `${getApiUrl()}/api/jira-templates/epics/${editingEpic.id}`,
        {
          method: 'PUT',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(editForm),
        }
      );

      if (!response.ok) {
        throw new Error('Failed to update epic');
      }

      notify('Epic updated successfully', { type: 'success' });
      setEditDialogOpen(false);
      fetchEpics(); // Refresh list
    } catch (error: any) {
      notify(`Error updating epic: ${error.message}`, { type: 'error' });
    }
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
        <Alert severity="info" sx={{ flexGrow: 1, ml: 3 }}>
          These templates will be used to create epics and tickets in new Jira projects.
          {epics.length > 0 && ` Currently ${epics.length} epics with ${epics.reduce((sum, e) => sum + e.ticket_count, 0)} tickets.`}
        </Alert>
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
                <Chip
                  label={`${epic.ticket_count} tickets`}
                  size="small"
                  variant="outlined"
                />
                <IconButton
                  size="small"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleEditEpic(epic);
                  }}
                  sx={{ ml: 'auto' }}
                >
                  <Edit fontSize="small" />
                </IconButton>
              </Box>
            </AccordionSummary>
            <AccordionDetails>
              <Box>
                {epic.summary && (
                  <Typography variant="body2" color="text.secondary" mb={2}>
                    {epic.summary}
                  </Typography>
                )}

                <Typography variant="subtitle2" fontWeight={600} mb={1}>
                  Tickets ({epic.ticket_count})
                </Typography>

                <TableContainer component={Paper} variant="outlined">
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell>Issue Type</TableCell>
                        <TableCell>Summary</TableCell>
                        <TableCell>Description</TableCell>
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

      {/* Edit Epic Dialog */}
      <Dialog
        open={editDialogOpen}
        onClose={() => setEditDialogOpen(false)}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>Edit Epic Template</DialogTitle>
        <DialogContent>
          <Box display="flex" flexDirection="column" gap={2} mt={1}>
            <TextField
              label="Epic Name"
              value={editForm.epic_name}
              onChange={(e) =>
                setEditForm({ ...editForm, epic_name: e.target.value })
              }
              fullWidth
            />
            <TextField
              label="Summary"
              value={editForm.summary}
              onChange={(e) =>
                setEditForm({ ...editForm, summary: e.target.value })
              }
              fullWidth
            />
            <TextField
              label="Description"
              value={editForm.description}
              onChange={(e) =>
                setEditForm({ ...editForm, description: e.target.value })
              }
              fullWidth
              multiline
              rows={4}
            />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setEditDialogOpen(false)}>Cancel</Button>
          <Button onClick={handleSaveEpic} variant="contained">
            Save
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default JiraTemplatesManagement;
