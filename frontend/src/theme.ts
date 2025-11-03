import { createTheme } from '@mui/material/styles';
import { nanoLightTheme, nanoDarkTheme } from 'react-admin';
import { deepmerge } from '@mui/utils';

// Custom theme overrides for both light and dark modes
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
  },
  palette: {
    mode: 'light' as const,
    primary: {
      main: '#1976d2',
      contrastText: '#ffffff',
    },
    secondary: {
      main: '#dc004e',
      contrastText: '#ffffff',
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

// Dark theme overrides with improved contrast and legibility
const darkThemeOverrides = {
  ...customThemeOverrides,
  components: {
    RaAppBar: {
      styleOverrides: {
        root: {
          backgroundColor: '#1e1e1e',
          color: '#ffffff',
          boxShadow: '0 1px 3px rgba(0, 0, 0, 0.5)',
        },
      },
    },
    RaMenuItemLink: {
      styleOverrides: {
        root: {
          color: '#e0e0e0',
          '&.RaMenuItemLink-active': {
            color: '#90caf9',
            backgroundColor: 'rgba(144, 202, 249, 0.16)',
          },
          '&:hover': {
            backgroundColor: 'rgba(255, 255, 255, 0.08)',
          },
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundColor: '#2a2a2a',
          color: '#e0e0e0',
        },
      },
    },
    MuiTableCell: {
      styleOverrides: {
        root: {
          color: '#e0e0e0',
          borderColor: 'rgba(255, 255, 255, 0.12)',
        },
        head: {
          color: '#ffffff',
          fontWeight: 600,
        },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: {
          backgroundColor: 'rgba(255, 255, 255, 0.16)',
          color: '#e0e0e0',
        },
      },
    },
  },
  palette: {
    mode: 'dark' as const,
    primary: {
      main: '#90caf9',
      contrastText: '#000000',
    },
    secondary: {
      main: '#f48fb1',
      contrastText: '#000000',
    },
    background: {
      default: '#121212',
      paper: '#2a2a2a',
    },
    text: {
      primary: '#ffffff',
      secondary: '#b0b0b0',
    },
    divider: 'rgba(255, 255, 255, 0.12)',
  },
};

// Merge custom overrides with Nano themes
export const customLightTheme = createTheme(
  deepmerge(nanoLightTheme, lightThemeOverrides)
);

export const customDarkTheme = createTheme(
  deepmerge(nanoDarkTheme, darkThemeOverrides)
);
