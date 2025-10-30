import React, { useState } from 'react';
import {
  Box,
  Switch,
  Typography,
  CircularProgress,
  FormControlLabel,
} from '@mui/material';

interface InlineToggleFieldProps {
  value: boolean;
  label: string;
  onSave: (newValue: boolean) => Promise<void>;
  helperText?: string;
  variant?: 'body1' | 'body2' | 'h6' | 'subtitle1';
}

export const InlineToggleField: React.FC<InlineToggleFieldProps> = ({
  value,
  label,
  onSave,
  helperText,
  variant = 'body1',
}) => {
  const [isLoading, setIsLoading] = useState(false);

  const handleChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const newValue = event.target.checked;

    if (newValue === value) {
      return;
    }

    setIsLoading(true);
    try {
      await onSave(newValue);
    } catch (error) {
      console.error('Failed to save:', error);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <FormControlLabel
          control={
            <Switch
              checked={value}
              onChange={handleChange}
              disabled={isLoading}
              color="primary"
            />
          }
          label={
            <Typography variant={variant}>
              {label}
            </Typography>
          }
        />
        {isLoading && <CircularProgress size={20} />}
      </Box>
      {helperText && (
        <Typography
          variant="caption"
          color="text.secondary"
          sx={{ pl: 4.5 }}
        >
          {helperText}
        </Typography>
      )}
    </Box>
  );
};
