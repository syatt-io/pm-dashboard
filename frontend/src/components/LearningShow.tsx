import React from 'react';
import {
    Show,
    SimpleShowLayout,
    TextField,
    DateField,
    ShowProps,
} from 'react-admin';
import { Card, CardContent, Box, Typography } from '@mui/material';
import LightbulbIcon from '@mui/icons-material/Lightbulb';

export const LearningShow = (props: ShowProps) => (
    <Show {...props} title="View Learning">
        <SimpleShowLayout>
            <Card sx={{ width: '100%' }}>
                <CardContent>
                    <Box display="flex" alignItems="flex-start" gap={2} mb={3}>
                        <LightbulbIcon color="primary" fontSize="large" />
                        <Box flex={1}>
                            <Typography variant="h5" component="div" gutterBottom>
                                <TextField source="content" />
                            </Typography>

                            <Box display="flex" gap={2} mt={2}>
                                <TextField source="category" emptyText="No category" />
                            </Box>
                        </Box>
                    </Box>

                    <Box mt={4} p={2} bgcolor="grey.50" borderRadius={1}>
                        <Typography variant="subtitle2" gutterBottom color="text.secondary">
                            Details
                        </Typography>
                        <Box display="grid" gridTemplateColumns="1fr 1fr" gap={3}>
                            <Box>
                                <Typography variant="caption" color="text.secondary">
                                    Submitted by
                                </Typography>
                                <Typography variant="body1">
                                    <TextField source="submitted_by" />
                                </Typography>
                            </Box>
                            <Box>
                                <Typography variant="caption" color="text.secondary">
                                    Created
                                </Typography>
                                <Typography variant="body1">
                                    <DateField source="created_at" showTime />
                                </Typography>
                            </Box>
                            <Box>
                                <Typography variant="caption" color="text.secondary">
                                    Source
                                </Typography>
                                <Typography variant="body1">
                                    <TextField source="source" />
                                </Typography>
                            </Box>
                            <Box>
                                <Typography variant="caption" color="text.secondary">
                                    Last Updated
                                </Typography>
                                <Typography variant="body1">
                                    <DateField source="updated_at" showTime />
                                </Typography>
                            </Box>
                        </Box>

                        <Box mt={2}>
                            <Typography variant="caption" color="text.secondary">
                                Learning ID
                            </Typography>
                            <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                                <TextField source="id" />
                            </Typography>
                        </Box>
                    </Box>
                </CardContent>
            </Card>
        </SimpleShowLayout>
    </Show>
);