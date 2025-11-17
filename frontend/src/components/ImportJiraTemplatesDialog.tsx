import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Box,
  Typography,
  Checkbox,
  FormControlLabel,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Chip,
  CircularProgress,
  Alert,
  LinearProgress,
} from '@mui/material';
import { CheckCircle, Error as ErrorIcon } from '@mui/icons-material';
import { getApiUrl } from '../config';
import { useNotify } from 'react-admin';

interface TemplateTicket {
  id: number;
  summary: string;
  issue_type: string;
}

interface TemplateEpic {
  id: number;
  epic_name: string;
  summary: string;
  epic_color: string;
  ticket_count: number;
  tickets: TemplateTicket[];
}

interface ImportJiraTemplatesDialogProps {
  open: boolean;
  onClose: () => void;
  projectKey: string;
  onSuccess?: () => void;
}

const ImportJiraTemplatesDialog: React.FC<ImportJiraTemplatesDialogProps> = ({
  open,
  onClose,
  projectKey,
  onSuccess,
}) => {
  const [epics, setEpics] = useState<TemplateEpic[]>([]);
  const [selectedEpicIds, setSelectedEpicIds] = useState<Set<number>>(new Set());
  const [importTickets, setImportTickets] = useState(true);
  const [loading, setLoading] = useState(false);
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState<any>(null);
  const notify = useNotify();

  // Fetch templates when dialog opens
  useEffect(() => {
    if (open) {
      fetchTemplates();
      setImportResult(null);
    }
  }, [open]);

  const fetchTemplates = async () => {
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

      // Select all epics by default
      const allEpicIds = (data.epics || []).map((epic: TemplateEpic) => epic.id);
      setSelectedEpicIds(new Set(allEpicIds));
    } catch (error: any) {
      notify(`Error loading templates: ${error.message}`, { type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  const toggleEpic = (epicId: number) => {
    const newSelected = new Set(selectedEpicIds);
    if (newSelected.has(epicId)) {
      newSelected.delete(epicId);
    } else {
      newSelected.add(epicId);
    }
    setSelectedEpicIds(newSelected);
  };

  const toggleSelectAll = () => {
    if (selectedEpicIds.size === epics.length) {
      setSelectedEpicIds(new Set());
    } else {
      setSelectedEpicIds(new Set(epics.map((e) => e.id)));
    }
  };

  const handleImport = async () => {
    if (selectedEpicIds.size === 0) {
      notify('Please select at least one epic to import', { type: 'warning' });
      return;
    }

    try {
      setImporting(true);
      const token = localStorage.getItem('auth_token');
      const response = await fetch(
        `${getApiUrl()}/api/jira-templates/import/${projectKey}`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            epic_ids: Array.from(selectedEpicIds),
            import_tickets: importTickets,
          }),
        }
      );

      if (!response.ok) {
        throw new Error('Failed to import templates');
      }

      const result = await response.json();
      setImportResult(result);

      if (result.success) {
        notify(
          `Successfully imported ${result.imported.epics} epics and ${result.imported.tickets} tickets`,
          { type: 'success' }
        );
        if (onSuccess) {
          onSuccess();
        }
      }
    } catch (error: any) {
      notify(`Error importing templates: ${error.message}`, { type: 'error' });
    } finally {
      setImporting(false);
    }
  };

  const selectedEpics = epics.filter((e) => selectedEpicIds.has(e.id));
  const totalTickets = selectedEpics.reduce((sum, e) => sum + e.ticket_count, 0);

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>
        Import Starter Templates to {projectKey}
      </DialogTitle>

      <DialogContent>
        {loading ? (
          <Box display="flex" justifyContent="center" p={4}>
            <CircularProgress />
          </Box>
        ) : importResult ? (
          // Show results
          <Box>
            <Alert severity="success" sx={{ mb: 2 }}>
              Import complete! Created {importResult.imported.epics} epics and{' '}
              {importResult.imported.tickets} tickets.
            </Alert>

            <Typography variant="h6" mb={2}>
              Created Epics
            </Typography>

            <TableContainer component={Paper} variant="outlined">
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableRow>
                      <TableCell>Epic Name</TableCell>
                      <TableCell>Epic Key</TableCell>
                      <TableCell>Tickets Created</TableCell>
                      <TableCell>Status</TableCell>
                    </TableRow>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {importResult.details.map((detail: any) => (
                    <TableRow key={detail.template_epic_id}>
                      <TableCell>{detail.epic_name}</TableCell>
                      <TableCell>
                        <Chip label={detail.epic_key} size="small" />
                      </TableCell>
                      <TableCell>{detail.tickets_created}</TableCell>
                      <TableCell>
                        <Chip
                          icon={<CheckCircle />}
                          label={detail.status}
                          size="small"
                          color="success"
                        />
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>

            {importResult.errors && importResult.errors.length > 0 && (
              <Box mt={2}>
                <Typography variant="h6" mb={1}>
                  Errors
                </Typography>
                {importResult.errors.map((error: any, index: number) => (
                  <Alert key={index} severity="error" sx={{ mb: 1 }}>
                    {error.epic_name}: {error.error}
                  </Alert>
                ))}
              </Box>
            )}
          </Box>
        ) : (
          // Show selection UI
          <Box>
            <Alert severity="info" sx={{ mb: 2 }}>
              Select which starter epics and tickets to import into project {projectKey}.
            </Alert>

            <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
              <FormControlLabel
                control={
                  <Checkbox
                    checked={selectedEpicIds.size === epics.length}
                    indeterminate={
                      selectedEpicIds.size > 0 && selectedEpicIds.size < epics.length
                    }
                    onChange={toggleSelectAll}
                  />
                }
                label={`Select All (${selectedEpicIds.size}/${epics.length})`}
              />

              <FormControlLabel
                control={
                  <Checkbox
                    checked={importTickets}
                    onChange={(e) => setImportTickets(e.target.checked)}
                  />
                }
                label="Import tickets with epics"
              />
            </Box>

            {selectedEpics.length > 0 && (
              <Alert severity="info" sx={{ mb: 2 }}>
                Will create {selectedEpics.length} epics
                {importTickets && ` and ${totalTickets} tickets`}
              </Alert>
            )}

            <TableContainer component={Paper} variant="outlined" sx={{ maxHeight: 400 }}>
              <Table size="small" stickyHeader>
                <TableHead>
                  <TableRow>
                    <TableCell padding="checkbox"></TableCell>
                    <TableCell>Epic Name</TableCell>
                    <TableCell>Tickets</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {epics.map((epic) => (
                    <TableRow key={epic.id} hover>
                      <TableCell padding="checkbox">
                        <Checkbox
                          checked={selectedEpicIds.has(epic.id)}
                          onChange={() => toggleEpic(epic.id)}
                        />
                      </TableCell>
                      <TableCell>
                        <Box display="flex" alignItems="center" gap={1}>
                          <Box
                            width={12}
                            height={12}
                            borderRadius="2px"
                            bgcolor={epic.epic_color}
                          />
                          <Typography fontWeight={500}>{epic.epic_name}</Typography>
                        </Box>
                        <Typography variant="caption" color="text.secondary">
                          {epic.summary}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Chip label={epic.ticket_count} size="small" />
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </Box>
        )}

        {importing && (
          <Box mt={2}>
            <LinearProgress />
            <Typography variant="body2" color="text.secondary" mt={1} textAlign="center">
              Creating epics and tickets in Jira...
            </Typography>
          </Box>
        )}
      </DialogContent>

      <DialogActions>
        {importResult ? (
          <Button onClick={onClose} variant="contained">
            Close
          </Button>
        ) : (
          <>
            <Button onClick={onClose} disabled={importing}>
              Cancel
            </Button>
            <Button
              onClick={handleImport}
              variant="contained"
              disabled={importing || selectedEpicIds.size === 0}
            >
              {importing ? 'Importing...' : 'Import Selected'}
            </Button>
          </>
        )}
      </DialogActions>
    </Dialog>
  );
};

export default ImportJiraTemplatesDialog;
