import React from 'react';
import { Layout, Logout, MenuItemLink, UserMenu } from 'react-admin';
import { Typography, Box } from '@mui/material';
import AccountCircleIcon from '@mui/icons-material/AccountCircle';
import OnboardingAlert from './OnboardingAlert';
import { SidebarProvider, SidebarTrigger } from './ui/sidebar';
import { AppSidebar } from './AppSidebar';

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

// Custom UserMenu with My Profile link
const CustomUserMenu = () => {
  return (
    <>
      <MenuItemLink
        to="/profile"
        primaryText="My Profile"
        leftIcon={<AccountCircleIcon />}
      />
      <Logout />
    </>
  );
};

// Custom AppBar component matching reference design
const CustomAppBar = () => (
  <header className="sticky top-0 z-10 flex h-14 items-center gap-4 border-b px-6" style={{ backgroundColor: '#8B5CF6' }}>
    <SidebarTrigger className="text-white -ml-2 hover:bg-white/10" />
    <SyattTitle />
    <div className="flex-1" />
    <UserMenu>
      <CustomUserMenu />
    </UserMenu>
  </header>
);

export const CustomLayout = (props: any) => (
  <SidebarProvider>
    <div className="flex min-h-screen w-full">
      <AppSidebar />
      <div className="flex-1">
        <CustomAppBar />
        <Layout
          {...props}
          appBar={() => null}
          sidebar={() => null}
          sx={{
            '& .RaLayout-appFrame': {
              marginTop: 0,
              paddingTop: 0,
            },
            '& .RaLayout-content': {
              padding: '16px',
            },
          }}
        />
        <OnboardingAlert />
      </div>
    </div>
  </SidebarProvider>
);