import React from 'react';
import {
    Create,
    SimpleForm,
    TextInput,
    SelectInput,
    required,
    CreateProps,
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

export const LearningCreate = (props: CreateProps) => (
    <Create {...props} title="Add New Learning">
        <SimpleForm>
            <Card sx={{ width: '100%' }}>
                <CardContent>
                    <Box display="flex" alignItems="center" gap={2} mb={3}>
                        <LightbulbIcon color="primary" fontSize="large" />
                        <Typography variant="h6">
                            Share a Learning or Insight
                        </Typography>
                    </Box>

                    <TextInput
                        source="content"
                        label="Learning"
                        validate={[required()]}
                        fullWidth
                        multiline
                        rows={4}
                        helperText="Share an insight, best practice, or lesson learned that could help the team"
                    />

                    <SelectInput
                        source="category"
                        label="Category (Optional)"
                        choices={categoryChoices}
                        fullWidth
                        helperText="Categorize this learning to make it easier to find later"
                    />

                    <Box mt={2}>
                        <Typography variant="caption" color="text.secondary">
                            💡 Tips for good learnings:
                        </Typography>
                        <ul style={{ margin: '8px 0', paddingLeft: '20px' }}>
                            <li>
                                <Typography variant="caption" color="text.secondary">
                                    Be specific and actionable
                                </Typography>
                            </li>
                            <li>
                                <Typography variant="caption" color="text.secondary">
                                    Include context if relevant (project, situation)
                                </Typography>
                            </li>
                            <li>
                                <Typography variant="caption" color="text.secondary">
                                    Focus on what the team can apply in the future
                                </Typography>
                            </li>
                        </ul>
                    </Box>
                </CardContent>
            </Card>
        </SimpleForm>
    </Create>
);