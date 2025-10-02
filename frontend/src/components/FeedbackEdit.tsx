import React from 'react';
import {
    Edit,
    SimpleForm,
    TextInput,
    SelectInput,
    DateField,
    required,
    EditProps,
} from 'react-admin';
import { Card, CardContent, Box, Typography } from '@mui/material';
import FeedbackIcon from '@mui/icons-material/Feedback';

const statusChoices = [
    { id: 'draft', name: 'Draft' },
    { id: 'given', name: 'Given' },
];

export const FeedbackEdit = (props: EditProps) => (
    <Edit {...props} title="Edit Feedback">
        <SimpleForm>
            <Card sx={{ width: '100%' }}>
                <CardContent>
                    <Box display="flex" alignItems="center" gap={2} mb={3}>
                        <FeedbackIcon color="primary" fontSize="large" />
                        <Typography variant="h6">
                            Edit Feedback
                        </Typography>
                    </Box>

                    <Box mb={2}>
                        <Typography variant="caption" color="text.secondary">
                            Created: <DateField source="created_at" showTime />
                        </Typography>
                    </Box>

                    <TextInput
                        source="recipient"
                        label="Recipient (Optional)"
                        fullWidth
                        helperText="Who is this feedback for?"
                    />

                    <TextInput
                        source="content"
                        label="Feedback"
                        validate={[required()]}
                        fullWidth
                        multiline
                        rows={5}
                    />

                    <SelectInput
                        source="status"
                        label="Status"
                        choices={statusChoices}
                        fullWidth
                        helperText="Mark as 'Given' once you've shared this feedback"
                    />
                </CardContent>
            </Card>
        </SimpleForm>
    </Edit>
);
