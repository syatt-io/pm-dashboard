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
} from '@mui/material';
import {
  Assessment as AnalyticsIcon,
  TrendingUp as ForecastIcon,
  Warning as WarningIcon,
  Lock as LockIcon,
} from '@mui/icons-material';
import { usePermissions } from 'react-admin';
import axios from 'axios';

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
  const [tabValue, setTabValue] = useState(0);
  const [baselines, setBaselines] = useState<EpicBaseline[]>([]);
  const [highRiskEpics, setHighRiskEpics] = useState<EpicBaseline[]>([]);
  const [loading, setLoading] = useState(true);
  const [forecastLoading, setForecastLoading] = useState(false);
  const [forecastResult, setForecastResult] = useState<ForecastResult | null>(null);
  const [epicInput, setEpicInput] = useState('');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Only fetch data if user is admin
    if (!permissionsLoading && permissions === 'admin') {
      fetchBaselines();
      fetchHighRiskEpics();
    } else if (!permissionsLoading) {
      setLoading(false);
    }
  }, [permissions, permissionsLoading]);

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

  // Show loading while checking permissions
  if (permissionsLoading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress />
      </Box>
    );
  }

  // Show access denied for non-admins
  if (permissions !== 'admin') {
    return (
      <Box p={3}>
        <Card>
          <CardContent>
            <Box display="flex" flexDirection="column" alignItems="center" gap={2} py={4}>
              <LockIcon sx={{ fontSize: 64, color: 'text.secondary' }} />
              <Typography variant="h5" color="text.primary">
                Access Denied
              </Typography>
              <Typography variant="body1" color="text.secondary" textAlign="center">
                The Analytics & Forecasting feature is currently restricted to administrators only.
              </Typography>
              <Typography variant="body2" color="text.secondary" textAlign="center">
                Please contact your administrator if you need access to this feature.
              </Typography>
            </Box>
          </CardContent>
        </Card>
      </Box>
    );
  }

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box p={3}>
      <Typography variant="h4" gutterBottom>
        Analytics & Forecasting
      </Typography>
      <Typography variant="body2" color="textSecondary" gutterBottom>
        Historical baseline estimates and project forecasting tools
      </Typography>

      <Box sx={{ borderBottom: 1, borderColor: 'divider', mt: 3, mb: 3 }}>
        <Tabs value={tabValue} onChange={handleTabChange}>
          <Tab icon={<AnalyticsIcon />} label="Epic Baselines" />
          <Tab icon={<ForecastIcon />} label="Project Forecasting" />
          <Tab icon={<WarningIcon />} label="High-Risk Epics" />
        </Tabs>
      </Box>

      {/* Tab 1: Epic Baselines */}
      {tabValue === 0 && (
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
                    <TableCell><strong>Epic Category</strong></TableCell>
                    <TableCell align="right"><strong>Median</strong></TableCell>
                    <TableCell align="right"><strong>P75</strong></TableCell>
                    <TableCell align="right"><strong>P90</strong></TableCell>
                    <TableCell align="right"><strong>Range</strong></TableCell>
                    <TableCell align="center"><strong>Projects</strong></TableCell>
                    <TableCell align="center"><strong>Variance</strong></TableCell>
                    <TableCell align="right"><strong>Recommended</strong></TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {baselines.map((baseline) => (
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

      {/* Tab 2: Project Forecasting */}
      {tabValue === 1 && (
        <Grid container spacing={3}>
          <Grid item xs={12} md={6}>
            <Card>
              <CardHeader title="Forecast Project" subheader="Enter epic names (one per line)" />
              <CardContent>
                <MuiTextField
                  fullWidth
                  multiline
                  rows={12}
                  variant="outlined"
                  label="Epic Names"
                  placeholder="Header&#10;Footer&#10;Cart&#10;Product Detail Page&#10;Search"
                  value={epicInput}
                  onChange={(e) => setEpicInput(e.target.value)}
                  sx={{ mb: 2 }}
                />
                <MuiButton
                  variant="contained"
                  color="primary"
                  fullWidth
                  onClick={handleForecast}
                  disabled={forecastLoading}
                  startIcon={forecastLoading ? <CircularProgress size={20} /> : <ForecastIcon />}
                >
                  {forecastLoading ? 'Generating Forecast...' : 'Generate Forecast'}
                </MuiButton>
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} md={6}>
            {forecastResult && (
              <Card>
                <CardHeader
                  title="Forecast Results"
                  subheader={
                    <Chip
                      label={`${forecastResult.summary.confidence.toUpperCase()} Confidence`}
                      size="small"
                      color={getConfidenceColor(forecastResult.summary.confidence) as any}
                    />
                  }
                />
                <CardContent>
                  {/* Summary */}
                  <Box mb={3}>
                    <Typography variant="h6" gutterBottom>
                      Hours Estimate
                    </Typography>
                    <Grid container spacing={2}>
                      <Grid item xs={6}>
                        <Typography variant="body2" color="textSecondary">
                          Development:
                        </Typography>
                        <Typography variant="h6">
                          {forecastResult.summary.development_hours.toFixed(1)}h
                        </Typography>
                      </Grid>
                      <Grid item xs={6}>
                        <Typography variant="body2" color="textSecondary">
                          PM Overhead (25%):
                        </Typography>
                        <Typography variant="h6">
                          {forecastResult.summary.pm_overhead_hours.toFixed(1)}h
                        </Typography>
                      </Grid>
                      <Grid item xs={12}>
                        <Divider sx={{ my: 1 }} />
                        <Typography variant="body2" color="textSecondary">
                          TOTAL HOURS:
                        </Typography>
                        <Typography variant="h4" color="primary">
                          {forecastResult.summary.total_hours.toFixed(1)}h
                        </Typography>
                        <Typography variant="body2" color="textSecondary">
                          Range: {forecastResult.summary.range_low.toFixed(1)}h -{' '}
                          {forecastResult.summary.range_high.toFixed(1)}h
                        </Typography>
                      </Grid>
                    </Grid>
                  </Box>

                  {/* Timeline */}
                  <Box mb={3}>
                    <Typography variant="h6" gutterBottom>
                      Timeline
                    </Typography>
                    <Grid container spacing={2}>
                      <Grid item xs={6}>
                        <Typography variant="body2" color="textSecondary">
                          Project Size:
                        </Typography>
                        <Chip label={forecastResult.timeline.project_size.toUpperCase()} />
                      </Grid>
                      <Grid item xs={6}>
                        <Typography variant="body2" color="textSecondary">
                          Duration:
                        </Typography>
                        <Typography variant="body1">
                          {forecastResult.timeline.estimated_months} months
                        </Typography>
                      </Grid>
                      <Grid item xs={12}>
                        <Typography variant="body2" color="textSecondary">
                          Avg Burn Rate:
                        </Typography>
                        <Typography variant="body1">
                          {forecastResult.timeline.avg_burn_rate.toFixed(1)}h/month
                        </Typography>
                      </Grid>
                    </Grid>
                  </Box>

                  {/* Risks */}
                  {(forecastResult.risks.custom_epics.length > 0 ||
                    forecastResult.risks.high_risk_epics.length > 0) && (
                    <Box>
                      <Typography variant="h6" gutterBottom>
                        Risks
                      </Typography>
                      {forecastResult.risks.custom_epics.length > 0 && (
                        <Alert severity="warning" sx={{ mb: 2 }}>
                          <strong>Custom Epics ({forecastResult.risks.custom_epics.length}):</strong>
                          <br />
                          {forecastResult.risks.custom_epics.join(', ')}
                          <br />
                          <Typography variant="caption">
                            No historical data - requires detailed scoping
                          </Typography>
                        </Alert>
                      )}
                      {forecastResult.risks.high_risk_epics.length > 0 && (
                        <Alert severity="error">
                          <strong>High-Risk Epics ({forecastResult.risks.high_risk_epics.length}):</strong>
                          <br />
                          {forecastResult.risks.high_risk_epics.join(', ')}
                          <br />
                          <Typography variant="caption">
                            High variance - add buffer to estimates
                          </Typography>
                        </Alert>
                      )}
                    </Box>
                  )}
                </CardContent>
              </Card>
            )}
          </Grid>
        </Grid>
      )}

      {/* Tab 3: High-Risk Epics */}
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
