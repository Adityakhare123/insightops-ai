import type {
  LoginResponse,
  TokenPair,
  UserRead,
} from "../types/auth";

const AUTH_STORAGE_KEY = "insightops.auth.session";

export interface StoredAuthSession {
  accessToken: string;
  refreshToken: string;
  tokenType: "bearer";
  expiresIn: number;
  expiresAt: number;
  user: UserRead | null;
}

function canUseLocalStorage(): boolean {
  return typeof window !== "undefined"
    && typeof window.localStorage !== "undefined";
}

function readStoredSession(): StoredAuthSession | null {
  if (!canUseLocalStorage()) {
    return null;
  }

  const storedValue = window.localStorage.getItem(
    AUTH_STORAGE_KEY,
  );

  if (!storedValue) {
    return null;
  }

  try {
    const parsedValue = JSON.parse(
      storedValue,
    ) as Partial<StoredAuthSession>;

    if (
      typeof parsedValue.accessToken !== "string"
      || typeof parsedValue.refreshToken !== "string"
      || parsedValue.tokenType !== "bearer"
      || typeof parsedValue.expiresIn !== "number"
      || typeof parsedValue.expiresAt !== "number"
    ) {
      clearAuthSession();
      return null;
    }

    return {
      accessToken: parsedValue.accessToken,
      refreshToken: parsedValue.refreshToken,
      tokenType: parsedValue.tokenType,
      expiresIn: parsedValue.expiresIn,
      expiresAt: parsedValue.expiresAt,
      user: parsedValue.user ?? null,
    };
  } catch {
    clearAuthSession();
    return null;
  }
}

function writeStoredSession(
  session: StoredAuthSession,
): void {
  if (!canUseLocalStorage()) {
    return;
  }

  window.localStorage.setItem(
    AUTH_STORAGE_KEY,
    JSON.stringify(session),
  );
}

function calculateExpirationTime(
  expiresInSeconds: number,
): number {
  return Date.now() + expiresInSeconds * 1000;
}

export function saveLoginSession(
  loginResponse: LoginResponse,
): void {
  writeStoredSession({
    accessToken: loginResponse.access_token,
    refreshToken: loginResponse.refresh_token,
    tokenType: loginResponse.token_type,
    expiresIn: loginResponse.expires_in,
    expiresAt: calculateExpirationTime(
      loginResponse.expires_in,
    ),
    user: loginResponse.user,
  });
}

export function updateStoredTokenPair(
  tokenPair: TokenPair,
): void {
  const currentSession = readStoredSession();

  writeStoredSession({
    accessToken: tokenPair.access_token,
    refreshToken: tokenPair.refresh_token,
    tokenType: tokenPair.token_type,
    expiresIn: tokenPair.expires_in,
    expiresAt: calculateExpirationTime(
      tokenPair.expires_in,
    ),
    user: currentSession?.user ?? null,
  });
}

export function updateStoredUser(
  user: UserRead,
): void {
  const currentSession = readStoredSession();

  if (!currentSession) {
    return;
  }

  writeStoredSession({
    ...currentSession,
    user,
  });
}

export function getAuthSession(): StoredAuthSession | null {
  return readStoredSession();
}

export function getAccessToken(): string | null {
  return readStoredSession()?.accessToken ?? null;
}

export function getRefreshToken(): string | null {
  return readStoredSession()?.refreshToken ?? null;
}

export function getStoredUser(): UserRead | null {
  return readStoredSession()?.user ?? null;
}

export function hasStoredSession(): boolean {
  const session = readStoredSession();

  return Boolean(
    session?.accessToken
    && session.refreshToken,
  );
}

export function clearAuthSession(): void {
  if (!canUseLocalStorage()) {
    return;
  }

  window.localStorage.removeItem(
    AUTH_STORAGE_KEY,
  );
}