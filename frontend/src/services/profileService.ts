import { UserProfile, UserActivity, UserLevelInfo } from "@/types/profile";
import { 
  getStoredProfile, 
  saveStoredProfile, 
  getActiveProfileId, 
  setActiveProfileId, 
  getStoredProfilesList, 
  saveStoredProfilesList 
} from "@/lib/storage";
import { apiFetch, apiFetchDetailed } from "@/lib/api";

export { getActiveProfileId, setActiveProfileId };

export async function fetchProfiles(): Promise<UserProfile[]> {
  try {
    const res = await apiFetch<{ profiles: UserProfile[]; count: number }>("/profiles/all");
    if (res && Array.isArray(res.profiles)) {
      saveStoredProfilesList(res.profiles);
      return res.profiles;
    }
  } catch (err) {
    console.warn("fetchProfiles network error, falling back to local storage:", err);
  }
  return getStoredProfilesList();
}

export async function fetchProfile(profileId?: number): Promise<UserProfile> {
  const activeId = profileId || getActiveProfileId();
  const queryStr = activeId ? `?profile_id=${activeId}` : "";
  try {
    const backendProfile = await apiFetch<UserProfile>(`/profile${queryStr}`);
    if (backendProfile) {
      saveStoredProfile(backendProfile, backendProfile.userId || (backendProfile as any).user_id);
      return backendProfile;
    }
  } catch (err) {
    console.warn("fetchProfile network error, falling back to local storage:", err);
  }
  return getStoredProfile();
}

export async function createProfile(data: Partial<UserProfile>): Promise<UserProfile> {
  const payload = {
    relationship: data.relationship || "Other",
    name: data.name || data.fullName || "Family Member",
    ...data,
  };

  const res = await apiFetchDetailed<UserProfile>("/profiles", {
    method: "POST",
    body: JSON.stringify(payload),
  });

  if (res.data && (res.status === 200 || res.status === 201)) {
    if (res.data.id) {
      setActiveProfileId(res.data.id);
    }
    saveStoredProfile(res.data, res.data.userId || (res.data as any).user_id);
    fetchProfiles().catch(() => {});
    return res.data;
  }

  throw new Error(res.error || "Failed to create profile. Please try again.");
}

export async function updateProfile(data: Partial<UserProfile>, profileId?: number): Promise<UserProfile> {
  const targetId = profileId || data.id || getActiveProfileId();
  const current = getStoredProfile();
  const payload: UserProfile = { ...current, ...data };
  if (targetId) payload.id = targetId;

  // Calculate completeness
  const keyFields = [
    payload.name, payload.age, payload.gender, payload.occupation, payload.annualIncome,
    payload.state, payload.district, payload.education, payload.category
  ];
  const filled = keyFields.filter(f => f !== undefined && f !== null && String(f).trim() !== "").length;
  payload.completenessPercent = Math.round((filled / keyFields.length) * 100);

  const endpoint = targetId ? `/profiles/${targetId}` : "/profile";
  const res = await apiFetchDetailed<UserProfile>(endpoint, {
    method: "PUT",
    body: JSON.stringify(payload),
  });

  if (res.data && (res.status === 200 || res.status === 201)) {
    saveStoredProfile(res.data, res.data.userId || (res.data as any).user_id);
    fetchProfiles().catch(() => {});
    return res.data;
  }

  throw new Error(res.error || "Failed to save profile. Please check your inputs and try again.");
}

export async function deleteProfile(profileId: number): Promise<boolean> {
  try {
    await apiFetch<{ success: boolean }>(`/profiles/${profileId}`, {
      method: "DELETE",
    });
    const currentActive = getActiveProfileId();
    if (currentActive === profileId) {
      setActiveProfileId(null);
    }
    await fetchProfiles();
    return true;
  } catch (err) {
    console.error("deleteProfile failed:", err);
    return false;
  }
}

export async function fetchUserActivities(): Promise<UserActivity[]> {
  try {
    const res = await apiFetch<{ activities: UserActivity[]; count: number }>("/profile/activities");
    if (res && Array.isArray(res.activities)) {
      return res.activities;
    }
  } catch (err) {
    console.warn("fetchUserActivities network error:", err);
  }
  return [];
}

export async function fetchUserLevel(profileId?: number): Promise<UserLevelInfo | null> {
  try {
    const q = profileId ? `?profile_id=${profileId}` : "";
    const res = await apiFetch<UserLevelInfo>(`/profile/level${q}`);
    if (res && res.level) {
      return res;
    }
  } catch (err) {
    console.warn("fetchUserLevel network error:", err);
  }
  return null;
}
