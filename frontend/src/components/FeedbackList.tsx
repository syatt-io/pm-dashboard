import React from 'react';
import {
    List,
    Datagrid,
    EditButton,
    DeleteButton,
    TopToolbar,
    FilterButton,
    CreateButton,
    TextInput,
    SelectInput,
    ListProps,
    SimpleList,
    useRecordContext,
} from 'react-admin';
import { Card, CardContent, Typography, Chip, Box } from '@mui/material';
import FeedbackIcon from '@mui/icons-material/Feedback';
import { useMediaQuery, useTheme } from '@mui/material';

const feedbackFilters = [
    <TextInput label="Search" source="q" alwaysOn />,
    <SelectInput
        label="Status"
        source="status"
        choices={[
            { id: 'draft', name: 'Draft' },
            { id: 'given', name: 'Given' },
        ]}
    />,
    <TextInput label="Recipient" source="recipient" />,
];

const FeedbackListActions = () => (
    <TopToolbar>
        <FilterButton />
        <CreateButton />
    </TopToolbar>
);

const FeedbackCard = () => {
    const record = useRecordContext();
    if (!record) return null;

    const statusColor = record.status === 'given' ? 'success' : 'default';

    return (
        <Box sx={{ marginBottom: 2 }}>
            <Card>
                <CardContent>
                    <Box display="flex" alignItems="flex-start" gap={2}>
                        <FeedbackIcon color="primary" />
                        <Box flex={1}>
                            <Box display="flex" gap={1} alignItems="center" mb={1}>
                                <Chip
                                    label={record.status}
                                    size="small"
                                    color={statusColor}
                                />
                                {record.recipient && (
                                    <Typography variant="body2" color="text.secondary">
                                        For: <strong>{record.recipient}</strong>
                                    </Typography>
                                )}
                            </Box>
                            <Typography variant="body1" component="div">
                                {record.content}
                            </Typography>
                            <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
                                Created: {new Date(record.created_at).toLocaleDateString()}
                            </Typography>
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

export const FeedbackList = (props: ListProps) => {
    const theme = useTheme();
    const isSmall = useMediaQuery(theme.breakpoints.down('sm'));

    return (
        <List
            {...props}
            filters={feedbackFilters}
            actions={<FeedbackListActions />}
            title="My Feedback"
        >
            {isSmall ? (
                <SimpleList
                    primaryText={record => record.content}
                    secondaryText={record => record.recipient ? `For: ${record.recipient}` : 'No recipient'}
                    tertiaryText={record => `${record.status} • ${new Date(record.created_at).toLocaleDateString()}`}
                    leftIcon={() => <FeedbackIcon />}
                />
            ) : (
                <Datagrid bulkActionButtons={false}>
                    <FeedbackCard />
                </Datagrid>
            )}
        </List>
    );
};
