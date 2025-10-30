import React, { useState, useEffect, useRef } from 'react';
import {
  Box,
  TextField,
  Typography,
  CircularProgress,
  IconButton,
} from '@mui/material';
import EditIcon from '@mui/icons-material/Edit';
import CheckIcon from '@mui/icons-material/Check';
import CloseIcon from '@mui/icons-material/Close';

interface InlineNumberFieldProps {
  value: number | null | undefined;
  label: string;
  onSave: (newValue: number | null) => Promise<void>;
  placeholder?: string;
  variant?: 'body1' | 'body2' | 'h6' | 'subtitle1';
  required?: boolean;
  min?: number;
  max?: number;
  step?: number;
}

export const InlineNumberField: React.FC<InlineNumberFieldProps> = ({
  value,
  label,
  onSave,
  placeholder = 'Click to edit',
  variant = 'body1',
  required = false,
  min,
  max,
  step = 1,
}) => {
  const [isEditing, setIsEditing] = useState(false);
  const [currentValue, setCurrentValue] = useState<string>(
    value !== null && value !== undefined ? value.toString() : ''
  );
  const [isLoading, setIsLoading] = useState(false);
  const [showEditIcon, setShowEditIcon] = useState(false);
  const [error, setError] = useState<string>('');
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setCurrentValue(value !== null && value !== undefined ? value.toString() : '');
  }, [value]);

  useEffect(() => {
    if (isEditing && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [isEditing]);

  const handleClick = () => {
    if (!isEditing) {
      setIsEditing(true);
      setError('');
    }
  };

  const validateNumber = (val: string): { isValid: boolean; error: string; numValue: number | null } => {
    if (!val.trim()) {
      if (required) {
        return { isValid: false, error: `${label} is required`, numValue: null };
      }
      return { isValid: true, error: '', numValue: null };
    }

    const numValue = parseFloat(val);

    if (isNaN(numValue)) {
      return { isValid: false, error: 'Please enter a valid number', numValue: null };
    }

    if (min !== undefined && numValue < min) {
      return { isValid: false, error: `Value must be at least ${min}`, numValue: null };
    }

    if (max !== undefined && numValue > max) {
      return { isValid: false, error: `Value must be at most ${max}`, numValue: null };
    }

    return { isValid: true, error: '', numValue };
  };

  const handleSave = async () => {
    const validation = validateNumber(currentValue);

    if (!validation.isValid) {
      setError(validation.error);
      return;
    }

    // Check if value actually changed
    if (validation.numValue === value || (validation.numValue === null && (value === null || value === undefined))) {
      setIsEditing(false);
      setError('');
      return;
    }

    setIsLoading(true);
    try {
      await onSave(validation.numValue);
      setIsEditing(false);
      setError('');
    } catch (error) {
      console.error('Failed to save:', error);
      setCurrentValue(value !== null && value !== undefined ? value.toString() : '');
      setError('Failed to save changes');
    } finally {
      setIsLoading(false);
    }
  };

  const handleCancel = () => {
    setCurrentValue(value !== null && value !== undefined ? value.toString() : '');
    setIsEditing(false);
    setError('');
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      handleCancel();
    } else if (e.key === 'Enter') {
      e.preventDefault();
      handleSave();
    }
  };

  const handleBlur = () => {
    setTimeout(() => {
      if (isEditing && !isLoading) {
        handleSave();
      }
    }, 150);
  };

  const getDisplayValue = () => {
    if (value === null || value === undefined) {
      return placeholder;
    }
    return value.toLocaleString();
  };

  if (isEditing) {
    return (
      <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1, width: '100%', maxWidth: 300 }}>
        <TextField
          inputRef={inputRef}
          type="number"
          value={currentValue}
          onChange={(e) => setCurrentValue(e.target.value)}
          onKeyDown={handleKeyDown}
          onBlur={handleBlur}
          size="small"
          fullWidth
          placeholder={placeholder}
          required={required}
          error={!!error}
          helperText={error}
          disabled={isLoading}
          inputProps={{
            min,
            max,
            step,
          }}
        />
        {isLoading ? (
          <CircularProgress size={20} sx={{ mt: 1 }} />
        ) : (
          <Box sx={{ display: 'flex', gap: 0.5, mt: 0.5 }}>
            <IconButton
              size="small"
              onClick={handleSave}
              disabled={!!error}
              color="primary"
            >
              <CheckIcon fontSize="small" />
            </IconButton>
            <IconButton size="small" onClick={handleCancel}>
              <CloseIcon fontSize="small" />
            </IconButton>
          </Box>
        )}
      </Box>
    );
  }

  return (
    <Box
      onClick={handleClick}
      onMouseEnter={() => setShowEditIcon(true)}
      onMouseLeave={() => setShowEditIcon(false)}
      sx={{
        display: 'flex',
        alignItems: 'center',
        gap: 1,
        cursor: 'pointer',
        padding: '4px 8px',
        borderRadius: 1,
        '&:hover': {
          backgroundColor: 'action.hover',
        },
        minHeight: '32px',
      }}
    >
      <Typography
        variant={variant}
        sx={{
          color: value === null || value === undefined ? 'text.secondary' : 'text.primary',
          fontStyle: value === null || value === undefined ? 'italic' : 'normal',
          flex: 1,
        }}
      >
        {getDisplayValue()}
      </Typography>
      {showEditIcon && (
        <EditIcon
          fontSize="small"
          sx={{ color: 'action.active', opacity: 0.7 }}
        />
      )}
    </Box>
  );
};
