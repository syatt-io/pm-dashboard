// TypeScript declaration overrides for React Admin compatibility
import '@mui/material/Grid';

declare module '@mui/material/Grid' {
  interface GridProps {
    item?: boolean;
  }
}

declare module 'react-admin' {
  interface TextFieldProps {
    multiline?: boolean;
  }
}