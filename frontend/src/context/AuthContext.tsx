"use client";

import React, { createContext, useContext, useState, useEffect, ReactNode } from "react";
import { User, LoginCredentials, RegisterData } from "@/types/auth";
import { UserProfile } from "@/types/profile";
import { 
  login as apiLogin, 
  register as apiRegister, 
  logout as apiLogout, 
  getCurrentUser, 
  getStoredUser, 
  isLoggedIn as checkIsLoggedIn 
} from "@/services/authService";
import { 
  getStoredProfile, 
  saveStoredProfile, 
  getActiveProfileId, 
  setActiveProfileId,
  getStoredProfilesList,
  saveStoredProfilesList,
  emptyProfile,
  clearAllUserData
} from "@/lib/storage";
import { fetchProfiles, fetchProfile } from "@/services/profileService";

interface AuthContextType {
  user: User | null;
  profile: UserProfile | null;
  familyProfiles: UserProfile[];
  activeProfileId: number | null;
  loading: boolean;
  isAuthenticated: boolean;
  login: (credentials: LoginCredentials) => Promise<{ success: boolean; error?: string }>;
  register: (data: RegisterData) => Promise<{ success: boolean; error?: string }>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
  updateProfileState: (newProfile: UserProfile) => void;
  switchActiveProfile: (profileOrId: UserProfile | number) => Promise<void>;
  refreshFamilyProfiles: () => Promise<UserProfile[]>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [familyProfiles, setFamilyProfiles] = useState<UserProfile[]>([]);
  const [activeProfileId, setActiveProfileIdState] = useState<number | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  // Initialize from storage and verify session with backend
  useEffect(() => {
    async function initAuth() {
      if (checkIsLoggedIn()) {
        const stored = getStoredUser();

        if (stored && stored.role !== 'admin') {
          const storedProf = getStoredProfile(stored.id);
          const storedList = getStoredProfilesList(stored.id);
          const storedActiveId = getActiveProfileId(stored.id);

          setUser(stored);
          setProfile(storedProf);
          setFamilyProfiles(storedList);
          setActiveProfileIdState(storedActiveId);
        } else {
          setUser(null);
          setProfile(null);
          setFamilyProfiles([]);
        }

        try {
          const remote = await getCurrentUser();
          if (remote.user && remote.user.role !== 'admin') {
            setUser(remote.user);
            
            // Fetch all family profiles from backend
            const remoteProfiles = await fetchProfiles();
            if (remoteProfiles && remoteProfiles.length > 0) {
              setFamilyProfiles(remoteProfiles);
              saveStoredProfilesList(remoteProfiles, remote.user.id);

              // Find active profile
              const activeId = getActiveProfileId(remote.user.id);
              const active = (activeId && remoteProfiles.find(p => p.id === activeId))
                || remoteProfiles.find(p => p.relationship === "Self")
                || remoteProfiles[0];

              if (active) {
                setProfile(active);
                saveStoredProfile(active, remote.user.id);
                if (active.id) {
                  setActiveProfileId(active.id, remote.user.id);
                  setActiveProfileIdState(active.id);
                }
              }
            } else {
              setFamilyProfiles([]);
              saveStoredProfilesList([], remote.user.id);
              if (remote.profile) {
                setProfile(remote.profile);
                saveStoredProfile(remote.profile, remote.user.id);
              } else {
                const clean: UserProfile = {
                  ...emptyProfile,
                  userId: remote.user.id,
                  name: remote.user.name || remote.user.email?.split("@")[0] || "",
                  relationship: "Self",
                  isProfileSaved: false,
                  completenessPercent: 0
                };
                setProfile(clean);
                saveStoredProfile(clean, remote.user.id);
              }
              setActiveProfileId(null, remote.user.id);
              setActiveProfileIdState(null);
            }
          } else {
            setUser(null);
            setProfile(null);
            setFamilyProfiles([]);
          }
        } catch {
          // If network is offline, keep stored session
        }
      } else {
        setUser(null);
        setProfile(null);
        setFamilyProfiles([]);
      }
      setLoading(false);
    }

    initAuth();
  }, []);

  const refreshFamilyProfiles = async (): Promise<UserProfile[]> => {
    const list = await fetchProfiles();
    const activeUserId = user?.id;
    if (list && list.length > 0) {
      setFamilyProfiles(list);
      saveStoredProfilesList(list, activeUserId);

      // Verify active profile is still in list
      const currentActiveId = getActiveProfileId(activeUserId);
      const currentActive = list.find(p => p.id === currentActiveId) 
        || list.find(p => p.relationship === "Self") 
        || list[0];

      if (currentActive) {
        setProfile(currentActive);
        saveStoredProfile(currentActive, activeUserId);
        if (currentActive.id) {
          setActiveProfileId(currentActive.id, activeUserId);
          setActiveProfileIdState(currentActive.id);
        }
      }
      return list;
    } else {
      setFamilyProfiles([]);
      saveStoredProfilesList([], activeUserId);
      return [];
    }
  };

  const switchActiveProfile = async (profileOrId: UserProfile | number) => {
    let targetProfile: UserProfile | undefined;
    if (typeof profileOrId === "number") {
      targetProfile = familyProfiles.find(p => p.id === profileOrId);
      if (!targetProfile) {
        // Fetch from backend
        targetProfile = await fetchProfile(profileOrId);
      }
    } else {
      targetProfile = profileOrId;
    }

    if (targetProfile) {
      setProfile(targetProfile);
      saveStoredProfile(targetProfile, user?.id);
      if (targetProfile.id) {
        setActiveProfileId(targetProfile.id, user?.id);
        setActiveProfileIdState(targetProfile.id);
      }
    }
  };

  const login = async (credentials: LoginCredentials) => {
    setLoading(true);
    clearAllUserData();
    const res = await apiLogin(credentials);
    if (res.success && res.data) {
      if (res.data.user.role === 'admin') {
        setLoading(false);
        return { success: false, error: 'Administrator accounts must sign in via the Admin Portal.' };
      }
      setUser(res.data.user);
      if (res.data.profile) {
        setProfile(res.data.profile);
        saveStoredProfile(res.data.profile, res.data.user.id);
      } else {
        const clean: UserProfile = {
          ...emptyProfile,
          userId: res.data.user.id,
          name: res.data.user.name || res.data.user.email?.split("@")[0] || "",
          relationship: "Self",
          isProfileSaved: false,
          completenessPercent: 0
        };
        setProfile(clean);
        saveStoredProfile(clean, res.data.user.id);
      }
      await refreshFamilyProfiles();
      setLoading(false);
      return { success: true };
    }
    setLoading(false);
    return { success: false, error: res.error };
  };

  const register = async (data: RegisterData) => {
    setLoading(true);
    clearAllUserData();
    const res = await apiRegister(data);
    if (res.success && res.data) {
      setUser(res.data.user);
      const initialProfile: UserProfile = res.data.profile || {
        ...emptyProfile,
        userId: res.data.user.id,
        name: data.name || res.data.user.email?.split("@")[0] || "",
        relationship: "Self",
        isProfileSaved: false,
        completenessPercent: 0
      };
      setProfile(initialProfile);
      saveStoredProfile(initialProfile, res.data.user.id);
      setFamilyProfiles([]);
      saveStoredProfilesList([], res.data.user.id);
      setActiveProfileId(null, res.data.user.id);
      setActiveProfileIdState(null);
      setLoading(false);
      return { success: true };
    }
    setLoading(false);
    return { success: false, error: res.error };
  };

  const logout = async () => {
    setLoading(true);
    try {
      await apiLogout();
    } finally {
      clearAllUserData();
      setActiveProfileId(null);
      setUser(null);
      setProfile(null);
      setFamilyProfiles([]);
      setActiveProfileIdState(null);
      setLoading(false);
    }
  };

  const refreshUser = async () => {
    if (checkIsLoggedIn()) {
      const remote = await getCurrentUser();
      if (remote.user && remote.user.role !== 'admin') {
        setUser(remote.user);
        await refreshFamilyProfiles();
      }
    }
  };

  const updateProfileState = (newProfile: UserProfile) => {
    setProfile(newProfile);
    const activeUserId = user?.id || newProfile.userId || (newProfile as any).user_id;
    saveStoredProfile(newProfile, activeUserId);
    if (newProfile.id) {
      setActiveProfileId(newProfile.id, activeUserId);
      setActiveProfileIdState(newProfile.id);
    }
    // Update in familyProfiles list
    setFamilyProfiles(prev => {
      const idx = prev.findIndex(p => (newProfile.id && p.id === newProfile.id) || (p.relationship === newProfile.relationship && p.name === newProfile.name));
      if (idx >= 0) {
        const next = [...prev];
        next[idx] = newProfile;
        saveStoredProfilesList(next, activeUserId);
        return next;
      }
      const next = [...prev, newProfile];
      saveStoredProfilesList(next, activeUserId);
      return next;
    });
  };

  const isCitizenAuthenticated = Boolean(user && user.role !== "admin");

  return (
    <AuthContext.Provider
      value={{
        user,
        profile,
        familyProfiles,
        activeProfileId,
        loading,
        isAuthenticated: isCitizenAuthenticated,
        login,
        register,
        logout,
        refreshUser,
        updateProfileState,
        switchActiveProfile,
        refreshFamilyProfiles,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
};
