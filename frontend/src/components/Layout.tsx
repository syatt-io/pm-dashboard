import React from 'react';
import { Layout, AppBar, Sidebar, Menu, UserMenu, Logout, MenuItemLink } from 'react-admin';
import { Typography, Box } from '@mui/material';
import { styled } from '@mui/material/styles';
import SettingsIcon from '@mui/icons-material/Settings';
import OnboardingAlert from './OnboardingAlert';

// Custom AppBar with Syatt branding
const CustomAppBar = styled(AppBar)(({ theme }) => ({
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
        background: 'linear-gradient(45deg, #FFFFFF 30%, #00FFCE 90%)',
        backgroundClip: 'text',
        WebkitBackgroundClip: 'text',
        WebkitTextFillColor: 'transparent',
      }}
    >
      PM Command Center
    </Typography>
    <Typography
      variant="caption"
      sx={{
        background: 'rgba(255, 255, 255, 0.7)',
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

// Custom Menu with icons and enhanced styling
const CustomMenu = styled(Menu)(({ theme }) => ({
  '& .RaMenuItemLink-root': {
    borderRadius: '8px',
    margin: '4px 8px',
    padding: '12px 16px',
    transition: 'all 0.2s ease',
    '&:hover': {
      backgroundColor: 'rgba(85, 77, 255, 0.08)',
      transform: 'translateX(4px)',
    },
    '&.RaMenuItemLink-active': {
      backgroundColor: 'rgba(85, 77, 255, 0.12)',
      borderLeft: '3px solid #554DFF',
      fontWeight: 600,
    },
  },
  '& .RaMenuItemLink-icon': {
    color: '#656083',
    transition: 'color 0.2s ease',
  },
  '& .RaMenuItemLink-active .RaMenuItemLink-icon': {
    color: '#554DFF',
  },
}));

// Custom UserMenu with Settings link
const CustomUserMenu = () => (
  <UserMenu>
    <MenuItemLink
      to="/settings"
      primaryText="Settings"
      leftIcon={<SettingsIcon />}
    />
    <Logout />
  </UserMenu>
);

export const CustomLayout = (props: any) => (
  <>
    <Layout
      {...props}
      appBar={() => (
        <CustomAppBar>
          <SyattTitle />
          <CustomUserMenu />
        </CustomAppBar>
      )}
      sidebar={() => (
        <CustomSidebar>
          <CustomMenu />
        </CustomSidebar>
      )}
    />
    <OnboardingAlert />
  </>
);