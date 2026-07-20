export type UserRole =
  | "business_user"
  | "reviewer"
  | "administrator"
  | "organization_owner";

export interface UserRead {
  id: string;
  workspace_id: string;
  email: string;
  full_name: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface CurrentUserResponse {
  user: UserRead;
  workspace_name: string;
  workspace_slug: string;
}

export interface LoginRequest {
  workspace_slug: string;
  email: string;
  password: string;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: "bearer";
  expires_in: number;
}

export interface LoginResponse extends TokenPair {
  user: UserRead;
}

export interface RefreshTokenRequest {
  refresh_token: string;
}

export type RefreshTokenResponse = TokenPair;

export interface ApiValidationError {
  loc?: Array<string | number>;
  msg?: string;
  type?: string;
}

export interface ApiErrorPayload {
  detail?: string | ApiValidationError[];
  message?: string;
}