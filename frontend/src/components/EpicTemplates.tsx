import React, { useState, useEffect } from 'react';
import {
  Card,
  CardContent,
  Typography,
  Box,
  TextField,
  Button,
  Alert,
  Snackbar,
  CircularProgress,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  IconButton,
  Tooltip,
} from '@mui/material';
import {
  Add as AddIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
  Save as SaveIcon,
  Cancel as CancelIcon,
  DragIndicator as DragIcon,
} from '@mui/icons-material';
import { Title, Loading, useNotify, usePermissions } from 'react-admin';
import { getApiUrl } from '../config';
import { DragDropContext, Droppable, Draggable, DropResult } from '@hello-pangea/dnd';

interface EpicTemplate {
  id: number;
  name: string;
  description: string | null;
  typical_hours_min: number | null;
  typical_hours_max: number | null;
  order: number;
}

const EpicTemplates: React.FC = () => {
  const { permissions } = usePermissions();
  const notify = useNotify();

  // All hooks must be called before any conditional returns
  const [templates, setTemplates] = useState<EpicTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [editingTemplate, setEditingTemplate] = useState<EpicTemplate | null>(null);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [formData, setFormData] = useState<Partial<EpicTemplate>>({
    name: '',
    description: '',
    typical_hours_min: null,
    typical_hours_max: null,
  });
  const [snackbar, setSnackbar] = useState<{ open: boolean; message: string; severity: 'success' | 'error' }>({
    open: false,
    message: '',
    severity: 'success',
  });

  useEffect(() => {
    if (permissions === 'admin') {
      fetchTemplates();
    }
  }, [permissions]);

  // Admin only - show access denied if not admin
  if (permissions !== 'admin') {
    return (
      <Card>
        <Title title="Epic Templates" />
        <CardContent>
          <Alert severity="error">
            Access Denied. This page is only accessible to administrators.
          </Alert>
        </CardContent>
      </Card>
    );
  }

  const fetchTemplates = async () => {
    try {
      const token = localStorage.getItem('auth_token');
      const response = await fetch(`${getApiUrl()}/api/epic-templates`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error('Failed to fetch templates');
      }

      const data = await response.json();
      setTemplates(data.templates || []);
    } catch (error) {
      console.error('Error fetching templates:', error);
      showSnackbar('Failed to fetch templates', 'error');
    } finally {
      setLoading(false);
    }
  };

  const showSnackbar = (message: string, severity: 'success' | 'error') => {
    setSnackbar({ open: true, message, severity });
  };

  const handleCloseSnackbar = () => {
    setSnackbar({ ...snackbar, open: false });
  };

  const handleOpenDialog = (template?: EpicTemplate) => {
    if (template) {
      setEditingTemplate(template);
      setFormData({
        name: template.name,
        description: template.description || '',
        typical_hours_min: template.typical_hours_min,
        typical_hours_max: template.typical_hours_max,
      });
    } else {
      setEditingTemplate(null);
      setFormData({
        name: '',
        description: '',
        typical_hours_min: null,
        typical_hours_max: null,
      });
    }
    setIsDialogOpen(true);
  };

  const handleCloseDialog = () => {
    setIsDialogOpen(false);
    setEditingTemplate(null);
    setFormData({
      name: '',
      description: '',
      typical_hours_min: null,
      typical_hours_max: null,
    });
  };

  const handleSaveTemplate = async () => {
    if (!formData.name?.trim()) {
      showSnackbar('Template name is required', 'error');
      return;
    }

    setSaving(true);
    try {
      const token = localStorage.getItem('auth_token');
      const url = editingTemplate
        ? `${getApiUrl()}/api/epic-templates/${editingTemplate.id}`
        : `${getApiUrl()}/api/epic-templates`;
      const method = editingTemplate ? 'PUT' : 'POST';

      const response = await fetch(url, {
        method,
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(formData),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Failed to save template');
      }

      showSnackbar(
        editingTemplate ? 'Template updated successfully' : 'Template created successfully',
        'success'
      );
      handleCloseDialog();
      await fetchTemplates();
    } catch (error: any) {
      console.error('Error saving template:', error);
      showSnackbar(error.message || 'Failed to save template', 'error');
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteTemplate = async (template: EpicTemplate) => {
    if (!window.confirm(`Are you sure you want to delete "${template.name}"?`)) {
      return;
    }

    setSaving(true);
    try {
      const token = localStorage.getItem('auth_token');
      const response = await fetch(`${getApiUrl()}/api/epic-templates/${template.id}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error('Failed to delete template');
      }

      showSnackbar('Template deleted successfully', 'success');
      await fetchTemplates();
    } catch (error) {
      console.error('Error deleting template:', error);
      showSnackbar('Failed to delete template', 'error');
    } finally {
      setSaving(false);
    }
  };

  const handleDragEnd = async (result: DropResult) => {
    if (!result.destination) {
      return;
    }

    const items = Array.from(templates);
    const [reorderedItem] = items.splice(result.source.index, 1);
    items.splice(result.destination.index, 0, reorderedItem);

    // Optimistically update UI
    setTemplates(items);

    // Save new order to backend
    try {
      const token = localStorage.getItem('auth_token');
      const response = await fetch(`${getApiUrl()}/api/epic-templates/reorder`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          template_ids: items.map(t => t.id),
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to reorder templates');
      }

      showSnackbar('Templates reordered successfully', 'success');
    } catch (error) {
      console.error('Error reordering templates:', error);
      showSnackbar('Failed to reorder templates', 'error');
      // Revert on error
      await fetchTemplates();
    }
  };

  if (loading) {
    return <Loading />;
  }

  return (
    <Box sx={{ p: 3 }}>
      <Title title="Epic Templates" />

      <Card>
        <CardContent>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
            <Typography variant="h5" component="h2">
              Standard Epic Templates
            </Typography>
            <Button
              variant="contained"
              startIcon={<AddIcon />}
              onClick={() => handleOpenDialog()}
              disabled={saving}
            >
              Add Template
            </Button>
          </Box>

          <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
            Define standard epic names and hour ranges for project forecasting. Drag to reorder.
          </Typography>

          {templates.length === 0 ? (
            <Alert severity="info">
              No epic templates defined yet. Click "Add Template" to create one.
            </Alert>
          ) : (
            <DragDropContext onDragEnd={handleDragEnd}>
              <Droppable droppableId="templates">
                {(provided) => (
                  <TableContainer component={Paper} {...provided.droppableProps} ref={provided.innerRef}>
                    <Table>
                      <TableHead>
                        <TableRow>
                          <TableCell width="40px"></TableCell>
                          <TableCell><strong>Name</strong></TableCell>
                          <TableCell><strong>Description</strong></TableCell>
                          <TableCell align="center"><strong>Min Hours</strong></TableCell>
                          <TableCell align="center"><strong>Max Hours</strong></TableCell>
                          <TableCell align="right"><strong>Actions</strong></TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {templates.map((template, index) => (
                          <Draggable
                            key={template.id}
                            draggableId={String(template.id)}
                            index={index}
                          >
                            {(provided, snapshot) => (
                              <TableRow
                                ref={provided.innerRef}
                                {...provided.draggableProps}
                                sx={{
                                  backgroundColor: snapshot.isDragging ? 'action.hover' : 'inherit',
                                }}
                              >
                                <TableCell {...provided.dragHandleProps}>
                                  <DragIcon color="action" />
                                </TableCell>
                                <TableCell>{template.name}</TableCell>
                                <TableCell>
                                  <Typography variant="body2" color="text.secondary">
                                    {template.description || '—'}
                                  </Typography>
                                </TableCell>
                                <TableCell align="center">
                                  {template.typical_hours_min || '—'}
                                </TableCell>
                                <TableCell align="center">
                                  {template.typical_hours_max || '—'}
                                </TableCell>
                                <TableCell align="right">
                                  <Tooltip title="Edit">
                                    <IconButton
                                      size="small"
                                      onClick={() => handleOpenDialog(template)}
                                      disabled={saving}
                                    >
                                      <EditIcon fontSize="small" />
                                    </IconButton>
                                  </Tooltip>
                                  <Tooltip title="Delete">
                                    <IconButton
                                      size="small"
                                      onClick={() => handleDeleteTemplate(template)}
                                      disabled={saving}
                                      color="error"
                                    >
                                      <DeleteIcon fontSize="small" />
                                    </IconButton>
                                  </Tooltip>
                                </TableCell>
                              </TableRow>
                            )}
                          </Draggable>
                        ))}
                        {provided.placeholder}
                      </TableBody>
                    </Table>
                  </TableContainer>
                )}
              </Droppable>
            </DragDropContext>
          )}
        </CardContent>
      </Card>

      {/* Create/Edit Dialog */}
      <Dialog open={isDialogOpen} onClose={handleCloseDialog} maxWidth="sm" fullWidth>
        <DialogTitle>
          {editingTemplate ? 'Edit Epic Template' : 'Create Epic Template'}
        </DialogTitle>
        <DialogContent>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 1 }}>
            <TextField
              label="Template Name"
              value={formData.name || ''}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              required
              fullWidth
              autoFocus
            />
            <TextField
              label="Description"
              value={formData.description || ''}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              multiline
              rows={3}
              fullWidth
            />
            <Box sx={{ display: 'flex', gap: 2 }}>
              <TextField
                label="Typical Min Hours"
                type="number"
                value={formData.typical_hours_min || ''}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    typical_hours_min: e.target.value ? parseInt(e.target.value) : null,
                  })
                }
                fullWidth
              />
              <TextField
                label="Typical Max Hours"
                type="number"
                value={formData.typical_hours_max || ''}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    typical_hours_max: e.target.value ? parseInt(e.target.value) : null,
                  })
                }
                fullWidth
              />
            </Box>
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseDialog} disabled={saving}>
            Cancel
          </Button>
          <Button
            onClick={handleSaveTemplate}
            variant="contained"
            disabled={saving || !formData.name?.trim()}
            startIcon={saving ? <CircularProgress size={20} /> : <SaveIcon />}
          >
            {saving ? 'Saving...' : 'Save'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Snackbar for notifications */}
      <Snackbar
        open={snackbar.open}
        autoHideDuration={6000}
        onClose={handleCloseSnackbar}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert onClose={handleCloseSnackbar} severity={snackbar.severity} sx={{ width: '100%' }}>
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Box>
  );
};

export default EpicTemplates;
