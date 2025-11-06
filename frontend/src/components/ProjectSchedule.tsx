import React, { useState } from 'react';
import {
  Card,
  CardContent,
  CardHeader,
  Typography,
  Box,
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
  MenuItem,
  Select,
  FormControl,
  InputLabel,
} from '@mui/material';
import {
  Download as DownloadIcon,
  CalendarMonth as ScheduleIcon,
} from '@mui/icons-material';
import axios from 'axios';

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

export const ProjectScheduleTab = () => {
  const [totalHours, setTotalHours] = useState<number>(1150);
  const [durationMonths, setDurationMonths] = useState<number>(7);
  const [startDate, setStartDate] = useState<string>(
    new Date().toISOString().split('T')[0]
  );
  const [schedule, setSchedule] = useState<ProjectSchedule | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleGenerateSchedule = async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await axios.post('/api/analytics/project-schedule', {
        total_hours: totalHours,
        duration_months: durationMonths,
        start_date: startDate,
      });

      setSchedule(response.data.schedule);
    } catch (err: any) {
      setError(err.response?.data?.error || err.message || 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  const handleDownloadCSV = async () => {
    try {
      const response = await axios.post(
        '/api/analytics/project-schedule/export',
        {
          total_hours: totalHours,
          duration_months: durationMonths,
          start_date: startDate,
        },
        {
          responseType: 'blob',
        }
      );

      // Create download link
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `project_schedule_${startDate}.csv`);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (err: any) {
      setError('Failed to download CSV');
    }
  };

  // Format month for display (e.g., "2025-01" -> "Jan 2025")
  const formatMonth = (monthStr: string) => {
    const [year, month] = monthStr.split('-');
    const date = new Date(parseInt(year), parseInt(month) - 1);
    return date.toLocaleDateString('en-US', { month: 'short', year: 'numeric' });
  };

  return (
    <Box>
      <Grid container spacing={3}>
        {/* Input Form */}
        <Grid item xs={12} md={4}>
          <Card>
            <CardHeader
              title="Project Parameters"
              avatar={<ScheduleIcon />}
              subheader="Configure your project schedule"
            />
            <CardContent>
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
                {/* Total Hours Input */}
                <MuiTextField
                  fullWidth
                  type="number"
                  label="Total Project Hours"
                  value={totalHours}
                  onChange={(e) => setTotalHours(parseInt(e.target.value) || 0)}
                  helperText="Estimated total hours for the project"
                />

                {/* Duration Dropdown */}
                <FormControl fullWidth>
                  <InputLabel>Project Duration</InputLabel>
                  <Select
                    value={durationMonths}
                    label="Project Duration"
                    onChange={(e) => setDurationMonths(e.target.value as number)}
                  >
                    {[5, 6, 7, 8, 9, 10, 11, 12].map((months) => (
                      <MenuItem key={months} value={months}>
                        {months} months
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>

                {/* Start Date Picker */}
                <MuiTextField
                  fullWidth
                  type="date"
                  label="Project Start Date"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                  InputLabelProps={{ shrink: true }}
                />

                {/* Generate Button */}
                <MuiButton
                  variant="contained"
                  color="primary"
                  fullWidth
                  onClick={handleGenerateSchedule}
                  disabled={loading || !totalHours || !durationMonths || !startDate}
                  startIcon={loading ? <CircularProgress size={20} /> : <ScheduleIcon />}
                >
                  {loading ? 'Generating...' : 'Generate Schedule'}
                </MuiButton>

                {/* Reference Info */}
                <Alert severity="info">
                  <Typography variant="body2" sx={{ fontWeight: 600, mb: 1 }}>
                    Reference Ranges:
                  </Typography>
                  <Typography variant="caption" component="div">
                    • Small: ~650h over 5-7 months
                  </Typography>
                  <Typography variant="caption" component="div">
                    • Medium: ~1150h over 7-9 months
                  </Typography>
                  <Typography variant="caption" component="div">
                    • Large: ~1500h+ over 9-12 months
                  </Typography>
                </Alert>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        {/* Results */}
        <Grid item xs={12} md={8}>
          {error && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {error}
            </Alert>
          )}

          {schedule && (
            <Card>
              <CardHeader
                title="Project Schedule"
                subheader={`${schedule.total_hours}h over ${schedule.duration_months} months starting ${new Date(
                  schedule.start_date
                ).toLocaleDateString()}`}
                action={
                  <MuiButton
                    variant="outlined"
                    startIcon={<DownloadIcon />}
                    onClick={handleDownloadCSV}
                  >
                    Download CSV
                  </MuiButton>
                }
              />
              <CardContent>
                <TableContainer component={Paper} sx={{ maxHeight: 600 }}>
                  <Table stickyHeader size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell sx={{ fontWeight: 600, minWidth: 200, position: 'sticky', left: 0, backgroundColor: 'white', zIndex: 2 }}>
                          Epic Category
                        </TableCell>
                        <TableCell align="right" sx={{ fontWeight: 600, minWidth: 80 }}>
                          Ratio %
                        </TableCell>
                        <TableCell align="right" sx={{ fontWeight: 600, minWidth: 100 }}>
                          Total Hours
                        </TableCell>
                        {schedule.months.map((month) => (
                          <TableCell key={month} align="right" sx={{ fontWeight: 600, minWidth: 100 }}>
                            {formatMonth(month)}
                          </TableCell>
                        ))}
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {schedule.epics.map((epic) => (
                        <TableRow key={epic.epic_category} hover>
                          <TableCell sx={{ position: 'sticky', left: 0, backgroundColor: 'white', zIndex: 1 }}>
                            {epic.epic_category}
                          </TableCell>
                          <TableCell align="right">
                            {(epic.ratio * 100).toFixed(2)}%
                          </TableCell>
                          <TableCell align="right" sx={{ fontWeight: 500 }}>
                            {epic.allocated_hours.toFixed(1)}h
                          </TableCell>
                          {epic.monthly_breakdown.map((monthData, idx) => {
                            // Color-code cells based on hours intensity
                            const maxHours = Math.max(...epic.monthly_breakdown.map(m => m.hours));
                            const intensity = maxHours > 0 ? (monthData.hours / maxHours) : 0;
                            const bgColor = `rgba(85, 77, 255, ${intensity * 0.2})`;

                            return (
                              <TableCell
                                key={idx}
                                align="right"
                                sx={{ backgroundColor: bgColor }}
                              >
                                {monthData.hours.toFixed(1)}h
                              </TableCell>
                            );
                          })}
                        </TableRow>
                      ))}
                      {/* Totals Row */}
                      <TableRow sx={{ backgroundColor: 'rgba(0, 0, 0, 0.04)' }}>
                        <TableCell sx={{ fontWeight: 700, position: 'sticky', left: 0, backgroundColor: 'rgba(0, 0, 0, 0.04)', zIndex: 1 }}>
                          TOTAL
                        </TableCell>
                        <TableCell />
                        <TableCell align="right" sx={{ fontWeight: 700 }}>
                          {schedule.total_hours.toFixed(1)}h
                        </TableCell>
                        {schedule.monthly_totals.map((monthTotal, idx) => (
                          <TableCell key={idx} align="right" sx={{ fontWeight: 700 }}>
                            {monthTotal.total_hours.toFixed(1)}h
                          </TableCell>
                        ))}
                      </TableRow>
                    </TableBody>
                  </Table>
                </TableContainer>
              </CardContent>
            </Card>
          )}

          {!schedule && !error && (
            <Card>
              <CardContent>
                <Box
                  sx={{
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    py: 8,
                    gap: 2,
                  }}
                >
                  <ScheduleIcon sx={{ fontSize: 64, color: 'text.secondary' }} />
                  <Typography variant="h6" color="text.secondary">
                    Generate a Project Schedule
                  </Typography>
                  <Typography variant="body2" color="text.secondary" textAlign="center" maxWidth={400}>
                    Enter your project parameters and generate a month-by-month breakdown
                    based on historical epic ratios and temporal distribution patterns.
                  </Typography>
                </Box>
              </CardContent>
            </Card>
          )}
        </Grid>
      </Grid>
    </Box>
  );
};
