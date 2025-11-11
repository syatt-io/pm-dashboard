import React, { useState, useEffect } from 'react';
import {
  Box,
  Button,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
  CircularProgress,
  Chip,
  Alert,
  Checkbox,
  Collapse,
  IconButton,
} from '@mui/material';
import {
  Download as DownloadIcon,
  Refresh as RefreshIcon,
  CloudDownload as ImportIcon,
  ExpandMore as ExpandMoreIcon,
  ExpandLess as ExpandLessIcon,
} from '@mui/icons-material';
import { useNotify } from 'react-admin';

interface Epic {
  key: string;
  summary: string;
  status: string;
  created: string;
  updated: string;
  assignee: string | null;
  description: string;
}

interface ProjectEpicsTabProps {
  projectKey: string;
}

export const ProjectEpicsTab: React.FC<ProjectEpicsTabProps> = ({ projectKey }) => {
  const [epics, setEpics] = useState<Epic[]>([]);
  const [selectedEpics, setSelectedEpics] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(false);
  const [importing, setImporting] = useState(false);
  const [isExpanded, setIsExpanded] = useState(true); // Auto-expand by default for easier access
  const [error, setError] = useState<string | null>(null);
  const notify = useNotify();

  const fetchEpics = async () => {
    setLoading(true);
    setError(null);

    try {
      const token = localStorage.getItem('auth_token');
      const response = await fetch(`/api/jira/projects/${projectKey}/epics`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error(`Failed to fetch epics: ${response.statusText}`);
      }

      const data = await response.json();

      if (data.success) {
        setEpics(data.data.epics);
        notify(`Loaded ${data.data.count} epics`, { type: 'success' });
      } else {
        throw new Error(data.error || 'Failed to fetch epics');
      }
    } catch (err: any) {
      const errorMessage = err.message || 'An error occurred while fetching epics';
      setError(errorMessage);
      notify(errorMessage, { type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  const importToBudgets = async () => {
    if (selectedEpics.size === 0) {
      notify('Please select at least one epic to import', { type: 'warning' });
      return;
    }

    setImporting(true);
    setError(null);

    try {
      const token = localStorage.getItem('auth_token');

      // Filter epics to only include selected ones
      const epicsToImport = epics
        .filter(epic => selectedEpics.has(epic.key))
        .map(epic => ({
          epic_key: epic.key,
          epic_summary: epic.summary,
          estimated_hours: 0
        }));

      const response = await fetch(`/api/epic-budgets/bulk`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          project_key: projectKey,
          budgets: epicsToImport
        }),
      });

      if (!response.ok) {
        throw new Error(`Failed to import epics: ${response.statusText}`);
      }

      const data = await response.json();

      notify(
        `Import complete: ${data.created} new budgets created, ${data.updated} already existed`,
        { type: 'success' }
      );

      // Clear selection and collapse section
      setSelectedEpics(new Set());
      setIsExpanded(false);

      // Optionally refresh the page to show updated budgets section
      window.location.reload();
    } catch (err: any) {
      const errorMessage = err.message || 'An error occurred while importing epics';
      setError(errorMessage);
      notify(errorMessage, { type: 'error' });
    } finally {
      setImporting(false);
    }
  };

  const handleSelectAll = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.checked) {
      setSelectedEpics(new Set(epics.map(e => e.key)));
    } else {
      setSelectedEpics(new Set());
    }
  };

  const handleSelectEpic = (epicKey: string) => {
    const newSelection = new Set(selectedEpics);
    if (newSelection.has(epicKey)) {
      newSelection.delete(epicKey);
    } else {
      newSelection.add(epicKey);
    }
    setSelectedEpics(newSelection);
  };

  // Removed automatic epic fetching on mount - user must click "Refresh Epics" button
  // useEffect(() => {
  //   if (projectKey) {
  //     fetchEpics();
  //   }
  // }, [projectKey]);

  const formatDate = (dateString: string | null) => {
    if (!dateString) return 'N/A';
    try {
      return new Date(dateString).toLocaleDateString();
    } catch {
      return dateString;
    }
  };

  const getStatusColor = (status: string): 'default' | 'primary' | 'secondary' | 'error' | 'info' | 'success' | 'warning' => {
    const statusLower = status.toLowerCase();
    if (statusLower.includes('done') || statusLower.includes('closed')) return 'success';
    if (statusLower.includes('progress') || statusLower.includes('active')) return 'primary';
    if (statusLower.includes('todo') || statusLower.includes('backlog')) return 'default';
    return 'info';
  };

  return (
    <Box sx={{ p: 3 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Typography variant="h6">Import Epics from Jira</Typography>
          <IconButton
            size="small"
            onClick={() => setIsExpanded(!isExpanded)}
          >
            {isExpanded ? <ExpandLessIcon /> : <ExpandMoreIcon />}
          </IconButton>
        </Box>
        <Box sx={{ display: 'flex', gap: 2 }}>
          <Button
            variant="outlined"
            startIcon={loading ? <CircularProgress size={20} /> : <RefreshIcon />}
            onClick={fetchEpics}
            disabled={loading || importing}
          >
            {loading ? 'Loading...' : 'Refresh Epics'}
          </Button>
          <Button
            variant="contained"
            color="primary"
            startIcon={importing ? <CircularProgress size={20} /> : <ImportIcon />}
            onClick={importToBudgets}
            disabled={loading || importing || selectedEpics.size === 0}
          >
            {importing ? 'Importing...' : `Import Selected (${selectedEpics.size})`}
          </Button>
        </Box>
      </Box>

      <Collapse in={isExpanded}>
        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}

        {epics.length === 0 && !loading && !error && (
          <Alert severity="info">
            No epics found for this project. Click "Refresh Epics" to fetch from Jira.
          </Alert>
        )}

        {epics.length > 0 && (
          <>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              Showing {epics.length} epic{epics.length !== 1 ? 's' : ''} • {selectedEpics.size} selected
            </Typography>

            <TableContainer component={Paper}>
              <Table>
                <TableHead>
                  <TableRow>
                    <TableCell padding="checkbox">
                      <Checkbox
                        checked={selectedEpics.size === epics.length && epics.length > 0}
                        indeterminate={selectedEpics.size > 0 && selectedEpics.size < epics.length}
                        onChange={handleSelectAll}
                      />
                    </TableCell>
                    <TableCell><strong>Key</strong></TableCell>
                    <TableCell><strong>Summary</strong></TableCell>
                    <TableCell><strong>Status</strong></TableCell>
                    <TableCell><strong>Assignee</strong></TableCell>
                    <TableCell><strong>Created</strong></TableCell>
                    <TableCell><strong>Updated</strong></TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {epics.map((epic) => (
                    <TableRow key={epic.key} hover>
                      <TableCell padding="checkbox">
                        <Checkbox
                          checked={selectedEpics.has(epic.key)}
                          onChange={() => handleSelectEpic(epic.key)}
                        />
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" fontWeight="medium">
                          {epic.key}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2">
                          {epic.summary}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Chip
                          label={epic.status}
                          size="small"
                          color={getStatusColor(epic.status)}
                        />
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2">
                          {epic.assignee || 'Unassigned'}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" color="text.secondary">
                          {formatDate(epic.created)}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" color="text.secondary">
                          {formatDate(epic.updated)}
                        </Typography>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </>
        )}
      </Collapse>
    </Box>
  );
};
