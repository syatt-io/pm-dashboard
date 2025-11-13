import React, { useState, useMemo } from 'react';
import {
  Box,
  Button,
  Card,
  CardContent,
  CardHeader,
  TextField,
  Typography,
  Grid,
  Slider,
  Alert,
  CircularProgress,
  Chip,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Checkbox,
  FormControlLabel,
  FormGroup,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  RadioGroup,
  Radio,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
} from '@mui/material';
import { Download, Upload } from '@mui/icons-material';
import axios from 'axios';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';

const API_BASE_URL = process.env.REACT_APP_API_URL ||
  (window.location.hostname === 'localhost'
    ? 'http://localhost:4000'
    : 'https://agent-pm-tsbbb.ondigitalocean.app');

// Type definitions
interface TeamForecast {
  team: string;
  total_hours: number;
  percentage: number;
  monthly_breakdown: Array<{
    month: number;
    phase: string;
    hours: number;
  }>;
}

interface EpicForecast {
  epic: string;
  total_hours: number;
  percentage: number;
  reasoning: string;
}

interface ForecastResult {
  total_hours: number;
  estimated_months: number;
  teams: TeamForecast[];
  epics?: EpicForecast[];  // AI-generated epic allocations
  distribution_ratios: { [team: string]: number };
  baseline_set_used: string;
  characteristics?: {
    be_integrations: number;
    custom_theme: number;
    custom_designs: number;
    ux_research: number;
    extensive_customizations: number;
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

const ProjectForecastTab: React.FC = () => {
  // Form state
  const [totalHours, setTotalHours] = useState<number>(1500);
  const [estimatedMonths, setEstimatedMonths] = useState<number>(8);
  const [startDate, setStartDate] = useState<string>(
    new Date().toISOString().split('T')[0]
  );

  // Project characteristics (1-5 sliders)
  const [beIntegrations, setBeIntegrations] = useState<number>(1);
  const [customTheme, setCustomTheme] = useState<number>(1);
  const [customDesigns, setCustomDesigns] = useState<number>(1);
  const [uxResearch, setUxResearch] = useState<number>(1);
  const [extensiveCustomizations, setExtensiveCustomizations] = useState<number>(1);
  const [projectOversight, setProjectOversight] = useState<number>(3); // Default to 3 (typical)

  // Teams selection
  const availableTeams = ['BE Devs', 'FE Devs', 'Design', 'UX', 'PMs', 'Data'];
  const [teamsSelected, setTeamsSelected] = useState<string[]>([
    'BE Devs',
    'FE Devs',
    'PMs',
  ]);

  // Results state
  const [teamForecast, setTeamForecast] = useState<ForecastResult | null>(null);
  const [epicSchedule, setEpicSchedule] = useState<ProjectSchedule | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Jira export modal state
  const [exportModalOpen, setExportModalOpen] = useState<boolean>(false);
  const [projectKey, setProjectKey] = useState<string>('');
  const [fuzzyMatches, setFuzzyMatches] = useState<any>(null);
  const [epicMappings, setEpicMappings] = useState<{[key: string]: {action: string, existing_key?: string, story_points?: number}}>({});
  const [exportLoading, setExportLoading] = useState<boolean>(false);
  const [exportResult, setExportResult] = useState<any>(null);

  // Helper functions
  const handleTeamToggle = (team: string) => {
    setTeamsSelected((prev) =>
      prev.includes(team) ? prev.filter((t) => t !== team) : [...prev, team]
    );
  };

  const handleGenerateForecast = async () => {
    if (teamsSelected.length === 0) {
      setError('Please select at least one team');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      // Calculate actual calendar months needed (accounts for mid-month starts)
      const projectStartDate = new Date(startDate);
      const startDay = projectStartDate.getDate();
      const isMidMonthStart = startDay > 1;
      const calendarMonths = isMidMonthStart ? estimatedMonths + 1 : estimatedMonths;

      // Call team forecast API
      const teamResponse = await axios.post(
        `${API_BASE_URL}/api/forecasts/calculate-from-total`,
        {
          total_hours: totalHours,
          be_integrations: beIntegrations,
          custom_theme: customTheme,
          custom_designs: customDesigns,
          ux_research: uxResearch,
          extensive_customizations: extensiveCustomizations,
          project_oversight: projectOversight,
          teams_selected: teamsSelected,
          estimated_months: calendarMonths,  // Use calendar months, not project duration
          start_date: startDate,  // Pass start date for proration
        }
      );
      setTeamForecast(teamResponse.data);

      // Call epic schedule API
      const epicResponse = await axios.post(
        `${API_BASE_URL}/api/analytics/project-schedule`,
        {
          total_hours: totalHours,
          duration_months: calendarMonths,  // Use calendar months, not project duration
          start_date: startDate,
          project_oversight: projectOversight,
        }
      );
      setEpicSchedule(epicResponse.data);
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to generate forecast');
      console.error('Forecast error:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleDownloadCSV = async () => {
    try {
      // Calculate actual calendar months needed (accounts for mid-month starts)
      const projectStartDate = new Date(startDate);
      const startDay = projectStartDate.getDate();
      const isMidMonthStart = startDay > 1;
      const calendarMonths = isMidMonthStart ? estimatedMonths + 1 : estimatedMonths;

      const response = await axios.post(
        `${API_BASE_URL}/api/forecasts/export-combined-forecast`,
        {
          total_hours: totalHours,
          be_integrations: beIntegrations,
          custom_theme: customTheme,
          custom_designs: customDesigns,
          ux_research: uxResearch,
          extensive_customizations: extensiveCustomizations,
          project_oversight: projectOversight,
          teams_selected: teamsSelected,
          estimated_months: calendarMonths,  // Use calendar months, not project duration
          start_date: startDate,
        },
        {
          responseType: 'blob',
        }
      );

      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `project_forecast_${startDate}.csv`);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (err) {
      console.error('CSV download error:', err);
      setError('Failed to download CSV');
    }
  };

  const handleExportToJira = async () => {
    if (!epicSchedule || !epicSchedule.epics || epicSchedule.epics.length === 0) {
      setError('No epic schedule to export');
      return;
    }

    setExportModalOpen(true);
    setExportResult(null);

    if (!projectKey) {
      // Default to first available project key or show input
      return;
    }

    // Call fuzzy matching endpoint
    try {
      const epicNames = epicSchedule.epics.map((e) => e.epic_category);
      const response = await axios.post(
        `${API_BASE_URL}/api/forecasts/match-jira-epics`,
        {
          project_key: projectKey,
          epic_names: epicNames,
        }
      );

      setFuzzyMatches(response.data.matches);

      // Initialize mappings with default "create" action
      const initialMappings: any = {};
      response.data.matches.forEach((match: any) => {
        initialMappings[match.forecast_epic] = {
          action: 'create',
        };
      });
      setEpicMappings(initialMappings);
    } catch (err: any) {
      console.error('Fuzzy matching error:', err);
      setError(err.response?.data?.error || 'Failed to match epics');
    }
  };

  const handleMappingChange = (epicName: string, field: string, value: any) => {
    setEpicMappings((prev) => ({
      ...prev,
      [epicName]: {
        ...prev[epicName],
        [field]: value,
      },
    }));
  };

  const handleConfirmExport = async () => {
    if (!epicSchedule || !projectKey) {
      setError('Missing required data for export');
      return;
    }

    setExportLoading(true);
    setExportResult(null);

    try {
      // Prepare export payload
      const epicsToExport = epicSchedule.epics.map((epic) => {
        const mapping = epicMappings[epic.epic_category] || { action: 'create' };

        return {
          name: epic.epic_category,
          description: `Forecasted epic from project planning.\n\nTotal Hours: ${epic.allocated_hours.toFixed(1)}h`,
          estimated_hours: epic.allocated_hours,
          story_points: mapping.story_points,
          action: mapping.action,
          existing_epic_key: mapping.existing_key,
        };
      });

      const response = await axios.post(
        `${API_BASE_URL}/api/forecasts/export-to-jira`,
        {
          project_key: projectKey,
          epics: epicsToExport,
        }
      );

      setExportResult(response.data);
    } catch (err: any) {
      console.error('Export error:', err);
      setError(err.response?.data?.error || 'Failed to export to Jira');
      setExportResult(err.response?.data);
    } finally {
      setExportLoading(false);
    }
  };

  const chartData = useMemo(() => {
    if (!teamForecast) return [];

    // Parse start date to determine calendar months
    const projectStartDate = new Date(startDate);

    // Use the number of months from the backend response (already accounts for mid-month)
    const totalCalendarMonths = teamForecast.estimated_months;

    // Generate calendar month labels
    const calendarMonths = Array.from(
      { length: totalCalendarMonths },
      (_, i) => {
        const monthDate = new Date(projectStartDate);
        monthDate.setMonth(projectStartDate.getMonth() + i);
        return monthDate.toLocaleDateString('en-US', {
          month: 'short',
          year: 'numeric'
        });
      }
    );

    // Map team hours to calendar months
    const data = calendarMonths.map((monthLabel, index) => {
      const dataPoint: any = { month: monthLabel };
      const projectMonth = index + 1;

      teamForecast.teams.forEach((team) => {
        const monthData = team.monthly_breakdown.find((m) => m.month === projectMonth);
        dataPoint[team.team] = monthData ? monthData.hours : 0;
      });

      return dataPoint;
    });

    // Debug logging
    console.log('=== Chart Data Debug ===');
    console.log('Total Calendar Months:', totalCalendarMonths);
    console.log('Chart Data:', data);

    // Calculate totals for each team
    teamForecast.teams.forEach((team) => {
      const chartTotal = data.reduce((sum, month) => sum + (month[team.team] || 0), 0);
      const breakdownTotal = team.monthly_breakdown.reduce((sum, m) => sum + m.hours, 0);
      const teamTotalHours = team.total_hours; // Original allocation before proration
      console.log(`${team.team}:`);
      console.log(`  Chart Total: ${chartTotal.toFixed(2)}h`);
      console.log(`  Breakdown Total: ${breakdownTotal.toFixed(2)}h`);
      console.log(`  Original Allocation: ${teamTotalHours}h`);
      console.log(`  Chart vs Breakdown Match: ${Math.abs(chartTotal - breakdownTotal) < 0.01 ? '✅' : '❌'}`);
      console.log(`  Proration Reduction: ${(teamTotalHours - breakdownTotal).toFixed(2)}h`);
    });

    return data;
  }, [teamForecast, startDate]);

  const formatMonth = (monthStr: string): string => {
    const [year, month] = monthStr.split('-');
    const date = new Date(parseInt(year), parseInt(month) - 1);
    return date.toLocaleDateString('en-US', { month: 'short', year: 'numeric' });
  };

  const getSliderLabel = (value: number): string => {
    const labels: { [key: number]: string } = {
      1: 'Minimal',
      2: 'Low',
      3: 'Moderate',
      4: 'High',
      5: 'Very High',
    };
    return labels[value] || '';
  };

  const phaseColors: { [key: string]: string } = {
    'Ramp Up': '#554DFF',
    'Busy (Peak)': '#00FFCE',
    'Ramp Down': '#7D00FF',
  };

  return (
    <Grid container spacing={3}>
      {/* Left Column: Input Form */}
      <Grid item xs={12} md={4}>
        <Card>
          <CardHeader
            title="Project Forecast"
            subheader="Configure your project parameters"
          />
          <CardContent>
            {/* Total Hours */}
            <TextField
              fullWidth
              label="Total Hours Budget"
              type="number"
              value={totalHours}
              onChange={(e) => setTotalHours(Number(e.target.value))}
              margin="normal"
              inputProps={{ min: 100, step: 50 }}
            />

            {/* Start Date */}
            <TextField
              fullWidth
              label="Project Start Date"
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              margin="normal"
              InputLabelProps={{ shrink: true }}
            />

            {/* Estimated Duration */}
            <Box sx={{ mt: 3, mb: 2 }}>
              <Typography gutterBottom>
                Estimated Duration: {estimatedMonths} months
              </Typography>
              <Slider
                value={estimatedMonths}
                onChange={(_, value) => setEstimatedMonths(value as number)}
                min={3}
                max={18}
                marks
                valueLabelDisplay="auto"
              />
            </Box>

            {/* Project Characteristics (5 Sliders) */}
            <Typography variant="h6" sx={{ mt: 3, mb: 2 }}>
              Project Characteristics
            </Typography>

            <Box sx={{ mb: 3 }}>
              <Typography variant="body2" gutterBottom>
                Backend Integrations: {getSliderLabel(beIntegrations)}
              </Typography>
              <Slider
                value={beIntegrations}
                onChange={(_, value) => setBeIntegrations(value as number)}
                min={1}
                max={5}
                step={1}
                marks
                valueLabelDisplay="auto"
              />
            </Box>

            <Box sx={{ mb: 3 }}>
              <Typography variant="body2" gutterBottom>
                Custom Theme: {getSliderLabel(customTheme)}
              </Typography>
              <Slider
                value={customTheme}
                onChange={(_, value) => setCustomTheme(value as number)}
                min={1}
                max={5}
                step={1}
                marks
                valueLabelDisplay="auto"
              />
            </Box>

            <Box sx={{ mb: 3 }}>
              <Typography variant="body2" gutterBottom>
                Custom Designs: {getSliderLabel(customDesigns)}
              </Typography>
              <Slider
                value={customDesigns}
                onChange={(_, value) => setCustomDesigns(value as number)}
                min={1}
                max={5}
                step={1}
                marks
                valueLabelDisplay="auto"
              />
            </Box>

            <Box sx={{ mb: 3 }}>
              <Typography variant="body2" gutterBottom>
                UX Research: {getSliderLabel(uxResearch)}
              </Typography>
              <Slider
                value={uxResearch}
                onChange={(_, value) => setUxResearch(value as number)}
                min={1}
                max={5}
                step={1}
                marks
                valueLabelDisplay="auto"
              />
            </Box>

            <Box sx={{ mb: 3 }}>
              <Typography variant="body2" gutterBottom>
                Extensive Customizations: {getSliderLabel(extensiveCustomizations)}
              </Typography>
              <Slider
                value={extensiveCustomizations}
                onChange={(_, value) => setExtensiveCustomizations(value as number)}
                min={1}
                max={5}
                step={1}
                marks
                valueLabelDisplay="auto"
              />
            </Box>

            <Box sx={{ mb: 3 }}>
              <Typography variant="body2" gutterBottom>
                Project Oversight: {getSliderLabel(projectOversight)}
              </Typography>
              <Slider
                value={projectOversight}
                onChange={(_, value) => setProjectOversight(value as number)}
                min={1}
                max={5}
                step={1}
                marks
                valueLabelDisplay="auto"
              />
              <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, display: 'block' }}>
                Adjusts PM allocation (1=less oversight, 3=typical, 5=high oversight)
              </Typography>
            </Box>

            {/* Teams Selection */}
            <Typography variant="h6" sx={{ mt: 3, mb: 1 }}>
              Teams Involved
            </Typography>
            <FormGroup>
              {availableTeams.map((team) => (
                <FormControlLabel
                  key={team}
                  control={
                    <Checkbox
                      checked={teamsSelected.includes(team)}
                      onChange={() => handleTeamToggle(team)}
                    />
                  }
                  label={team}
                />
              ))}
            </FormGroup>

            {/* Generate Button */}
            <Button
              fullWidth
              variant="contained"
              onClick={handleGenerateForecast}
              disabled={loading}
              sx={{ mt: 3 }}
            >
              {loading ? <CircularProgress size={24} /> : 'Generate Forecast'}
            </Button>
          </CardContent>
        </Card>
      </Grid>

      {/* Right Column: Results */}
      <Grid item xs={12} md={8}>
        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}

        {teamForecast && epicSchedule ? (
          <>
            {/* Download CSV Button */}
            <Box sx={{ mb: 2, display: 'flex', justifyContent: 'flex-end' }}>
              <Button
                variant="outlined"
                startIcon={<Download />}
                onClick={handleDownloadCSV}
              >
                Download Full Forecast (CSV)
              </Button>
            </Box>

            {/* Team Distribution Section */}
            <Card sx={{ mb: 3 }}>
              <CardHeader
                title="Team Distribution"
                subheader={`Total: ${teamForecast.total_hours}h over ${teamForecast.estimated_months} months`}
              />
              <CardContent>
                <Box sx={{ mb: 2 }}>
                  <Chip
                    label={`Baseline: ${teamForecast.baseline_set_used}`}
                    color="primary"
                    size="small"
                    sx={{ mr: 1 }}
                  />
                  {(teamForecast.characteristics?.be_integrations ?? 0) >= 3 && (
                    <Chip
                      label="Backend Integrations"
                      color="secondary"
                      size="small"
                      sx={{ mr: 1 }}
                    />
                  )}
                  {(teamForecast.characteristics?.extensive_customizations ?? 0) >= 3 && (
                    <Chip
                      label="Extensive Customizations"
                      color="warning"
                      size="small"
                    />
                  )}
                </Box>

                {/* Team Allocation Table */}
                <TableContainer component={Paper} sx={{ mb: 3 }}>
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell>Team</TableCell>
                        <TableCell align="right">Hours</TableCell>
                        <TableCell align="right">% of Total</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {teamForecast.teams.map((team) => (
                        <TableRow key={team.team}>
                          <TableCell>{team.team}</TableCell>
                          <TableCell align="right">{team.total_hours}</TableCell>
                          <TableCell align="right">{team.percentage}%</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>

                {/* Monthly Distribution Chart */}
                <Typography variant="h6" gutterBottom>
                  Monthly Distribution
                </Typography>
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={chartData} key={JSON.stringify(teamForecast)}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="month" />
                    <YAxis />
                    <Tooltip />
                    <Legend />
                    {teamForecast.teams.map((team, index) => (
                      <Bar
                        key={team.team}
                        dataKey={team.team}
                        stackId="a"
                        fill={`hsl(${(index * 360) / teamForecast.teams.length}, 70%, 50%)`}
                      />
                    ))}
                  </BarChart>
                </ResponsiveContainer>

                {/* Monthly Breakdown Table */}
                <Typography variant="h6" sx={{ mt: 3, mb: 2 }}>
                  Monthly Breakdown
                </Typography>
                <TableContainer component={Paper}>
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell sx={{ position: 'sticky', left: 0, bgcolor: 'background.paper', zIndex: 1 }}>
                          Team
                        </TableCell>
                        <TableCell align="right" sx={{ position: 'sticky', left: 80, bgcolor: 'background.paper', zIndex: 1 }}>
                          Total
                        </TableCell>
                        {chartData.map((monthData, index) => (
                          <TableCell key={index} align="right">
                            {monthData.month}
                          </TableCell>
                        ))}
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {teamForecast.teams.map((team) => {
                        // Calculate actual total from monthly breakdown (includes proration)
                        const actualTotal = team.monthly_breakdown.reduce((sum, m) => sum + m.hours, 0);

                        return (
                          <TableRow key={team.team}>
                            <TableCell sx={{ position: 'sticky', left: 0, bgcolor: 'background.paper' }}>
                              {team.team}
                            </TableCell>
                            <TableCell align="right" sx={{ position: 'sticky', left: 80, bgcolor: 'background.paper', fontWeight: 'bold' }}>
                              {actualTotal.toFixed(1)}h
                            </TableCell>
                            {team.monthly_breakdown.map((monthData) => {
                              const maxHours = Math.max(...team.monthly_breakdown.map((m) => m.hours));
                              const intensity = maxHours > 0 ? monthData.hours / maxHours : 0;

                              return (
                                <TableCell
                                  key={monthData.month}
                                  align="right"
                                  sx={{
                                    bgcolor: `${phaseColors[monthData.phase]}${Math.round(intensity * 40 + 10).toString(16)}`,
                                  }}
                                >
                                  {monthData.hours.toFixed(1)}
                                </TableCell>
                              );
                            })}
                          </TableRow>
                        );
                      })}

                      {/* Totals Row */}
                      <TableRow sx={{ fontWeight: 'bold', bgcolor: 'action.hover' }}>
                        <TableCell sx={{ position: 'sticky', left: 0, bgcolor: 'action.hover' }}>
                          <strong>Total</strong>
                        </TableCell>
                        <TableCell align="right" sx={{ position: 'sticky', left: 80, bgcolor: 'action.hover' }}>
                          <strong>
                            {teamForecast.teams.reduce((sum, team) =>
                              sum + team.monthly_breakdown.reduce((s, m) => s + m.hours, 0), 0
                            ).toFixed(1)}h
                          </strong>
                        </TableCell>
                        {chartData.map((monthData, index) => {
                          const monthTotal = teamForecast.teams.reduce((sum, team) => {
                            const teamMonth = team.monthly_breakdown.find((m) => m.month === index + 1);
                            return sum + (teamMonth ? teamMonth.hours : 0);
                          }, 0);

                          return (
                            <TableCell key={index} align="right">
                              <strong>{monthTotal.toFixed(1)}</strong>
                            </TableCell>
                          );
                        })}
                      </TableRow>
                    </TableBody>
                  </Table>
                </TableContainer>

                {/* Monthly Breakdown by Epic */}
                {epicSchedule && epicSchedule.epics && epicSchedule.epics.length > 0 && (
                  <>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mt: 4, mb: 2 }}>
                      <Typography variant="h6">
                        Monthly Breakdown by Epic
                      </Typography>
                      <Button
                        variant="contained"
                        color="primary"
                        startIcon={<Upload />}
                        onClick={handleExportToJira}
                        size="small"
                      >
                        Export to Jira
                      </Button>
                    </Box>
                    <TableContainer component={Paper}>
                      <Table size="small">
                        <TableHead>
                          <TableRow>
                            <TableCell sx={{ position: 'sticky', left: 0, bgcolor: 'background.paper', zIndex: 1 }}>
                              Epic Category
                            </TableCell>
                            <TableCell align="right">Ratio %</TableCell>
                            <TableCell align="right">Total Hours</TableCell>
                            {epicSchedule.months?.map((month) => (
                              <TableCell key={month} align="right">
                                {formatMonth(month)}
                              </TableCell>
                            ))}
                          </TableRow>
                        </TableHead>
                        <TableBody>
                          {epicSchedule.epics.map((epic) => {
                            const maxHours = Math.max(
                              ...epic.monthly_breakdown.map((m) => m.hours)
                            );
                            return (
                              <TableRow key={epic.epic_category}>
                                <TableCell sx={{ position: 'sticky', left: 0, bgcolor: 'background.paper' }}>
                                  {epic.epic_category}
                                </TableCell>
                                <TableCell align="right">{(epic.ratio * 100).toFixed(1)}%</TableCell>
                                <TableCell align="right">{epic.allocated_hours.toFixed(1)}h</TableCell>
                                {epic.monthly_breakdown.map((monthData) => {
                                  const intensity = maxHours > 0 ? monthData.hours / maxHours : 0;
                                  return (
                                    <TableCell
                                      key={monthData.month}
                                      align="right"
                                      sx={{
                                        bgcolor: `rgba(85, 77, 255, ${intensity * 0.3})`,
                                      }}
                                    >
                                      {monthData.hours.toFixed(1)}
                                    </TableCell>
                                  );
                                })}
                              </TableRow>
                            );
                          })}
                          {/* Totals Row */}
                          <TableRow sx={{ fontWeight: 'bold', bgcolor: 'action.hover' }}>
                            <TableCell sx={{ position: 'sticky', left: 0, bgcolor: 'action.hover' }}>
                              <strong>Total</strong>
                            </TableCell>
                            <TableCell align="right">100%</TableCell>
                            <TableCell align="right">{epicSchedule.total_hours.toFixed(1)}h</TableCell>
                            {epicSchedule.monthly_totals?.map((monthTotal) => (
                              <TableCell key={monthTotal.month} align="right">
                                <strong>{monthTotal.total_hours.toFixed(1)}</strong>
                              </TableCell>
                            ))}
                          </TableRow>
                        </TableBody>
                      </Table>
                    </TableContainer>
                  </>
                )}
              </CardContent>
            </Card>

            {/* AI Epic Forecast Section */}
            {teamForecast.epics && teamForecast.epics.length > 0 && (
              <Card sx={{ mb: 3 }}>
                <CardHeader
                  title="AI Epic Category Forecast"
                  subheader="AI-predicted distribution by epic category based on project characteristics"
                />
                <CardContent>
                  {/* Epic Allocation Summary Cards */}
                  <Grid container spacing={2} sx={{ mb: 3 }}>
                    {teamForecast.epics
                      .sort((a, b) => b.percentage - a.percentage)
                      .map((epic) => (
                        <Grid item xs={12} sm={6} md={4} key={epic.epic}>
                          <Card variant="outlined" sx={{ height: '100%' }}>
                            <CardContent>
                              <Typography variant="h6" color="primary" gutterBottom>
                                {epic.epic}
                              </Typography>
                              <Typography variant="h4">
                                {epic.total_hours.toFixed(1)}h
                              </Typography>
                              <Typography variant="body2" color="text.secondary">
                                {epic.percentage.toFixed(1)}% of total
                              </Typography>
                              {epic.reasoning && (
                                <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
                                  {epic.reasoning}
                                </Typography>
                              )}
                            </CardContent>
                          </Card>
                        </Grid>
                      ))}
                  </Grid>

                  {/* Epic Allocation Table */}
                  <Typography variant="h6" gutterBottom>
                    Epic Category Breakdown
                  </Typography>
                  <TableContainer component={Paper}>
                    <Table size="small">
                      <TableHead>
                        <TableRow>
                          <TableCell>Epic Category</TableCell>
                          <TableCell align="right">Hours</TableCell>
                          <TableCell align="right">% of Total</TableCell>
                          <TableCell>AI Reasoning</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {teamForecast.epics
                          .sort((a, b) => b.percentage - a.percentage)
                          .map((epic) => (
                            <TableRow key={epic.epic}>
                              <TableCell>
                                <strong>{epic.epic}</strong>
                              </TableCell>
                              <TableCell align="right">
                                {epic.total_hours.toFixed(1)}h
                              </TableCell>
                              <TableCell align="right">
                                {epic.percentage.toFixed(1)}%
                              </TableCell>
                              <TableCell>
                                <Typography variant="body2" color="text.secondary">
                                  {epic.reasoning}
                                </Typography>
                              </TableCell>
                            </TableRow>
                          ))}
                      </TableBody>
                    </Table>
                  </TableContainer>
                </CardContent>
              </Card>
            )}
          </>
        ) : (
          <Box sx={{ textAlign: 'center', py: 8 }}>
            <Typography variant="body1" color="text.secondary">
              Configure your project parameters and click "Generate Forecast" to see
              team distribution and epic schedule breakdown.
            </Typography>
          </Box>
        )}
      </Grid>

      {/* Jira Export Modal */}
      <Dialog
        open={exportModalOpen}
        onClose={() => setExportModalOpen(false)}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>Export Forecast to Jira</DialogTitle>
        <DialogContent>
          {!exportResult ? (
            <>
              <TextField
                label="Jira Project Key"
                value={projectKey}
                onChange={(e) => setProjectKey(e.target.value.toUpperCase())}
                fullWidth
                margin="normal"
                placeholder="e.g., PROJ"
                helperText="Enter the Jira project key where epics will be created"
              />

              {fuzzyMatches && fuzzyMatches.length > 0 && (
                <Box sx={{ mt: 3 }}>
                  <Typography variant="h6" gutterBottom>
                    Epic Mapping
                  </Typography>
                  {fuzzyMatches.map((match: any) => {
                    const mapping = epicMappings[match.forecast_epic] || { action: 'create' };
                    return (
                      <Card key={match.forecast_epic} sx={{ mb: 2, p: 2 }}>
                        <Typography variant="subtitle1" fontWeight="bold">
                          {match.forecast_epic}
                        </Typography>

                        <FormControl component="fieldset" sx={{ mt: 2 }}>
                          <RadioGroup
                            value={mapping.action || 'create'}
                            onChange={(e) =>
                              handleMappingChange(
                                match.forecast_epic,
                                'action',
                                e.target.value
                              )
                            }
                          >
                            <FormControlLabel
                              value="create"
                              control={<Radio />}
                              label="Create New Epic"
                            />
                            {match.suggestions && match.suggestions.length > 0 && (
                              <FormControlLabel
                                value="link"
                                control={<Radio />}
                                label="Link to Existing Epic"
                              />
                            )}
                          </RadioGroup>
                        </FormControl>

                        {mapping.action === 'link' &&
                          match.suggestions &&
                          match.suggestions.length > 0 && (
                            <FormControl fullWidth sx={{ mt: 2 }}>
                              <InputLabel>Select Existing Epic</InputLabel>
                              <Select
                                value={mapping.existing_key || ''}
                                onChange={(e) =>
                                  handleMappingChange(
                                    match.forecast_epic,
                                    'existing_key',
                                    e.target.value
                                  )
                                }
                                label="Select Existing Epic"
                              >
                                {match.suggestions.map((suggestion: any) => (
                                  <MenuItem
                                    key={suggestion.key}
                                    value={suggestion.key}
                                  >
                                    {suggestion.key} - {suggestion.name} (Score:{' '}
                                    {suggestion.score})
                                  </MenuItem>
                                ))}
                              </Select>
                            </FormControl>
                          )}

                        <TextField
                          label="Story Points (optional)"
                          type="number"
                          value={mapping.story_points || ''}
                          onChange={(e) =>
                            handleMappingChange(
                              match.forecast_epic,
                              'story_points',
                              parseInt(e.target.value) || undefined
                            )
                          }
                          fullWidth
                          margin="normal"
                          helperText="Optionally set story points for this epic"
                        />
                      </Card>
                    );
                  })}
                </Box>
              )}
            </>
          ) : (
            <Box>
              {exportResult.success ? (
                <Alert severity="success" sx={{ mb: 2 }}>
                  Successfully exported {exportResult.results?.length || 0} epics
                  to Jira!
                </Alert>
              ) : (
                <Alert severity="error" sx={{ mb: 2 }}>
                  {exportResult.error || 'Export failed'}
                </Alert>
              )}

              {exportResult.results && exportResult.results.length > 0 && (
                <Box sx={{ mt: 2 }}>
                  <Typography variant="h6" gutterBottom>
                    Results:
                  </Typography>
                  {exportResult.results.map((result: any, index: number) => (
                    <Box key={index} sx={{ mb: 1 }}>
                      <Typography variant="body2">
                        <strong>{result.epic_name}:</strong>{' '}
                        {result.success ? (
                          <>
                            ✓ {result.action === 'created' ? 'Created' : 'Updated'}{' '}
                            ({result.epic_key})
                          </>
                        ) : (
                          <>✗ {result.error}</>
                        )}
                      </Typography>
                    </Box>
                  ))}
                </Box>
              )}
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          {!exportResult ? (
            <>
              <Button onClick={() => setExportModalOpen(false)}>Cancel</Button>
              <Button
                onClick={handleConfirmExport}
                variant="contained"
                color="primary"
                disabled={exportLoading || !projectKey || !fuzzyMatches}
              >
                {exportLoading ? <CircularProgress size={20} /> : 'Confirm Export'}
              </Button>
            </>
          ) : (
            <Button onClick={() => setExportModalOpen(false)} variant="contained">
              Close
            </Button>
          )}
        </DialogActions>
      </Dialog>
    </Grid>
  );
};

export default ProjectForecastTab;
