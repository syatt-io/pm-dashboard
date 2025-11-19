import { createTheme } from '@mui/material/styles';
import { nanoLightTheme } from 'react-admin';
import { deepmerge } from '@mui/utils';

// Custom theme overrides
const customThemeOverrides = {
  typography: {
    fontSize: 15, // Increased from default 14px
    body1: {
      fontSize: '1rem', // 15px base
    },
    body2: {
      fontSize: '0.933rem', // ~14px
    },
  },
};

// Light theme overrides with improved contrast
const lightThemeOverrides = {
  ...customThemeOverrides,
  components: {
    RaAppBar: {
      styleOverrides: {
        root: {
          backgroundColor: '#ffffff',
          color: '#1a1a1a',
          boxShadow: '0 1px 3px rgba(0, 0, 0, 0.12)',
        },
      },
    },
    RaMenuItemLink: {
      styleOverrides: {
        root: {
          '&.RaMenuItemLink-active': {
            color: '#1976d2',
            backgroundColor: 'rgba(25, 118, 210, 0.08)',
          },
        },
      },
    },
    RaLayout: {
      styleOverrides: {
        root: {
          '& .RaLayout-content': {
            paddingTop: '12px', // Reduced from default (usually 16-24px)
            marginTop: 0,
          },
        },
      },
    },
    MuiToolbar: {
      styleOverrides: {
        root: {
          minHeight: '48px !important', // Reduced from default 64px
          '@media (min-width: 600px)': {
            minHeight: '48px !important',
          },
        },
      },
    },
    MuiSelect: {
      styleOverrides: {
        root: {
          borderRadius: '8px',
          transition: 'all 0.2s ease-in-out',
          '&:hover': {
            backgroundColor: 'rgba(0, 0, 0, 0.02)',
          },
        },
      },
      defaultProps: {
        variant: 'outlined',
      },
    },
    MuiOutlinedInput: {
      styleOverrides: {
        root: {
          borderRadius: '8px',
          '&:hover .MuiOutlinedInput-notchedOutline': {
            borderColor: '#1976d2',
          },
        },
      },
    },
    MuiMenu: {
      styleOverrides: {
        paper: {
          borderRadius: '8px',
          marginTop: '4px',
        },
      },
    },
  },
  palette: {
    mode: 'light' as const,
    primary: {
      main: '#8B5CF6', // Royal Purple from Syatt design system
      contrastText: '#ffffff',
    },
    secondary: {
      main: '#00FFCE', // Neon Mint from Syatt design system
      contrastText: '#000000',
    },
    background: {
      default: '#f5f5f5',
      paper: '#ffffff',
    },
    text: {
      primary: '#1a1a1a',
      secondary: '#666666',
    },
  },
};

// Merge custom overrides with Nano light theme
export const customLightTheme = createTheme(
  deepmerge(nanoLightTheme, lightThemeOverrides)
);
