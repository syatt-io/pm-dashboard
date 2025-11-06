import { Resource, usePermissions } from 'react-admin';
import { ComponentType } from 'react';

interface AdminOnlyResourceProps {
  name: string;
  list?: ComponentType<any>;
  icon?: ComponentType<any>;
  options?: any;
  [key: string]: any;
}

/**
 * Wrapper for Resource that only renders for admin users.
 * Non-admin users won't see this in the menu at all.
 */
export const AdminOnlyResource = ({ name, list, icon, options, ...props }: AdminOnlyResourceProps) => {
  const { permissions, isLoading } = usePermissions();

  console.log('AdminOnlyResource - permissions:', permissions, 'isLoading:', isLoading);

  // Wait for permissions to load before deciding
  if (isLoading) {
    // Still render the resource while loading to avoid flickering
    return <Resource name={name} list={list} icon={icon} options={options} {...props} />;
  }

  // Only render the resource if user is admin
  if (permissions === 'admin') {
    console.log('AdminOnlyResource - rendering for admin');
    return <Resource name={name} list={list} icon={icon} options={options} {...props} />;
  }

  console.log('AdminOnlyResource - hiding for non-admin');
  // Return null for non-admins - resource won't appear in menu
  return null;
};
