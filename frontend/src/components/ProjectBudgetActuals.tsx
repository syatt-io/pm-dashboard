import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  CircularProgress,
  Alert,
  TextField,
  IconButton,
  Tooltip,
} from '@mui/material';
import {
  Edit as EditIcon,
  Check as CheckIcon,
  Close as CloseIcon,
} from '@mui/icons-material';
import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL ||
  (window.location.hostname === 'localhost'
    ? 'http://localhost:4000'
    : 'https://agent-pm-tsbbb.ondigitalocean.app');

interface EpicBudget {
  id: number;
  project_key: string;
  epic_key: string;
  epic_summary: string;
  estimated_hours: number;
  total_actual: number;
  remaining: number;
  pct_complete: number;
  actuals_by_month: { [month: string]: number };
}

interface ProjectBudgetActualsProps {
  projectKey: string;
}

const ProjectBudgetActuals: React.FC<ProjectBudgetActualsProps> = ({ projectKey }) => {
  const [budgets, setBudgets] = useState<EpicBudget[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editValue, setEditValue] = useState<string>('');

  // Get unique months from all budgets
  const allMonths = Array.from(
    new Set(
      budgets.flatMap(b => Object.keys(b.actuals_by_month || {}))
    )
  ).sort();

  useEffect(() => {
    loadBudgets();
  }, [projectKey]);

  const loadBudgets = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await axios.get(`${API_BASE_URL}/api/epic-budgets/${projectKey}`);
      setBudgets(response.data.budgets || []);
    } catch (err: any) {
      console.error('Error loading budgets:', err);
      setError(err.response?.data?.error || 'Failed to load budget data');
    } finally {
      setLoading(false);
    }
  };

  const handleStartEdit = (budget: EpicBudget) => {
    setEditingId(budget.id);
    setEditValue(budget.estimated_hours.toString());
  };

  const handleSaveEdit = async (budgetId: number) => {
    try {
      const newValue = parseFloat(editValue);
      if (isNaN(newValue) || newValue < 0) {
        alert('Please enter a valid positive number');
        return;
      }

      await axios.put(`${API_BASE_URL}/api/epic-budgets/${budgetId}`, {
        estimated_hours: newValue,
      });

      // Reload budgets to get updated calculations
      await loadBudgets();
      setEditingId(null);
    } catch (err: any) {
      console.error('Error updating budget:', err);
      alert(err.response?.data?.error || 'Failed to update budget');
    }
  };

  const handleCancelEdit = () => {
    setEditingId(null);
    setEditValue('');
  };

  const getStatusColor = (pctComplete: number) => {
    if (pctComplete >= 100) return '#ef5350'; // Red - over budget
    if (pctComplete >= 80) return '#ff9800'; // Orange - warning
    return '#66bb6a'; // Green - on track
  };

  const getStatusIcon = (pctComplete: number) => {
    if (pctComplete >= 100) return '🔴';
    if (pctComplete >= 80) return '🟡';
    return '🟢';
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Alert severity="error" sx={{ mb: 2 }}>
        {error}
      </Alert>
    );
  }

  if (budgets.length === 0) {
    return (
      <Alert severity="info" sx={{ mb: 2 }}>
        No epic budgets configured for this project yet.
      </Alert>
    );
  }

  return (
    <Card>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          Epic Budget vs Actuals
        </Typography>

        <TableContainer component={Paper} sx={{ mt: 2 }}>
          <Table size="small" stickyHeader>
            <TableHead>
              <TableRow>
                <TableCell sx={{ fontWeight: 'bold', minWidth: 200 }}>Epic</TableCell>
                <TableCell align="right" sx={{ fontWeight: 'bold', minWidth: 120 }}>
                  Estimate
                </TableCell>
                {allMonths.map((month) => (
                  <TableCell key={month} align="right" sx={{ fontWeight: 'bold', minWidth: 80 }}>
                    {new Date(month + '-01').toLocaleDateString('en-US', { month: 'short', year: '2-digit' })}
                  </TableCell>
                ))}
                <TableCell align="right" sx={{ fontWeight: 'bold', minWidth: 100 }}>
                  Total Actual
                </TableCell>
                <TableCell align="right" sx={{ fontWeight: 'bold', minWidth: 100 }}>
                  Remaining
                </TableCell>
                <TableCell align="right" sx={{ fontWeight: 'bold', minWidth: 100 }}>
                  % Complete
                </TableCell>
                <TableCell sx={{ minWidth: 60 }}>Status</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {budgets.map((budget) => (
                <TableRow key={budget.id} hover>
                  <TableCell>
                    <Tooltip title={budget.epic_summary || budget.epic_key}>
                      <Typography variant="body2" noWrap sx={{ maxWidth: 200 }}>
                        {budget.epic_key}
                      </Typography>
                    </Tooltip>
                    {budget.epic_summary && (
                      <Typography variant="caption" color="textSecondary" noWrap sx={{ maxWidth: 200, display: 'block' }}>
                        {budget.epic_summary}
                      </Typography>
                    )}
                  </TableCell>
                  <TableCell align="right">
                    {editingId === budget.id ? (
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                        <TextField
                          size="small"
                          type="number"
                          value={editValue}
                          onChange={(e) => setEditValue(e.target.value)}
                          sx={{ width: 80 }}
                        />
                        <IconButton size="small" onClick={() => handleSaveEdit(budget.id)} color="primary">
                          <CheckIcon fontSize="small" />
                        </IconButton>
                        <IconButton size="small" onClick={handleCancelEdit}>
                          <CloseIcon fontSize="small" />
                        </IconButton>
                      </Box>
                    ) : (
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, justifyContent: 'flex-end' }}>
                        <Typography variant="body2">
                          {budget.estimated_hours.toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 })}h
                        </Typography>
                        <IconButton size="small" onClick={() => handleStartEdit(budget)}>
                          <EditIcon fontSize="small" />
                        </IconButton>
                      </Box>
                    )}
                  </TableCell>
                  {allMonths.map((month) => (
                    <TableCell key={month} align="right">
                      <Typography variant="body2">
                        {(budget.actuals_by_month[month] || 0).toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 })}
                      </Typography>
                    </TableCell>
                  ))}
                  <TableCell align="right">
                    <Typography variant="body2" sx={{ fontWeight: 600 }}>
                      {budget.total_actual.toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 })}h
                    </Typography>
                  </TableCell>
                  <TableCell align="right">
                    <Typography
                      variant="body2"
                      sx={{
                        color: budget.remaining < 0 ? '#ef5350' : 'text.primary',
                        fontWeight: budget.remaining < 0 ? 600 : 400
                      }}
                    >
                      {budget.remaining.toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 })}h
                    </Typography>
                  </TableCell>
                  <TableCell align="right">
                    <Typography
                      variant="body2"
                      sx={{ color: getStatusColor(budget.pct_complete), fontWeight: 600 }}
                    >
                      {budget.pct_complete.toFixed(1)}%
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2">
                      {getStatusIcon(budget.pct_complete)}
                    </Typography>
                  </TableCell>
                </TableRow>
              ))}

              {/* Totals Row */}
              <TableRow sx={{ backgroundColor: '#f5f5f5', borderTop: '2px solid #ddd' }}>
                <TableCell sx={{ fontWeight: 'bold' }}>
                  TOTAL
                </TableCell>
                <TableCell align="right" sx={{ fontWeight: 'bold' }}>
                  {budgets.reduce((sum, b) => sum + b.estimated_hours, 0).toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 })}h
                </TableCell>
                {allMonths.map((month) => (
                  <TableCell key={month} align="right" sx={{ fontWeight: 'bold' }}>
                    {budgets.reduce((sum, b) => sum + (b.actuals_by_month[month] || 0), 0).toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 })}
                  </TableCell>
                ))}
                <TableCell align="right" sx={{ fontWeight: 'bold' }}>
                  {budgets.reduce((sum, b) => sum + b.total_actual, 0).toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 })}h
                </TableCell>
                <TableCell align="right" sx={{ fontWeight: 'bold' }}>
                  {budgets.reduce((sum, b) => sum + b.remaining, 0).toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 })}h
                </TableCell>
                <TableCell align="right" sx={{ fontWeight: 'bold' }}>
                  {(budgets.reduce((sum, b) => sum + b.total_actual, 0) /
                    budgets.reduce((sum, b) => sum + b.estimated_hours, 0) * 100).toFixed(1)}%
                </TableCell>
                <TableCell />
              </TableRow>
            </TableBody>
          </Table>
        </TableContainer>
      </CardContent>
    </Card>
  );
};

export default ProjectBudgetActuals;
