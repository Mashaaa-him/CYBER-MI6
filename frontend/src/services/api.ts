import { auth } from '../lib/auth';
import { get } from 'svelte/store';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

interface FetchOptions extends RequestInit {
  requireAuth?: boolean;
}

export async function apiFetch<T>(endpoint: string, options: FetchOptions = {}): Promise<T> {
  const { requireAuth = true, headers, ...customConfig } = options;
  const currentAuth = get(auth);
  
  const config: RequestInit = {
    ...customConfig,
    headers: {
      'Content-Type': 'application/json',
      ...headers,
    },
  };

  if (requireAuth && currentAuth.token) {
    (config.headers as Record<string, string>)['Authorization'] = `Bearer ${currentAuth.token}`;
  } else {
    const apiKey = import.meta.env.VITE_API_KEY;
    if (apiKey) {
      (config.headers as Record<string, string>)['X-API-Key'] = apiKey;
    }
  }

  const response = await fetch(`${API_BASE}${endpoint}`, config);

  if (response.status === 401) {
    auth.logout();
    throw new Error('Session expired. Please log in again.');
  }

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `API request failed with status ${response.status}`);
  }

  return response.json();
}