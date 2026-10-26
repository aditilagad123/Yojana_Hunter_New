import { demoDocuments } from "@/data/demoData";
import { UserProfile } from "@/types/profile";
import { CitizenDocument } from "@/types/document";
import { ApplicationDraft } from "@/types/application";

const KEYS = {
  PROFILE: "yojana_user_profile",
  LANGUAGE: "yojana_user_lang",
  DOCUMENTS: "yojana_user_documents",
  DRAFT: "yojana_user_draft",
  ACTIVE_PROFILE_ID: "yojana_active_profile_id",
  PROFILES_LIST: "yojana_user_profiles_list",
};

export const emptyProfile: UserProfile = {
  relationship: "Self",
  name: "",
  occupation: "",
  age: 0,
  gender: "",
  state: "",
  district: "",
  annualIncome: "",
  education: "",
  category: "",
  fatherName: "",
  dateOfBirth: "",
  completenessPercent: 0,
  language: "en",
  isFarmer: false,
  isStudent: false,
  hasBusiness: false,
  isDisabled: false,
};

export const emptyApplicationDraft: ApplicationDraft = {
  id: "",
  schemeId: "",
  schemeName: "",
  applicantName: "",
  fatherName: "",
  dateOfBirth: "",
  education: "",
  familyIncome: "",
  state: "",
  district: "",
  status: "draft",
  createdAt: "",
};

function getActiveUserId(): number | string | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem("yojana_auth_user");
    if (raw) {
      const u = JSON.parse(raw);
      return u?.id || null;
    }
  } catch {
    return null;
  }
  return null;
}

export const getStoredProfile = (userId?: number | string): UserProfile => {
  if (typeof window === "undefined") return emptyProfile;
  try {
    const activeId = userId !== undefined ? userId : getActiveUserId();
    const key = activeId ? `${KEYS.PROFILE}_${activeId}` : KEYS.PROFILE;
    const data = localStorage.getItem(key);
    if (data) {
      const parsed = JSON.parse(data);
      // Ensure data strictly matches requested or active user
      if (activeId && parsed.userId && String(parsed.userId) !== String(activeId) && String(parsed.user_id) !== String(activeId)) {
        return emptyProfile;
      }
      return parsed;
    }
    return emptyProfile;
  } catch {
    return emptyProfile;
  }
};

export const saveStoredProfile = (profile: UserProfile, userId?: number | string): void => {
  if (typeof window === "undefined") return;
  try {
    const activeId = userId !== undefined ? userId : (profile.userId || profile.user_id || getActiveUserId());
    const key = activeId ? `${KEYS.PROFILE}_${activeId}` : KEYS.PROFILE;
    localStorage.setItem(key, JSON.stringify(profile));
    if (!activeId) {
      localStorage.setItem(KEYS.PROFILE, JSON.stringify(profile));
    } else {
      localStorage.removeItem(KEYS.PROFILE);
    }
  } catch (err) {
    console.error("Failed to save profile to storage", err);
  }
};

export const clearStoredProfile = (userId?: number | string): void => {
  if (typeof window === "undefined") return;
  try {
    const activeId = userId !== undefined ? userId : getActiveUserId();
    localStorage.removeItem(KEYS.PROFILE);
    localStorage.removeItem(KEYS.PROFILES_LIST);
    localStorage.removeItem(KEYS.ACTIVE_PROFILE_ID);
    if (activeId) {
      localStorage.removeItem(`${KEYS.PROFILE}_${activeId}`);
      localStorage.removeItem(`${KEYS.PROFILES_LIST}_${activeId}`);
      localStorage.removeItem(`${KEYS.ACTIVE_PROFILE_ID}_${activeId}`);
    }
    for (let i = localStorage.length - 1; i >= 0; i--) {
      const key = localStorage.key(i);
      if (key && (
        key.startsWith(KEYS.PROFILE) ||
        key.startsWith(KEYS.PROFILES_LIST) ||
        key.startsWith(KEYS.ACTIVE_PROFILE_ID)
      )) {
        localStorage.removeItem(key);
      }
    }
  } catch (err) {
    console.error("Failed to clear profile from storage", err);
  }
};

export const getActiveProfileId = (userId?: number | string): number | null => {
  if (typeof window === "undefined") return null;
  try {
    const activeId = userId !== undefined ? userId : getActiveUserId();
    const key = activeId ? `${KEYS.ACTIVE_PROFILE_ID}_${activeId}` : KEYS.ACTIVE_PROFILE_ID;
    const raw = localStorage.getItem(key);
    return raw ? parseInt(raw, 10) : null;
  } catch {
    return null;
  }
};

export const setActiveProfileId = (id: number | null, userId?: number | string): void => {
  if (typeof window === "undefined") return;
  try {
    const activeId = userId !== undefined ? userId : getActiveUserId();
    const key = activeId ? `${KEYS.ACTIVE_PROFILE_ID}_${activeId}` : KEYS.ACTIVE_PROFILE_ID;
    if (id !== null && id !== undefined) {
      localStorage.setItem(key, String(id));
    } else {
      localStorage.removeItem(key);
    }
    if (activeId) {
      localStorage.removeItem(KEYS.ACTIVE_PROFILE_ID);
    }
  } catch (err) {
    console.error("Failed to set active profile ID", err);
  }
};

export const getStoredProfilesList = (userId?: number | string): UserProfile[] => {
  if (typeof window === "undefined") return [];
  try {
    const activeId = userId !== undefined ? userId : getActiveUserId();
    const key = activeId ? `${KEYS.PROFILES_LIST}_${activeId}` : KEYS.PROFILES_LIST;
    const raw = localStorage.getItem(key);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed)) return parsed;
    }
  } catch {
    return [];
  }
  return [];
};

export const saveStoredProfilesList = (profiles: UserProfile[], userId?: number | string): void => {
  if (typeof window === "undefined") return;
  try {
    const activeId = userId !== undefined ? userId : getActiveUserId();
    const key = activeId ? `${KEYS.PROFILES_LIST}_${activeId}` : KEYS.PROFILES_LIST;
    localStorage.setItem(key, JSON.stringify(profiles));
    if (activeId) {
      localStorage.removeItem(KEYS.PROFILES_LIST);
    }
  } catch (err) {
    console.error("Failed to save profiles list", err);
  }
};

export const clearAllUserData = (): void => {
  if (typeof window === "undefined") return;
  try {
    const keysToRemove: string[] = [];
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (key && (
        key.startsWith("yojana_user_profile") ||
        key.startsWith("yojana_user_profiles_list") ||
        key.startsWith("yojana_active_profile_id") ||
        key.startsWith("yojana_user_documents") ||
        key.startsWith("yojana_user_draft") ||
        key === "yojana_auth_user" ||
        key === "yojana_auth_token"
      )) {
        keysToRemove.push(key);
      }
    }
    keysToRemove.forEach(k => localStorage.removeItem(k));
  } catch (err) {
    console.error("Failed to clear all user data", err);
  }
};

export const getStoredLanguage = (): "en" | "hi" | "mr" => {
  if (typeof window === "undefined") return "en";
  try {
    return (localStorage.getItem(KEYS.LANGUAGE) as "en" | "hi" | "mr") || "en";
  } catch {
    return "en";
  }
};

export const saveStoredLanguage = (lang: "en" | "hi" | "mr"): void => {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(KEYS.LANGUAGE, lang);
  } catch (err) {
    console.error("Failed to save language to storage", err);
  }
};

export const getStoredDocuments = (): CitizenDocument[] => {
  if (typeof window === "undefined") return [];
  try {
    const data = localStorage.getItem(KEYS.DOCUMENTS);
    return data ? JSON.parse(data) : [];
  } catch {
    return [];
  }
};

export const saveStoredDocuments = (docs: CitizenDocument[]): void => {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(KEYS.DOCUMENTS, JSON.stringify(docs));
  } catch (err) {
    console.error("Failed to save documents to storage", err);
  }
};

export const getStoredDraft = (): ApplicationDraft => {
  if (typeof window === "undefined") return emptyApplicationDraft;
  try {
    const data = localStorage.getItem(KEYS.DRAFT);
    return data ? JSON.parse(data) : emptyApplicationDraft;
  } catch {
    return emptyApplicationDraft;
  }
};

export const saveStoredDraft = (draft: ApplicationDraft): void => {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(KEYS.DRAFT, JSON.stringify(draft));
  } catch (err) {
    console.error("Failed to save draft to storage", err);
  }
};

export const clearStoredDraft = (): void => {
  if (typeof window === "undefined") return;
  try {
    localStorage.removeItem(KEYS.DRAFT);
  } catch (err) {
    console.error("Failed to clear draft from storage", err);
  }
};
