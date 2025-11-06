import React from 'react';
import { Menu, usePermissions, MenuItemLink, useSidebarState } from 'react-admin';
import { useResourceDefinitions } from 'react-admin';
import { styled } from '@mui/material/styles';

/**
 * Custom Menu that filters resources based on user permissions.
 * - Admins see all menu items including Analytics
 * - Non-admins don't see Analytics menu item
 */

// Styled wrapper for menu items with Syatt design
const StyledMenuContainer = styled('div')(({ theme }) => ({
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

export const CustomMenu = () => {
  const { permissions, isLoading } = usePermissions();
  const resources = useResourceDefinitions();
  const [open] = useSidebarState();

  // While loading permissions, show all menu items to avoid flicker
  if (isLoading) {
    return <Menu />;
  }

  const isAdmin = permissions === 'admin';

  return (
    <StyledMenuContainer>
      {Object.keys(resources).map((name) => {
        const resource = resources[name];

        // Skip resources without list component (they're not in menu anyway)
        if (!resource.hasList) {
          return null;
        }

        // Filter out analytics for non-admins
        if (name === 'analytics' && !isAdmin) {
          return null;
        }

        // Skip meetings resource (it's hidden from nav)
        if (name === 'meetings') {
          return null;
        }

        return (
          <MenuItemLink
            key={name}
            to={`/${name}`}
            primaryText={resource.options?.label || name}
            leftIcon={resource.icon ? <resource.icon /> : undefined}
            sidebarIsOpen={open}
          />
        );
      })}
    </StyledMenuContainer>
  );
};
