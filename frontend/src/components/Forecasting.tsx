import React, { useState, useEffect } from 'react';
import {
  Card,
  CardContent,
  CardHeader,
  Typography,
  Box,
  Chip,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Alert,
  Button as MuiButton,
  TextField as MuiTextField,
  CircularProgress,
  Grid,
  Tabs,
  Tab,
  Divider,
  TableSortLabel,
} from '@mui/material';
import {
  Assessment as AnalyticsIcon,
  TrendingUp as ForecastIcon,
  Warning as WarningIcon,
} from '@mui/icons-material';
import { usePermissions } from 'react-admin';
import axios from 'axios';
import ProjectForecastTab from './ProjectForecastTab';
import { useTabWithUrl } from '../hooks/useTabWithUrl';

interface EpicBaseline {
  epic_category: string;
  median_hours: number;
  mean_hours: number;
  p75_hours: number;
  p90_hours: number;
  min_hours: number;
  max_hours: number;
  project_count: number;
  occurrence_count: number;
  coefficient_of_variation: number;
  variance_level: 'low' | 'medium' | 'high';
  recommended_estimate: number;
}

interface ForecastResult {
  summary: {
    total_epics: number;
    matched_epics: number;
    custom_epics: number;
    development_hours: number;
    pm_overhead_hours: number;
    total_hours: number;
    confidence: 'low' | 'medium' | 'high';
    range_low: number;
    range_high: number;
  };
  timeline: {
    project_size: 'small' | 'medium' | 'large';
    estimated_months: number;
    avg_burn_rate: number;
  };
  burn_schedule: Array<{ month: number; hours: number; cumulative: number }>;
  epic_breakdown: Array<{
    epic: string;
    matched_category?: string;
    hours: number | null;
    variance_level: string;
    confidence: string;
    range?: string;
  }>;
  risks: {
    custom_epics: string[];
    high_risk_epics: string[];
  };
}

interface ProjectSchedule {
  total_hours: number;
  duration_months: number;
  start_date: string;
  months: string[];
  epics: Array<{
    epic_category: string;
    ratio: number;
    allocated_hours: number;
    monthly_breakdown: Array<{
      month: string;
      hours: number;
    }>;
  }>;
  monthly_totals: Array<{
    month: string;
    total_hours: number;
  }>;
}

const getVarianceColor = (level: string) => {
  switch (level) {
    case 'low':
      return 'success';
    case 'medium':
      return 'warning';
    case 'high':
      return 'error';
    default:
      return 'default';
  }
};

const getConfidenceColor = (confidence: string) => {
  switch (confidence) {
    case 'high':
      return 'success';
    case 'medium':
      return 'warning';
    case 'low':
      return 'error';
    default:
      return 'default';
  }
};

export const AnalyticsList = () => {
  const { permissions, isLoading: permissionsLoading } = usePermissions();
  const [tabValue, setTabValue] = useTabWithUrl('meetings-tab', 0);
  const [baselines, setBaselines] = useState<EpicBaseline[]>([]);
  const [highRiskEpics, setHighRiskEpics] = useState<EpicBaseline[]>([]);
  const [loading, setLoading] = useState(true);
  const [forecastLoading, setForecastLoading] = useState(false);
  const [forecastResult, setForecastResult] = useState<ForecastResult | null>(null);
  const [epicInput, setEpicInput] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [sortField, setSortField] = useState<'epic_category' | 'median_hours' | 'project_count'>('epic_category');
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc');

  useEffect(() => {
    // Fetch data for all logged-in users
    if (!permissionsLoading) {
      fetchBaselines();
      fetchHighRiskEpics();
    }
  }, [permissionsLoading]);

  const fetchBaselines = async () => {
    try {
      const response = await axios.get('/api/analytics/baselines');
      setBaselines(response.data.baselines || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  const fetchHighRiskEpics = async () => {
    try {
      const response = await axios.get('/api/analytics/variance');
      setHighRiskEpics(response.data.high_risk_epics || []);
    } catch (err) {
      console.error('Error fetching high-risk epics:', err);
    }
  };


  const handleForecast = async () => {
    if (!epicInput.trim()) {
      setError('Please enter epic names');
      return;
    }

    setForecastLoading(true);
    setError(null);

    try {
      const epics = epicInput.split('\n').map(e => e.trim()).filter(e => e);
      const response = await axios.post('/api/analytics/forecast', { epics });
      setForecastResult(response.data.forecast);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setForecastLoading(false);
    }
  };

  const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
    setTabValue(newValue);
  };

  const handleSort = (field: 'epic_category' | 'median_hours' | 'project_count') => {
    if (sortField === field) {
      // Toggle direction if same field
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      // New field, default to asc for epic_category, desc for numbers
      setSortField(field);
      setSortDirection(field === 'epic_category' ? 'asc' : 'desc');
    }
  };

  // Sort baselines
  const sortedBaselines = [...baselines].sort((a, b) => {
    let aVal: string | number = a[sortField];
    let bVal: string | number = b[sortField];

    if (sortField === 'epic_category') {
      aVal = (aVal as string).toLowerCase();
      bVal = (bVal as string).toLowerCase();
    }

    if (sortDirection === 'asc') {
      return aVal > bVal ? 1 : aVal < bVal ? -1 : 0;
    } else {
      return aVal < bVal ? 1 : aVal > bVal ? -1 : 0;
    }
  });

  if (loading || permissionsLoading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box p={3}>
      <Box sx={{ mb: 2 }}>
        <Typography variant="h4" gutterBottom>
          Analytics & Forecasting
        </Typography>
        <Typography variant="body2" color="textSecondary">
          Historical baseline estimates and project forecasting tools
        </Typography>
      </Box>

      <Box sx={{ borderBottom: 1, borderColor: 'divider', mt: 3, mb: 3 }}>
        <Tabs value={tabValue} onChange={handleTabChange}>
          <Tab icon={<ForecastIcon />} label="Project Forecast" />
          <Tab icon={<AnalyticsIcon />} label="Epic Baselines" />
          <Tab icon={<WarningIcon />} label="High-Risk Epics" />
        </Tabs>
      </Box>

      {/* Tab 0: Project Forecast (Unified) */}
      {tabValue === 0 && <ProjectForecastTab />}

      {/* Tab 1: Epic Baselines */}
      {tabValue === 1 && (
        <Card>
          <CardHeader
            title="Epic Baselines"
            subheader={`${baselines.length} common epics with historical data`}
          />
          <CardContent>
            {error && (
              <Alert severity="error" sx={{ mb: 2 }}>
                {error}
              </Alert>
            )}

            <TableContainer component={Paper}>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>
                      <TableSortLabel
                        active={sortField === 'epic_category'}
                        direction={sortField === 'epic_category' ? sortDirection : 'asc'}
                        onClick={() => handleSort('epic_category')}
                      >
                        <strong>Epic Category</strong>
                      </TableSortLabel>
                    </TableCell>
                    <TableCell align="right">
                      <TableSortLabel
                        active={sortField === 'median_hours'}
                        direction={sortField === 'median_hours' ? sortDirection : 'desc'}
                        onClick={() => handleSort('median_hours')}
                      >
                        <strong>Median</strong>
                      </TableSortLabel>
                    </TableCell>
                    <TableCell align="right"><strong>P75</strong></TableCell>
                    <TableCell align="right"><strong>P90</strong></TableCell>
                    <TableCell align="right"><strong>Range</strong></TableCell>
                    <TableCell align="center">
                      <TableSortLabel
                        active={sortField === 'project_count'}
                        direction={sortField === 'project_count' ? sortDirection : 'desc'}
                        onClick={() => handleSort('project_count')}
                      >
                        <strong>Projects</strong>
                      </TableSortLabel>
                    </TableCell>
                    <TableCell align="center"><strong>Variance</strong></TableCell>
                    <TableCell align="right"><strong>Recommended</strong></TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {sortedBaselines.map((baseline) => (
                    <TableRow key={baseline.epic_category}>
                      <TableCell>{baseline.epic_category}</TableCell>
                      <TableCell align="right">{baseline.median_hours.toFixed(1)}h</TableCell>
                      <TableCell align="right">{baseline.p75_hours.toFixed(1)}h</TableCell>
                      <TableCell align="right">{baseline.p90_hours.toFixed(1)}h</TableCell>
                      <TableCell align="right">
                        {baseline.min_hours.toFixed(1)}-{baseline.max_hours.toFixed(1)}h
                      </TableCell>
                      <TableCell align="center">{baseline.project_count}</TableCell>
                      <TableCell align="center">
                        <Chip
                          label={baseline.variance_level}
                          size="small"
                          color={getVarianceColor(baseline.variance_level) as any}
                        />
                      </TableCell>
                      <TableCell align="right">
                        <strong>{baseline.recommended_estimate.toFixed(1)}h</strong>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </CardContent>
        </Card>
      )}

      {/* Tab 2: High-Risk Epics */}
      {tabValue === 2 && (
        <Card>
          <CardHeader
            title="High-Risk Epics"
            subheader={`${highRiskEpics.length} epics with high variance requiring careful scoping`}
          />
          <CardContent>
            <Alert severity="warning" sx={{ mb: 2 }}>
              These epics have high variance (CV {'>'} 120%). Consider using P90 estimates and adding
              contingency buffer.
            </Alert>

            <TableContainer component={Paper}>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell><strong>Epic Category</strong></TableCell>
                    <TableCell align="right"><strong>Median</strong></TableCell>
                    <TableCell align="right"><strong>Range</strong></TableCell>
                    <TableCell align="right"><strong>CV%</strong></TableCell>
                    <TableCell align="center"><strong>Projects</strong></TableCell>
                    <TableCell align="right"><strong>Recommended (P90)</strong></TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {highRiskEpics.map((epic) => (
                    <TableRow key={epic.epic_category}>
                      <TableCell>{epic.epic_category}</TableCell>
                      <TableCell align="right">{epic.median_hours.toFixed(1)}h</TableCell>
                      <TableCell align="right">
                        {epic.min_hours.toFixed(1)}-{epic.max_hours.toFixed(1)}h
                      </TableCell>
                      <TableCell align="right">{epic.coefficient_of_variation.toFixed(1)}%</TableCell>
                      <TableCell align="center">{epic.project_count}</TableCell>
                      <TableCell align="right">
                        <strong>{epic.recommended_estimate.toFixed(1)}h</strong>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </CardContent>
        </Card>
      )}
    </Box>
  );
};
