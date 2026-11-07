export interface UserProfile {
  id: string;
  username: string;
  role: 'admin' | 'analyst';
  permissions: string[];
  status: 'active' | 'disabled';
  lastLogin?: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: UserProfile;
}