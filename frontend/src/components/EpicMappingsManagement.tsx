import React, { useState, useEffect } from 'react';
import {
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
  Select,
  MenuItem,
  TextField,
  FormControl,
  InputLabel,
  Box,
  Chip,
  CircularProgress,
  Alert,
  Snackbar,
  Pagination,
  FormControlLabel,
  Switch,
  IconButton,
  Tooltip,
} from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import { getApiUrl } from '../config';

interface EpicMapping {
  epic_key: string;
  epic_summary: string;
  project_key: string;
  category: string | null;
  updated_at: string | null;
}

interface PaginationInfo {
  page: number;
  per_page: number;
  total: number;
  total_pages: number;
}

const EpicMappingsManagement: React.FC = () => {
  // State
  const [mappings, setMappings] = useState<EpicMapping[]>([]);
  const [categories, setCategories] = useState<string[]>([]);
  const [projects, setProjects] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<string | null>(null); // epic_key being saved

  // Filters
  const [projectFilter, setProjectFilter] = useState<string>('');
  const [categoryFilter, setCategoryFilter] = useState<string>('');
  const [searchFilter, setSearchFilter] = useState<string>('');
  const [showUncategorizedOnly, setShowUncategorizedOnly] = useState(false);

  // Pagination
  const [pagination, setPagination] = useState<PaginationInfo>({
    page: 1,
    per_page: 50,
    total: 0,
    total_pages: 0,
  });

  // Snackbar
  const [snackbar, setSnackbar] = useState<{
    open: boolean;
    message: string;
    severity: 'success' | 'error' | 'info';
  }>({
    open: false,
    message: '',
    severity: 'success',
  });

  // Load categories and projects on mount
  useEffect(() => {
    loadCategories();
    loadProjects();
  }, []);

  // Load mappings when filters or page change
  useEffect(() => {
    loadMappings();
  }, [projectFilter, categoryFilter, searchFilter, showUncategorizedOnly, pagination.page]);

  const loadCategories = async () => {
    try {
      const token = localStorage.getItem('auth_token');
      const response = await fetch(`${getApiUrl()}/api/epic-categories`, {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });
      const data = await response.json();
      if (data.success) {
        setCategories(data.categories.map((c: any) => c.name));
      }
    } catch (error) {
      console.error('Error loading categories:', error);
    }
  };

  const loadProjects = async () => {
    try {
      const token = localStorage.getItem('auth_token');
      // Fetch ALL epics without filters to get all projects
      const response = await fetch(`${getApiUrl()}/api/epic-categories/mappings/enriched?per_page=1000`, {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });
      const data = await response.json();
      if (data.success) {
        // Extract unique projects from ALL epics
        const uniqueProjects = Array.from(
          new Set(data.mappings.map((m: EpicMapping) => m.project_key))
        ).sort() as string[];
        setProjects(uniqueProjects);
      }
    } catch (error) {
      console.error('Error loading projects:', error);
    }
  };

  const loadMappings = async () => {
    try {
      setLoading(true);
      const token = localStorage.getItem('auth_token');

      // Build query params
      const params = new URLSearchParams();
      if (projectFilter) params.append('project_key', projectFilter);
      if (searchFilter) params.append('search', searchFilter);

      // Category filter: showUncategorizedOnly overrides categoryFilter
      if (showUncategorizedOnly) {
        params.append('category', 'Uncategorized');
      } else if (categoryFilter) {
        params.append('category', categoryFilter);
      }

      params.append('page', pagination.page.toString());
      params.append('per_page', pagination.per_page.toString());

      const response = await fetch(`${getApiUrl()}/api/epic-categories/mappings/enriched?${params}`, {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      const data = await response.json();

      if (data.success) {
        setMappings(data.mappings);
        setPagination(data.pagination);
        // Projects are loaded separately in loadProjects() - don't overwrite here
      } else {
        setSnackbar({
          open: true,
          message: `Error: ${data.error}`,
          severity: 'error',
        });
      }
    } catch (error) {
      console.error('Error loading mappings:', error);
      setSnackbar({
        open: true,
        message: 'Failed to load epic mappings',
        severity: 'error',
      });
    } finally {
      setLoading(false);
    }
  };

  const handleCategoryChange = async (epic_key: string, newCategory: string) => {
    try {
      setSaving(epic_key);
      const token = localStorage.getItem('auth_token');

      const response = await fetch(`${getApiUrl()}/api/epic-categories/mappings/${epic_key}`, {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ category: newCategory }),
      });

      const data = await response.json();

      if (data.success) {
        // Update local state
        setMappings(prev => prev.map(m =>
          m.epic_key === epic_key
            ? { ...m, category: newCategory }
            : m
        ));

        setSnackbar({
          open: true,
          message: `${epic_key} categorized as "${newCategory}"`,
          severity: 'success',
        });
      } else {
        setSnackbar({
          open: true,
          message: `Error: ${data.error}`,
          severity: 'error',
        });
      }
    } catch (error) {
      console.error('Error updating category:', error);
      setSnackbar({
        open: true,
        message: 'Failed to update category',
        severity: 'error',
      });
    } finally {
      setSaving(null);
    }
  };

  const handleRefresh = () => {
    loadMappings();
  };

  const handlePageChange = (_event: React.ChangeEvent<unknown>, value: number) => {
    setPagination(prev => ({ ...prev, page: value }));
  };

  const getCategoryColor = (category: string | null): 'warning' | 'primary' | 'success' | 'default' => {
    if (!category || category === 'Uncategorized') return 'warning';
    return 'primary';
  };

  return (
    <Card>
      <CardContent>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
          <Typography variant="h5" component="h2">
            Epic Category Mappings
          </Typography>
          <Tooltip title="Refresh data">
            <IconButton onClick={handleRefresh} disabled={loading}>
              <RefreshIcon />
            </IconButton>
          </Tooltip>
        </Box>

        <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
          Review and assign categories to epics for accurate forecasting.
          Epics marked as "Uncategorized" need manual review.
        </Typography>

        {/* Filter Controls */}
        <Box sx={{ display: 'flex', gap: 2, mb: 3, flexWrap: 'wrap' }}>
          <FormControl sx={{ minWidth: 150 }}>
            <InputLabel>Project</InputLabel>
            <Select
              value={projectFilter}
              label="Project"
              onChange={(e) => setProjectFilter(e.target.value)}
              disabled={loading}
            >
              <MenuItem value="">All Projects</MenuItem>
              {projects.map(project => (
                <MenuItem key={project} value={project}>{project}</MenuItem>
              ))}
            </Select>
          </FormControl>

          <FormControl sx={{ minWidth: 150 }}>
            <InputLabel>Category</InputLabel>
            <Select
              value={categoryFilter}
              label="Category"
              onChange={(e) => setCategoryFilter(e.target.value)}
              disabled={loading || showUncategorizedOnly}
            >
              <MenuItem value="">All Categories</MenuItem>
              <MenuItem value="Uncategorized">Uncategorized</MenuItem>
              {categories.map(category => (
                <MenuItem key={category} value={category}>{category}</MenuItem>
              ))}
            </Select>
          </FormControl>

          <TextField
            label="Search"
            placeholder="Epic key or summary"
            value={searchFilter}
            onChange={(e) => setSearchFilter(e.target.value)}
            disabled={loading}
            sx={{ minWidth: 250 }}
          />

          <FormControlLabel
            control={
              <Switch
                checked={showUncategorizedOnly}
                onChange={(e) => {
                  setShowUncategorizedOnly(e.target.checked);
                  if (e.target.checked) setCategoryFilter('');
                }}
                disabled={loading}
              />
            }
            label="Uncategorized only"
          />
        </Box>

        {/* Stats */}
        <Box sx={{ mb: 2 }}>
          <Typography variant="body2" color="text.secondary">
            Showing {mappings.length} of {pagination.total} epics
            {showUncategorizedOnly && ` (${pagination.total} need categorization)`}
          </Typography>
        </Box>

        {/* Table */}
        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
            <CircularProgress />
          </Box>
        ) : mappings.length === 0 ? (
          <Alert severity="info">
            No epics found matching your filters.
          </Alert>
        ) : (
          <>
            <TableContainer component={Paper} variant="outlined">
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell width="15%"><strong>Epic Key</strong></TableCell>
                    <TableCell width="35%"><strong>Summary</strong></TableCell>
                    <TableCell width="10%"><strong>Project</strong></TableCell>
                    <TableCell width="25%"><strong>Category</strong></TableCell>
                    <TableCell width="15%"><strong>Last Updated</strong></TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {mappings.map((mapping) => {
                    // Check if category is invalid (not in valid categories list)
                    const isInvalidCategory = mapping.category &&
                                             !categories.includes(mapping.category) &&
                                             mapping.category !== 'Uncategorized';
                    const isUncategorized = !mapping.category ||
                                           mapping.category === 'Uncategorized' ||
                                           isInvalidCategory;

                    return (
                    <TableRow
                      key={mapping.epic_key}
                      sx={{
                        backgroundColor: isUncategorized
                          ? 'rgba(255, 152, 0, 0.08)'
                          : 'inherit'
                      }}
                    >
                      <TableCell>
                        <Typography variant="body2" fontFamily="monospace">
                          {mapping.epic_key}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" noWrap>
                          {mapping.epic_summary}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Chip
                          label={mapping.project_key}
                          size="small"
                          color="default"
                        />
                      </TableCell>
                      <TableCell>
                        <FormControl fullWidth size="small">
                          <Select
                            value={
                              // Only use category if it exists in valid categories list
                              mapping.category && (categories.includes(mapping.category) || mapping.category === 'Uncategorized')
                                ? mapping.category
                                : 'Uncategorized'
                            }
                            onChange={(e) => handleCategoryChange(mapping.epic_key, e.target.value)}
                            disabled={saving === mapping.epic_key}
                            displayEmpty
                          >
                            <MenuItem value="Uncategorized">
                              <em>Uncategorized</em>
                            </MenuItem>
                            {categories.map(category => (
                              <MenuItem key={category} value={category}>
                                {category}
                              </MenuItem>
                            ))}
                          </Select>
                        </FormControl>
                        {saving === mapping.epic_key && (
                          <CircularProgress size={16} sx={{ ml: 1 }} />
                        )}
                      </TableCell>
                      <TableCell>
                        <Typography variant="caption" color="text.secondary">
                          {mapping.updated_at
                            ? new Date(mapping.updated_at).toLocaleDateString()
                            : 'Never'
                          }
                        </Typography>
                      </TableCell>
                    </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </TableContainer>

            {/* Pagination */}
            {pagination.total_pages > 1 && (
              <Box sx={{ display: 'flex', justifyContent: 'center', mt: 3 }}>
                <Pagination
                  count={pagination.total_pages}
                  page={pagination.page}
                  onChange={handlePageChange}
                  color="primary"
                  disabled={loading}
                />
              </Box>
            )}
          </>
        )}

        {/* Snackbar */}
        <Snackbar
          open={snackbar.open}
          autoHideDuration={4000}
          onClose={() => setSnackbar({ ...snackbar, open: false })}
          anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
        >
          <Alert
            onClose={() => setSnackbar({ ...snackbar, open: false })}
            severity={snackbar.severity}
            sx={{ width: '100%' }}
          >
            {snackbar.message}
          </Alert>
        </Snackbar>
      </CardContent>
    </Card>
  );
};

export default EpicMappingsManagement;
