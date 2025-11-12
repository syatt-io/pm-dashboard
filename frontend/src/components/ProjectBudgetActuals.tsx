import React, { useState, useEffect, useMemo } from 'react';
import {
  Box,
  Button,
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
  LinearProgress,
  Alert,
  TextField,
  IconButton,
  Tooltip,
  Select,
  MenuItem,
  FormControl,
  Checkbox,
  Collapse,
  Snackbar,
} from '@mui/material';
import {
  Edit as EditIcon,
  Check as CheckIcon,
  Close as CloseIcon,
  Delete as DeleteIcon,
  Sync as SyncIcon,
  ExpandMore as ExpandMoreIcon,
  CloudDownload as ImportIcon,
  Info as InfoIcon,
  TrendingUp as TrendingUpIcon,
} from '@mui/icons-material';
import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL ||
  (window.location.hostname === 'localhost'
    ? 'http://localhost:4000'
    : 'https://agent-pm-tsbbb.ondigitalocean.app');

interface EpicBudget {
  id: number | null;
  project_key: string;
  epic_key: string;
  epic_summary: string;
  epic_category: string | null;
  estimated_hours: number;
  total_actual: number;
  remaining: number;
  pct_complete: number;
  actuals_by_month: { [month: string]: number };
  is_budgeted: boolean;
}

interface ProjectBudgetActualsProps {
  projectKey: string;
}

const ProjectBudgetActuals: React.FC<ProjectBudgetActualsProps> = ({ projectKey }) => {
  const [budgets, setBudgets] = useState<EpicBudget[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [syncProgress, setSyncProgress] = useState<{current: number; total: number; percent: number; message: string} | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editValue, setEditValue] = useState<string>('');
  const [categories, setCategories] = useState<string[]>([]);
  const [categoryMappings, setCategoryMappings] = useState<{ [epicKey: string]: string }>({});
  const [selectedEpics, setSelectedEpics] = useState<string[]>([]);
  const [bulkCategory, setBulkCategory] = useState<string>('');
  const [expandedCategories, setExpandedCategories] = useState<{ [key: string]: boolean }>({});
  const [successSnackbar, setSuccessSnackbar] = useState<{open: boolean; message: string}>({
    open: false,
    message: ''
  });

  // Group budgets by category
  const groupedBudgets = useMemo(() => {
    const groups: { [key: string]: EpicBudget[] } = {};

    // Sort budgets by epic_summary/epic_key
    const sortedBudgets = [...budgets].sort((a, b) =>
      (a.epic_summary || a.epic_key).localeCompare(b.epic_summary || b.epic_key)
    );

    sortedBudgets.forEach((budget) => {
      const category = categoryMappings[budget.epic_key] || budget.epic_category || 'Uncategorized';
      if (!groups[category]) {
        groups[category] = [];
      }
      groups[category].push(budget);
    });

    return groups;
  }, [budgets, categoryMappings]);

  // Get category order: Uncategorized first, then by display_order from categories array
  const orderedCategories = useMemo(() => {
    const categoryOrder: string[] = [];

    // Add Uncategorized first if it exists
    if (groupedBudgets['Uncategorized']) {
      categoryOrder.push('Uncategorized');
    }

    // Add other categories in their display order
    categories.forEach((cat) => {
      if (groupedBudgets[cat]) {
        categoryOrder.push(cat);
      }
    });

    // Add any remaining categories not in the categories list (edge case)
    Object.keys(groupedBudgets).forEach((cat) => {
      if (!categoryOrder.includes(cat)) {
        categoryOrder.push(cat);
      }
    });

    return categoryOrder;
  }, [groupedBudgets, categories]);

  // Calculate budget totals
  const budgetSummary = useMemo(() => {
    const totalBudget = budgets.reduce((sum, b) => sum + b.estimated_hours, 0);
    const totalActual = budgets.reduce((sum, b) => sum + b.total_actual, 0);
    const totalRemaining = budgets.reduce((sum, b) => sum + b.remaining, 0);
    const overallPctComplete = totalBudget > 0 ? (totalActual / totalBudget) * 100 : 0;

    return {
      totalBudget,
      totalActual,
      totalRemaining,
      overallPctComplete
    };
  }, [budgets]);

  // Get unique months from all budgets
  const allMonths = Array.from(
    new Set(
      budgets.flatMap(b => Object.keys(b.actuals_by_month || {}))
    )
  ).sort();

  // Calculate category subtotals
  const categorySubtotals = useMemo(() => {
    const subtotals: {
      [category: string]: {
        estimatedHours: number;
        monthlyActuals: { [month: string]: number };
        totalActual: number;
        remaining: number;
        pctComplete: number;
      };
    } = {};

    Object.keys(groupedBudgets).forEach((category) => {
      const categoryBudgets = groupedBudgets[category];
      const estimatedHours = categoryBudgets.reduce((sum, b) => sum + b.estimated_hours, 0);
      const totalActual = categoryBudgets.reduce((sum, b) => sum + b.total_actual, 0);
      const remaining = categoryBudgets.reduce((sum, b) => sum + b.remaining, 0);
      const pctComplete = estimatedHours > 0 ? (totalActual / estimatedHours) * 100 : 0;

      const monthlyActuals: { [month: string]: number } = {};
      allMonths.forEach((month) => {
        monthlyActuals[month] = categoryBudgets.reduce(
          (sum, b) => sum + (b.actuals_by_month[month] || 0),
          0
        );
      });

      subtotals[category] = {
        estimatedHours,
        monthlyActuals,
        totalActual,
        remaining,
        pctComplete,
      };
    });

    return subtotals;
  }, [groupedBudgets, allMonths]);

  useEffect(() => {
    loadBudgets();
    loadCategories();
  }, [projectKey]);

  // Initialize all categories as expanded on first load
  useEffect(() => {
    if (orderedCategories.length > 0) {
      const initialExpanded: { [key: string]: boolean } = {};
      orderedCategories.forEach((cat) => {
        if (!(cat in expandedCategories)) {
          initialExpanded[cat] = true;
        }
      });
      if (Object.keys(initialExpanded).length > 0) {
        setExpandedCategories((prev) => ({ ...prev, ...initialExpanded }));
      }
    }
  }, [orderedCategories]);

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

  const loadCategories = async () => {
    try {
      // Load available categories
      const categoriesResponse = await axios.get(`${API_BASE_URL}/api/epic-categories/categories`);
      setCategories(categoriesResponse.data.categories || []);

      // Load category mappings
      const mappingsResponse = await axios.get(`${API_BASE_URL}/api/epic-categories/mappings`);
      setCategoryMappings(mappingsResponse.data.mappings || {});
    } catch (err: any) {
      console.error('Error loading categories:', err);
      // Don't set error state for categories - it's not critical
    }
  };

  const handleCategoryChange = async (epicKey: string, newCategory: string) => {
    try {
      if (newCategory === '') {
        // Delete category mapping
        await axios.delete(`${API_BASE_URL}/api/epic-categories/mappings/${epicKey}`);
        setCategoryMappings((prev) => {
          const updated = { ...prev };
          delete updated[epicKey];
          return updated;
        });
      } else {
        // Set/update category mapping
        await axios.put(`${API_BASE_URL}/api/epic-categories/mappings/${epicKey}`, {
          category: newCategory,
        });
        setCategoryMappings((prev) => ({
          ...prev,
          [epicKey]: newCategory,
        }));
      }

      // Reload budgets to refresh epic_category field
      await loadBudgets();
    } catch (err: any) {
      console.error('Error updating category:', err);
      alert(err.response?.data?.error || 'Failed to update category');
    }
  };

  const handleBulkAssign = async () => {
    if (selectedEpics.length === 0) {
      alert('Please select at least one epic');
      return;
    }

    if (!bulkCategory) {
      alert('Please select a category');
      return;
    }

    try {
      // Update all selected epics
      for (const epicKey of selectedEpics) {
        if (bulkCategory === '') {
          // Delete category mapping
          await axios.delete(`${API_BASE_URL}/api/epic-categories/mappings/${epicKey}`);
        } else {
          // Set/update category mapping
          await axios.put(`${API_BASE_URL}/api/epic-categories/mappings/${epicKey}`, {
            category: bulkCategory,
          });
        }
      }

      // Reload data
      await loadCategories();
      await loadBudgets();

      // Clear selection
      setSelectedEpics([]);

      // Show success snackbar
      const epicCount = selectedEpics.length;
      setSuccessSnackbar({
        open: true,
        message: `✅ Successfully assigned ${epicCount} epic${epicCount > 1 ? 's' : ''} to "${bulkCategory}"`
      });

      setBulkCategory('');
    } catch (err: any) {
      console.error('Error bulk assigning categories:', err);
      alert(err.response?.data?.error || 'Failed to bulk assign categories');
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

  const handleDelete = async (budgetId: number, epicKey: string) => {
    if (!window.confirm(`Are you sure you want to delete the budget for ${epicKey}? This action cannot be undone.`)) {
      return;
    }

    try {
      await axios.delete(`${API_BASE_URL}/api/epic-budgets/${budgetId}`);
      // Reload budgets after deletion
      await loadBudgets();
    } catch (err: any) {
      console.error('Error deleting budget:', err);
      alert(err.response?.data?.error || 'Failed to delete budget');
    }
  };

  const pollTaskStatus = async (taskId: string) => {
    const pollInterval = setInterval(async () => {
      try {
        const response = await axios.get(`${API_BASE_URL}/api/jira/celery/task-status/${taskId}`);
        const status = response.data?.data;

        if (!status) {
          return;
        }

        // Update progress if task is running
        if (status.state === 'PROGRESS' && status.progress) {
          setSyncProgress({
            current: status.progress.current,
            total: status.progress.total,
            percent: status.progress.percent,
            message: status.progress.message,
          });
        }

        // Handle completion
        if (status.ready) {
          clearInterval(pollInterval);
          setSyncing(false);

          if (status.successful) {
            setSyncProgress(null);
            // Reload budgets to show updated data
            await loadBudgets();
            alert('✅ Sync completed successfully! Data has been refreshed.');
          } else if (status.failed) {
            setSyncProgress(null);
            const errorMsg = status.error || 'Task failed';
            setError(`Sync failed: ${errorMsg}`);
          }
        }
      } catch (err: any) {
        console.error('Error polling task status:', err);
        // Don't clear interval on poll errors - keep trying
      }
    }, 2000); // Poll every 2 seconds

    // Set timeout to stop polling after 10 minutes
    setTimeout(() => {
      clearInterval(pollInterval);
      if (syncing) {
        setSyncing(false);
        setError('Sync timed out after 10 minutes. Please try again or contact support.');
      }
    }, 600000);
  };

  const handleSyncHours = async () => {
    try {
      setSyncing(true);
      setError(null);
      setSyncProgress(null);

      const response = await axios.post(`${API_BASE_URL}/api/jira/projects/${projectKey}/sync-hours`);
      const taskId = response.data?.data?.task_id;

      if (taskId) {
        // Start polling for task status
        await pollTaskStatus(taskId);
      } else {
        throw new Error('No task ID returned from sync request');
      }
    } catch (err: any) {
      console.error('Error syncing hours:', err);
      setSyncing(false);
      setError(err.response?.data?.error || 'Failed to start sync');
    }
  };

  const handleToggleCategory = (category: string) => {
    setExpandedCategories((prev) => ({
      ...prev,
      [category]: !prev[category],
    }));
  };

  const handleToggleEpic = (epicKey: string) => {
    setSelectedEpics((prev) =>
      prev.includes(epicKey)
        ? prev.filter((key) => key !== epicKey)
        : [...prev, epicKey]
    );
  };

  const handleSelectAll = () => {
    if (selectedEpics.length === budgets.length) {
      // Deselect all
      setSelectedEpics([]);
    } else {
      // Select all
      setSelectedEpics(budgets.map((b) => b.epic_key));
    }
  };

  const isAllSelected = budgets.length > 0 && selectedEpics.length === budgets.length;
  const isSomeSelected = selectedEpics.length > 0 && selectedEpics.length < budgets.length;

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
      <Card sx={{
        mb: 2,
        background: 'linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%)',
        border: '2px dashed #90caf9'
      }}>
        <CardContent sx={{ textAlign: 'center', py: 6 }}>
          <Box sx={{ mb: 3 }}>
            <ImportIcon sx={{ fontSize: 64, color: '#1976d2', opacity: 0.8 }} />
          </Box>
          <Typography variant="h5" gutterBottom sx={{ fontWeight: 600, color: '#1976d2' }}>
            No Epic Budgets Yet
          </Typography>
          <Typography variant="body1" color="text.secondary" sx={{ mb: 3, maxWidth: 600, mx: 'auto' }}>
            Get started by importing epics from Jira using the "Import Epics from Jira" section above.
            Once imported, you can set budget estimates and track actual hours against them.
          </Typography>
          <Box sx={{
            display: 'flex',
            flexDirection: 'column',
            gap: 1.5,
            maxWidth: 500,
            mx: 'auto',
            textAlign: 'left',
            backgroundColor: 'rgba(255, 255, 255, 0.7)',
            p: 2.5,
            borderRadius: 2,
            border: '1px solid rgba(25, 118, 210, 0.2)'
          }}>
            <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 2 }}>
              <InfoIcon sx={{ color: '#1976d2', mt: 0.5, fontSize: 20 }} />
              <Box>
                <Typography variant="body2" sx={{ fontWeight: 600, mb: 0.5 }}>
                  Step 1: Import Epics
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  Scroll up to find the "Import Epics from Jira" section and click "Refresh Epics"
                </Typography>
              </Box>
            </Box>
            <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 2 }}>
              <InfoIcon sx={{ color: '#1976d2', mt: 0.5, fontSize: 20 }} />
              <Box>
                <Typography variant="body2" sx={{ fontWeight: 600, mb: 0.5 }}>
                  Step 2: Select & Import
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  Choose the epics you want to track and click "Import Selected"
                </Typography>
              </Box>
            </Box>
            <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 2 }}>
              <InfoIcon sx={{ color: '#1976d2', mt: 0.5, fontSize: 20 }} />
              <Box>
                <Typography variant="body2" sx={{ fontWeight: 600, mb: 0.5 }}>
                  Step 3: Set Budgets & Track
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  Set estimated hours for each epic and sync actual hours from Tempo to track progress
                </Typography>
              </Box>
            </Box>
          </Box>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardContent>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
          <Typography variant="h6">
            Epic Budget vs Actuals
          </Typography>
          <Tooltip title="Sync epic hours from Tempo to populate monthly breakdown">
            <Button
              variant="outlined"
              startIcon={syncing ? <CircularProgress size={20} /> : <SyncIcon />}
              onClick={handleSyncHours}
              disabled={syncing}
              size="small"
            >
              {syncing ? 'Syncing...' : 'Sync Hours from Tempo'}
            </Button>
          </Tooltip>
        </Box>

        {/* Budget Summary Card */}
        <Box sx={{
          mb: 3,
          p: 3,
          background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
          borderRadius: 2,
          color: 'white',
          boxShadow: '0 4px 20px rgba(102, 126, 234, 0.3)'
        }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
            <TrendingUpIcon />
            <Typography variant="h6" sx={{ fontWeight: 600 }}>
              Budget Summary
            </Typography>
          </Box>

          <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 3, mb: 2 }}>
            <Box>
              <Typography variant="caption" sx={{ opacity: 0.9, display: 'block', mb: 0.5 }}>
                Total Budget
              </Typography>
              <Typography variant="h4" sx={{ fontWeight: 700 }}>
                {budgetSummary.totalBudget.toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 })}h
              </Typography>
            </Box>
            <Box>
              <Typography variant="caption" sx={{ opacity: 0.9, display: 'block', mb: 0.5 }}>
                Hours Used
              </Typography>
              <Typography variant="h4" sx={{ fontWeight: 700 }}>
                {budgetSummary.totalActual.toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 })}h
              </Typography>
            </Box>
            <Box>
              <Typography variant="caption" sx={{ opacity: 0.9, display: 'block', mb: 0.5 }}>
                Remaining
              </Typography>
              <Typography
                variant="h4"
                sx={{
                  fontWeight: 700,
                  color: budgetSummary.totalRemaining < 0 ? '#ffcdd2' : 'white'
                }}
              >
                {budgetSummary.totalRemaining.toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 })}h
              </Typography>
            </Box>
          </Box>

          <Box>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
              <Typography variant="body2" sx={{ fontWeight: 600 }}>
                Overall Progress
              </Typography>
              <Typography variant="body2" sx={{ fontWeight: 700 }}>
                {budgetSummary.overallPctComplete.toFixed(1)}%
              </Typography>
            </Box>
            <LinearProgress
              variant="determinate"
              value={Math.min(budgetSummary.overallPctComplete, 100)}
              sx={{
                height: 8,
                borderRadius: 4,
                backgroundColor: 'rgba(255, 255, 255, 0.3)',
                '& .MuiLinearProgress-bar': {
                  borderRadius: 4,
                  backgroundColor: budgetSummary.overallPctComplete >= 100 ? '#ff5252' :
                                  budgetSummary.overallPctComplete >= 80 ? '#ffa726' : '#66bb6a'
                }
              }}
            />
          </Box>
        </Box>

        {/* Bulk Assignment Toolbar */}
        {selectedEpics.length > 0 && (
          <Box
            sx={{
              mb: 2,
              p: 2,
              backgroundColor: '#f5f5f5',
              borderRadius: 1,
              display: 'flex',
              alignItems: 'center',
              gap: 2,
            }}
          >
            <Typography variant="body2" sx={{ fontWeight: 600 }}>
              {selectedEpics.length} epic{selectedEpics.length > 1 ? 's' : ''} selected
            </Typography>
            <FormControl size="small" sx={{ minWidth: 200 }}>
              <Select
                value={bulkCategory}
                onChange={(e) => setBulkCategory(e.target.value)}
                displayEmpty
              >
                <MenuItem value="">
                  <em>Select category...</em>
                </MenuItem>
                {categories.map((cat) => (
                  <MenuItem key={cat} value={cat}>
                    {cat}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <Button
              variant="contained"
              color="primary"
              onClick={handleBulkAssign}
              disabled={!bulkCategory}
              size="small"
            >
              Assign Category
            </Button>
            <Button
              variant="outlined"
              onClick={() => setSelectedEpics([])}
              size="small"
            >
              Clear Selection
            </Button>
          </Box>
        )}

        {/* Progress indicator */}
        {syncing && syncProgress && (
          <Box sx={{ mb: 2 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
              <Typography variant="body2" color="text.secondary">
                {syncProgress.message}
              </Typography>
              <Typography variant="body2" color="text.secondary" fontWeight="bold">
                {syncProgress.percent}%
              </Typography>
            </Box>
            <LinearProgress variant="determinate" value={syncProgress.percent} />
            <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, display: 'block' }}>
              {syncProgress.current} / {syncProgress.total} worklogs processed
            </Typography>
          </Box>
        )}

        {/* Error display */}
        {error && (
          <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
            {error}
          </Alert>
        )}

        <TableContainer component={Paper} sx={{ mt: 2 }}>
          <Table size="small" stickyHeader>
            <TableHead>
              <TableRow>
                <TableCell padding="checkbox" sx={{ width: 50 }}>
                  <Checkbox
                    indeterminate={isSomeSelected}
                    checked={isAllSelected}
                    onChange={handleSelectAll}
                    inputProps={{ 'aria-label': 'Select all epics' }}
                  />
                </TableCell>
                <TableCell sx={{ fontWeight: 'bold', minWidth: 200 }}>Epic</TableCell>
                <TableCell sx={{ fontWeight: 'bold', minWidth: 150 }}>Category</TableCell>
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
                <TableCell sx={{ minWidth: 80 }}>Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {orderedCategories.map((category) => (
                <React.Fragment key={category}>
                  {/* Category Header Row */}
                  <TableRow
                    sx={{
                      backgroundColor: category === 'Uncategorized' ? '#fff3e0' : '#e3f2fd',
                      cursor: 'pointer',
                      '&:hover': { backgroundColor: category === 'Uncategorized' ? '#ffe0b2' : '#bbdefb' },
                    }}
                    onClick={() => handleToggleCategory(category)}
                  >
                    {/* Checkbox cell - empty */}
                    <TableCell padding="checkbox" />

                    {/* Epic cell - with expand icon and category name */}
                    <TableCell>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <IconButton size="small" sx={{ transform: expandedCategories[category] ? 'rotate(0deg)' : 'rotate(-90deg)', transition: 'transform 0.2s' }}>
                          <ExpandMoreIcon />
                        </IconButton>
                        <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
                          {category} ({groupedBudgets[category]?.length || 0})
                        </Typography>
                      </Box>
                    </TableCell>

                    {/* Category cell - empty */}
                    <TableCell />

                    {/* Estimate cell - subtotal */}
                    <TableCell align="right">
                      <Typography variant="body2" sx={{ fontWeight: 600, fontStyle: 'italic', color: 'text.secondary' }}>
                        {categorySubtotals[category]?.estimatedHours.toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 })}h
                      </Typography>
                    </TableCell>

                    {/* Monthly cells - subtotals */}
                    {allMonths.map((month) => (
                      <TableCell key={month} align="right">
                        <Typography variant="body2" sx={{ fontStyle: 'italic', color: 'text.secondary' }}>
                          {categorySubtotals[category]?.monthlyActuals[month]?.toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 }) || '0.0'}
                        </Typography>
                      </TableCell>
                    ))}

                    {/* Total Actual cell - subtotal */}
                    <TableCell align="right">
                      <Typography variant="body2" sx={{ fontWeight: 600, fontStyle: 'italic', color: 'text.secondary' }}>
                        {categorySubtotals[category]?.totalActual.toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 })}h
                      </Typography>
                    </TableCell>

                    {/* Remaining cell - subtotal */}
                    <TableCell align="right">
                      <Typography
                        variant="body2"
                        sx={{
                          fontWeight: 600,
                          fontStyle: 'italic',
                          color: categorySubtotals[category]?.remaining < 0 ? '#ef5350' : 'text.secondary'
                        }}
                      >
                        {categorySubtotals[category]?.remaining.toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 })}h
                      </Typography>
                    </TableCell>

                    {/* % Complete cell - subtotal */}
                    <TableCell align="right">
                      <Typography variant="body2" sx={{ fontWeight: 600, fontStyle: 'italic', color: 'text.secondary' }}>
                        {categorySubtotals[category]?.pctComplete.toFixed(1)}%
                      </Typography>
                    </TableCell>

                    {/* Status cell - empty */}
                    <TableCell />

                    {/* Actions cell - empty */}
                    <TableCell />
                  </TableRow>

                  {/* Epics in this category */}
                  {groupedBudgets[category]?.map((budget) => (
                    <TableRow
                      key={budget.id || budget.epic_key}
                      hover
                      sx={{
                        backgroundColor: !budget.is_budgeted ? 'rgba(255, 152, 0, 0.08)' : 'inherit',
                        display: expandedCategories[category] ? 'table-row' : 'none',
                      }}
                    >
                      <TableCell padding="checkbox">
                        <Checkbox
                          checked={selectedEpics.includes(budget.epic_key)}
                          onChange={() => handleToggleEpic(budget.epic_key)}
                          inputProps={{ 'aria-label': `Select ${budget.epic_key}` }}
                        />
                      </TableCell>
                      <TableCell>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          <Box sx={{ flex: 1 }}>
                            <Tooltip title={budget.epic_summary || budget.epic_key}>
                              <Typography variant="body2" fontWeight="medium" noWrap sx={{ maxWidth: 200 }}>
                                {budget.epic_summary || budget.epic_key}
                              </Typography>
                            </Tooltip>
                            <Typography variant="caption" color="textSecondary" noWrap sx={{ maxWidth: 200, display: 'block' }}>
                              {budget.epic_key}
                            </Typography>
                          </Box>
                          {!budget.is_budgeted && (
                            <Tooltip title="This epic has actual hours but no budget estimate set. Synced from Tempo.">
                              <Typography
                                variant="caption"
                                sx={{
                                  backgroundColor: '#ff9800',
                                  color: 'white',
                                  px: 0.75,
                                  py: 0.25,
                                  borderRadius: 1,
                                  fontWeight: 600,
                                  fontSize: '0.65rem'
                                }}
                              >
                                UNBUDGETED
                              </Typography>
                            </Tooltip>
                          )}
                        </Box>
                      </TableCell>
                      <TableCell>
                        <FormControl size="small" fullWidth>
                          <Select
                            value={categoryMappings[budget.epic_key] || budget.epic_category || ''}
                            onChange={(e) => handleCategoryChange(budget.epic_key, e.target.value)}
                            displayEmpty
                            sx={{ fontSize: '0.875rem' }}
                          >
                            <MenuItem value="">
                              <em>None</em>
                            </MenuItem>
                            {categories.map((cat) => (
                              <MenuItem key={cat} value={cat}>
                                {cat}
                              </MenuItem>
                            ))}
                          </Select>
                        </FormControl>
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
                            <Tooltip title="Edit estimate">
                              <IconButton size="small" onClick={() => handleStartEdit(budget)}>
                                <EditIcon fontSize="small" />
                              </IconButton>
                            </Tooltip>
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
                      <TableCell>
                        <Tooltip title="Delete epic budget">
                          <IconButton
                            size="small"
                            onClick={() => handleDelete(budget.id, budget.epic_key)}
                            color="error"
                          >
                            <DeleteIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                      </TableCell>
                    </TableRow>
                  ))}
                </React.Fragment>
              ))}

              {/* Keep the old ungrouped rendering logic for reference - we'll remove this after testing */}
              {false && budgets
                .slice()
                .sort((a, b) => (a.epic_summary || a.epic_key).localeCompare(b.epic_summary || b.epic_key))
                .map((budget) => (
                <TableRow
                  key={budget.id || budget.epic_key}
                  hover
                  sx={{
                    backgroundColor: !budget.is_budgeted ? 'rgba(255, 152, 0, 0.08)' : 'inherit'
                  }}
                >
                  <TableCell padding="checkbox">
                    <Checkbox
                      checked={selectedEpics.includes(budget.epic_key)}
                      onChange={() => handleToggleEpic(budget.epic_key)}
                      inputProps={{ 'aria-label': `Select ${budget.epic_key}` }}
                    />
                  </TableCell>
                  <TableCell>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <Box sx={{ flex: 1 }}>
                        <Tooltip title={budget.epic_summary || budget.epic_key}>
                          <Typography variant="body2" fontWeight="medium" noWrap sx={{ maxWidth: 200 }}>
                            {budget.epic_summary || budget.epic_key}
                          </Typography>
                        </Tooltip>
                        <Typography variant="caption" color="textSecondary" noWrap sx={{ maxWidth: 200, display: 'block' }}>
                          {budget.epic_key}
                        </Typography>
                      </Box>
                      {!budget.is_budgeted && (
                        <Tooltip title="This epic has actual hours but no budget estimate set. Synced from Tempo.">
                          <Typography
                            variant="caption"
                            sx={{
                              backgroundColor: '#ff9800',
                              color: 'white',
                              px: 0.75,
                              py: 0.25,
                              borderRadius: 1,
                              fontWeight: 600,
                              fontSize: '0.65rem'
                            }}
                          >
                            UNBUDGETED
                          </Typography>
                        </Tooltip>
                      )}
                    </Box>
                  </TableCell>
                  <TableCell>
                    <FormControl size="small" fullWidth>
                      <Select
                        value={categoryMappings[budget.epic_key] || budget.epic_category || ''}
                        onChange={(e) => handleCategoryChange(budget.epic_key, e.target.value)}
                        displayEmpty
                        sx={{ fontSize: '0.875rem' }}
                      >
                        <MenuItem value="">
                          <em>None</em>
                        </MenuItem>
                        {categories.map((cat) => (
                          <MenuItem key={cat} value={cat}>
                            {cat}
                          </MenuItem>
                        ))}
                      </Select>
                    </FormControl>
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
                        <Tooltip title="Edit estimate">
                          <IconButton size="small" onClick={() => handleStartEdit(budget)}>
                            <EditIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
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
                  <TableCell>
                    <Tooltip title="Delete epic budget">
                      <IconButton
                        size="small"
                        onClick={() => handleDelete(budget.id, budget.epic_key)}
                        color="error"
                      >
                        <DeleteIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                  </TableCell>
                </TableRow>
              ))}

              {/* Totals Row */}
              <TableRow sx={{ backgroundColor: '#f5f5f5', borderTop: '2px solid #ddd' }}>
                <TableCell padding="checkbox" />
                <TableCell sx={{ fontWeight: 'bold' }}>
                  TOTAL
                </TableCell>
                <TableCell />
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

      {/* Success Snackbar */}
      <Snackbar
        open={successSnackbar.open}
        autoHideDuration={4000}
        onClose={() => setSuccessSnackbar({ open: false, message: '' })}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert
          onClose={() => setSuccessSnackbar({ open: false, message: '' })}
          severity="success"
          sx={{ width: '100%', fontWeight: 600 }}
        >
          {successSnackbar.message}
        </Alert>
      </Snackbar>
    </Card>
  );
};

export default ProjectBudgetActuals;
