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
} from '@mui/material';
import { Download as DownloadIcon, Refresh as RefreshIcon } from '@mui/icons-material';
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
  const [loading, setLoading] = useState(false);
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

  useEffect(() => {
    if (projectKey) {
      fetchEpics();
    }
  }, [projectKey]);

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
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h6">Epics from Jira</Typography>
        <Button
          variant="contained"
          startIcon={loading ? <CircularProgress size={20} /> : <RefreshIcon />}
          onClick={fetchEpics}
          disabled={loading}
        >
          {loading ? 'Loading...' : 'Refresh Epics'}
        </Button>
      </Box>

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
            Showing {epics.length} epic{epics.length !== 1 ? 's' : ''}
          </Typography>

          <TableContainer component={Paper}>
            <Table>
              <TableHead>
                <TableRow>
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
    </Box>
  );
};
