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

interface InlineTextFieldProps {
  value: string;
  label: string;
  onSave: (newValue: string) => Promise<void>;
  multiline?: boolean;
  placeholder?: string;
  variant?: 'body1' | 'body2' | 'h6' | 'subtitle1';
  required?: boolean;
}

export const InlineTextField: React.FC<InlineTextFieldProps> = ({
  value,
  label,
  onSave,
  multiline = false,
  placeholder = 'Click to edit',
  variant = 'body1',
  required = false,
}) => {
  const [isEditing, setIsEditing] = useState(false);
  const [currentValue, setCurrentValue] = useState(value);
  const [isLoading, setIsLoading] = useState(false);
  const [showEditIcon, setShowEditIcon] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setCurrentValue(value);
  }, [value]);

  useEffect(() => {
    if (isEditing && inputRef.current) {
      inputRef.current.focus();
      // Select all text for easy replacement
      inputRef.current.select();
    }
  }, [isEditing]);

  const handleClick = () => {
    if (!isEditing) {
      setIsEditing(true);
    }
  };

  const handleSave = async () => {
    if (currentValue === value) {
      setIsEditing(false);
      return;
    }

    if (required && !currentValue.trim()) {
      return; // Don't save if required field is empty
    }

    setIsLoading(true);
    try {
      await onSave(currentValue);
      setIsEditing(false);
    } catch (error) {
      console.error('Failed to save:', error);
      // Reset to original value on error
      setCurrentValue(value);
    } finally {
      setIsLoading(false);
    }
  };

  const handleCancel = () => {
    setCurrentValue(value);
    setIsEditing(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      handleCancel();
    } else if (e.key === 'Enter' && !multiline) {
      e.preventDefault();
      handleSave();
    }
  };

  const handleBlur = () => {
    // Small delay to allow clicking save/cancel buttons
    setTimeout(() => {
      if (isEditing && !isLoading) {
        handleSave();
      }
    }, 150);
  };

  if (isEditing) {
    return (
      <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1, width: '100%' }}>
        <TextField
          inputRef={inputRef}
          value={currentValue}
          onChange={(e) => setCurrentValue(e.target.value)}
          onKeyDown={handleKeyDown}
          onBlur={handleBlur}
          multiline={multiline}
          rows={multiline ? 3 : 1}
          size="small"
          fullWidth
          placeholder={placeholder}
          required={required}
          error={required && !currentValue.trim()}
          helperText={required && !currentValue.trim() ? `${label} is required` : ''}
          disabled={isLoading}
        />
        {isLoading ? (
          <CircularProgress size={20} sx={{ mt: 1 }} />
        ) : (
          <Box sx={{ display: 'flex', gap: 0.5, mt: 0.5 }}>
            <IconButton
              size="small"
              onClick={handleSave}
              disabled={required && !currentValue.trim()}
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
          color: !value ? 'text.secondary' : 'text.primary',
          fontStyle: !value ? 'italic' : 'normal',
          flex: 1,
          whiteSpace: multiline ? 'pre-wrap' : 'nowrap',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
        }}
      >
        {value || placeholder}
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
