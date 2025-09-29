import React from 'react';
import {
    Edit,
    SimpleForm,
    TextInput,
    SelectInput,
    required,
    EditProps,
    DateField,
    TextField,
} from 'react-admin';
import { Card, CardContent, Box, Typography } from '@mui/material';
import LightbulbIcon from '@mui/icons-material/Lightbulb';

const categoryChoices = [
    { id: 'technical', name: 'Technical' },
    { id: 'process', name: 'Process' },
    { id: 'team', name: 'Team' },
    { id: 'client', name: 'Client Communication' },
    { id: 'retrospective', name: 'Retrospective' },
    { id: 'best_practice', name: 'Best Practice' },
    { id: 'pitfall', name: 'Pitfall to Avoid' },
];

export const LearningEdit = (props: EditProps) => (
    <Edit {...props} title="Edit Learning">
        <SimpleForm>
            <Card sx={{ width: '100%' }}>
                <CardContent>
                    <Box display="flex" alignItems="center" gap={2} mb={3}>
                        <LightbulbIcon color="primary" fontSize="large" />
                        <Typography variant="h6">
                            Edit Learning
                        </Typography>
                    </Box>

                    <TextInput
                        source="content"
                        label="Learning"
                        validate={[required()]}
                        fullWidth
                        multiline
                        rows={4}
                    />

                    <SelectInput
                        source="category"
                        label="Category"
                        choices={categoryChoices}
                        fullWidth
                    />

                    <Box mt={3} p={2} bgcolor="grey.50" borderRadius={1}>
                        <Typography variant="subtitle2" gutterBottom>
                            Metadata
                        </Typography>
                        <Box display="flex" gap={4}>
                            <Box>
                                <Typography variant="caption" color="text.secondary">
                                    Submitted by
                                </Typography>
                                <TextField source="submitted_by" />
                            </Box>
                            <Box>
                                <Typography variant="caption" color="text.secondary">
                                    Created
                                </Typography>
                                <DateField source="created_at" showTime />
                            </Box>
                            <Box>
                                <Typography variant="caption" color="text.secondary">
                                    Source
                                </Typography>
                                <TextField source="source" />
                            </Box>
                        </Box>
                    </Box>
                </CardContent>
            </Card>
        </SimpleForm>
    </Edit>
);