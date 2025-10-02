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
import FeedbackIcon from '@mui/icons-material/Feedback';

const statusChoices = [
    { id: 'draft', name: 'Draft' },
    { id: 'given', name: 'Given' },
];

export const FeedbackCreate = (props: CreateProps) => (
    <Create {...props} title="Add New Feedback">
        <SimpleForm>
            <Card sx={{ width: '100%' }}>
                <CardContent>
                    <Box display="flex" alignItems="center" gap={2} mb={3}>
                        <FeedbackIcon color="primary" fontSize="large" />
                        <Typography variant="h6">
                            Save Feedback for Later
                        </Typography>
                    </Box>

                    <TextInput
                        source="recipient"
                        label="Recipient (Optional)"
                        fullWidth
                        helperText="Who is this feedback for? Leave empty if not specific to someone"
                    />

                    <TextInput
                        source="content"
                        label="Feedback"
                        validate={[required()]}
                        fullWidth
                        multiline
                        rows={5}
                        helperText="What feedback do you want to give? Be specific and constructive"
                    />

                    <SelectInput
                        source="status"
                        label="Status"
                        choices={statusChoices}
                        defaultValue="draft"
                        fullWidth
                        helperText="Mark as 'Given' once you've shared this feedback"
                    />

                    <Box mt={2} p={2} bgcolor="info.light" borderRadius={1}>
                        <Typography variant="caption" color="text.secondary">
                            🔒 Your feedback is private. Only you can see it. Use this to prepare feedback before 1-on-1s or performance reviews.
                        </Typography>
                    </Box>
                </CardContent>
            </Card>
        </SimpleForm>
    </Create>
);
