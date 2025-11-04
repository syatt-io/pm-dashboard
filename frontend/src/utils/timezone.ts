/**
 * Timezone utilities for consistent EST/EDT formatting across the application.
 *
 * All dates in the UI should be displayed in EST/EDT timezone with explicit timezone label.
 */

/**
 * Convert a date to EST/EDT timezone and format it.
 *
 * @param date - Date string or Date object
 * @param options - Intl.DateTimeFormatOptions (optional)
 * @returns Formatted date string with EST/EDT timezone
 */
export function formatESTDateTime(
  date: string | Date | null | undefined,
  options?: Intl.DateTimeFormatOptions
): string {
  if (!date) return 'N/A';

  const dateObj = typeof date === 'string' ? new Date(date) : date;

  // Default options for datetime display
  const defaultOptions: Intl.DateTimeFormatOptions = {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    timeZone: 'America/New_York',
    timeZoneName: 'short', // Shows "EST" or "EDT"
    ...options,
  };

  return dateObj.toLocaleString('en-US', defaultOptions);
}

/**
 * Format date only (no time) in EST/EDT timezone.
 *
 * @param date - Date string or Date object
 * @returns Formatted date string like "January 15, 2025"
 */
export function formatESTDate(date: string | Date | null | undefined): string {
  if (!date) return 'N/A';

  const dateObj = typeof date === 'string' ? new Date(date) : date;

  return dateObj.toLocaleString('en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    timeZone: 'America/New_York',
  });
}

/**
 * Format date with short month in EST/EDT timezone.
 *
 * @param date - Date string or Date object
 * @returns Formatted date string like "Jan 15, 2025"
 */
export function formatESTDateShort(date: string | Date | null | undefined): string {
  if (!date) return 'N/A';

  const dateObj = typeof date === 'string' ? new Date(date) : date;

  return dateObj.toLocaleString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    timeZone: 'America/New_York',
  });
}

/**
 * Format time only in EST/EDT timezone.
 *
 * @param date - Date string or Date object
 * @returns Formatted time string like "2:30 PM EST"
 */
export function formatESTTime(date: string | Date | null | undefined): string {
  if (!date) return 'N/A';

  const dateObj = typeof date === 'string' ? new Date(date) : date;

  return dateObj.toLocaleString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    timeZone: 'America/New_York',
    timeZoneName: 'short',
  });
}

/**
 * Get current date/time in EST/EDT timezone.
 *
 * @returns Current Date object
 */
export function nowEST(): Date {
  return new Date();
}

/**
 * Format datetime for display in lists and tables.
 * Shows date and time with timezone.
 *
 * @param date - Date string or Date object
 * @returns Formatted string like "Jan 15, 2025, 2:30 PM EST"
 */
export function formatESTDateTimeShort(date: string | Date | null | undefined): string {
  if (!date) return 'N/A';

  const dateObj = typeof date === 'string' ? new Date(date) : date;

  return dateObj.toLocaleString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    timeZone: 'America/New_York',
    timeZoneName: 'short',
  });
}
