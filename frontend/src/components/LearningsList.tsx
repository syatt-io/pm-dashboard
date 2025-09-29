import React, { useEffect, useState } from 'react';
import {
    List,
    Datagrid,
    TextField,
    DateField,
    EditButton,
    DeleteButton,
    TopToolbar,
    FilterButton,
    CreateButton,
    useRefresh,
    useNotify,
    TextInput,
    SelectInput,
    Button,
    ListProps,
    SimpleList,
    useRecordContext,
} from 'react-admin';
import { Card, CardContent, Typography, Chip, Box } from '@mui/material';
import LightbulbIcon from '@mui/icons-material/Lightbulb';
import { useMediaQuery, useTheme } from '@mui/material';

const learningFilters = [
    <TextInput label="Search" source="q" alwaysOn />,
    <SelectInput
        label="Category"
        source="category"
        choices={[
            { id: 'technical', name: 'Technical' },
            { id: 'process', name: 'Process' },
            { id: 'team', name: 'Team' },
            { id: 'client', name: 'Client' },
        ]}
    />,
];

const LearningListActions = () => (
    <TopToolbar>
        <FilterButton />
        <CreateButton />
    </TopToolbar>
);

const LearningCard = () => {
    const record = useRecordContext();
    if (!record) return null;

    return (
        <Box sx={{ marginBottom: 2 }}>
            <Card>
                <CardContent>
                    <Box display="flex" alignItems="flex-start" gap={2}>
                        <LightbulbIcon color="primary" />
                        <Box flex={1}>
                            <Typography variant="body1" component="div" sx={{ fontWeight: 500 }}>
                                {record.content}
                            </Typography>
                            <Box display="flex" gap={1} mt={1} alignItems="center">
                                {record.category && (
                                    <Chip
                                        label={record.category}
                                        size="small"
                                        color="primary"
                                        variant="outlined"
                                    />
                                )}
                                <Typography variant="caption" color="text.secondary">
                                    by {record.submitted_by} • {new Date(record.created_at).toLocaleDateString()}
                                </Typography>
                            </Box>
                        </Box>
                        <Box>
                            <EditButton />
                            <DeleteButton />
                        </Box>
                    </Box>
                </CardContent>
            </Card>
        </Box>
    );
};

export const LearningsList = (props: ListProps) => {
    const theme = useTheme();
    const isSmall = useMediaQuery(theme.breakpoints.down('sm'));
    const [stats, setStats] = useState<any>(null);
    const notify = useNotify();
    const refresh = useRefresh();

    useEffect(() => {
        fetchStats();
    }, []);

    const fetchStats = async () => {
        try {
            const token = localStorage.getItem('token');
            const response = await fetch('http://localhost:4000/api/learnings/stats', {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });
            const data = await response.json();
            if (data.success) {
                setStats(data.stats);
            }
        } catch (error) {
            console.error('Error fetching stats:', error);
        }
    };

    return (
        <>
            {stats && (
                <Box sx={{ marginBottom: 2 }}>
                    <Card>
                        <CardContent>
                            <Typography variant="h6" gutterBottom>
                                📊 Learning Statistics
                            </Typography>
                            <Box display="flex" gap={4} flexWrap="wrap">
                                <Box>
                                    <Typography variant="caption" color="text.secondary">
                                        Total Learnings
                                    </Typography>
                                    <Typography variant="h4">{stats.total}</Typography>
                                </Box>
                                <Box>
                                    <Typography variant="caption" color="text.secondary">
                                        Today
                                    </Typography>
                                    <Typography variant="h4">{stats.today}</Typography>
                                </Box>
                                <Box>
                                    <Typography variant="caption" color="text.secondary">
                                        This Week
                                    </Typography>
                                    <Typography variant="h4">{stats.this_week}</Typography>
                                </Box>
                                <Box>
                                    <Typography variant="caption" color="text.secondary">
                                        Categories
                                    </Typography>
                                    <Typography variant="h4">{stats.categories_count}</Typography>
                                </Box>
                            </Box>
                        </CardContent>
                    </Card>
                </Box>
            )}

            <List
                {...props}
                filters={learningFilters}
                actions={<LearningListActions />}
                title="Team Learnings"
            >
                {isSmall ? (
                    <SimpleList
                        primaryText={record => record.content}
                        secondaryText={record => `${record.submitted_by} • ${record.category || 'Uncategorized'}`}
                        tertiaryText={record => new Date(record.created_at).toLocaleDateString()}
                        leftIcon={() => <LightbulbIcon />}
                    />
                ) : (
                    <Datagrid bulkActionButtons={false}>
                        <LearningCard />
                    </Datagrid>
                )}
            </List>
        </>
    );
};