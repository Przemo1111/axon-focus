const BACKEND_URL = process.env.EXPO_PUBLIC_BACKEND_URL || '';

export interface FocusSession {
  id: string;
  user_id: string;
  start_time: string;
  end_time: string | null;
  duration: number;
  date: string;
  completed: boolean;
}

export interface BlockedSite {
  id: string;
  user_id: string;
  site_url: string;
  created_at: string;
}

export interface TodayStats {
  date: string;
  total_minutes: number;
  session_count: number;
}

export interface WeeklyStats {
  date: string;
  day: string;
  minutes: number;
}

// Focus Session APIs
export const startFocusSession = async (userId: string, duration: number): Promise<FocusSession> => {
  const response = await fetch(`${BACKEND_URL}/api/focus-sessions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_id: userId, duration }),
  });
  if (!response.ok) throw new Error('Failed to start focus session');
  return response.json();
};

export const endFocusSession = async (sessionId: string, actualDuration: number): Promise<FocusSession> => {
  const response = await fetch(`${BACKEND_URL}/api/focus-sessions/${sessionId}/end`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ actual_duration: actualDuration }),
  });
  if (!response.ok) throw new Error('Failed to end focus session');
  return response.json();
};

export const getUserSessions = async (userId: string, days: number = 7): Promise<FocusSession[]> => {
  const response = await fetch(`${BACKEND_URL}/api/focus-sessions/${userId}?days=${days}`);
  if (!response.ok) throw new Error('Failed to get sessions');
  return response.json();
};

export const getTodayStats = async (userId: string): Promise<TodayStats> => {
  const response = await fetch(`${BACKEND_URL}/api/focus-sessions/${userId}/today`);
  if (!response.ok) throw new Error('Failed to get today stats');
  return response.json();
};

export const getWeeklyStats = async (userId: string): Promise<WeeklyStats[]> => {
  const response = await fetch(`${BACKEND_URL}/api/focus-sessions/${userId}/weekly`);
  if (!response.ok) throw new Error('Failed to get weekly stats');
  return response.json();
};

// Blocked Sites APIs
export const getBlockedSites = async (userId: string): Promise<BlockedSite[]> => {
  const response = await fetch(`${BACKEND_URL}/api/blocked-sites/${userId}`);
  if (!response.ok) throw new Error('Failed to get blocked sites');
  return response.json();
};

export const addBlockedSite = async (userId: string, siteUrl: string): Promise<BlockedSite> => {
  const response = await fetch(`${BACKEND_URL}/api/blocked-sites`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_id: userId, site_url: siteUrl }),
  });
  if (!response.ok) throw new Error('Failed to add blocked site');
  return response.json();
};

export const removeBlockedSite = async (siteId: string): Promise<void> => {
  const response = await fetch(`${BACKEND_URL}/api/blocked-sites/${siteId}`, {
    method: 'DELETE',
  });
  if (!response.ok) throw new Error('Failed to remove blocked site');
};
