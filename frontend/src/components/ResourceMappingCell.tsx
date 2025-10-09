// @ts-nocheck
import React, { useState, useEffect } from 'react';
import {
  Box,
  Chip,
  IconButton,
  Popover,
  TextField,
  List,
  ListItem,
  ListItemText,
  CircularProgress,
  Typography,
} from '@mui/material';
import { Add as AddIcon, Close as CloseIcon } from '@mui/icons-material';

const API_BASE_URL = process.env.REACT_APP_API_URL || '' + (window.location.hostname === 'localhost' ? 'http://localhost:4000' : 'https://agent-pm-tsbbb.ondigitalocean.app') + '';

interface ResourceMappingCellProps {
  projectKey: string;
  resourceType: 'slack' | 'notion' | 'github' | 'jira';
  values: string[];
  onChange: (newValues: string[]) => void;
}

export const ResourceMappingCell: React.FC<ResourceMappingCellProps> = ({
  projectKey,
  resourceType,
  values,
  onChange
}) => {
  const [anchorEl, setAnchorEl] = useState<HTMLButtonElement | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  const open = Boolean(anchorEl);

  const handleClick = (event: React.MouseEvent<HTMLButtonElement>) => {
    setAnchorEl(event.currentTarget);
    setSearchQuery('');
    setSearchResults([]);
  };

  const handleClose = () => {
    setAnchorEl(null);
    setSearchQuery('');
    setSearchResults([]);
  };

  const handleRemove = (valueToRemove: string) => {
    onChange(values.filter(v => v !== valueToRemove));
  };

  const handleAdd = (item: any) => {
    let newValue: string;

    if (resourceType === 'slack') {
      newValue = item.id;
    } else if (resourceType === 'notion') {
      newValue = item.id;
    } else if (resourceType === 'jira') {
      newValue = item.key;
    } else {
      newValue = item.name;
    }

    if (!values.includes(newValue)) {
      onChange([...values, newValue]);
    }

    handleClose();
  };

  useEffect(() => {
    if (!open || searchQuery.length < 2) {
      setSearchResults([]);
      return;
    }

    const searchEndpoint = {
      slack: '/api/search/slack-channels',
      notion: '/api/search/notion-pages',
      github: '/api/search/github-repos',
      jira: '/api/search/jira-projects'
    }[resourceType];

    setLoading(true);

    fetch(`${API_BASE_URL}${searchEndpoint}?q=${encodeURIComponent(searchQuery)}`)
      .then(res => res.json())
      .then(data => {
        if (data.success) {
          if (resourceType === 'slack') {
            setSearchResults(data.channels || []);
          } else if (resourceType === 'notion') {
            setSearchResults(data.pages || []);
          } else if (resourceType === 'jira') {
            setSearchResults(data.projects || []);
          } else {
            setSearchResults(data.repos || []);
          }
        }
        setLoading(false);
      })
      .catch(() => {
        setLoading(false);
      });
  }, [searchQuery, open, resourceType]);

  const getDisplayName = (value: string) => {
    if (resourceType === 'slack') {
      return `#${value.substring(0, 12)}...`;
    } else if (resourceType === 'notion') {
      return value.substring(0, 12) + '...';
    } else {
      return value;
    }
  };

  const getLabel = () => {
    switch (resourceType) {
      case 'slack': return 'Slack Channels';
      case 'notion': return 'Notion Pages';
      case 'github': return 'GitHub Repos';
      case 'jira': return 'Jira Projects';
    }
  };

  return (
    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, alignItems: 'center' }}>
      {values.map((value, idx) => (
        <Chip
          key={idx}
          label={getDisplayName(value)}
          size="small"
          onDelete={() => handleRemove(value)}
          sx={{ maxWidth: '120px' }}
        />
      ))}

      <IconButton
        size="small"
        onClick={handleClick}
        sx={{ width: 24, height: 24 }}
      >
        <AddIcon fontSize="small" />
      </IconButton>

      <Popover
        open={open}
        anchorEl={anchorEl}
        onClose={handleClose}
        anchorOrigin={{
          vertical: 'bottom',
          horizontal: 'left',
        }}
      >
        <Box sx={{ p: 2, width: 350, maxHeight: 400 }}>
          <Typography variant="subtitle2" gutterBottom>
            Add {getLabel()}
          </Typography>

          <TextField
            fullWidth
            size="small"
            placeholder={`Search ${getLabel().toLowerCase()}...`}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            autoFocus
            sx={{ mb: 1 }}
          />

          {loading && (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 2 }}>
              <CircularProgress size={24} />
            </Box>
          )}

          {searchQuery.length < 2 && !loading && (
            <Typography variant="caption" color="text.secondary">
              Type at least 2 characters to search
            </Typography>
          )}

          {!loading && searchQuery.length >= 2 && searchResults.length === 0 && (
            <Typography variant="caption" color="text.secondary">
              No results found
            </Typography>
          )}

          {!loading && searchResults.length > 0 && (
            <List dense sx={{ maxHeight: 300, overflow: 'auto' }}>
              {searchResults.map((item, idx) => {
                const displayText = resourceType === 'slack'
                  ? `#${item.name} ${item.is_private ? '🔒' : ''}`
                  : resourceType === 'notion'
                  ? item.title
                  : resourceType === 'jira'
                  ? `${item.key} - ${item.name}`
                  : item.name;

                const secondaryText = resourceType === 'slack'
                  ? `${item.num_members} members`
                  : undefined;

                return (
                  <ListItem
                    key={idx}
                    button
                    onClick={() => handleAdd(item)}
                  >
                    <ListItemText
                      primary={displayText}
                      secondary={secondaryText}
                      primaryTypographyProps={{ variant: 'body2' }}
                      secondaryTypographyProps={{ variant: 'caption' }}
                    />
                  </ListItem>
                );
              })}
            </List>
          )}
        </Box>
      </Popover>
    </Box>
  );
};
