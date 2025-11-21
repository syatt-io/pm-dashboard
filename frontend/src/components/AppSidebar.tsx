import React from 'react';
import { ChevronRight } from "lucide-react";
import { useLocation, useNavigate } from "react-router-dom";
import {
  LayoutDashboard,
  FolderKanban,
  Users,
  CheckSquare,
  MessageSquare,
  Lightbulb,
  TrendingUp,
  Settings as SettingsIcon,
} from "lucide-react";
import { usePermissions } from 'react-admin';

import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSub,
  SidebarMenuSubItem,
  SidebarMenuSubButton,
  useSidebar,
} from "./ui/sidebar";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "./ui/collapsible";

interface SubMenuItem {
  title: string;
  url: string;
  tabParam?: string;
  adminOnly?: boolean;
}

interface MenuItem {
  title: string;
  url: string;
  icon: any;
  subItems?: SubMenuItem[];
  adminOnly?: boolean;
}

const menuItems: MenuItem[] = [
  { title: "Dashboard", url: "/", icon: LayoutDashboard },
  {
    title: "Projects",
    url: "/projects",
    icon: FolderKanban,
    subItems: [
      { title: "My Projects", url: "/projects", tabParam: "0" },  // Tab index 0
      { title: "Active Projects", url: "/projects", tabParam: "1" },  // Tab index 1
      { title: "Monthly Forecasts", url: "/projects", tabParam: "2" },  // Tab index 2
    ],
  },
  { title: "My Meetings", url: "/analysis", icon: Users },
  { title: "My TODOs", url: "/todos", icon: CheckSquare },
  { title: "My Feedback", url: "/feedback", icon: MessageSquare },
  { title: "Team Learnings", url: "/learnings", icon: Lightbulb },
  { title: "Forecasting", url: "/forecasting", icon: TrendingUp },
  {
    title: "Settings",
    url: "/settings",
    icon: SettingsIcon,
    adminOnly: true,  // Hide entire Settings section from non-admin users
    subItems: [
      { title: "Project Settings", url: "/settings", tabParam: "0" },  // Tab index 0 (was 1)
      { title: "Insights & Escalation", url: "/settings", tabParam: "1" },  // Tab index 1 (was 3)
      { title: "AI Configuration", url: "/settings", tabParam: "2", adminOnly: true },  // Tab index 2 (was 4)
      { title: "User Management", url: "/settings", tabParam: "3", adminOnly: true },  // Tab index 3 (was 5)
      { title: "Epic Categories", url: "/settings", tabParam: "4", adminOnly: true },  // Tab index 4 (was 6)
      { title: "Jira Templates", url: "/settings", tabParam: "5", adminOnly: true },  // Tab index 5 (was 7)
      { title: "Data Management", url: "/settings", tabParam: "6", adminOnly: true },  // Tab index 6
    ],
  },
];

export function AppSidebar() {
  const { state } = useSidebar();
  const location = useLocation();
  const navigate = useNavigate();
  const { permissions } = usePermissions();
  const isAdmin = permissions === 'admin';

  const currentPath = location.pathname;
  const searchParams = new URLSearchParams(location.search);

  // Check if a URL is active (considering both path and tab parameter)
  const isActive = (path: string, tabParam?: string) => {
    if (path === '/' && currentPath === '/') return true;
    if (path === '/' && currentPath !== '/') return false;

    // Check for exact match or child route (e.g., /analysis matches /analysis/123)
    const pathMatches = currentPath === path || currentPath.startsWith(path + '/');

    if (!tabParam) return pathMatches;

    // Use resource-specific tab param names
    let tabParamName = 'tab';
    if (path === '/projects') tabParamName = 'projects-tab';
    if (path === '/settings') tabParamName = 'settings-tab';

    const currentTab = searchParams.get(tabParamName);

    return pathMatches && currentTab === tabParam;
  };

  // Check if a group is active (parent or any child)
  const isGroupActive = (item: MenuItem) => {
    if (isActive(item.url)) return true;
    return item.subItems?.some((sub) => isActive(sub.url, sub.tabParam)) ?? false;
  };

  // Handle navigation with tab parameter support
  const handleNavigate = (url: string, tabParam?: string) => {
    if (tabParam) {
      // Use resource-specific tab param names
      let tabParamName = 'tab';
      if (url === '/projects') tabParamName = 'projects-tab';
      if (url === '/settings') tabParamName = 'settings-tab';

      navigate(`${url}?${tabParamName}=${tabParam}`);
    } else {
      navigate(url);
    }
  };

  // Filter admin-only items based on permissions
  const filteredMenuItems = menuItems.filter(item => {
    if (item.adminOnly && !isAdmin) return false;

    // Filter admin-only sub-items
    if (item.subItems) {
      item.subItems = item.subItems.filter(subItem => {
        if ((subItem as any).adminOnly && !isAdmin) return false;
        return true;
      });
    }

    return true;
  });

  return (
    <Sidebar collapsible="icon" className="border-r border-sidebar-border">
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel className="text-xs font-semibold uppercase tracking-wider text-muted-foreground px-3 py-2">
            Navigation
          </SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu className="gap-1">
              {filteredMenuItems.map((item) => {
                const hasSubItems = item.subItems && item.subItems.length > 0;
                const groupActive = isGroupActive(item);

                if (!hasSubItems) {
                  return (
                    <SidebarMenuItem key={item.title}>
                      <SidebarMenuButton
                        onClick={() => handleNavigate(item.url)}
                        isActive={isActive(item.url)}
                        tooltip={state === "collapsed" ? item.title : undefined}
                        className="cursor-pointer h-10 px-3 gap-3"
                      >
                        <item.icon className="h-4 w-4 flex-shrink-0" />
                        <span className="text-sm">{item.title}</span>
                      </SidebarMenuButton>
                    </SidebarMenuItem>
                  );
                }

                return (
                  <Collapsible
                    key={item.title}
                    defaultOpen={groupActive}
                    className="group/collapsible"
                  >
                    <SidebarMenuItem>
                      <CollapsibleTrigger asChild>
                        <SidebarMenuButton
                          isActive={groupActive}
                          tooltip={state === "collapsed" ? item.title : undefined}
                          className="h-10 px-3 gap-3"
                        >
                          <item.icon className="h-4 w-4 flex-shrink-0" />
                          <span className="flex-1 text-left text-sm">{item.title}</span>
                          <ChevronRight className="h-3.5 w-3.5 transition-transform duration-200 group-data-[state=open]/collapsible:rotate-90" />
                        </SidebarMenuButton>
                      </CollapsibleTrigger>
                      <CollapsibleContent>
                        <SidebarMenuSub className="gap-1">
                          {item.subItems?.map((subItem) => (
                            <SidebarMenuSubItem key={subItem.title}>
                              <SidebarMenuSubButton
                                onClick={() => handleNavigate(subItem.url, subItem.tabParam)}
                                isActive={isActive(subItem.url, subItem.tabParam)}
                                className="cursor-pointer h-9 px-3 text-sm"
                                asChild
                              >
                                <span>{subItem.title}</span>
                              </SidebarMenuSubButton>
                            </SidebarMenuSubItem>
                          ))}
                        </SidebarMenuSub>
                      </CollapsibleContent>
                    </SidebarMenuItem>
                  </Collapsible>
                );
              })}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
    </Sidebar>
  );
}
