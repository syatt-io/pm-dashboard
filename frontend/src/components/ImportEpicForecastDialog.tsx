import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Box,
  Typography,
  Alert,
  AlertTitle,
  CircularProgress,
  Autocomplete,
  TextField,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Chip,
  IconButton,
  Paper,
  FormControlLabel,
  Checkbox,
  Stepper,
  Step,
  StepLabel,
} from '@mui/material';
import EditIcon from '@mui/icons-material/Edit';
import axios from 'axios';
import {
  ForecastEpic,
  PreviewImportResponse,
  EpicMapping,
  ImportMapping,
  CreatePlaceholder,
  epicBudgetsApi,
} from '../api/epicBudgets';

const API_BASE_URL =
  process.env.REACT_APP_API_URL ||
  (window.location.hostname === 'localhost'
    ? 'http://localhost:4000'
    : 'https://agent-pm-tsbbb.ondigitalocean.app');

interface Project {
  key: string;
  name: string;
  is_active: boolean;
  start_date: string | null;
  epic_count?: number;
}

interface ImportEpicForecastDialogProps {
  open: boolean;
  onClose: () => void;
  forecastEpics: ForecastEpic[];
  onSuccess?: () => void;
}

const ImportEpicForecastDialog: React.FC<ImportEpicForecastDialogProps> = ({
  open,
  onClose,
  forecastEpics,
  onSuccess,
}) => {
  // Step state
  const [activeStep, setActiveStep] = useState(0);
  const steps = ['Select Project', 'Review AI Mappings', 'Confirm Import'];

  // Data state
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProject, setSelectedProject] = useState<Project | null>(null);
  const [previewData, setPreviewData] = useState<PreviewImportResponse | null>(
    null
  );
  const [editedMappings, setEditedMappings] = useState<EpicMapping[]>([]);
  const [placeholderChoices, setPlaceholderChoices] = useState<
    Record<string, boolean>
  >({});

  // UI state
  const [loadingProjects, setLoadingProjects] = useState(false);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [importing, setImporting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch active projects on mount
  useEffect(() => {
    if (open) {
      fetchActiveProjects();
    }
  }, [open]);

  const fetchActiveProjects = async () => {
    try {
      setLoadingProjects(true);
      setError(null);

      const response = await axios.get(`${API_BASE_URL}/api/jira/projects`, {
        params: { is_active: true },
      });

      setProjects(response.data.data?.projects || []);
    } catch (err: any) {
      console.error('Error fetching projects:', err);
      setError(err.response?.data?.error || 'Failed to load active projects');
    } finally {
      setLoadingProjects(false);
    }
  };

  const handleProjectSelect = async (project: Project | null) => {
    setSelectedProject(project);
    setPreviewData(null);
    setEditedMappings([]);
    setPlaceholderChoices({});

    if (project) {
      // Auto-trigger AI mapping preview
      await fetchPreviewMappings(project.key);
    }
  };

  const fetchPreviewMappings = async (projectKey: string) => {
    try {
      setLoadingPreview(true);
      setError(null);

      const preview = await epicBudgetsApi.previewImport(
        projectKey,
        forecastEpics
      );

      if (preview.error) {
        setError(preview.error);
        return;
      }

      setPreviewData(preview);
      setEditedMappings(preview.mappings || []);

      // Initialize placeholder choices (default to true for user to choose)
      const initialChoices: Record<string, boolean> = {};
      (preview.unmapped_forecasts || []).forEach((epic) => {
        initialChoices[epic] = false; // Default to NOT creating placeholders
      });
      setPlaceholderChoices(initialChoices);

      // Move to next step
      setActiveStep(1);
    } catch (err: any) {
      console.error('Error fetching preview:', err);
      setError(err.message || 'Failed to load AI mappings');
    } finally {
      setLoadingPreview(false);
    }
  };

  const handleHoursChange = (
    mappingIndex: number,
    epicIndex: number,
    newHours: number
  ) => {
    const updated = [...editedMappings];
    updated[mappingIndex].matched_epics[epicIndex].allocated_hours = newHours;
    setEditedMappings(updated);
  };

  const handleNext = () => {
    if (activeStep === 0 && selectedProject) {
      // Already handled in handleProjectSelect
    } else if (activeStep === 1) {
      setActiveStep(2); // Move to confirmation
    }
  };

  const handleBack = () => {
    setActiveStep(Math.max(0, activeStep - 1));
  };

  const handleImport = async () => {
    if (!selectedProject || !previewData) return;

    try {
      setImporting(true);
      setError(null);

      // Build import request
      const mappings: ImportMapping[] = editedMappings.map((mapping) => {
        const epicAllocations: Record<string, number> = {};
        mapping.matched_epics.forEach((epic) => {
          epicAllocations[epic.epic_key] = epic.allocated_hours;
        });

        return {
          forecast_epic: mapping.forecast_epic,
          forecast_hours: mapping.forecast_hours,
          epic_allocations: epicAllocations,
        };
      });

      const createPlaceholders: CreatePlaceholder[] = [];
      Object.entries(placeholderChoices).forEach(([epic, shouldCreate]) => {
        if (shouldCreate) {
          // Find the forecast epic to get hours
          const forecastEpic = forecastEpics.find((e) => e.epic === epic);
          if (forecastEpic) {
            createPlaceholders.push({
              forecast_epic: epic,
              hours: forecastEpic.total_hours,
            });
          }
        }
      });

      const result = await epicBudgetsApi.importFromForecast({
        project_key: selectedProject.key,
        mappings,
        create_placeholders: createPlaceholders,
        categories: previewData.categories, // Include AI-suggested categories
      });

      if (result.error) {
        setError(result.error);
        return;
      }

      // Success!
      if (onSuccess) {
        onSuccess();
      }
      handleClose();
    } catch (err: any) {
      console.error('Error importing forecast:', err);
      setError(err.message || 'Failed to import forecast');
    } finally {
      setImporting(false);
    }
  };

  const handleClose = () => {
    setActiveStep(0);
    setSelectedProject(null);
    setPreviewData(null);
    setEditedMappings([]);
    setPlaceholderChoices({});
    setError(null);
    onClose();
  };

  const getTotalHoursToImport = () => {
    let total = 0;

    // Sum mapped hours
    editedMappings.forEach((mapping) => {
      mapping.matched_epics.forEach((epic) => {
        total += epic.allocated_hours;
      });
    });

    // Add placeholder hours
    Object.entries(placeholderChoices).forEach(([epic, shouldCreate]) => {
      if (shouldCreate) {
        const forecastEpic = forecastEpics.find((e) => e.epic === epic);
        if (forecastEpic) {
          total += forecastEpic.total_hours;
        }
      }
    });

    return total;
  };

  const renderStepContent = () => {
    switch (activeStep) {
      case 0:
        return (
          <Box>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              Select an active project to import these forecast epics into. AI
              will automatically map forecasted epics to existing project epics.
            </Typography>

            <Autocomplete
              options={projects}
              getOptionLabel={(option) => `${option.key} - ${option.name}`}
              value={selectedProject}
              onChange={(_, newValue) => handleProjectSelect(newValue)}
              loading={loadingProjects}
              renderInput={(params) => (
                <TextField
                  {...params}
                  label="Select Active Project"
                  placeholder="Choose a project..."
                  InputProps={{
                    ...params.InputProps,
                    endAdornment: (
                      <>
                        {loadingProjects ? (
                          <CircularProgress color="inherit" size={20} />
                        ) : null}
                        {params.InputProps.endAdornment}
                      </>
                    ),
                  }}
                />
              )}
            />

            {loadingPreview && (
              <Box sx={{ mt: 3, textAlign: 'center' }}>
                <CircularProgress size={40} />
                <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
                  AI is analyzing your project epics...
                </Typography>
              </Box>
            )}
          </Box>
        );

      case 1:
        return (
          <Box>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              Review AI-suggested mappings. You can adjust hour allocations before
              importing.
            </Typography>

            {/* Mappings Table */}
            {editedMappings.length > 0 && (
              <TableContainer component={Paper} sx={{ mb: 3 }}>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Forecasted Epic</TableCell>
                      <TableCell>Hours</TableCell>
                      <TableCell>Confidence</TableCell>
                      <TableCell>Existing Epic</TableCell>
                      <TableCell>Category</TableCell>
                      <TableCell>Import Hours</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {editedMappings.map((mapping, mappingIdx) => (
                      <React.Fragment key={mappingIdx}>
                        {mapping.matched_epics.map((epic, epicIdx) => (
                          <TableRow key={`${mappingIdx}-${epicIdx}`}>
                            {epicIdx === 0 && (
                              <>
                                <TableCell rowSpan={mapping.matched_epics.length}>
                                  <Typography variant="body2" fontWeight="medium">
                                    {mapping.forecast_epic}
                                  </Typography>
                                  <Typography
                                    variant="caption"
                                    color="text.secondary"
                                  >
                                    {forecastEpics.find(
                                      (e) => e.epic === mapping.forecast_epic
                                    )?.reasoning || ''}
                                  </Typography>
                                </TableCell>
                                <TableCell rowSpan={mapping.matched_epics.length}>
                                  {mapping.forecast_hours}h
                                </TableCell>
                              </>
                            )}
                            <TableCell>
                              <Chip
                                label={`${Math.round(epic.confidence * 100)}%`}
                                color={
                                  epic.confidence > 0.8
                                    ? 'success'
                                    : epic.confidence > 0.6
                                    ? 'warning'
                                    : 'default'
                                }
                                size="small"
                              />
                            </TableCell>
                            <TableCell>
                              <Typography variant="body2">
                                {epic.epic_key}
                              </Typography>
                              <Typography
                                variant="caption"
                                color="text.secondary"
                              >
                                {epic.epic_summary}
                              </Typography>
                              <Typography
                                variant="caption"
                                display="block"
                                color="text.secondary"
                                sx={{ fontStyle: 'italic', mt: 0.5 }}
                              >
                                {epic.reasoning}
                              </Typography>
                            </TableCell>
                            <TableCell>
                              {epic.category ? (
                                <Chip
                                  label={epic.category}
                                  size="small"
                                  color="primary"
                                  variant="outlined"
                                />
                              ) : (
                                <Typography variant="caption" color="text.secondary">
                                  Uncategorized
                                </Typography>
                              )}
                            </TableCell>
                            <TableCell>
                              <TextField
                                type="number"
                                value={epic.allocated_hours}
                                onChange={(e) =>
                                  handleHoursChange(
                                    mappingIdx,
                                    epicIdx,
                                    parseFloat(e.target.value) || 0
                                  )
                                }
                                size="small"
                                sx={{ width: 80 }}
                                InputProps={{
                                  endAdornment: <Typography variant="caption">h</Typography>,
                                }}
                              />
                            </TableCell>
                          </TableRow>
                        ))}
                      </React.Fragment>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            )}

            {/* Unmapped Forecasts */}
            {previewData && previewData.unmapped_forecasts.length > 0 && (
              <Alert severity="warning" sx={{ mt: 2 }}>
                <AlertTitle>Unmapped Forecast Epics</AlertTitle>
                <Typography variant="body2" sx={{ mb: 1 }}>
                  The following forecasted epics have no matching project epics.
                  You can create placeholder epics for them:
                </Typography>
                {previewData.unmapped_forecasts.map((epic) => {
                  const forecastEpic = forecastEpics.find((e) => e.epic === epic);
                  return (
                    <Box key={epic} sx={{ mb: 1 }}>
                      <FormControlLabel
                        control={
                          <Checkbox
                            checked={placeholderChoices[epic] || false}
                            onChange={(e) =>
                              setPlaceholderChoices({
                                ...placeholderChoices,
                                [epic]: e.target.checked,
                              })
                            }
                          />
                        }
                        label={
                          <Box>
                            <Typography variant="body2" fontWeight="medium">
                              {epic} ({forecastEpic?.total_hours || 0}h)
                            </Typography>
                            <Typography variant="caption" color="text.secondary">
                              {forecastEpic?.reasoning || ''}
                            </Typography>
                          </Box>
                        }
                      />
                    </Box>
                  );
                })}
              </Alert>
            )}
          </Box>
        );

      case 2:
        const totalHours = getTotalHoursToImport();
        const willUpdate = editedMappings.reduce(
          (sum, m) => sum + m.matched_epics.length,
          0
        );
        const willCreatePlaceholders = Object.values(placeholderChoices).filter(
          (v) => v
        ).length;

        // Build detailed import items list
        const importItems = [
          // Matched epics that will be updated
          ...editedMappings.flatMap((mapping) =>
            mapping.matched_epics.map((epic) => ({
              epic_key: epic.epic_key,
              epic_summary: epic.epic_summary,
              hours: epic.allocated_hours,
              source: mapping.forecast_epic,
              action: 'update' as const,
            }))
          ),
          // Placeholder epics that will be created
          ...Object.entries(placeholderChoices)
            .filter(([_, create]) => create)
            .map(([epic, _]) => {
              const forecastEpic = forecastEpics.find((e) => e.epic === epic);
              return {
                epic_key: `${selectedProject?.key}-FORECAST-?`,
                epic_summary: epic,
                hours: forecastEpic?.total_hours || 0,
                source: epic,
                action: 'create_placeholder' as const,
              };
            }),
        ];

        return (
          <Box>
            <Alert severity="info" sx={{ mb: 2 }}>
              <AlertTitle>Import Summary</AlertTitle>
              <Typography variant="body2">
                Will update <strong>{willUpdate}</strong> epic{willUpdate !== 1 ? 's' : ''}
                {previewData && previewData.will_skip > 0 && (
                  <>, skip <strong>{previewData.will_skip}</strong> (already have estimates)</>
                )}
                {willCreatePlaceholders > 0 && (
                  <>, create <strong>{willCreatePlaceholders}</strong> placeholder{willCreatePlaceholders !== 1 ? 's' : ''}</>
                )}
              </Typography>
              <Typography variant="body2" sx={{ mt: 1 }} color="primary">
                Total hours to import: <strong>{totalHours.toFixed(1)}h</strong>
              </Typography>
            </Alert>

            {/* Detailed breakdown table */}
            <TableContainer component={Paper} sx={{ mb: 2 }}>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Epic</TableCell>
                    <TableCell>Hours</TableCell>
                    <TableCell>Source Category</TableCell>
                    <TableCell>Action</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {importItems.map((item, idx) => (
                    <TableRow key={idx}>
                      <TableCell>
                        <Typography variant="body2" fontWeight="medium">
                          {item.epic_key}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          {item.epic_summary}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" fontWeight="medium">
                          {item.hours.toFixed(1)}h
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="caption" color="text.secondary">
                          {item.source}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Chip
                          label={item.action === 'update' ? 'Update' : 'Create Placeholder'}
                          color={item.action === 'update' ? 'primary' : 'default'}
                          size="small"
                        />
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>

            <Typography variant="body2" color="text.secondary">
              Ready to import forecast epics into project{' '}
              <strong>{selectedProject?.name}</strong>?
            </Typography>
          </Box>
        );

      default:
        return null;
    }
  };

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="md" fullWidth>
      <DialogTitle>Import Forecast to Project</DialogTitle>
      <DialogContent>
        <Stepper activeStep={activeStep} sx={{ mb: 3, mt: 1 }}>
          {steps.map((label) => (
            <Step key={label}>
              <StepLabel>{label}</StepLabel>
            </Step>
          ))}
        </Stepper>

        {error && (
          <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
            {error}
          </Alert>
        )}

        {renderStepContent()}
      </DialogContent>
      <DialogActions>
        <Button onClick={handleClose} disabled={importing}>
          Cancel
        </Button>
        {activeStep > 0 && activeStep < steps.length - 1 && (
          <Button onClick={handleBack} disabled={importing}>
            Back
          </Button>
        )}
        {activeStep < steps.length - 1 && (
          <Button
            onClick={handleNext}
            variant="contained"
            disabled={!selectedProject || loadingPreview}
          >
            Next
          </Button>
        )}
        {activeStep === steps.length - 1 && (
          <Button
            onClick={handleImport}
            variant="contained"
            disabled={importing || !selectedProject}
          >
            {importing ? <CircularProgress size={24} /> : 'Import Estimates'}
          </Button>
        )}
      </DialogActions>
    </Dialog>
  );
};

export default ImportEpicForecastDialog;
