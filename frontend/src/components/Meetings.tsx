import React, { useState } from 'react';
import {
  List,
  Datagrid,
  TextField,
  DateField,
  NumberField,
  Show,
  SimpleShowLayout,
  Edit,
  SimpleForm,
  TextInput,
  DateInput,
  useRecordContext,
  FunctionField,
  Button,
  useRedirect,
  useNotify,
  useListContext,
} from 'react-admin';
import {
  Card,
  CardContent,
  Typography,
  Box,
  Chip,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Tooltip,
} from '@mui/material';
import { Analytics, PlayArrow, Launch, CheckCircle } from '@mui/icons-material';

const MeetingTitle = () => {
  const record = useRecordContext();
  const isAnalyzed = record?.analyzed_at || record?.action_items_count > 0;

  return record ? (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <Typography variant="h6" component="div">
          {record.title}
        </Typography>
        {isAnalyzed && (
          <Tooltip title="This meeting has been analyzed by AI">
            <CheckCircle sx={{ color: 'success.main', fontSize: 16 }} />
          </Tooltip>
        )}
      </Box>
      <Typography variant="caption" color="text.secondary">
        {record.meeting_id}
      </Typography>
    </Box>
  ) : null;
};

const RelevanceScore = () => {
  const record = useRecordContext();
  if (!record) return null;

  const score = record.relevance_score || 0;
  const color = score >= 80 ? 'success' : score >= 60 ? 'warning' : 'error';

  return (
    <Chip
      label={`${score}%`}
      color={color}
      size="small"
      variant="outlined"
    />
  );
};

const AnalyzeButton = () => {
  const record = useRecordContext();
  const redirect = useRedirect();
  const notify = useNotify();

  const handleAnalyze = (event: React.MouseEvent) => {
    // Prevent row click navigation
    event.stopPropagation();

    if (record?.meeting_id || record?.id) {
      const meetingId = record.meeting_id || record.id;
      // Redirect to React Admin analysis resource
      notify('Opening analysis view...', { type: 'info' });
      redirect(`/analysis/${meetingId}/show`);
    }
  };

  return (
    <Button
      onClick={handleAnalyze}
      label="Analyze"
      variant="contained"
      color="primary"
      size="small"
    >
      <Analytics />
    </Button>
  );
};

const TranscriptButton = () => {
  const record = useRecordContext();
  const notify = useNotify();

  const handleViewTranscript = () => {
    if (record?.transcript) {
      // Create a simple modal-like display with the transcript
      const transcriptWindow = window.open('', 'transcript', 'width=800,height=600,scrollbars=yes');
      if (transcriptWindow) {
        transcriptWindow.document.write(`
          <html>
            <head>
              <title>Meeting Transcript - ${record.title}</title>
              <style>
                body { font-family: Arial, sans-serif; padding: 20px; line-height: 1.6; }
                h1 { color: #333; border-bottom: 2px solid #554DFF; padding-bottom: 10px; }
                .transcript { white-space: pre-wrap; background: #f5f5f5; padding: 20px; border-radius: 8px; }
              </style>
            </head>
            <body>
              <h1>${record.title}</h1>
              <p><strong>Date:</strong> ${new Date(record.date).toLocaleString()}</p>
              <p><strong>Duration:</strong> ${record.duration} minutes</p>
              <div class="transcript">${record.transcript}</div>
            </body>
          </html>
        `);
        transcriptWindow.document.close();
      }
    } else {
      notify('No transcript available for this meeting', { type: 'warning' });
    }
  };

  return (
    <Button
      onClick={handleViewTranscript}
      variant="outlined"
      color="secondary"
      label="View Transcript"
      size="small"
    >
      <PlayArrow sx={{ mr: 1 }} />
      Transcript
    </Button>
  );
};

const FirefliesButton = () => {
  const record = useRecordContext();
  const notify = useNotify();

  const handleOpenFireflies = (event: React.MouseEvent) => {
    // Prevent row click navigation
    event.stopPropagation();

    if (record?.meeting_id || record?.id) {
      const meetingId = record.meeting_id || record.id;
      // Construct Fireflies URL - adjust based on actual URL pattern
      const firefliesUrl = `https://app.fireflies.ai/view/${meetingId}`;
      window.open(firefliesUrl, '_blank');
      notify('Opening Fireflies meeting...', { type: 'info' });
    } else {
      notify('Meeting ID not available', { type: 'warning' });
    }
  };

  return (
    <Button
      onClick={handleOpenFireflies}
      variant="outlined"
      color="secondary"
      label="View in Fireflies"
      size="small"
    >
      <Launch sx={{ mr: 1 }} />
      Fireflies
    </Button>
  );
};

const DateRangeFilter = () => {
  const { filterValues, setFilters, refetch } = useListContext();
  const [dateRange, setDateRange] = useState(filterValues?.dateRange || '7');

  const handleDateRangeChange = (newRange: string) => {
    setDateRange(newRange);
    const newFilters = { ...filterValues, dateRange: newRange };
    setFilters(newFilters);
    // Force a refetch of the data
    setTimeout(() => refetch(), 100);
  };

  return (
    <Card sx={{ mb: 2, p: 2 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
        <Typography variant="h6">Filter by Date Range:</Typography>
        <FormControl size="small" sx={{ minWidth: 120 }}>
          <InputLabel>Date Range</InputLabel>
          <Select
            value={dateRange}
            onChange={(e) => handleDateRangeChange(e.target.value as string)}
            label="Date Range"
          >
            <MenuItem value="1">Last 1 day</MenuItem>
            <MenuItem value="7">Last 7 days</MenuItem>
            <MenuItem value="30">Last 30 days</MenuItem>
            <MenuItem value="all">All time</MenuItem>
          </Select>
        </FormControl>
      </Box>
    </Card>
  );
};

export const MeetingList = () => (
  <Box>
    <List
      title="📞 Meeting Transcripts"
      sort={{ field: 'date', order: 'DESC' }}
      perPage={25}
      actions={false}
      filters={[]} // Disable default filters since we have custom
    >
      <DateRangeFilter />
      <Datagrid rowClick="show" bulkActionButtons={false}>
        <FunctionField
          label="Meeting"
          render={(record: any) => <MeetingTitle />}
        />
        <DateField
          source="date"
          label="Date"
          options={{
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
          }}
        />
        <FunctionField
          label="Relevance"
          render={(record: any) => <RelevanceScore />}
        />
        <NumberField
          source="action_items_count"
          label="Action Items"
        />
        <FunctionField
          label="Actions"
          render={(record: any) => (
            <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
              <AnalyzeButton />
              <FirefliesButton />
            </Box>
          )}
        />
      </Datagrid>
    </List>
  </Box>
);

export const MeetingShow = () => (
  <Show title="📞 Meeting Details">
    <SimpleShowLayout>
      <Box sx={{ display: 'flex', gap: 3, flexWrap: 'wrap' }}>
        <Box sx={{ flex: '2 1 400px' }}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Meeting Information
              </Typography>
              <TextField source="title" label="Title" />
              <DateField
                source="date"
                label="Date & Time"
                options={{
                  year: 'numeric',
                  month: 'long',
                  day: 'numeric',
                  hour: '2-digit',
                  minute: '2-digit',
                }}
              />
              <TextField source="meeting_id" label="Meeting ID" />
            </CardContent>
          </Card>
        </Box>
        <Box sx={{ flex: '1 1 300px' }}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Analysis Metrics
              </Typography>
              <Box sx={{ mb: 2 }}>
                <Typography variant="body2" color="text.secondary">
                  Relevance Score
                </Typography>
                <FunctionField render={(record: any) => <RelevanceScore />} />
              </Box>
              <Box sx={{ mb: 2 }}>
                <Typography variant="body2" color="text.secondary">
                  Action Items
                </Typography>
                <NumberField source="action_items_count" />
              </Box>
              <Box sx={{ mb: 2 }}>
                <Typography variant="body2" color="text.secondary">
                  Confidence
                </Typography>
                <FunctionField
                  render={(record: any) =>
                    `${Math.round((record.confidence || 0) * 100)}%`
                  }
                />
              </Box>
            </CardContent>
          </Card>
        </Box>
      </Box>

      <Card sx={{ mt: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Quick Actions
          </Typography>
          <Box sx={{ display: 'flex', gap: 2 }}>
            <AnalyzeButton />
            <TranscriptButton />
          </Box>
        </CardContent>
      </Card>
    </SimpleShowLayout>
  </Show>
);

export const MeetingEdit = () => (
  <Edit title="✏️ Edit Meeting">
    <SimpleForm>
      <TextInput source="title" label="Title" fullWidth />
      <DateInput source="date" label="Date" />
      <TextInput source="meeting_id" label="Meeting ID" disabled />
    </SimpleForm>
  </Edit>
);