import React, { useState } from 'react';
import {
  Box,
  Select,
  MenuItem,
  Typography,
  CircularProgress,
  FormControl,
  SelectChangeEvent,
} from '@mui/material';
import EditIcon from '@mui/icons-material/Edit';

interface SelectOption {
  value: string;
  label: string;
}

interface InlineSelectFieldProps {
  value: string;
  label: string;
  options: SelectOption[];
  onSave: (newValue: string) => Promise<void>;
  placeholder?: string;
  variant?: 'body1' | 'body2' | 'h6' | 'subtitle1';
  required?: boolean;
}

export const InlineSelectField: React.FC<InlineSelectFieldProps> = ({
  value,
  label,
  options,
  onSave,
  placeholder = 'Select an option',
  variant = 'body1',
  required = false,
}) => {
  const [isEditing, setIsEditing] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [showEditIcon, setShowEditIcon] = useState(false);

  const handleClick = () => {
    if (!isEditing) {
      setIsEditing(true);
    }
  };

  const handleChange = async (event: SelectChangeEvent<string>) => {
    const newValue = event.target.value;

    if (newValue === value) {
      setIsEditing(false);
      return;
    }

    setIsLoading(true);
    try {
      await onSave(newValue);
      setIsEditing(false);
    } catch (error) {
      console.error('Failed to save:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleBlur = () => {
    // Delay closing to allow async save operation to complete
    setTimeout(() => {
      if (!isLoading) {
        setIsEditing(false);
      }
    }, 150);
  };

  const getDisplayValue = () => {
    const option = options.find((opt) => opt.value === value);
    return option ? option.label : value || placeholder;
  };

  if (isEditing) {
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, minWidth: 200 }}>
        <FormControl size="small" fullWidth disabled={isLoading}>
          <Select
            value={value || ''}
            onChange={handleChange}
            onBlur={handleBlur}
            autoFocus
            displayEmpty
            required={required}
          >
            {!required && (
              <MenuItem value="">
                <em>{placeholder}</em>
              </MenuItem>
            )}
            {options.map((option) => (
              <MenuItem key={option.value} value={option.value}>
                {option.label}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
        {isLoading && <CircularProgress size={20} />}
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
