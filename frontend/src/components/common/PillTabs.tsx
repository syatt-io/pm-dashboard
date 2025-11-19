import React from 'react';
import { Tabs, Tab, TabsProps } from '@mui/material';

/**
 * Reusable styled tabs component with pill/button-style active state
 * Matches the design with light background bar and purple rounded active tab
 */
export const PillTabs: React.FC<TabsProps> = (props) => {
  return (
    <Tabs
      {...props}
      sx={{
        // Light gray background bar spanning full width
        backgroundColor: '#F5F5F5',
        borderRadius: '8px',
        padding: '4px',
        minHeight: '48px',
        ...props.sx,
        '& .MuiTabs-indicator': {
          display: 'none', // Remove default underline indicator
        },
        '& .MuiTab-root': {
          // Inactive tab styling
          textTransform: 'none',
          fontWeight: 500,
          fontSize: '14px',
          color: '#666',
          minHeight: '40px',
          borderRadius: '6px',
          marginRight: '4px',
          transition: 'all 0.2s ease',
          '&:hover': {
            backgroundColor: 'rgba(85, 77, 255, 0.08)',
            color: '#554DFF',
          },
          // Active tab styling - purple rounded button/pill
          '&.Mui-selected': {
            backgroundColor: '#554DFF',
            color: '#FFF',
            fontWeight: 600,
            boxShadow: '0 2px 4px rgba(85, 77, 255, 0.2)',
          },
        },
      }}
    />
  );
};

/**
 * Individual Tab component - re-exported from MUI for convenience
 */
export { Tab } from '@mui/material';
