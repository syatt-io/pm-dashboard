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

// Merge custom overrides with Nano themes
export const customLightTheme = createTheme(
  deepmerge(nanoLightTheme, customThemeOverrides)
);

export const customDarkTheme = createTheme(
  deepmerge(nanoDarkTheme, customThemeOverrides)
);
