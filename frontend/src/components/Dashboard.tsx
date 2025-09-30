import React, { useEffect, useState } from 'react';
import {
  Card,
  CardContent,
  CardHeader,
  Typography,
  Box,
  Chip,
  LinearProgress,
} from '@mui/material';
import {
  MeetingRoom,
  Task,
  CheckCircle,
  TrendingUp,
  Business,
} from '@mui/icons-material';
import { useGetList } from 'react-admin';
import API_BASE_URL from '../config';

const StatCard = ({ title, value, icon, color = 'primary', subtitle }: any) => (
  <Card sx={{ height: '100%' }}>
    <CardContent>
      <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
        <Box
          sx={{
            p: 1,
            borderRadius: 2,
            backgroundColor: `${color}.light`,
            color: `${color}.contrastText`,
            mr: 2,
          }}
        >
          {icon}
        </Box>
        <Box>
          <Typography variant="h4" component="div" fontWeight="bold">
            {value}
          </Typography>
          <Typography color="text.secondary" variant="body2">
            {title}
          </Typography>
          {subtitle && (
            <Typography color="text.secondary" variant="caption">
              {subtitle}
            </Typography>
          )}
        </Box>
      </Box>
    </CardContent>
  </Card>
);

const RecentActivityCard = () => {
  const { data: meetings, isLoading: meetingsLoading } = useGetList('meetings', {
    pagination: { page: 1, perPage: 5 },
    sort: { field: 'date', order: 'DESC' },
  });

  const { data: todos, isLoading: todosLoading } = useGetList('todos', {
    pagination: { page: 1, perPage: 5 },
    sort: { field: 'created_at', order: 'DESC' },
  });

  return (
    <Card>
      <CardHeader title="Recent Activity" />
      <CardContent>
        {meetingsLoading || todosLoading ? (
          <LinearProgress />
        ) : (
          <Box>
            <Typography variant="subtitle2" gutterBottom>
              Recent Meetings
            </Typography>
            {meetings?.slice(0, 3).map((meeting: any) => (
              <Box key={meeting.id} sx={{ mb: 1, p: 1, borderRadius: 1, backgroundColor: 'grey.50' }}>
                <Typography variant="body2" fontWeight="medium">
                  {meeting.title}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  {new Date(meeting.date).toLocaleDateString()}
                </Typography>
              </Box>
            ))}

            <Typography variant="subtitle2" gutterBottom sx={{ mt: 2 }}>
              Recent TODOs
            </Typography>
            {todos?.slice(0, 3).map((todo: any) => (
              <Box key={todo.id} sx={{ mb: 1, p: 1, borderRadius: 1, backgroundColor: 'grey.50' }}>
                <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <Typography variant="body2" fontWeight="medium">
                    {todo.title}
                  </Typography>
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

export const Dashboard = () => {
  const [stats, setStats] = useState({
    total_meetings: 0,
    total_todos: 0,
    completed_todos: 0,
    active_todos: 0,
    total_projects: 0,
    todo_completion_rate: 0,
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const token = localStorage.getItem('auth_token');
        const response = await fetch(`${API_BASE_URL}/api/dashboard/stats`, {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });

        if (response.ok) {
          const data = await response.json();
          if (data.success) {
            setStats(data.data);
          }
        }
      } catch (error) {
        // Failed to fetch stats - will show zeros
      } finally {
        setLoading(false);
      }
    };

    fetchStats();
  }, []);

  const totalMeetings = stats.total_meetings;
  const totalTodos = stats.total_todos;
  const completedTodos = stats.completed_todos;
  const totalProjects = stats.total_projects;
  const todoCompletionRate = stats.todo_completion_rate;

  if (loading) {
    return (
      <Box p={3}>
        <Typography variant="h4" gutterBottom fontWeight="bold">
          🚀 PM Command Center
        </Typography>
        <LinearProgress sx={{ mt: 2 }} />
      </Box>
    );
  }

  return (
    <Box p={3}>
      <Typography variant="h4" gutterBottom fontWeight="bold">
        🚀 PM Command Center
      </Typography>
      <Typography variant="body1" color="text.secondary" gutterBottom sx={{ mb: 4 }}>
        Your autonomous project management dashboard
      </Typography>

      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
        {/* Stats Cards */}
        <Box sx={{ display: 'flex', gap: 3, flexWrap: 'wrap' }}>
          <Box sx={{ flex: '1 1 240px' }}>
            <StatCard
              title="Total Meetings"
              value={totalMeetings}
              icon={<MeetingRoom />}
              color="primary"
              subtitle="This week"
            />
          </Box>
          <Box sx={{ flex: '1 1 240px' }}>
            <StatCard
              title="Active TODOs"
              value={totalTodos - completedTodos}
              icon={<Task />}
              color="warning"
              subtitle={`${completedTodos} completed`}
            />
          </Box>
          <Box sx={{ flex: '1 1 240px' }}>
            <StatCard
              title="Completion Rate"
              value={`${todoCompletionRate}%`}
              icon={<CheckCircle />}
              color="success"
              subtitle={`${completedTodos}/${totalTodos} done`}
            />
          </Box>
          <Box sx={{ flex: '1 1 240px' }}>
            <StatCard
              title="Active Projects"
              value={totalProjects}
              icon={<Business />}
              color="secondary"
              subtitle="In Jira"
            />
          </Box>
        </Box>

        {/* Recent Activity and Quick Actions */}
        <Box sx={{ display: 'flex', gap: 3, flexWrap: 'wrap' }}>
          <Box sx={{ flex: '1 1 400px' }}>
            <RecentActivityCard />
          </Box>

          <Box sx={{ flex: '1 1 400px' }}>
            <Card>
              <CardHeader title="Quick Actions" />
              <CardContent>
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                  <Box
                    sx={{
                      p: 2,
                      borderRadius: 2,
                      backgroundColor: 'primary.light',
                      color: 'primary.contrastText',
                      cursor: 'pointer',
                      transition: 'transform 0.2s',
                      '&:hover': { transform: 'translateY(-2px)' },
                    }}
                  >
                    <Typography variant="h6">📋 Analyze Meeting</Typography>
                    <Typography variant="body2">
                      Process new meeting transcripts and extract action items
                    </Typography>
                  </Box>
                  <Box
                    sx={{
                      p: 2,
                      borderRadius: 2,
                      backgroundColor: 'secondary.light',
                      color: 'secondary.contrastText',
                      cursor: 'pointer',
                      transition: 'transform 0.2s',
                      '&:hover': { transform: 'translateY(-2px)' },
                    }}
                  >
                    <Typography variant="h6">🎫 Create Jira Tickets</Typography>
                    <Typography variant="body2">
                      Convert action items into Jira tickets
                    </Typography>
                  </Box>
                  <Box
                    sx={{
                      p: 2,
                      borderRadius: 2,
                      backgroundColor: 'warning.light',
                      color: 'warning.contrastText',
                      cursor: 'pointer',
                      transition: 'transform 0.2s',
                      '&:hover': { transform: 'translateY(-2px)' },
                    }}
                  >
                    <Typography variant="h6">📝 Manage TODOs</Typography>
                    <Typography variant="body2">
                      View and update your TODO list
                    </Typography>
                  </Box>
                </Box>
              </CardContent>
            </Card>
          </Box>
        </Box>
      </Box>
    </Box>
  );
};