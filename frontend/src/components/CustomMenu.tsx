import React, { useState } from 'react';
import { Menu, usePermissions, MenuItemLink, useSidebarState, DashboardMenuItem, useResourceDefinitions } from 'react-admin';
import { styled } from '@mui/material/styles';
import { Box, Collapse, List, ListItemButton, ListItemIcon, ListItemText, Divider } from '@mui/material';
import DashboardIcon from '@mui/icons-material/Dashboard';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import BusinessIcon from '@mui/icons-material/Business';
import SettingsIcon from '@mui/icons-material/Settings';
import AnalyticsIcon from '@mui/icons-material/Analytics';
import CategoryIcon from '@mui/icons-material/Category';
import LabelIcon from '@mui/icons-material/Label';
import PeopleIcon from '@mui/icons-material/People';
import ViewListIcon from '@mui/icons-material/ViewList';
import ArchiveIcon from '@mui/icons-material/Archive';
import AssessmentIcon from '@mui/icons-material/Assessment';
import TimelineIcon from '@mui/icons-material/Timeline';

/**
 * Enhanced Custom Menu with nested navigation and accordion behavior.
 * Features:
 * - Nested sub-items for Projects, Settings, and Analytics
 * - Smooth accordion expand/collapse animations
 * - Enhanced visual hierarchy with Syatt design colors
 * - Improved spacing and typography
 */

// Styled wrapper for menu items with Syatt design and enhanced animations
const StyledMenuContainer = styled('div')(({ theme }) => ({
  paddingTop: theme.spacing(1),
  paddingBottom: theme.spacing(1),

  // Parent menu items
  '& .RaMenuItemLink-root': {
    borderRadius: '8px',
    margin: '4px 8px',
    padding: '12px 16px',
    minHeight: '44px',
    transition: 'all 0.2s ease',
    fontWeight: 500,

    '&:hover': {
      backgroundColor: 'rgba(85, 77, 255, 0.08)',
      transform: 'translateX(4px)',
      boxShadow: '0 2px 8px rgba(85, 77, 255, 0.1)',
    },
    '&.RaMenuItemLink-active': {
      backgroundColor: 'rgba(85, 77, 255, 0.15)',
      borderLeft: '4px solid #554DFF',
      fontWeight: 600,
      backgroundImage: 'linear-gradient(90deg, rgba(85, 77, 255, 0.15) 0%, rgba(85, 77, 255, 0.05) 100%)',
    },
  },

  // Icon colors
  '& .RaMenuItemLink-icon': {
    color: '#656083',
    transition: 'color 0.2s ease',
  },
  '& .RaMenuItemLink-active .RaMenuItemLink-icon': {
    color: '#554DFF',
  },

  // Section dividers
  '& .menu-divider': {
    margin: '12px 16px',
    borderColor: 'rgba(101, 96, 131, 0.1)',
  },
}));

// Styled parent item with accordion functionality
const ParentMenuItem = styled(ListItemButton)(({ theme }) => ({
  borderRadius: '8px',
  margin: '4px 8px',
  padding: '12px 16px',
  minHeight: '44px',
  transition: 'all 0.2s ease',
  fontWeight: 600,

  '&:hover': {
    backgroundColor: 'rgba(85, 77, 255, 0.08)',
    transform: 'translateX(4px)',
    boxShadow: '0 2px 8px rgba(85, 77, 255, 0.1)',
  },

  '&.expanded': {
    backgroundColor: 'rgba(85, 77, 255, 0.12)',
    backgroundImage: 'linear-gradient(90deg, rgba(85, 77, 255, 0.12) 0%, rgba(85, 77, 255, 0.04) 100%)',
  },
}));

// Styled nested menu item
const NestedMenuItem = styled(Box)(({ theme }) => ({
  '& .MuiListItemButton-root': {
    borderRadius: '6px',
    margin: '2px 8px 2px 48px', // Increased left margin for nesting
    padding: '8px 12px',
    minHeight: '36px',
    transition: 'all 0.2s ease',
    fontWeight: 500,

    '&:hover': {
      backgroundColor: 'rgba(0, 255, 206, 0.08)', // Mint accent on hover
      transform: 'translateX(4px)',
    },

    '& .MuiListItemIcon-root': {
      minWidth: 36,
      color: '#8B86A3', // Lighter icon color for nested items
    },

    '& .MuiListItemText-primary': {
      fontSize: '0.9rem',
      color: '#656083',
    },
  },
}));

// Chevron icon with rotation animation
const ChevronIcon = styled(ExpandMoreIcon, {
  shouldForwardProp: (prop) => prop !== 'expanded',
})<{ expanded: boolean }>(({ expanded }) => ({
  transition: 'transform 0.3s ease',
  transform: expanded ? 'rotate(0deg)' : 'rotate(-90deg)',
  color: '#656083',
}));

export const CustomMenu = () => {
  const { permissions, isLoading } = usePermissions();
  const resources = useResourceDefinitions();
  const [open] = useSidebarState();

  // State for accordion sections
  const [expandedSections, setExpandedSections] = useState({
    projects: false,
    settings: false,
    analytics: false,
  });

  // While loading permissions, show skeleton menu
  if (isLoading) {
    return <Menu />;
  }

  const isAdmin = permissions === 'admin';

  const handleToggleSection = (section: keyof typeof expandedSections) => {
    setExpandedSections(prev => ({
      ...prev,
      [section]: !prev[section],
    }));
  };

  return (
    <StyledMenuContainer>
      {/* Dashboard */}
      <DashboardMenuItem
        leftIcon={<DashboardIcon />}
        sidebarIsOpen={open}
      />

      {/* My Projects with nested items */}
      <ParentMenuItem
        onClick={() => handleToggleSection('projects')}
        className={expandedSections.projects ? 'expanded' : ''}
      >
        <ListItemIcon>
          <BusinessIcon sx={{ color: expandedSections.projects ? '#554DFF' : '#656083' }} />
        </ListItemIcon>
        <ListItemText
          primary="My Projects"
          primaryTypographyProps={{ fontWeight: 600 }}
        />
        <ChevronIcon expanded={expandedSections.projects} />
      </ParentMenuItem>

      <Collapse in={expandedSections.projects} timeout={300} unmountOnExit>
        <List component="div" disablePadding>
          <NestedMenuItem>
            <ListItemButton component="a" href="/#/projects">
              <ListItemIcon>
                <ViewListIcon />
              </ListItemIcon>
              <ListItemText primary="All Projects" />
            </ListItemButton>
          </NestedMenuItem>
          <NestedMenuItem>
            <ListItemButton component="a" href="/#/projects?filter={%22is_active%22:true}">
              <ListItemIcon>
                <BusinessIcon />
              </ListItemIcon>
              <ListItemText primary="Active Projects" />
            </ListItemButton>
          </NestedMenuItem>
          <NestedMenuItem>
            <ListItemButton component="a" href="/#/projects?filter={%22is_active%22:false}">
              <ListItemIcon>
                <ArchiveIcon />
              </ListItemIcon>
              <ListItemText primary="Archived Projects" />
            </ListItemButton>
          </NestedMenuItem>
        </List>
      </Collapse>

      {/* Other flat menu items (My Meetings, TODOs, Feedback, Team Learnings) */}
      {Object.keys(resources).map((name) => {
        const resource = resources[name];

        // Skip resources without list component
        if (!resource.hasList) {
          return null;
        }

        // Skip resources that are handled separately
        if (name === 'projects' || name === 'settings' || name === 'analytics' || name === 'meetings' || name === 'epic-templates') {
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

      <Divider className="menu-divider" />

      {/* Analytics (admin only) with nested items */}
      {isAdmin && (
        <>
          <ParentMenuItem
            onClick={() => handleToggleSection('analytics')}
            className={expandedSections.analytics ? 'expanded' : ''}
          >
            <ListItemIcon>
              <AnalyticsIcon sx={{ color: expandedSections.analytics ? '#554DFF' : '#656083' }} />
            </ListItemIcon>
            <ListItemText
              primary="Analytics"
              primaryTypographyProps={{ fontWeight: 600 }}
            />
            <ChevronIcon expanded={expandedSections.analytics} />
          </ParentMenuItem>

          <Collapse in={expandedSections.analytics} timeout={300} unmountOnExit>
            <List component="div" disablePadding>
              <NestedMenuItem>
                <ListItemButton component="a" href="/#/analytics">
                  <ListItemIcon>
                    <AssessmentIcon />
                  </ListItemIcon>
                  <ListItemText primary="Overview" />
                </ListItemButton>
              </NestedMenuItem>
              <NestedMenuItem>
                <ListItemButton component="a" href="/#/analytics?view=projects">
                  <ListItemIcon>
                    <BusinessIcon />
                  </ListItemIcon>
                  <ListItemText primary="Project Analytics" />
                </ListItemButton>
              </NestedMenuItem>
              <NestedMenuItem>
                <ListItemButton component="a" href="/#/analytics?view=team">
                  <ListItemIcon>
                    <TimelineIcon />
                  </ListItemIcon>
                  <ListItemText primary="Team Performance" />
                </ListItemButton>
              </NestedMenuItem>
            </List>
          </Collapse>

          {/* Epic Templates (admin only) */}
          <MenuItemLink
            to="/epic-templates"
            primaryText="Epic Templates"
            leftIcon={<CategoryIcon />}
            sidebarIsOpen={open}
          />
        </>
      )}

      <Divider className="menu-divider" />

      {/* Settings with nested items */}
      <ParentMenuItem
        onClick={() => handleToggleSection('settings')}
        className={expandedSections.settings ? 'expanded' : ''}
      >
        <ListItemIcon>
          <SettingsIcon sx={{ color: expandedSections.settings ? '#554DFF' : '#656083' }} />
        </ListItemIcon>
        <ListItemText
          primary="Settings"
          primaryTypographyProps={{ fontWeight: 600 }}
        />
        <ChevronIcon expanded={expandedSections.settings} />
      </ParentMenuItem>

      <Collapse in={expandedSections.settings} timeout={300} unmountOnExit>
        <List component="div" disablePadding>
          <NestedMenuItem>
            <ListItemButton component="a" href="/#/settings">
              <ListItemIcon>
                <SettingsIcon />
              </ListItemIcon>
              <ListItemText primary="Profile" />
            </ListItemButton>
          </NestedMenuItem>
          <NestedMenuItem>
            <ListItemButton component="a" href="/#/settings?tab=categories">
              <ListItemIcon>
                <CategoryIcon />
              </ListItemIcon>
              <ListItemText primary="Epic Categories" />
            </ListItemButton>
          </NestedMenuItem>
          <NestedMenuItem>
            <ListItemButton component="a" href="/#/settings?tab=keywords">
              <ListItemIcon>
                <LabelIcon />
              </ListItemIcon>
              <ListItemText primary="Project Keywords" />
            </ListItemButton>
          </NestedMenuItem>
          <NestedMenuItem>
            <ListItemButton component="a" href="/#/settings?tab=resources">
              <ListItemIcon>
                <PeopleIcon />
              </ListItemIcon>
              <ListItemText primary="Resource Mappings" />
            </ListItemButton>
          </NestedMenuItem>
        </List>
      </Collapse>
    </StyledMenuContainer>
  );
};
