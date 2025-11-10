import { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';

/**
 * Hook to sync tab state with URL query parameters
 * @param paramName - The query parameter name (e.g., 'tab')
 * @param defaultValue - Default tab index if not in URL
 * @returns [tabValue, setTabValue] - Tab state and setter
 */
export function useTabWithUrl(paramName: string = 'tab', defaultValue: number = 0): [number, (value: number) => void] {
  const [searchParams, setSearchParams] = useSearchParams();

  // Initialize from URL or use default
  const initialTab = parseInt(searchParams.get(paramName) || String(defaultValue), 10);
  const [tabValue, setTabValueState] = useState(initialTab);

  // Sync URL when tab changes
  const setTabValue = (newValue: number) => {
    setTabValueState(newValue);
    const newParams = new URLSearchParams(searchParams);
    newParams.set(paramName, String(newValue));
    setSearchParams(newParams, { replace: true });
  };

  // Sync state when URL changes (e.g., browser back/forward)
  useEffect(() => {
    const urlTab = parseInt(searchParams.get(paramName) || String(defaultValue), 10);
    if (urlTab !== tabValue) {
      setTabValueState(urlTab);
    }
  }, [searchParams, paramName, defaultValue]);

  return [tabValue, setTabValue];
}
