import React, { useEffect, useState } from 'react';
import {
  Card,
  CardContent,
  CardHeader,
  Typography,
  Box,
  Chip,
  LinearProgress,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Alert,
  Link as MuiLink,
} from '@mui/material';
import {
  Star,
  Assignment as TaskIcon,
  Feedback as FeedbackIcon,
  Lightbulb as LearningIcon,
} from '@mui/icons-material';
import { useGetList, useRedirect } from 'react-admin';
import API_BASE_URL from '../config';

interface Project {
  key: string;
  name: string;
  current_month_hours?: number;
  forecasted_hours_month?: number;
  project_work_type?: string;
}

const MyProjectsSection = () => {
  const [watchedProjects, setWatchedProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const redirect = useRedirect();
  const currentMonth = new Date().toLocaleString('default', { month: 'long' });

  useEffect(() => {
    const fetchWatchedProjects = async () => {
      try {
        const token = localStorage.getItem('auth_token');
        if (!token) {
          setLoading(false);
          return;
        }

        // Fetch watched project keys
        const watchedResponse = await fetch(`${API_BASE_URL}/api/watched-projects`, {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
        });

        if (!watchedResponse.ok) {
          setLoading(false);
          return;
        }

        const watchedData = await watchedResponse.json();
        const watchedProjectKeys = watchedData.watched_projects || [];

        if (watchedProjectKeys.length === 0) {
          setLoading(false);
          return;
        }

        // Fetch all projects to get hours data
        const projectsResponse = await fetch(`${API_BASE_URL}/api/jira/projects`, {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
        });

        if (projectsResponse.ok) {
          const projectsData = await projectsResponse.json();
          // API returns {success: true, data: {projects: [...]}}
          const allProjects = projectsData?.data?.projects || [];

          // Filter to only watched projects
          const watched = allProjects.filter((p: Project) =>
            watchedProjectKeys.includes(p.key)
          );

          setWatchedProjects(watched);
        }
      } catch (error) {
        console.error('Error fetching watched projects:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchWatchedProjects();
  }, []);

  const getHoursColor = (currentHours: number, forecastedHours: number, projectType: string) => {
    if (projectType === 'n-a') return 'text.primary';
    if (!forecastedHours || forecastedHours === 0) return 'success.main';
    const percentage = (currentHours / forecastedHours) * 100;
    if (percentage > 100) return 'error.main';
    if (percentage > 80) return 'warning.main';
    return 'success.main';
  };

  if (loading) {
    return (
      <Card>
        <CardHeader title={`${currentMonth} - My Projects`} />
        <CardContent>
          <LinearProgress />
        </CardContent>
      </Card>
    );
  }

  if (watchedProjects.length === 0) {
    return (
      <Card>
        <CardHeader title={`${currentMonth} - My Projects`} />
        <CardContent>
          <Alert severity="info">
            <Typography variant="body2" gutterBottom>
              You haven't followed any projects yet.
            </Typography>
            <Typography variant="body2">
              <MuiLink
                component="button"
                onClick={() => redirect('/projects')}
                sx={{ cursor: 'pointer', textDecoration: 'underline' }}
              >
                Go to Projects
              </MuiLink>
              {' '}to follow projects and track their hours here.
            </Typography>
          </Alert>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader
        title={`${currentMonth} - My Projects`}
        action={
          <MuiLink
            component="button"
            onClick={() => redirect('/projects')}
            sx={{ cursor: 'pointer', textDecoration: 'underline', fontSize: '0.875rem' }}
          >
            View All Projects
          </MuiLink>
        }
      />
      <CardContent sx={{ maxHeight: '400px', overflow: 'auto', p: 0 }}>
        <TableContainer component={Paper} variant="outlined">
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Name</TableCell>
                <TableCell align="right">{currentMonth} Hours</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {watchedProjects.map((project) => {
                const currentHours = project.current_month_hours || 0;
                const forecastedHours = project.forecasted_hours_month || 0;
                const projectType = project.project_work_type || 'project-based';

                return (
                  <TableRow
                    key={project.key}
                    sx={{
                      cursor: 'pointer',
                      '&:hover': { backgroundColor: 'rgba(85, 77, 255, 0.08)' }
                    }}
                    onClick={() => redirect('show', 'projects', project.key)}
                  >
                    <TableCell>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <Star color="primary" fontSize="small" />
                        <Box>
                          <Typography variant="body2" fontWeight="medium">
                            {project.name}
                          </Typography>
                          <Typography variant="caption" color="text.secondary">
                            {project.key}
                          </Typography>
                        </Box>
                      </Box>
                    </TableCell>
                    <TableCell align="right">
                      <Typography
                        variant="body2"
                        sx={{
                          color: getHoursColor(currentHours, forecastedHours, projectType),
                          fontWeight: 'medium'
                        }}
                      >
                        {currentHours.toFixed(1)} / {forecastedHours.toFixed(1)}h
                      </Typography>
                      {forecastedHours > 0 && (
                        <Typography variant="caption" color="text.secondary">
                          ({((currentHours / forecastedHours) * 100).toFixed(0)}%)
                        </Typography>
                      )}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </TableContainer>
      </CardContent>
    </Card>
  );
};

const MyRecentMeetingsSection = () => {
  const [meetings, setMeetings] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const redirect = useRedirect();

  useEffect(() => {
    const fetchMeetings = async () => {
      try {
        const token = localStorage.getItem('auth_token');
        if (!token) {
          setLoading(false);
          return;
        }

        // Fetch watched project keys
        const watchedResponse = await fetch(`${API_BASE_URL}/api/watched-projects`, {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
        });

        if (!watchedResponse.ok) {
          setLoading(false);
          return;
        }

        const watchedData = await watchedResponse.json();
        const watchedProjectKeys = watchedData.watched_projects || [];

        if (watchedProjectKeys.length === 0) {
          setMeetings([]);
          setLoading(false);
          return;
        }

        // Fetch meetings for watched projects (limit 10)
        const projectsParam = watchedProjectKeys.join(',');
        const meetingsResponse = await fetch(
          `${API_BASE_URL}/api/meetings?resource_context=analysis&projects=${projectsParam}&sort_field=analyzed_at&sort_order=DESC&per_page=10`,
          {
            headers: {
              'Authorization': `Bearer ${token}`,
              'Content-Type': 'application/json',
            },
          }
        );

        if (meetingsResponse.ok) {
          const meetingsData = await meetingsResponse.json();
          setMeetings(meetingsData.data || []);
        }
      } catch (error) {
        console.error('Error fetching meetings:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchMeetings();
  }, []);

  return (
    <Card>
      <CardHeader
        title="My Recent Meetings"
        action={
          <MuiLink
            component="button"
            onClick={() => redirect('/analysis')}
            sx={{ cursor: 'pointer', textDecoration: 'underline', fontSize: '0.875rem' }}
          >
            View All Meetings
          </MuiLink>
        }
      />
      <CardContent sx={{ maxHeight: '400px', overflow: 'auto', p: 0 }}>
        {loading ? (
          <LinearProgress />
        ) : meetings.length === 0 ? (
          <Alert severity="info">
            No recent meetings found for your followed projects.
          </Alert>
        ) : (
          <TableContainer component={Paper} variant="outlined">
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Title</TableCell>
                  <TableCell>Meeting Day</TableCell>
                  <TableCell>Project</TableCell>
                  <TableCell align="center">Analyzed</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {meetings.map((meeting: any) => (
                  <TableRow
                    key={meeting.id}
                    sx={{
                      cursor: 'pointer',
                      '&:hover': { backgroundColor: 'rgba(85, 77, 255, 0.08)' }
                    }}
                    onClick={() => redirect('show', 'meetings', meeting.id)}
                  >
                    <TableCell>
                      <Typography variant="body2" fontWeight="medium">
                        {meeting.title || 'Untitled Meeting'}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2">
                        {new Date(meeting.date).toLocaleDateString('en-US', {
                          weekday: 'short',
                          month: 'short',
                          day: 'numeric'
                        })}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2" color="text.secondary">
                        {meeting.projects && meeting.projects.length > 0
                          ? meeting.projects.map((p: any) => p.key).join(', ')
                          : '-'}
                      </Typography>
                    </TableCell>
                    <TableCell align="center">
                      {meeting.analyzed ? (
                        <Chip label="Yes" size="small" color="success" />
                      ) : (
                        <Chip label="No" size="small" color="default" />
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </CardContent>
    </Card>
  );
};

const MyTodosSection = () => {
  const { data: todos, isLoading } = useGetList('todos', {
    pagination: { page: 1, perPage: 10 },
    sort: { field: 'created_at', order: 'DESC' },
  });
  const redirect = useRedirect();

  return (
    <Card>
      <CardHeader
        title="My TODOs"
        action={
          <MuiLink
            component="button"
            onClick={() => redirect('/todos')}
            sx={{ cursor: 'pointer', textDecoration: 'underline', fontSize: '0.875rem' }}
          >
            View All TODOs
          </MuiLink>
        }
      />
      <CardContent sx={{ maxHeight: '400px', overflow: 'auto' }}>
        {isLoading ? (
          <LinearProgress />
        ) : !todos || todos.length === 0 ? (
          <Alert severity="info">
            No TODOs found.
          </Alert>
        ) : (
          <Box>
            {todos.map((todo: any) => (
              <Box
                key={todo.id}
                sx={{
                  mb: 1,
                  p: 1.5,
                  borderRadius: 1,
                  backgroundColor: 'grey.50',
                  cursor: 'pointer',
                  '&:hover': { backgroundColor: 'grey.100' }
                }}
                onClick={() => redirect('edit', 'todos', todo.id)}
              >
                <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <Box sx={{ flex: 1, display: 'flex', alignItems: 'center', gap: 1 }}>
                    <TaskIcon fontSize="small" color="action" />
                    <Box>
                      <Typography variant="body2" fontWeight="medium">
                        {todo.title}
                      </Typography>
                      {todo.project_key && (
                        <Typography variant="caption" color="text.secondary">
                          {todo.project_key}
                        </Typography>
                      )}
                    </Box>
                  </Box>
                  <Chip
                    label={todo.status}
                    size="small"
                    color={todo.status === 'done' ? 'success' : todo.status === 'in_progress' ? 'warning' : 'default'}
                  />
                </Box>
              </Box>
            ))}
          </Box>
        )}
      </CardContent>
    </Card>
  );
};

const MyFeedbackSection = () => {
  const { data: feedback, isLoading } = useGetList('feedback', {
    pagination: { page: 1, perPage: 10 },
    sort: { field: 'submitted_at', order: 'DESC' },
  });
  const redirect = useRedirect();

  return (
    <Card>
      <CardHeader
        title="My Feedback"
        action={
          <MuiLink
            component="button"
            onClick={() => redirect('/feedback')}
            sx={{ cursor: 'pointer', textDecoration: 'underline', fontSize: '0.875rem' }}
          >
            View All Feedback
          </MuiLink>
        }
      />
      <CardContent sx={{ maxHeight: '400px', overflow: 'auto' }}>
        {isLoading ? (
          <LinearProgress />
        ) : !feedback || feedback.length === 0 ? (
          <Alert severity="info">
            No feedback found.
          </Alert>
        ) : (
          <Box>
            {feedback.map((item: any) => (
              <Box
                key={item.id}
                sx={{
                  mb: 1,
                  p: 1.5,
                  borderRadius: 1,
                  backgroundColor: 'grey.50',
                  cursor: 'pointer',
                  '&:hover': { backgroundColor: 'grey.100' }
                }}
                onClick={() => redirect('show', 'feedback', item.id)}
              >
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <FeedbackIcon fontSize="small" color="action" />
                  <Box sx={{ flex: 1 }}>
                    <Typography variant="body2" fontWeight="medium">
                      {item.content ? item.content.substring(0, 100) + (item.content.length > 100 ? '...' : '') : 'No content'}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {item.submitted_at ? new Date(item.submitted_at).toLocaleDateString() : 'Unknown date'}
                      {item.submitted_by && <> • {item.submitted_by}</>}
                    </Typography>
                  </Box>
                </Box>
              </Box>
            ))}
          </Box>
        )}
      </CardContent>
    </Card>
  );
};

const MyLearningsSection = () => {
  const { data: learnings, isLoading } = useGetList('learnings', {
    pagination: { page: 1, perPage: 10 },
    sort: { field: 'submitted_at', order: 'DESC' },
  });
  const redirect = useRedirect();

  return (
    <Card>
      <CardHeader
        title="My Learnings"
        action={
          <MuiLink
            component="button"
            onClick={() => redirect('/learnings')}
            sx={{ cursor: 'pointer', textDecoration: 'underline', fontSize: '0.875rem' }}
          >
            View All Learnings
          </MuiLink>
        }
      />
      <CardContent sx={{ maxHeight: '400px', overflow: 'auto' }}>
        {isLoading ? (
          <LinearProgress />
        ) : !learnings || learnings.length === 0 ? (
          <Alert severity="info">
            No learnings found.
          </Alert>
        ) : (
          <Box>
            {learnings.map((learning: any) => (
              <Box
                key={learning.id}
                sx={{
                  mb: 1,
                  p: 1.5,
                  borderRadius: 1,
                  backgroundColor: 'grey.50',
                  cursor: 'pointer',
                  '&:hover': { backgroundColor: 'grey.100' }
                }}
                onClick={() => redirect('show', 'learnings', learning.id)}
              >
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <LearningIcon fontSize="small" color="action" />
                  <Box sx={{ flex: 1 }}>
                    <Typography variant="body2" fontWeight="medium">
                      {learning.content ? learning.content.substring(0, 100) + (learning.content.length > 100 ? '...' : '') : 'No content'}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {learning.submitted_at ? new Date(learning.submitted_at).toLocaleDateString() : 'Unknown date'}
                      {learning.submitted_by && <> • {learning.submitted_by}</>}
                    </Typography>
                  </Box>
                </Box>
              </Box>
            ))}
          </Box>
        )}
      </CardContent>
    </Card>
  );
};

export const Dashboard = () => {
  return (
    <Box p={3}>
      <Typography variant="h4" gutterBottom fontWeight="bold">
        PM Command Center
      </Typography>
      <Typography variant="body1" color="text.secondary" gutterBottom sx={{ mb: 4 }}>
        Your autonomous project management dashboard
      </Typography>

      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
        {/* Row 1: My Projects + My Meetings */}
        <Box sx={{ display: 'flex', gap: 3, flexWrap: 'wrap' }}>
          <Box sx={{ flex: '1 1 400px' }}>
            <MyProjectsSection />
          </Box>
          <Box sx={{ flex: '1 1 400px' }}>
            <MyRecentMeetingsSection />
          </Box>
        </Box>

        {/* Row 2: My TODOs + My Feedback */}
        <Box sx={{ display: 'flex', gap: 3, flexWrap: 'wrap' }}>
          <Box sx={{ flex: '1 1 400px' }}>
            <MyTodosSection />
          </Box>
          <Box sx={{ flex: '1 1 400px' }}>
            <MyFeedbackSection />
          </Box>
        </Box>

        {/* Row 3: Team Learnings */}
        <Box>
          <MyLearningsSection />
        </Box>
      </Box>
    </Box>
  );
};