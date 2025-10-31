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
  const [pendingValue, setPendingValue] = useState<boolean | null>(null);

  const handleChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const newValue = event.target.checked;

    if (newValue === value) {
      return;
    }

    // Store the pending value and set loading state
    setPendingValue(newValue);
    setIsLoading(true);

    try {
      await onSave(newValue);
      setPendingValue(null);
    } catch (error) {
      console.error('Failed to save:', error);
      // Reset to original value on error
      setPendingValue(null);
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
              checked={pendingValue !== null ? pendingValue : value}
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
