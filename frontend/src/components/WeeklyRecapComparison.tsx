import React from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Grid,
  Box,
  Typography,
  Paper,
  CircularProgress,
} from '@mui/material';
import ReactMarkdown from 'react-markdown';

interface DigestData {
  success: boolean;
  project_key: string;
  project_name: string;
  days_back: number;
  activity_data: {
    meetings_count: number;
    tickets_completed: number;
    tickets_created: number;
    hours_logged: number;
    progress_summary: string;
    key_achievements: string;
    blockers_risks: string;
    next_steps: string;
  };
  formatted_agenda: string;
  from_cache?: boolean;
  cached_at?: string;
}

interface ComparisonData {
  without_context: DigestData;
  with_context: DigestData;
}

interface WeeklyRecapComparisonProps {
  open: boolean;
  onClose: () => void;
  comparisonData: ComparisonData | null;
  loading: boolean;
  projectName: string;
}

const WeeklyRecapComparison: React.FC<WeeklyRecapComparisonProps> = ({
  open,
  onClose,
  comparisonData,
  loading,
  projectName,
}) => {
  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="xl"
      fullWidth
      PaperProps={{
        sx: {
          minHeight: '80vh',
          maxHeight: '90vh',
        },
      }}
    >
      <DialogTitle sx={{ pb: 2 }}>
        <Typography variant="h5" component="div" sx={{ fontWeight: 600 }}>
          Weekly Recap A/B Comparison - {projectName}
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
          Compare Weekly Recaps generated with and without historical context from Pinecone
        </Typography>
      </DialogTitle>

      <DialogContent dividers sx={{ p: 0 }}>
        {loading ? (
          <Box
            sx={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              minHeight: '400px',
              gap: 2,
            }}
          >
            <CircularProgress size={60} />
            <Typography variant="body1" color="text.secondary">
              Generating both versions in parallel...
            </Typography>
            <Typography variant="body2" color="text.secondary">
              This may take 15-30 seconds
            </Typography>
          </Box>
        ) : comparisonData ? (
          <Grid container spacing={0} sx={{ height: '100%' }}>
            {/* Left Column - Without Context */}
            <Grid item xs={6} sx={{ borderRight: '1px solid', borderColor: 'divider' }}>
              <Box>
                {/* Header - Gray */}
                <Paper
                  elevation={0}
                  sx={{
                    p: 2,
                    backgroundColor: '#757575',
                    color: 'white',
                    borderRadius: 0,
                  }}
                >
                  <Typography variant="h6" sx={{ fontWeight: 600 }}>
                    Without Historical Context
                  </Typography>
                  {comparisonData.without_context.from_cache && (
                    <Typography variant="caption" sx={{ opacity: 0.9, mt: 0.5, display: 'block' }}>
                      From cache (generated {new Date(comparisonData.without_context.cached_at!).toLocaleString()})
                    </Typography>
                  )}
                </Paper>

                {/* Content */}
                <Box sx={{ p: 3 }}>
                  <ReactMarkdown>
                    {comparisonData.without_context.formatted_agenda}
                  </ReactMarkdown>
                </Box>
              </Box>
            </Grid>

            {/* Right Column - With Context */}
            <Grid item xs={6}>
              <Box>
                {/* Header - Purple */}
                <Paper
                  elevation={0}
                  sx={{
                    p: 2,
                    backgroundColor: '#554DFF',
                    color: 'white',
                    borderRadius: 0,
                  }}
                >
                  <Typography variant="h6" sx={{ fontWeight: 600 }}>
                    With Historical Context
                  </Typography>
                  {comparisonData.with_context.from_cache && (
                    <Typography variant="caption" sx={{ opacity: 0.9, mt: 0.5, display: 'block' }}>
                      From cache (generated {new Date(comparisonData.with_context.cached_at!).toLocaleString()})
                    </Typography>
                  )}
                </Paper>

                {/* Content */}
                <Box sx={{ p: 3 }}>
                  <ReactMarkdown>
                    {comparisonData.with_context.formatted_agenda}
                  </ReactMarkdown>
                </Box>
              </Box>
            </Grid>
          </Grid>
        ) : (
          <Box sx={{ p: 3, textAlign: 'center' }}>
            <Typography variant="body1" color="text.secondary">
              No comparison data available
            </Typography>
          </Box>
        )}
      </DialogContent>

      <DialogActions sx={{ p: 2 }}>
        <Button onClick={onClose} variant="outlined">
          Close
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default WeeklyRecapComparison;
