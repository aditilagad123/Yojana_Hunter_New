import { demoSchemes } from "@/data/demoData";
import { Scheme, EligibilityStatus } from "@/types/scheme";
import { UserProfile } from "@/types/profile";
import { getStoredProfile } from "@/lib/storage";
import { apiFetch, apiFetchDetailed } from "@/lib/api";

export function deduplicateSchemes(schemes: Scheme[]): Scheme[] {
  const seen = new Set<string>();
  const out: Scheme[] = [];
  for (const s of schemes) {
    const key = (s.id || (s as any).slug || (s as any).numericId || s.name || "").toString().toLowerCase().trim();
    const norm = (s.name || "").toLowerCase().replace(/[^a-z0-9]/g, "");
    if (!key || seen.has(key) || (norm && seen.has(norm))) continue;
    seen.add(key);
    if (norm) seen.add(norm);
    out.push(s);
  }
  return out;
}

export function isSchemeEligibleForGender(
  schemeGender?: string, 
  schemeName?: string, 
  userGender?: string
): boolean {
  if (!userGender) return true;
  const u = userGender.toLowerCase().trim();
  const isMale = ["male", "man", "men", "boy", "boys", "purush"].includes(u);
  const isFemale = ["female", "woman", "women", "girl", "girls", "mahila", "kanya", "ladki"].includes(u);
  if (!isMale && !isFemale) return true;

  const rawG = (schemeGender || "All").toLowerCase().trim();
  const name = (schemeName || "").toLowerCase().trim();

  let sGender = "all";
  if (["female", "female only", "women", "girl", "girls", "mahila", "kanya", "ladki"].includes(rawG)) {
    sGender = "female";
  } else if (["male", "male only", "men", "boy", "boys", "purush"].includes(rawG)) {
    sGender = "male";
  } else if (rawG === "all" || rawG === "any" || rawG === "unrestricted" || rawG === "both" || !rawG) {
    if (name.includes("for girl students") || name.includes("ladki bahin") || name.includes("matru vandana") || name.includes("for girls only")) {
      sGender = "female";
    } else if (name.includes("boys only") || name.includes("male only") || name.includes("for boys only")) {
      sGender = "male";
    } else {
      sGender = "all";
    }
  }

  if (sGender === "all") return true;
  if (isMale && sGender === "female") return false;
  if (isFemale && sGender === "male") return false;
  return true;
}

export async function getSchemes(
  filter?: EligibilityStatus | "all", 
  query?: string,
  category?: string,
  state?: string,
  profileOverride?: Partial<UserProfile> | Record<string, any>
): Promise<Scheme[]> {
  try {
    const params = new URLSearchParams();
    if (filter && filter !== "all") params.set("filter", filter);
    if (query && query.trim() !== "") params.set("q", query.trim());
    if (category && category !== "all") params.set("category", category);
    if (state && state !== "all") params.set("state", state);

    const active = profileOverride !== undefined ? profileOverride : getStoredProfile();
    if (active) {
      if (active.id) params.set("profile_id", String(active.id));
      if (active.relationship) params.set("relationship", active.relationship);
      if (active.occupation) params.set("profile_occupation", active.occupation);
      if (active.state) params.set("profile_state", active.state);
      if (active.age !== undefined && active.age !== null) params.set("profile_age", String(active.age));
      const inc = active.annualIncome || (active as any).annual_income;
      if (inc) params.set("profile_income", String(inc));
      if (active.education) params.set("profile_education", active.education);
      if (active.category) params.set("profile_category", active.category);
      if (active.gender) params.set("profile_gender", active.gender);

      const occLower = (active.occupation || "").toLowerCase().trim();
      const isStudentOcc = occLower.includes("student");
      const isFarmerOcc = occLower.includes("farmer") || occLower.includes("kisan") || occLower.includes("krishi") || occLower.includes("agri") || occLower.includes("cultivat");
      const isBizOcc = occLower.includes("business") || occLower.includes("self-employed") || occLower.includes("shop") || occLower.includes("entrepreneur") || occLower.includes("artisan") || occLower.includes("trader") || occLower.includes("merchant");

      let isFarmer = Boolean(active.isFarmer ?? (active as any).is_farmer);
      let isStudent = Boolean(active.isStudent ?? (active as any).is_student);
      let hasBusiness = Boolean(active.hasBusiness ?? (active as any).has_business);

      if (isStudentOcc && !isFarmerOcc) {
        isStudent = true;
        isFarmer = false;
      } else if (isFarmerOcc && !isStudentOcc) {
        isFarmer = true;
        isStudent = false;
      } else if (occLower) {
        // Custom occupation (e.g. Clerk, Teacher, Housewife, Shopkeeper, etc.)
        isStudent = false;
        const land = Number(active.landHoldingAcres || (active as any).land_holding_acres || 0);
        if (land <= 0) {
          isFarmer = false;
        }
        if (isBizOcc) {
          hasBusiness = true;
        }
      }

      params.set("profile_is_farmer", String(isFarmer));
      params.set("profile_is_student", String(isStudent));
      params.set("profile_has_business", String(hasBusiness));

      if (active.isDisabled !== undefined || (active as any).is_disabled !== undefined) {
        params.set("profile_is_disabled", String(Boolean(active.isDisabled ?? (active as any).is_disabled)));
      }
      const isGovt = occLower.includes("government") || occLower.includes("govt") || occLower.includes("sarkari") || Boolean(active.isGovtEmployee ?? (active as any).is_govt_employee);
      if (isGovt) {
        params.set("profile_is_govt_employee", "true");
      }
      const emp = active.employmentStatus || (active as any).employment_status;
      if (emp) params.set("profile_employment_status", String(emp));
    }


    const queryStr = params.toString() ? `?${params.toString()}` : "";
    const backendData = await apiFetch<any>(`/schemes${queryStr}`);
    
    let all: Scheme[] = [];
    if (Array.isArray(backendData)) {
      all = backendData;
    } else if (backendData && Array.isArray(backendData.schemes)) {
      all = backendData.schemes;
    } else {
      all = active?.occupation ? [] : demoSchemes;
    }

    let result = [...all];

    // Client-side fallback gender filtering
    if (active?.gender) {
      result = result.filter((s) => isSchemeEligibleForGender(s.gender, s.name, active.gender));
    }

    if (filter && filter !== "all") {
      result = result.filter((s) => s.eligibilityStatus === filter || (s as any).legacyEligibilityStatus === filter);
    }

    if (query && query.trim() !== "") {
      const q = query.toLowerCase();
      result = result.filter(
        (s) =>
          s.name.toLowerCase().includes(q) ||
          s.shortDescription.toLowerCase().includes(q) ||
          s.category.toLowerCase().includes(q) ||
          (s.benefits && s.benefits.toLowerCase().includes(q))
      );
    }

    return deduplicateSchemes(result);
  } catch {
    const active = profileOverride !== undefined ? profileOverride : getStoredProfile();
    let fallback = active?.occupation ? [] : demoSchemes;
    if (active?.gender) {
      const uGender = active.gender.toLowerCase().trim();
      const isMale = ["male", "man", "men", "boy"].includes(uGender);
      const isFemale = ["female", "woman", "women", "girl"].includes(uGender);

      fallback = fallback.filter((s) => {
        const sGender = (s.gender || "All").toLowerCase().trim();
        const sCat = (s.category || "").toLowerCase().trim();
        const sName = (s.name || "").toLowerCase().trim();
        const isWomenScheme = sGender === "female" || sGender === "female only" ||
          sCat.includes("women") || sName.includes("women") || sName.includes("girl") || sName.includes("ladki") || sName.includes("kanya");

        if (isMale && isWomenScheme) return false;
        if (isFemale && (sGender === "male" || sGender === "male only")) return false;
        return true;
      });
    }
    return fallback;
  }
}

export interface SchemesCatalogResult {
  schemes: Scheme[];
  totalMatchingCount: number;
  accessibleCount: number;
  isPremium: boolean;
  freeLimit: number;
  hasMore: boolean;
  subscription?: any;
  counts?: {
    total_in_db: number;
    all: number;
    eligible: number;
    possibly_eligible: number;
    not_eligible: number;
    applications_closed: number;
  };
}

export async function getSchemesCatalog(
  filter?: EligibilityStatus | "all", 
  query?: string,
  category?: string,
  state?: string,
  profileOverride?: Partial<UserProfile> | Record<string, any>
): Promise<SchemesCatalogResult> {
  try {
    const params = new URLSearchParams();
    if (filter && filter !== "all") {
      params.set("filter", filter);
      if (filter === "not_eligible" || filter === "applications_closed") {
        params.set("include_ineligible", "true");
      }
    }
    if (query && query.trim() !== "") params.set("q", query.trim());
    if (category && category !== "all") params.set("category", category);
    if (state && state !== "all") params.set("state", state);

    const active = profileOverride !== undefined ? profileOverride : getStoredProfile();
    if (active) {
      if (active.id) params.set("profile_id", String(active.id));
      const validRelationships = ["self", "father", "mother", "spouse", "child", "son", "daughter", "brother", "sister", "grandfather", "grandmother", "other"];
      if (active.relationship && validRelationships.includes(active.relationship.toLowerCase())) {
        params.set("relationship", active.relationship);
      }
      if (active.occupation) params.set("profile_occupation", active.occupation);
      if (active.state) params.set("profile_state", active.state);
      if (active.age !== undefined && active.age !== null) params.set("profile_age", String(active.age));
      const inc = active.annualIncome || (active as any).annual_income;
      if (inc) params.set("profile_income", String(inc));
      if (active.education) params.set("profile_education", active.education);
      if (active.category) params.set("profile_category", active.category);
      if (active.gender) params.set("profile_gender", active.gender);

      const occLower = (active.occupation || "").toLowerCase().trim();
      const isStudentOcc = occLower.includes("student");
      const isFarmerOcc = occLower.includes("farmer") || occLower.includes("kisan") || occLower.includes("krishi") || occLower.includes("agri") || occLower.includes("cultivat");
      const isBizOcc = occLower.includes("business") || occLower.includes("self-employed") || occLower.includes("shop") || occLower.includes("entrepreneur") || occLower.includes("artisan") || occLower.includes("trader") || occLower.includes("merchant");

      let isFarmer = Boolean(active.isFarmer ?? (active as any).is_farmer);
      let isStudent = Boolean(active.isStudent ?? (active as any).is_student);
      let hasBusiness = Boolean(active.hasBusiness ?? (active as any).has_business);

      if (isStudentOcc && !isFarmerOcc) {
        isStudent = true;
        isFarmer = false;
      } else if (isFarmerOcc && !isStudentOcc) {
        isFarmer = true;
        isStudent = false;
      } else if (occLower) {
        isStudent = false;
        const land = Number(active.landHoldingAcres || (active as any).land_holding_acres || 0);
        if (land <= 0) isFarmer = false;
        if (isBizOcc) hasBusiness = true;
      }

      params.set("profile_is_farmer", String(isFarmer));
      params.set("profile_is_student", String(isStudent));
      params.set("profile_has_business", String(hasBusiness));

      if (active.isDisabled !== undefined || (active as any).is_disabled !== undefined) {
        params.set("profile_is_disabled", String(Boolean(active.isDisabled ?? (active as any).is_disabled)));
      }
      const isGovt = occLower.includes("government") || occLower.includes("govt") || occLower.includes("sarkari") || Boolean(active.isGovtEmployee ?? (active as any).is_govt_employee);
      if (isGovt) {
        params.set("profile_is_govt_employee", "true");
      }
      const emp = active.employmentStatus || (active as any).employment_status;
      if (emp) params.set("profile_employment_status", String(emp));
    }

    const queryStr = params.toString() ? `?${params.toString()}` : "";
    const backendData = await apiFetch<any>(`/schemes${queryStr}`);

    let schemesList: Scheme[] = [];
    let totalMatchingCount = 0;
    let isPremium = false;
    let freeLimit = 5;
    let subscription = null;

    if (Array.isArray(backendData)) {
      schemesList = backendData;
      totalMatchingCount = backendData.length;
    } else if (backendData && Array.isArray(backendData.schemes)) {
      schemesList = backendData.schemes;
      totalMatchingCount = typeof backendData.total_matching_count === "number" 
        ? backendData.total_matching_count 
        : (backendData.total_count ?? backendData.schemes.length);
      isPremium = Boolean(backendData.is_premium);
      freeLimit = backendData.free_limit || 5;
      subscription = backendData.subscription;
    } else {
      schemesList = active?.occupation ? [] : demoSchemes;
      totalMatchingCount = schemesList.length;
    }

    let filtered = [...schemesList];

    // Client-side fallback gender filtering
    if (active?.gender) {
      filtered = filtered.filter((s) => isSchemeEligibleForGender(s.gender, s.name, active.gender));
    }

    if (filter && filter !== "all") {
      filtered = filtered.filter((s) => s.eligibilityStatus === filter || (s as any).legacyEligibilityStatus === filter);
    }

    if (query && query.trim() !== "") {
      const q = query.toLowerCase();
      filtered = filtered.filter(
        (s) =>
          s.name.toLowerCase().includes(q) ||
          s.shortDescription.toLowerCase().includes(q) ||
          s.category.toLowerCase().includes(q) ||
          (s.benefits && s.benefits.toLowerCase().includes(q))
      );
    }

    const dedupedSchemes = deduplicateSchemes(filtered);
    return {
      schemes: dedupedSchemes,
      totalMatchingCount: Math.max(totalMatchingCount, dedupedSchemes.length),
      accessibleCount: dedupedSchemes.length,
      isPremium,
      freeLimit,
      hasMore: !isPremium && totalMatchingCount > dedupedSchemes.length,
      subscription,
      counts: backendData?.counts
    };
  } catch {
    const list = await getSchemes(filter, query, category, state, profileOverride);
    return {
      schemes: list,
      totalMatchingCount: list.length,
      accessibleCount: list.length,
      isPremium: false,
      freeLimit: 5,
      hasMore: false,
      subscription: null
    };
  }
}


export async function getSchemeById(
  id: string,
  profileOverride?: Partial<UserProfile> | Record<string, any>
): Promise<Scheme | undefined> {
  try {
    const params = new URLSearchParams();
    const active = profileOverride !== undefined ? profileOverride : getStoredProfile();
    if (active) {
      if (active.occupation) params.set("profile_occupation", active.occupation);
      if (active.state) params.set("profile_state", active.state);
      if (active.age !== undefined && active.age !== null) params.set("profile_age", String(active.age));
      const inc = active.annualIncome || (active as any).annual_income;
      if (inc) params.set("profile_income", String(inc));
      if (active.education) params.set("profile_education", active.education);
      if (active.category) params.set("profile_category", active.category);
      if (active.gender) params.set("profile_gender", active.gender);

      const occLower = (active.occupation || "").toLowerCase().trim();
      const isStudentOcc = occLower.includes("student");
      const isFarmerOcc = occLower.includes("farmer") || occLower.includes("kisan") || occLower.includes("krishi") || occLower.includes("agri") || occLower.includes("cultivat");
      const isBizOcc = occLower.includes("business") || occLower.includes("self-employed") || occLower.includes("shop") || occLower.includes("entrepreneur") || occLower.includes("artisan") || occLower.includes("trader") || occLower.includes("merchant");

      let isFarmer = Boolean(active.isFarmer ?? (active as any).is_farmer);
      let isStudent = Boolean(active.isStudent ?? (active as any).is_student);
      let hasBusiness = Boolean(active.hasBusiness ?? (active as any).has_business);

      if (isStudentOcc && !isFarmerOcc) {
        isStudent = true;
        isFarmer = false;
      } else if (isFarmerOcc && !isStudentOcc) {
        isFarmer = true;
        isStudent = false;
      } else if (occLower) {
        isStudent = false;
        const land = Number(active.landHoldingAcres || (active as any).land_holding_acres || 0);
        if (land <= 0) isFarmer = false;
        if (isBizOcc) hasBusiness = true;
      }

      params.set("profile_is_farmer", String(isFarmer));
      params.set("profile_is_student", String(isStudent));
      params.set("profile_has_business", String(hasBusiness));

      if (active.isDisabled !== undefined || (active as any).is_disabled !== undefined) {
        params.set("profile_is_disabled", String(Boolean(active.isDisabled ?? (active as any).is_disabled)));
      }
      const emp = active.employmentStatus || (active as any).employment_status;
      if (emp) params.set("profile_employment_status", String(emp));
    }

    const queryStr = params.toString() ? `?${params.toString()}` : "";
    const detailed = await apiFetchDetailed<any>(`/schemes/${id}${queryStr}`);

    if (detailed.status === 403 && detailed.data && (detailed.data as any).is_locked) {
      const lockData = detailed.data as any;
      return {
        id: id,
        slug: id,
        name: lockData.scheme_name || "Premium Locked Scheme",
        shortDescription: lockData.message || "Upgrade to Yojana Hunter Premium to unlock full details for this scheme.",
        description: lockData.message || "This scheme details are locked under the free tier limit.",
        category: "Premium Restricted",
        department: "Government of India",
        level: "Central / State Scheme",
        eligibilityStatus: "eligible",
        matchScore: 90,
        benefit: "Detailed scheme guidelines & direct application link",
        officialUrl: "#",
        lastVerifiedDate: "Verified",
        criteria: [],
        requiredDocuments: [],
        isLocked: true,
        lockMessage: lockData.message,
        rank: lockData.rank
      };
    }

    if (detailed.data) return detailed.data as Scheme;
    return demoSchemes.find((s) => s.id === id || s.slug === id);
  } catch {
    return demoSchemes.find((s) => s.id === id || s.slug === id);
  }
}

export async function matchSchemesWithProfile(
  profilePayload: Record<string, any>
): Promise<{
  total_evaluated: number;
  eligible_count: number;
  possibly_eligible_count: number;
  not_eligible_count: number;
  applications_closed_count: number;
  schemes: Scheme[];
}> {
  try {
    const payload = { ...profilePayload };
    const occ = String(payload.occupation || "").trim();
    if (occ) {
      const occLower = occ.toLowerCase();
      const isStudentOcc = occLower.includes("student");
      const isFarmerOcc = occLower.includes("farmer") || occLower.includes("kisan") || occLower.includes("krishi") || occLower.includes("agri") || occLower.includes("cultivat");
      const isBizOcc = occLower.includes("business") || occLower.includes("self-employed") || occLower.includes("shop") || occLower.includes("entrepreneur") || occLower.includes("artisan") || occLower.includes("trader") || occLower.includes("merchant");

      if (isStudentOcc && !isFarmerOcc) {
        payload.is_student = true;
        payload.isStudent = true;
        payload.is_farmer = false;
        payload.isFarmer = false;
      } else if (isFarmerOcc && !isStudentOcc) {
        payload.is_farmer = true;
        payload.isFarmer = true;
        payload.is_student = false;
        payload.isStudent = false;
      } else if (occLower) {
        payload.is_student = false;
        payload.isStudent = false;
        const land = Number(payload.land_holding_acres || payload.landHoldingAcres || 0);
        if (land <= 0) {
          payload.is_farmer = false;
          payload.isFarmer = false;
        }
        if (isBizOcc) {
          payload.has_business = true;
          payload.hasBusiness = true;
        }
      }
    }

    const res = await apiFetch<any>("/schemes/match", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    if (res && Array.isArray(res.schemes)) {
      return res;
    }
    return {
      total_evaluated: 0,
      eligible_count: 0,
      possibly_eligible_count: 0,
      not_eligible_count: 0,
      applications_closed_count: 0,
      schemes: [],
    };
  } catch {
    return {
      total_evaluated: 0,
      eligible_count: 0,
      possibly_eligible_count: 0,
      not_eligible_count: 0,
      applications_closed_count: 0,
      schemes: [],
    };
  }
}

export interface SyncResponse {
  success: boolean;
  schemes_attempted: number;
  schemes_fetched: number;
  schemes_verified: number;
  schemes_inserted: number;
  schemes_updated: number;
  schemes_skipped_or_failed: number;
  demo_profile_matches?: {
    eligible_count: number;
    possibly_eligible_count: number;
    not_eligible_count: number;
    applications_closed_count: number;
    total_evaluated: number;
  };
  last_sync_time?: string;
  last_sync_display?: string;
  source_statuses?: Array<{
    slug: string;
    name: string;
    url: string;
    status: string;
    latency_ms: number;
    application_url?: string;
  }>;
  failures?: any[];
  error?: string;
}

export async function syncSchemes(profilePayload?: Record<string, any>): Promise<SyncResponse> {
  try {
    const res = await apiFetch<SyncResponse>("/schemes/sync", {
      method: "POST",
      body: JSON.stringify({ profile: profilePayload }),
    });
    return res || {
      success: false,
      schemes_attempted: 10,
      schemes_fetched: 0,
      schemes_verified: 0,
      schemes_inserted: 0,
      schemes_updated: 0,
      schemes_skipped_or_failed: 10,
      error: "No response from synchronization backend",
    };
  } catch (err: any) {
    return {
      success: false,
      schemes_attempted: 10,
      schemes_fetched: 0,
      schemes_verified: 0,
      schemes_inserted: 0,
      schemes_updated: 0,
      schemes_skipped_or_failed: 10,
      error: err?.message || "Failed to trigger scheme synchronization",
    };
  }
}

export async function getSyncStatus(): Promise<{
  total_schemes: number;
  verified_schemes: number;
  last_sync_time: string | null;
  last_verified_date: string;
  status: string;
}> {
  try {
    const res = await apiFetch<any>("/schemes/sync-status");
    if (res) return res;
    return {
      total_schemes: 10,
      verified_schemes: 10,
      last_sync_time: null,
      last_verified_date: "13 Oct 2026",
      status: "ready",
    };
  } catch {
    return {
      total_schemes: 10,
      verified_schemes: 10,
      last_sync_time: null,
      last_verified_date: "13 Oct 2026",
      status: "ready",
    };
  }
}

export async function getRecommendations(params?: {
  limit?: number;
  state?: string;
  occupation?: string;
}): Promise<{
  profile_evaluated: Record<string, any>;
  total_evaluated: number;
  recommendations_count: number;
  recommendations: Scheme[];
}> {
  try {
    const query = new URLSearchParams();
    if (params?.limit) query.set("limit", String(params.limit));
    if (params?.state) query.set("state", params.state);
    if (params?.occupation) query.set("occupation", params.occupation);

    const qs = query.toString() ? `?${query.toString()}` : "";
    const res = await apiFetch<any>(`/schemes/recommendations${qs}`);
    if (res && Array.isArray(res.recommendations)) return res;
    return {
      profile_evaluated: {},
      total_evaluated: 0,
      recommendations_count: 0,
      recommendations: [],
    };
  } catch {
    return {
      profile_evaluated: {},
      total_evaluated: 0,
      recommendations_count: 0,
      recommendations: [],
    };
  }
}

export interface SchemeExplanationResult {
  success: boolean;
  explanation: string;
  mode: string;
  citations: Array<{
    source_title: string;
    source_url: string;
    excerpt?: string;
  }>;
  grounding_chunks?: any[];
  error?: string | null;
}

export async function explainScheme(
  schemeId: string,
  profile?: Record<string, any>,
  userConsent: boolean = true
): Promise<SchemeExplanationResult> {
  try {
    const res = await apiFetch<SchemeExplanationResult>(`/schemes/${schemeId}/explain`, {
      method: "POST",
      body: JSON.stringify({
        profile: profile || {},
        user_consent: userConsent,
      }),
    });
    if (res) return res;
    return {
      success: false,
      explanation: "Unable to retrieve explanation at this time.",
      mode: "offline_fallback",
      citations: [],
      error: "No response received",
    };
  } catch (err: any) {
    return {
      success: false,
      explanation: "Unable to connect to AI explanation service.",
      mode: "error",
      citations: [],
      error: err?.message || "Network error",
    };
  }
}

export async function getSchemeCategories(): Promise<string[]> {
  try {
    const res = await apiFetch<{ categories: string[] }>("/schemes/categories");
    return res?.categories || [];
  } catch {
    return [];
  }
}

export async function getSchemeStates(): Promise<string[]> {
  try {
    const res = await apiFetch<{ states: string[] }>("/schemes/states");
    return res?.states || [];
  } catch {
    return [];
  }
}

export async function checkPortalStatus(schemeId: string, refresh: boolean = false): Promise<{
  schemeId: string;
  officialUrl?: string;
  alternativeUrl?: string;
  status: 'reachable' | 'temporarily_unavailable' | 'redirected' | 'unverified';
  isAvailable: boolean;
  statusCode?: number | null;
  statusMessage?: string;
  checkedAt?: string;
}> {
  try {
    const q = refresh ? "?refresh=true" : "";
    const res = await apiFetch<any>(`/schemes/${encodeURIComponent(schemeId)}/portal-status${q}`);
    return res || {
      schemeId,
      status: "temporarily_unavailable",
      isAvailable: false,
      statusMessage: "The official portal could not be reached. It may be temporarily unavailable. You can review the scheme details and try again later."
    };
  } catch (err: any) {
    return {
      schemeId,
      status: "temporarily_unavailable",
      isAvailable: false,
      statusMessage: "The official portal could not be reached. It may be temporarily unavailable. You can review the scheme details and try again later."
    };
  }
}

