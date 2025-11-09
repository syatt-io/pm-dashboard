import React, { useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  Box,
  Alert,
  CircularProgress,
} from '@mui/material';
import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL ||
  (window.location.hostname === 'localhost'
    ? 'http://localhost:4000'
    : 'https://agent-pm-tsbbb.ondigitalocean.app');

interface AddEpicBudgetDialogProps {
  open: boolean;
  onClose: () => void;
  projectKey: string;
  onSuccess: () => void;
}

const AddEpicBudgetDialog: React.FC<AddEpicBudgetDialogProps> = ({
  open,
  onClose,
  projectKey,
  onSuccess,
}) => {
  const [epicKey, setEpicKey] = useState('');
  const [epicSummary, setEpicSummary] = useState('');
  const [estimatedHours, setEstimatedHours] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    if (!epicKey || !estimatedHours) {
      setError('Epic Key and Estimated Hours are required');
      return;
    }

    const hours = parseFloat(estimatedHours);
    if (isNaN(hours) || hours <= 0) {
      setError('Please enter a valid positive number for hours');
      return;
    }

    try {
      setLoading(true);
      setError(null);

      await axios.post(`${API_BASE_URL}/api/epic-budgets`, {
        project_key: projectKey,
        epic_key: epicKey,
        epic_summary: epicSummary,
        estimated_hours: hours,
      });

      // Reset form
      setEpicKey('');
      setEpicSummary('');
      setEstimatedHours('');

      onSuccess();
      onClose();
    } catch (err: any) {
      console.error('Error creating budget:', err);
      setError(err.response?.data?.error || 'Failed to create budget');
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    setEpicKey('');
    setEpicSummary('');
    setEstimatedHours('');
    setError(null);
    onClose();
  };

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
      <DialogTitle>Add Epic Budget</DialogTitle>
      <DialogContent>
        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}

        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 1 }}>
          <TextField
            label="Epic Key"
            value={epicKey}
            onChange={(e) => setEpicKey(e.target.value.toUpperCase())}
            placeholder="e.g., PROJ-123"
            required
            fullWidth
            disabled={loading}
          />

          <TextField
            label="Epic Summary"
            value={epicSummary}
            onChange={(e) => setEpicSummary(e.target.value)}
            placeholder="Brief description of the epic"
            fullWidth
            disabled={loading}
          />

          <TextField
            label="Estimated Hours"
            type="number"
            value={estimatedHours}
            onChange={(e) => setEstimatedHours(e.target.value)}
            placeholder="e.g., 120"
            required
            fullWidth
            disabled={loading}
            inputProps={{ min: 0, step: 0.5 }}
          />
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={handleClose} disabled={loading}>
          Cancel
        </Button>
        <Button
          onClick={handleSubmit}
          variant="contained"
          disabled={loading}
        >
          {loading ? <CircularProgress size={24} /> : 'Add Budget'}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default AddEpicBudgetDialog;
