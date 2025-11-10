import React, { useState, useEffect } from 'react';
import {
  Card,
  CardContent,
  Typography,
  Box,
  Button,
  Alert,
  Snackbar,
  CircularProgress,
  Slider,
} from '@mui/material';
import { Save as SaveIcon } from '@mui/icons-material';
import { getApiUrl } from '../config';

interface ProjectCharacteristicsProps {
  projectKey: string;
}

interface Characteristics {
  be_integrations: number;
  custom_theme: number;
  custom_designs: number;
  ux_research: number;
  extensive_customizations: number;
  project_oversight: number;
}

const ProjectCharacteristics: React.FC<ProjectCharacteristicsProps> = ({ projectKey }) => {
  const [characteristics, setCharacteristics] = useState<Characteristics>({
    be_integrations: 3,
    custom_theme: 3,
    custom_designs: 3,
    ux_research: 3,
    extensive_customizations: 3,
    project_oversight: 3,
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [snackbar, setSnackbar] = useState<{ open: boolean; message: string; severity: 'success' | 'error' }>({
    open: false,
    message: '',
    severity: 'success',
  });

  useEffect(() => {
    if (projectKey) {
      fetchCharacteristics();
    }
  }, [projectKey]);

  const fetchCharacteristics = async () => {
    try {
      const token = localStorage.getItem('token');
      const response = await fetch(
        `${getApiUrl()}/api/projects/${projectKey}/characteristics`,
        {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
        }
      );

      if (!response.ok) {
        throw new Error('Failed to fetch characteristics');
      }

      const data = await response.json();
      if (data.success && data.characteristics) {
        setCharacteristics(data.characteristics);
      }
    } catch (error) {
      console.error('Error fetching characteristics:', error);
      showSnackbar('Failed to load characteristics', 'error');
    } finally {
      setLoading(false);
    }
  };

  const saveCharacteristics = async () => {
    setSaving(true);
    try {
      const token = localStorage.getItem('token');
      const response = await fetch(
        `${getApiUrl()}/api/projects/${projectKey}/characteristics`,
        {
          method: 'PUT',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(characteristics),
        }
      );

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Failed to save characteristics');
      }

      showSnackbar('Characteristics saved successfully', 'success');
    } catch (error: any) {
      console.error('Error saving characteristics:', error);
      showSnackbar(error.message || 'Failed to save characteristics', 'error');
    } finally {
      setSaving(false);
    }
  };

  const showSnackbar = (message: string, severity: 'success' | 'error') => {
    setSnackbar({ open: true, message, severity });
  };

  const handleCloseSnackbar = () => {
    setSnackbar({ ...snackbar, open: false });
  };

  const handleChange = (field: keyof Characteristics, value: number) => {
    setCharacteristics({ ...characteristics, [field]: value });
  };

  const getLabel = (value: number): string => {
    const labels = ['Minimal', 'Low', 'Moderate', 'High', 'Very High'];
    return labels[value - 1] || 'Moderate';
  };

  const CharacteristicSlider = ({
    label,
    field,
    description,
  }: {
    label: string;
    field: keyof Characteristics;
    description: string;
  }) => (
    <Box sx={{ mb: 3 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
        <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>
          {label}
        </Typography>
        <Typography
          variant="body2"
          sx={{
            color: '#554DFF',
            fontWeight: 600,
            minWidth: '100px',
            textAlign: 'right',
          }}
        >
          {getLabel(characteristics[field])}
        </Typography>
      </Box>
      <Slider
        value={characteristics[field]}
        onChange={(_, value) => handleChange(field, value as number)}
        min={1}
        max={5}
        step={1}
        marks
        sx={{
          '& .MuiSlider-markLabel': {
            fontSize: '11px',
          },
        }}
      />
      <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5 }}>
        {description}
      </Typography>
    </Box>
  );

  if (loading) {
    return (
      <Card>
        <CardContent>
          <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
            <CircularProgress />
          </Box>
        </CardContent>
      </Card>
    );
  }

  return (
    <>
      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Project Characteristics
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
            These characteristics help improve forecasting accuracy by matching similar historical
            projects. Rate each aspect from 1 (Minimal) to 5 (Very High).
          </Typography>

          <CharacteristicSlider
            label="Backend Integrations"
            field="be_integrations"
            description="Complexity of backend integrations (APIs, databases, external services)"
          />

          <CharacteristicSlider
            label="Custom Theme"
            field="custom_theme"
            description="Level of custom theme work required"
          />

          <CharacteristicSlider
            label="Custom Designs"
            field="custom_designs"
            description="Amount of custom design work needed"
          />

          <CharacteristicSlider
            label="UX Research"
            field="ux_research"
            description="Scope and depth of UX research activities"
          />

          <CharacteristicSlider
            label="Extensive Customizations"
            field="extensive_customizations"
            description="Level of extensive customizations and unique features"
          />

          <CharacteristicSlider
            label="Project Oversight"
            field="project_oversight"
            description="Required level of project management and oversight"
          />

          <Box sx={{ display: 'flex', justifyContent: 'flex-end', mt: 3 }}>
            <Button
              variant="contained"
              startIcon={saving ? <CircularProgress size={20} /> : <SaveIcon />}
              onClick={saveCharacteristics}
              disabled={saving}
            >
              {saving ? 'Saving...' : 'Save Characteristics'}
            </Button>
          </Box>
        </CardContent>
      </Card>

      <Snackbar
        open={snackbar.open}
        autoHideDuration={6000}
        onClose={handleCloseSnackbar}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert onClose={handleCloseSnackbar} severity={snackbar.severity} sx={{ width: '100%' }}>
          {snackbar.message}
        </Alert>
      </Snackbar>
    </>
  );
};

export default ProjectCharacteristics;
