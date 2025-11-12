import React, { useState, useEffect } from 'react';
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
  LinearProgress,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
} from '@mui/material';
import { Upload, CheckCircle } from '@mui/icons-material';
import axios from 'axios';

interface Project {
  key: string;
  name: string;
}

interface ImportResult {
  success: boolean;
  project_key: string;
  date_range: string;
  epic_count: number;
  records: number;
  processed: number;
  skipped: number;
}

const HistoricalDataImportTab: React.FC = () => {
  // Form state
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProject, setSelectedProject] = useState<string>('');
  const [startDate, setStartDate] = useState<string>('2023-01-01');
  const [endDate, setEndDate] = useState<string>(
    new Date().toISOString().split('T')[0]
  );

  // Project characteristics (1-5 sliders) - same as ProjectForecastTab
  const [beIntegrations, setBeIntegrations] = useState<number>(3);
  const [customTheme, setCustomTheme] = useState<number>(3);
  const [customDesigns, setCustomDesigns] = useState<number>(3);
  const [uxResearch, setUxResearch] = useState<number>(3);
  const [extensiveCustomizations, setExtensiveCustomizations] = useState<number>(3);
  const [projectOversight, setProjectOversight] = useState<number>(3);

  // Import state
  const [loading, setLoading] = useState<boolean>(false);
  const [loadingProjects, setLoadingProjects] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [progress, setProgress] = useState<{
    current: number;
    total: number;
    message: string;
  } | null>(null);
  const [result, setResult] = useState<ImportResult | null>(null);

  // Load projects on mount
  useEffect(() => {
    loadProjects();
  }, []);

  // Poll task status when taskId is set
  useEffect(() => {
    if (!taskId) return;

    const pollInterval = setInterval(() => {
      checkTaskStatus(taskId);
    }, 2000); // Poll every 2 seconds

    return () => clearInterval(pollInterval);
  }, [taskId]);

  const loadProjects = async () => {
    try {
      setLoadingProjects(true);
      const token = localStorage.getItem('auth_token');
      const response = await axios.get('/api/jira/projects', {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });
      // API returns { success: true, data: { projects: [...] } }
      const projectsData = response.data.data?.projects || response.data.projects || [];
      setProjects(Array.isArray(projectsData) ? projectsData : []);
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to load projects');
      console.error('Error loading projects:', err);
    } finally {
      setLoadingProjects(false);
    }
  };

  const checkTaskStatus = async (id: string) => {
    try {
      const token = localStorage.getItem('auth_token');
      const response = await axios.get(
        `/api/historical-import/task-status/${id}`,
        {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
        }
      );
      const { state, current, total, status, result: taskResult } = response.data;

      if (state === 'PROGRESS') {
        setProgress({
          current: current || 0,
          total: total || 1,
          message: status || 'Processing...',
        });
      } else if (state === 'SUCCESS') {
        setProgress(null);
        setResult(taskResult);
        setLoading(false);
        setTaskId(null);
      } else if (state === 'FAILURE') {
        setProgress(null);
        setError(response.data.error || 'Import failed');
        setLoading(false);
        setTaskId(null);
      }
    } catch (err: any) {
      console.error('Error checking task status:', err);
    }
  };

  const handleImport = async () => {
    // Validation
    if (!selectedProject) {
      setError('Please select a project');
      return;
    }

    if (new Date(startDate) >= new Date(endDate)) {
      setError('Start date must be before end date');
      return;
    }

    if (new Date(endDate) > new Date()) {
      setError('End date cannot be in the future');
      return;
    }

    setLoading(true);
    setError(null);
    setResult(null);
    setProgress(null);

    try {
      const token = localStorage.getItem('auth_token');
      const response = await axios.post(
        '/api/historical-import/import-project',
        {
          project_key: selectedProject,
          start_date: startDate,
          end_date: endDate,
          characteristics: {
            be_integrations: beIntegrations,
            custom_theme: customTheme,
            custom_designs: customDesigns,
            ux_research: uxResearch,
            extensive_customizations: extensiveCustomizations,
            project_oversight: projectOversight,
          },
        },
        {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
        }
      );

      if (response.data.success) {
        setTaskId(response.data.task_id);
        setProgress({
          current: 0,
          total: 100,
          message: 'Starting import...',
        });
      } else {
        setError(response.data.error || 'Failed to start import');
        setLoading(false);
      }
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to start import');
      setLoading(false);
      console.error('Import error:', err);
    }
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

  const progressPercent = progress
    ? Math.round((progress.current / progress.total) * 100)
    : 0;

  return (
    <Grid container spacing={3}>
      {/* Left Column: Import Form */}
      <Grid item xs={12} md={5}>
        <Card>
          <CardHeader
            title="Import Historical Data"
            subheader="Add historical epic hours for forecasting model training"
          />
          <CardContent>
            {/* Project Selection */}
            <FormControl fullWidth margin="normal">
              <InputLabel id="project-select-label">Project</InputLabel>
              <Select
                labelId="project-select-label"
                value={selectedProject}
                onChange={(e) => setSelectedProject(e.target.value)}
                label="Project"
                disabled={loadingProjects || loading}
              >
                {projects.map((project) => (
                  <MenuItem key={project.key} value={project.key}>
                    {project.key} - {project.name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            {/* Date Range */}
            <TextField
              fullWidth
              label="Start Date"
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              margin="normal"
              InputLabelProps={{ shrink: true }}
              disabled={loading}
            />

            <TextField
              fullWidth
              label="End Date"
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              margin="normal"
              InputLabelProps={{ shrink: true }}
              disabled={loading}
            />

            {/* Project Characteristics */}
            <Typography variant="h6" sx={{ mt: 3, mb: 2 }}>
              Project Characteristics
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              Configure the characteristics of this project for accurate forecasting
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
                disabled={loading}
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
                disabled={loading}
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
                disabled={loading}
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
                disabled={loading}
              />
            </Box>

            <Box sx={{ mb: 3 }}>
              <Typography variant="body2" gutterBottom>
                Extensive Customizations: {getSliderLabel(extensiveCustomizations)}
              </Typography>
              <Slider
                value={extensiveCustomizations}
                onChange={(_, value) =>
                  setExtensiveCustomizations(value as number)
                }
                min={1}
                max={5}
                step={1}
                marks
                valueLabelDisplay="auto"
                disabled={loading}
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
                disabled={loading}
              />
              <Typography
                variant="caption"
                color="text.secondary"
                sx={{ mt: 0.5, display: 'block' }}
              >
                1=less oversight, 3=typical, 5=high oversight
              </Typography>
            </Box>

            {/* Import Button */}
            <Button
              fullWidth
              variant="contained"
              onClick={handleImport}
              disabled={loading || loadingProjects}
              startIcon={loading ? <CircularProgress size={20} /> : <Upload />}
              sx={{ mt: 3 }}
            >
              {loading ? 'Importing...' : 'Import Data'}
            </Button>
          </CardContent>
        </Card>
      </Grid>

      {/* Right Column: Status & Results */}
      <Grid item xs={12} md={7}>
        {error && (
          <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
            {error}
          </Alert>
        )}

        {progress && (
          <Card sx={{ mb: 2 }}>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Import Progress
              </Typography>
              <Box sx={{ mb: 2 }}>
                <LinearProgress variant="determinate" value={progressPercent} />
                <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                  {progress.message}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  {progress.current} / {progress.total} worklogs ({progressPercent}%)
                </Typography>
              </Box>
            </CardContent>
          </Card>
        )}

        {result && (
          <Card>
            <CardHeader
              avatar={<CheckCircle color="success" sx={{ fontSize: 40 }} />}
              title="Import Successful"
              subheader={`Historical data imported for ${result.project_key}`}
            />
            <CardContent>
              <Grid container spacing={2}>
                <Grid item xs={6}>
                  <Typography variant="body2" color="text.secondary">
                    Date Range
                  </Typography>
                  <Typography variant="h6">{result.date_range}</Typography>
                </Grid>
                <Grid item xs={6}>
                  <Typography variant="body2" color="text.secondary">
                    Epics Imported
                  </Typography>
                  <Typography variant="h6">{result.epic_count}</Typography>
                </Grid>
                <Grid item xs={6}>
                  <Typography variant="body2" color="text.secondary">
                    Hours Records
                  </Typography>
                  <Typography variant="h6">{result.records}</Typography>
                </Grid>
                <Grid item xs={6}>
                  <Typography variant="body2" color="text.secondary">
                    Worklogs Processed
                  </Typography>
                  <Typography variant="h6">{result.processed}</Typography>
                </Grid>
              </Grid>

              <Alert severity="info" sx={{ mt: 3 }}>
                <Typography variant="body2">
                  <strong>Next Step:</strong> Go to the "Epic Baselines" tab and click
                  "Rebuild Models" to include this historical data in your forecasting
                  baselines.
                </Typography>
              </Alert>
            </CardContent>
          </Card>
        )}

        {!progress && !result && !error && (
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                How to Import Historical Data
              </Typography>
              <Typography variant="body2" paragraph>
                1. <strong>Select a project</strong> from the dropdown that you want to
                import historical data for
              </Typography>
              <Typography variant="body2" paragraph>
                2. <strong>Set the date range</strong> for the import (e.g., when the
                project started and ended)
              </Typography>
              <Typography variant="body2" paragraph>
                3. <strong>Configure project characteristics</strong> to help the AI
                understand the complexity and scope
              </Typography>
              <Typography variant="body2" paragraph>
                4. <strong>Click "Import Data"</strong> to fetch epic hours from Tempo
                and categorize them with AI
              </Typography>
              <Typography variant="body2" paragraph>
                5. <strong>Rebuild models</strong> in the Epic Baselines tab to include
                the new data in forecasting
              </Typography>

              <Alert severity="info" sx={{ mt: 2 }}>
                <Typography variant="body2">
                  <strong>Note:</strong> The import process will fetch all worklogs from
                  Tempo, categorize epics using AI, and save the data to the database.
                  This may take several minutes depending on the amount of data.
                </Typography>
              </Alert>
            </CardContent>
          </Card>
        )}
      </Grid>
    </Grid>
  );
};

export default HistoricalDataImportTab;
