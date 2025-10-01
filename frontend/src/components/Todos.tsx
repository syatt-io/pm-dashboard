// @ts-nocheck
import React, { useState } from 'react';
import {
  TextField,
  DateField,
  Show,
  SimpleShowLayout,
  Edit,
  Create,
  SimpleForm,
  TextInput,
  SelectInput,
  DateInput,
  useRecordContext,
  FunctionField,
  Button,
  useUpdate,
  useRedirect,
  useGetList,
  useDelete,
  Loading,
  Title,
  RecordContextProvider,
} from 'react-admin';
import {
  Card,
  CardContent,
  Typography,
  Box,
  Chip,
  IconButton,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Badge,
} from '@mui/material';
import {
  ExpandMore,
} from '@mui/icons-material';
import {
  CheckCircle,
  PlayArrow,
  Circle,
  ArrowBack,
  Edit as EditIcon,
  Delete as DeleteIcon,
} from '@mui/icons-material';

const ProjectSelectInput = (props: any) => {
  const { data: projects, isLoading, error } = useGetList('projects', {
    pagination: { page: 1, perPage: 1000 },
    sort: { field: 'key', order: 'ASC' },
  });

  const { data: todos } = useGetList('todos', {
    pagination: { page: 1, perPage: 1000 },
  });

  if (isLoading) {
    return <SelectInput {...props} choices={[]} disabled />;
  }

  if (error) {
    // Return a basic dropdown with just the existing project keys from todos
    const existingProjectKeys = [...new Set(todos?.map((todo: any) => todo.project_key).filter(Boolean))] || [];
    const fallbackChoices = existingProjectKeys.map(key => ({
      id: key,
      name: `${key} - (Unavailable)`,
    }));
    return <SelectInput {...props} choices={fallbackChoices} />;
  }

  // Get existing project keys from todos to include orphaned projects like "PM"
  const existingProjectKeys = [...new Set(todos?.map((todo: any) => todo.project_key).filter(Boolean))] || [];

  const choices = [];

  // Add choices from projects API - only include active projects
  if (projects) {
    const activeProjects = projects.filter((project: any) => project.is_active === true);
    choices.push(...activeProjects.map((project: any) => ({
      id: project.key,
      name: `${project.key} - ${project.name}`,
    })));
  }

  // Add any orphaned project keys that aren't in the active projects list
  const activeProjects = projects?.filter((project: any) => project.is_active === true) || [];
  const activeProjectKeysSet = new Set(activeProjects.map((p: any) => p.key));
  existingProjectKeys.forEach(key => {
    if (!activeProjectKeysSet.has(key)) {
      choices.push({
        id: key,
        name: `${key} - (Legacy Project)`,
      });
    }
  });

  // Sort choices alphabetically
  choices.sort((a, b) => a.id.localeCompare(b.id));

  return <SelectInput {...props} choices={choices} />;
};

const StatusChip = () => {
  const record = useRecordContext();
  if (!record) return null;

  const statusConfig = {
    pending: { color: 'default' as const, icon: <Circle />, label: 'Pending' },
    in_progress: { color: 'warning' as const, icon: <PlayArrow />, label: 'In Progress' },
    done: { color: 'success' as const, icon: <CheckCircle />, label: 'Done' },
  };

  const config = statusConfig[record.status as keyof typeof statusConfig] || statusConfig.pending;

  return (
    <Chip
      icon={config.icon}
      label={config.label}
      color={config.color}
      size="small"
      variant="outlined"
    />
  );
};

const BackButton = () => {
  const redirect = useRedirect();

  const handleBack = () => {
    redirect('/todos');
  };

  return (
    <Button
      onClick={handleBack}
      variant="outlined"
      startIcon={<ArrowBack />}
      sx={{ mr: 2 }}
    >
      Back to TODOs
    </Button>
  );
};

const MarkAsDoneButton = () => {
  const record = useRecordContext();
  const [update] = useUpdate();
  const notify = useNotify();
  const refresh = useRefresh();

  if (!record || record.status === 'done') return null;

  const handleMarkAsDone = () => {
    update(
      'todos',
      {
        id: record.id,
        data: { ...record, status: 'done' },
        previousData: record,
      },
      {
        onSuccess: () => {
          notify('TODO marked as done', { type: 'success' });
          refresh();
        },
        onError: () => {
          notify('Error updating TODO status', { type: 'error' });
        },
      }
    );
  };

  return (
    <Button
      onClick={handleMarkAsDone}
      variant="contained"
      color="success"
      startIcon={<CheckCircle />}
      sx={{ mr: 2 }}
    >
      Mark as Done
    </Button>
  );
};

const ChangeDueDateButton = () => {
  const record = useRecordContext();
  const [update] = useUpdate();
  const notify = useNotify();
  const refresh = useRefresh();
  const redirect = useRedirect();

  if (!record) return null;

  const handleEdit = () => {
    // Navigate to edit form
    redirect(`/todos/${record.id}`);
  };

  return (
    <Button
      onClick={handleEdit}
      variant="outlined"
      startIcon={<EditIcon />}
      sx={{ mr: 2 }}
    >
      Edit TODO
    </Button>
  );
};

const DeleteButton = () => {
  const record = useRecordContext();
  const [deleteOne] = useDelete();
  const notify = useNotify();
  const redirect = useRedirect();

  if (!record) return null;

  const handleDelete = () => {
    if (window.confirm('Are you sure you want to delete this TODO?')) {
      deleteOne(
        'todos',
        { id: record.id, previousData: record },
        {
          onSuccess: () => {
            notify('TODO deleted successfully', { type: 'success' });
            redirect('/todos');
          },
          onError: () => {
            notify('Error deleting TODO', { type: 'error' });
          },
        }
      );
    }
  };

  return (
    <Button
      onClick={handleDelete}
      variant="outlined"
      color="error"
      startIcon={<DeleteIcon />}
      sx={{ mr: 2 }}
    >
      Delete
    </Button>
  );
};

const PriorityChip = () => {
  const record = useRecordContext();
  if (!record) return null;

  const priorityConfig = {
    High: { color: 'error' as const },
    high: { color: 'error' as const },
    Medium: { color: 'warning' as const },
    medium: { color: 'warning' as const },
    Low: { color: 'info' as const },
    low: { color: 'info' as const },
  };

  const config = priorityConfig[record.priority as keyof typeof priorityConfig] || priorityConfig.Medium;

  return (
    <Chip
      label={record.priority || 'Medium'}
      color={config.color}
      size="small"
      variant="filled"
    />
  );
};

const TodoRowContent = ({ todo, onClick }: { todo: any; onClick: (todo: any) => void }) => (
  <Box
    sx={{
      display: 'flex',
      alignItems: 'center',
      p: 2,
      border: '1px solid #e0e0e0',
      borderRadius: 1,
      cursor: 'pointer',
      '&:hover': {
        backgroundColor: '#f5f5f5',
      },
      mb: 1,
    }}
    onClick={() => onClick(todo)}
  >
    <Box sx={{ flex: '2 1 0', minWidth: 0 }}>
      <Typography variant="body1" fontWeight="medium" noWrap>
        {todo.title}
      </Typography>
    </Box>
    <Box sx={{ flex: '1 1 0', display: 'flex', justifyContent: 'center' }}>
      <StatusChip />
    </Box>
    <Box sx={{ flex: '1 1 0', display: 'flex', justifyContent: 'center' }}>
      <PriorityChip />
    </Box>
    <Box sx={{ flex: '1 1 0', textAlign: 'center' }}>
      <Typography variant="body2" color="text.secondary">
        {todo.created_at ? new Date(todo.created_at).toLocaleDateString() : '-'}
      </Typography>
    </Box>
    <Box sx={{ flex: '1 1 0', textAlign: 'center' }}>
      <Typography variant="body2" color="text.secondary">
        {todo.due_date ? new Date(todo.due_date).toLocaleDateString() : '-'}
      </Typography>
    </Box>
  </Box>
);

// Wrapper to provide record context for StatusChip and PriorityChip
const TodoRow = ({ todo, onClick }: { todo: any; onClick: (todo: any) => void }) => {
  return (
    <RecordContextProvider value={todo}>
      <TodoRowContent todo={todo} onClick={onClick} />
    </RecordContextProvider>
  );
};

export const TodoList = () => {
  const { data: todos, isLoading, error } = useGetList('todos', {
    sort: { field: 'created_at', order: 'DESC' },
    pagination: { page: 1, perPage: 1000 },
  });

  const redirect = useRedirect();
  const [showCompleted, setShowCompleted] = useState(false);

  const handleTodoClick = (todo: any) => {
    redirect(`/todos/${todo.id}/show`);
  };

  if (isLoading) return <Loading />;
  if (error) return (
    <Box sx={{ p: 2 }}>
      <Typography color="error">
        Error loading TODOs: {error.message || 'Unknown error'}
      </Typography>
    </Box>
  );

  // Filter todos based on completed status
  const filteredTodos = todos?.filter((todo: any) =>
    showCompleted || todo.status !== 'done'
  );

  // Group todos by project
  const groupedTodos = filteredTodos?.reduce((groups: any, todo: any) => {
    const project = todo.project_key || 'No Project';
    if (!groups[project]) {
      groups[project] = [];
    }
    groups[project].push(todo);
    return groups;
  }, {});

  const projectKeys = Object.keys(groupedTodos || {}).sort();

  return (
    <Box sx={{ p: 2 }}>
      <Title title="📝 TODO Management" />
      <Typography variant="h4" gutterBottom>
        📝 TODO Management
      </Typography>

      {/* Filter Controls */}
      <Box sx={{ mb: 2, display: 'flex', alignItems: 'center', gap: 2 }}>
        <Button
          variant={showCompleted ? 'contained' : 'outlined'}
          onClick={() => setShowCompleted(!showCompleted)}
          size="small"
        >
          {showCompleted ? 'Hide Completed' : 'Show Completed'}
        </Button>
      </Box>

      {/* Header Row */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          p: 2,
          backgroundColor: '#f5f5f5',
          border: '1px solid #e0e0e0',
          borderRadius: 1,
          mb: 2,
          fontWeight: 'bold',
        }}
      >
        <Box sx={{ flex: '2 1 0', minWidth: 0 }}>
          <Typography variant="body2" fontWeight="bold">
            Title
          </Typography>
        </Box>
        <Box sx={{ flex: '1 1 0', textAlign: 'center' }}>
          <Typography variant="body2" fontWeight="bold">
            Status
          </Typography>
        </Box>
        <Box sx={{ flex: '1 1 0', textAlign: 'center' }}>
          <Typography variant="body2" fontWeight="bold">
            Priority
          </Typography>
        </Box>
        <Box sx={{ flex: '1 1 0', textAlign: 'center' }}>
          <Typography variant="body2" fontWeight="bold">
            Created
          </Typography>
        </Box>
        <Box sx={{ flex: '1 1 0', textAlign: 'center' }}>
          <Typography variant="body2" fontWeight="bold">
            Due Date
          </Typography>
        </Box>
      </Box>

      {projectKeys.map((projectKey) => {
        const projectTodos = groupedTodos[projectKey];
        return (
          <Accordion key={projectKey} defaultExpanded={true} sx={{ mb: 2 }}>
            <AccordionSummary expandIcon={<ExpandMore />}>
              <Typography variant="h6" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                {projectKey}
                <Badge badgeContent={projectTodos.length} color="primary" />
              </Typography>
            </AccordionSummary>
            <AccordionDetails sx={{ p: 0 }}>
              <Box sx={{ p: 2 }}>
                {projectTodos.map((todo: any) => (
                  <TodoRow key={todo.id} todo={todo} onClick={handleTodoClick} />
                ))}
              </Box>
            </AccordionDetails>
          </Accordion>
        );
      })}
    </Box>
  );
};

const TodoShowTitle = () => {
  const record = useRecordContext();
  return record?.title || 'TODO Details';
};

export const TodoShow = () => {
  return (
    <Show title={<TodoShowTitle />}>
      <SimpleShowLayout>
        <Card>
          <CardContent>
            <Typography variant="h5" gutterBottom sx={{ mb: 3, fontWeight: 600 }}>
              <TodoShowTitle />
            </Typography>

            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              <Box>
                <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                  Description
                </Typography>
                <TextField source="description" label="" sx={{ '& .MuiInputBase-root': { backgroundColor: 'transparent' } }} />
              </Box>

              <Box sx={{ display: 'flex', gap: 3, flexWrap: 'wrap' }}>
                <Box>
                  <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                    Status
                  </Typography>
                  <FunctionField
                    label=""
                    render={(record: any) => <StatusChip />}
                  />
                </Box>

                <Box>
                  <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                    Priority
                  </Typography>
                  <FunctionField
                    label=""
                    render={(record: any) => <PriorityChip />}
                  />
                </Box>

                <Box>
                  <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                    Project
                  </Typography>
                  <TextField source="project_key" label="" sx={{ '& .MuiInputBase-root': { backgroundColor: 'transparent' } }} />
                </Box>
              </Box>

              <Box sx={{ display: 'flex', gap: 3, flexWrap: 'wrap', mt: 2 }}>
                <Box>
                  <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                    Created At
                  </Typography>
                  <DateField
                    source="created_at"
                    label=""
                    options={{
                      year: 'numeric',
                      month: 'long',
                      day: 'numeric',
                      hour: '2-digit',
                      minute: '2-digit',
                    }}
                  />
                </Box>

                <Box>
                  <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                    Last Updated
                  </Typography>
                  <DateField
                    source="updated_at"
                    label=""
                    options={{
                      year: 'numeric',
                      month: 'long',
                      day: 'numeric',
                      hour: '2-digit',
                      minute: '2-digit',
                    }}
                  />
                </Box>

                <Box>
                  <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                    Due Date
                  </Typography>
                  <DateField
                    source="due_date"
                    label=""
                    options={{
                      year: 'numeric',
                      month: 'long',
                      day: 'numeric',
                    }}
                  />
                </Box>
              </Box>
            </Box>
          </CardContent>
        </Card>

        <Card sx={{ mt: 3 }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Actions
            </Typography>
            <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', alignItems: 'center' }}>
              <BackButton />
              <MarkAsDoneButton />
              <ChangeDueDateButton />
              <DeleteButton />
            </Box>
          </CardContent>
        </Card>
      </SimpleShowLayout>
    </Show>
  );
};

export const TodoEdit = () => (
  <Edit title="✏️ Edit TODO">
    <SimpleForm>
      <TextInput source="title" label="Title" fullWidth required />
      <TextInput
        source="description"
        label="Description"
        multiline
        rows={4}
        fullWidth
      />
      <SelectInput
        source="status"
        label="Status"
        choices={[
          { id: 'pending', name: 'Pending' },
          { id: 'in_progress', name: 'In Progress' },
          { id: 'done', name: 'Done' },
        ]}
      />
      <SelectInput
        source="priority"
        label="Priority"
        choices={[
          { id: 'Low', name: 'Low' },
          { id: 'low', name: 'Low' },
          { id: 'Medium', name: 'Medium' },
          { id: 'medium', name: 'Medium' },
          { id: 'High', name: 'High' },
          { id: 'high', name: 'High' },
        ]}
      />
      <DateInput source="due_date" label="Due Date" />
      <ProjectSelectInput source="project_key" label="Project" />
    </SimpleForm>
  </Edit>
);

export const TodoCreate = () => (
  <Create title="➕ Create TODO">
    <SimpleForm>
      <TextInput source="title" label="Title" fullWidth required />
      <TextInput
        source="description"
        label="Description"
        multiline
        rows={4}
        fullWidth
      />
      <SelectInput
        source="status"
        label="Status"
        choices={[
          { id: 'pending', name: 'Pending' },
          { id: 'in_progress', name: 'In Progress' },
          { id: 'done', name: 'Done' },
        ]}
        defaultValue="pending"
      />
      <SelectInput
        source="priority"
        label="Priority"
        choices={[
          { id: 'Low', name: 'Low' },
          { id: 'low', name: 'Low' },
          { id: 'Medium', name: 'Medium' },
          { id: 'medium', name: 'Medium' },
          { id: 'High', name: 'High' },
          { id: 'high', name: 'High' },
        ]}
        defaultValue="Medium"
      />
      <DateInput source="due_date" label="Due Date" />
      <ProjectSelectInput source="project_key" label="Project" />
    </SimpleForm>
  </Create>
);