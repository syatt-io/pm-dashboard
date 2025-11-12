import React from 'react';
import { Layout, AppBar, Sidebar, Logout, MenuItemLink } from 'react-admin';
import { Typography, Box } from '@mui/material';
import { styled } from '@mui/material/styles';
import SettingsIcon from '@mui/icons-material/Settings';
import OnboardingAlert from './OnboardingAlert';
import { CustomMenu } from './CustomMenu';

// Custom AppBar with Syatt branding
const CustomAppBar = styled(AppBar)(({ theme }) => ({
  position: 'fixed',
  zIndex: theme.zIndex.appBar,
  '& .RaAppBar-toolbar': {
    backgroundColor: theme.palette.primary.main,
  },
  '& .RaAppBar-title': {
    flex: 1,
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
    overflow: 'hidden',
  },
}));

const SyattTitle = () => (
  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
    <Typography
      variant="h6"
      component="div"
      sx={{
        fontWeight: 700,
        color: '#FFFFFF',
        textShadow: '0 2px 4px rgba(0, 0, 0, 0.3)',
      }}
    >
      PM Command Center
    </Typography>
    <Typography
      variant="caption"
      sx={{
        background: 'rgba(0, 255, 206, 0.2)',
        color: '#00FFCE',
        px: 1,
        py: 0.5,
        borderRadius: 1,
        fontSize: '0.7rem',
        fontWeight: 600,
      }}
    >
      by Syatt
    </Typography>
  </Box>
);

// Custom Sidebar with enhanced styling
const CustomSidebar = styled(Sidebar)(({ theme }) => ({
  '& .RaSidebar-fixed': {
    zIndex: theme.zIndex.drawer,
  },
  '& .MuiDrawer-paper': {
    backgroundColor: '#FFFFFF',
    borderRight: '1px solid rgba(101, 96, 131, 0.1)',
    boxShadow: '4px 0 16px rgba(30, 29, 39, 0.06)',
  },
}));

// Custom UserMenu with Settings link
const CustomUserMenu = () => {
  return (
    <>
      <MenuItemLink
        to="/settings"
        primaryText="Settings"
        leftIcon={<SettingsIcon />}
      />
      <Logout />
    </>
  );
};

// Create stable component instances to avoid re-rendering
const MyAppBar = (props: any) => (
  <CustomAppBar {...props} userMenu={<CustomUserMenu />}>
    <SyattTitle />
  </CustomAppBar>
);

const MySidebar = (props: any) => (
  <CustomSidebar {...props}>
    <CustomMenu />
  </CustomSidebar>
);

export const CustomLayout = (props: any) => (
  <>
    <Layout
      {...props}
      appBar={MyAppBar}
      sidebar={MySidebar}
    />
    <OnboardingAlert />
  </>
);