import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import {
  clearAuthSession,
  hasStoredSession,
  saveLoginSession,
  updateStoredUser,
} from "../../api/tokenStorage";

import {
  getCurrentUser,
  loginUser,
} from "./authApi";

import type {
  CurrentUserResponse,
  LoginRequest,
  UserRead,
} from "../../types/auth";


interface AuthContextValue {
  user: UserRead | null;
  workspaceName: string | null;
  workspaceSlug: string | null;
  isAuthenticated: boolean;
  isInitializing: boolean;
  login: (
    credentials: LoginRequest,
  ) => Promise<void>;
  logout: () => void;
  refreshCurrentUser: () => Promise<void>;
}


interface AuthProviderProps {
  children: ReactNode;
}


const AuthContext = createContext<
  AuthContextValue | undefined
>(undefined);


export function AuthProvider({
  children,
}: AuthProviderProps) {
  const [user, setUser] =
    useState<UserRead | null>(null);

  const [workspaceName, setWorkspaceName] =
    useState<string | null>(null);

  const [workspaceSlug, setWorkspaceSlug] =
    useState<string | null>(null);

  const [isInitializing, setIsInitializing] =
    useState(true);


  const applyCurrentUserResponse = useCallback(
    (
      response: CurrentUserResponse,
    ): void => {
      setUser(response.user);
      setWorkspaceName(response.workspace_name);
      setWorkspaceSlug(response.workspace_slug);

      updateStoredUser(response.user);
    },
    [],
  );


  const clearAuthenticationState =
    useCallback((): void => {
      clearAuthSession();

      setUser(null);
      setWorkspaceName(null);
      setWorkspaceSlug(null);
    }, []);


  const refreshCurrentUser =
    useCallback(async (): Promise<void> => {
      const currentUserResponse =
        await getCurrentUser();

      applyCurrentUserResponse(
        currentUserResponse,
      );
    }, [applyCurrentUserResponse]);


  const login = useCallback(
    async (
      credentials: LoginRequest,
    ): Promise<void> => {
      const loginResponse =
        await loginUser(credentials);

      saveLoginSession(loginResponse);

      try {
        const currentUserResponse =
          await getCurrentUser();

        applyCurrentUserResponse(
          currentUserResponse,
        );
      } catch (error) {
        clearAuthenticationState();
        throw error;
      }
    },
    [
      applyCurrentUserResponse,
      clearAuthenticationState,
    ],
  );


  const logout = useCallback((): void => {
    clearAuthenticationState();
  }, [clearAuthenticationState]);


  useEffect(() => {
    let isCancelled = false;

    async function initializeAuthentication():
    Promise<void> {
      if (!hasStoredSession()) {
        if (!isCancelled) {
          setIsInitializing(false);
        }

        return;
      }

      try {
        const currentUserResponse =
          await getCurrentUser();

        if (!isCancelled) {
          applyCurrentUserResponse(
            currentUserResponse,
          );
        }
      } catch {
        if (!isCancelled) {
          clearAuthenticationState();
        }
      } finally {
        if (!isCancelled) {
          setIsInitializing(false);
        }
      }
    }

    void initializeAuthentication();

    return () => {
      isCancelled = true;
    };
  }, [
    applyCurrentUserResponse,
    clearAuthenticationState,
  ]);


  const contextValue = useMemo<AuthContextValue>(
    () => ({
      user,
      workspaceName,
      workspaceSlug,
      isAuthenticated: user !== null,
      isInitializing,
      login,
      logout,
      refreshCurrentUser,
    }),
    [
      user,
      workspaceName,
      workspaceSlug,
      isInitializing,
      login,
      logout,
      refreshCurrentUser,
    ],
  );


  return (
    <AuthContext.Provider value={contextValue}>
      {children}
    </AuthContext.Provider>
  );
}


export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);

  if (context === undefined) {
    throw new Error(
      "useAuth must be used inside an AuthProvider.",
    );
  }

  return context;
}