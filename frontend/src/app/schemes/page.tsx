"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { 
  Sparkles, 
  ArrowRight, 
  RotateCcw, 
  RefreshCw, 
  ShieldCheck, 
  UserCheck, 
  CheckCircle2, 
  AlertCircle, 
  HelpCircle,
  Wheat,
  GraduationCap,
  MapPin,
  Calendar,
  Briefcase,
  IndianRupee,
  Layers,
  Edit3,
  Crown,
  Lock
} from "lucide-react";
import { getSchemes, getSchemesCatalog, syncSchemes, getSyncStatus } from "@/services/schemeService";
import { fetchProfile, updateProfile } from "@/services/profileService";
import { Scheme, EligibilityStatus } from "@/types/scheme";
import { SchemeCard } from "@/components/schemes/SchemeCard";
import { UserProfile } from "@/types/profile";
import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import { SubscriptionModal } from "@/components/subscription/SubscriptionModal";
import { useAuth } from "@/context/AuthContext";
import { FamilyProfileSwitcher } from "@/components/profile/FamilyProfileSwitcher";

function SchemesContent() {
  const { profile: authProfile } = useAuth();
  const [activeFilter, setActiveFilter] = useState<EligibilityStatus | "all">("eligible");
  const [selectedCategory, setSelectedCategory] = useState("all");
  const [selectedState, setSelectedState] = useState("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [schemes, setSchemes] = useState<Scheme[]>([]);
  const [visibleLimit, setVisibleLimit] = useState(10);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [syncMessage, setSyncMessage] = useState<string | null>(null);

  const [totalMatchingCount, setTotalMatchingCount] = useState<number>(0);
  const [isPremium, setIsPremium] = useState<boolean>(false);
  const [userSubscription, setUserSubscription] = useState<any>(null);
  const [subscriptionModalOpen, setSubscriptionModalOpen] = useState<boolean>(false);

  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [baseProfile, setBaseProfile] = useState<UserProfile | null>(null);
  const [comparisonOccupation, setComparisonOccupation] = useState<string | null>(null);

  const [counts, setCounts] = useState({
    all: 0,
    eligible: 0,
    possibly_eligible: 0,
    not_eligible: 0,
    applications_closed: 0,
  });

  const [syncMeta, setSyncMeta] = useState<{
    total_schemes: number;
    verified_schemes: number;
    last_sync_time: string | null;
    last_verified_date: string;
    status: string;
  }>({
    total_schemes: 10,
    verified_schemes: 10,
    last_sync_time: null,
    last_verified_date: "13 Oct 2026",
    status: "ready"
  });

  const categories = [
    "All Categories",
    "Agriculture",
    "Education",
    "Skill Development",
    "Employment & Enterprise",
    "Health & Wellness",
    "Social Welfare",
  ];

  const states = [
    "All States",
    "Uttar Pradesh",
    "Maharashtra",
    "Karnataka",
    "Delhi",
    "Gujarat",
    "Rajasthan",
    "Madhya Pradesh",
    "Punjab",
    "Bihar",
  ];

  const loadData = async (overrideProfile?: UserProfile | null) => {
    setLoading(true);
    const catParam = selectedCategory === "All Categories" ? "all" : selectedCategory;
    const stateParam = selectedState === "All States" ? "all" : selectedState;

    let p: UserProfile | null = null;
    let meta: any = null;

    if (overrideProfile !== undefined) {
      p = overrideProfile;
      meta = await getSyncStatus();
    } else {
      const [fetchedP, fetchedMeta] = await Promise.all([
        fetchProfile(),
        getSyncStatus()
      ]);
      p = fetchedP;
      meta = fetchedMeta;
      setBaseProfile(fetchedP);
    }

    setProfile(p);
    setSyncMeta(meta);

    const [allCatalog, filteredCatalog] = await Promise.all([
      getSchemesCatalog("all", undefined, catParam, stateParam, p),
      activeFilter === "all" && (!searchQuery || searchQuery.trim() === "")
        ? null
        : getSchemesCatalog(activeFilter, searchQuery, catParam, stateParam, p)
    ]);

    const activeCatalog = filteredCatalog || allCatalog;

    setTotalMatchingCount(allCatalog.totalMatchingCount);
    setIsPremium(activeCatalog.isPremium);
    setUserSubscription(activeCatalog.subscription);

    if (allCatalog.counts) {
      setCounts(allCatalog.counts as any);
    } else {
      setCounts({
        all: allCatalog.totalMatchingCount,
        eligible: allCatalog.schemes.filter((s) => s.eligibilityStatus === "eligible").length,
        possibly_eligible: allCatalog.schemes.filter((s) => s.eligibilityStatus === "possibly_eligible" || (s as any).legacyEligibilityStatus === "almost").length,
        not_eligible: allCatalog.schemes.filter((s) => s.eligibilityStatus === "not_eligible" || (s as any).legacyEligibilityStatus === "ineligible").length,
        applications_closed: allCatalog.schemes.filter((s) => s.eligibilityStatus === "applications_closed").length,
      });
    }

    setSchemes(activeCatalog.schemes);
    setLoading(false);
  };

  useEffect(() => {
    setVisibleLimit(10);
    const timer = setTimeout(loadData, 150);
    return () => clearTimeout(timer);
  }, [activeFilter, searchQuery, selectedCategory, selectedState, authProfile]);

  const handleSyncNow = async () => {
    setSyncing(true);
    setSyncMessage(null);
    try {
      const res = await syncSchemes(profile || undefined);
      if (res.success) {
        setSyncMessage(`Successfully verified ${res.schemes_verified}/${res.schemes_attempted} official sources! Upserted ${res.schemes_updated + res.schemes_inserted} scheme records.`);
      } else {
        setSyncMessage(`Sync completed with notice: ${res.error || "Some sources took longer to respond."}`);
      }
      await loadData();
    } catch {
      setSyncMessage("Synchronization request sent to backend.");
    } finally {
      setSyncing(false);
      setTimeout(() => setSyncMessage(null), 8000);
    }
  };

  const handleSetFarmerDemoProfile = async () => {
    const farmerProfile: Partial<UserProfile> = {
      name: "Ramesh Verma",
      occupation: "Farmer",
      gender: "Male",
      annualIncome: "1 – 3 Lakh",
      incomeNumeric: 180000,
      age: 24,
      state: "Uttar Pradesh",
      district: "Varanasi",
      education: "10th Pass",
      category: "OBC",
      isFarmer: true,
      isStudent: false,
      landHoldingAcres: 2.0,
      isTaxPayer: false,
      isGovtEmployee: false,
    };
    await updateProfile(farmerProfile);
    await loadData();
  };

  const handleSwitchStateToMaharashtra = async () => {
    if (!profile) return;
    await updateProfile({ state: "Maharashtra" });
    await loadData();
  };

  const handleSwitchOccupationToStudent = async () => {
    if (!profile) return;
    await updateProfile({
      occupation: "Student",
      isFarmer: false,
      isStudent: true,
      education: "B.E. (Final Year)",
    });
    await loadData();
  };

  const [customOccInput, setCustomOccInput] = useState("");
  const [showCustomOcc, setShowCustomOcc] = useState(false);

  const handleQuickOccupationSwitch = (newOcc: string) => {
    const base = baseProfile || profile;
    if (!base) return;

    // Toggle off if clicking the already selected comparison occupation
    if (comparisonOccupation && comparisonOccupation.toLowerCase() === newOcc.toLowerCase()) {
      handleResetComparison();
      return;
    }

    setComparisonOccupation(newOcc);

    const occLower = newOcc.toLowerCase().trim();
    const isFarmer = occLower.includes("farmer") || occLower.includes("kisan") || occLower.includes("agri") || occLower.includes("cultivat");
    const isStudent = occLower.includes("student");
    const hasBusiness = occLower.includes("shop") || occLower.includes("business") || occLower.includes("self-employed") || occLower.includes("trader") || occLower.includes("merchant") || occLower.includes("artisan");
    const isGovtEmployee = occLower.includes("government") || occLower.includes("govt") || occLower.includes("sarkari");

    // Construct temporary evaluation profile WITHOUT updating PostgreSQL
    const evalProfile: UserProfile = {
      ...base,
      occupation: newOcc,
      isFarmer,
      isStudent,
      hasBusiness,
      isGovtEmployee,
      landHoldingAcres: isFarmer ? (base.landHoldingAcres && base.landHoldingAcres > 0 ? base.landHoldingAcres : 2.0) : 0,
    };

    setProfile(evalProfile);
    loadData(evalProfile);
  };

  const handleResetComparison = () => {
    setComparisonOccupation(null);
    if (baseProfile) {
      setProfile(baseProfile);
      loadData(baseProfile);
    } else {
      loadData();
    }
  };

  const handleQuickGenderSwitch = (newGender: string) => {
    const current = profile || baseProfile;
    if (!current) return;
    const evalProfile: UserProfile = {
      ...current,
      gender: newGender,
    };
    setProfile(evalProfile);
    loadData(evalProfile);
  };

  const handleResetFilters = () => {
    setActiveFilter("all");
    setSelectedCategory("all");
    setSelectedState("all");
    setSearchQuery("");
  };

  return (
    <main className="flex-1 bg-brand-bg py-8 px-4 sm:px-6 lg:px-8">
      <div className="max-w-5xl mx-auto space-y-6">

        {/* Header & Subtitle */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="px-2.5 py-0.5 rounded-md text-2xs font-extrabold uppercase bg-emerald-50 text-emerald-800 border border-emerald-200 flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
                Official Government Sources
              </span>
              <span className="text-2xs text-slate-500">
                PostgreSQL Database Verified
              </span>
            </div>
            <div className="flex items-center gap-2 flex-wrap">
              <h1 className="text-2xl sm:text-3xl font-extrabold text-brand-navy tracking-tight">
                Government Scheme Recommendations
              </h1>
              {totalMatchingCount > 0 && (
                <span className="px-2.5 py-1 rounded-xl text-xs font-black bg-blue-100 text-brand-blue border border-blue-200 shadow-2xs">
                  {totalMatchingCount} Matching Schemes
                </span>
              )}
              {isPremium ? (
                <span className="px-2.5 py-1 rounded-xl text-xs font-black bg-gradient-to-r from-amber-400/20 to-amber-500/20 text-amber-800 border border-amber-300 flex items-center gap-1 shadow-2xs">
                  <Crown className="w-3.5 h-3.5 text-amber-600" />
                  Premium Active
                </span>
              ) : (
                <button
                  onClick={() => setSubscriptionModalOpen(true)}
                  className="px-2.5 py-1 rounded-xl text-xs font-bold bg-amber-50 hover:bg-amber-100 text-amber-800 border border-amber-300 flex items-center gap-1 shadow-2xs transition"
                >
                  <Crown className="w-3.5 h-3.5 text-amber-600" />
                  Upgrade to Premium
                </button>
              )}
            </div>
            <p className="text-xs sm:text-sm text-slate-500">
              Deterministic matching engine evaluated against your 7 chatbot profile fields.
            </p>
          </div>

          <div className="flex items-center gap-2 self-start sm:self-auto shrink-0 flex-wrap">
            <button
              onClick={handleSyncNow}
              disabled={syncing}
              className="inline-flex items-center gap-2 px-3.5 py-2 rounded-xl bg-white hover:bg-slate-50 text-slate-700 font-bold text-xs border border-brand-border shadow-xs transition"
              title="Probe official government portals and sync live records"
            >
              <RefreshCw className={`w-3.5 h-3.5 text-brand-blue ${syncing ? "animate-spin text-brand-blue" : ""}`} />
              <span>{syncing ? "Probing Sources..." : "Synchronize Schemes"}</span>
            </button>
          </div>
        </div>

        {/* Sync Success / Alert Toast */}
        {syncMessage && (
          <div className="p-3.5 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-900 text-xs font-semibold flex items-center justify-between gap-3 shadow-xs">
            <div className="flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-emerald-600 shrink-0" />
              <span>{syncMessage}</span>
            </div>
            <button onClick={() => setSyncMessage(null)} className="text-emerald-700 hover:text-emerald-900 text-xs">Dismiss</button>
          </div>
        )}

        {/* Unsaved Profile Warning Banner */}
        {(!profile?.isProfileSaved && !profile?.is_profile_saved && (!profile?.occupation || !profile?.state || (profile?.completenessPercent ?? 0) === 0)) && (
          <div className="p-4 rounded-2xl bg-amber-50 border-2 border-amber-300 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-amber-900 shadow-sm animate-fadeIn">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-xl bg-amber-100 flex items-center justify-center shrink-0">
                <AlertCircle className="w-5 h-5 text-amber-600" />
              </div>
              <div>
                <h4 className="text-xs sm:text-sm font-extrabold text-amber-900">
                  Please save your profile details before finding schemes.
                </h4>
                <p className="text-2xs text-amber-700">
                  You are currently seeing the general catalog. Save your profile details for personalized criteria evaluation.
                </p>
              </div>
            </div>
            <Link
              href="/profile"
              className="inline-flex items-center gap-1.5 px-4 py-2 bg-amber-600 hover:bg-amber-700 text-white rounded-xl text-xs font-bold shrink-0 shadow-xs transition"
            >
              <span>Save Profile Details →</span>
            </Link>
          </div>
        )}

        {/* 1. BENEFICIARY PROFILE SWITCHER */}
        <FamilyProfileSwitcher
          onProfileChanged={(newProf) => {
            setProfile(newProf);
            loadData(newProf);
          }}
        />

        {/* 2. MENTOR DEMO PROFILE SUMMARY CARD */}
        <div className="p-5 bg-white rounded-2xl border border-brand-border shadow-card space-y-3.5">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-100">
            <div className="flex items-center gap-2.5">
              <div className="w-9 h-9 rounded-xl bg-blue-50 border border-blue-200 flex items-center justify-center shrink-0">
                <UserCheck className="w-5 h-5 text-brand-blue" />
              </div>
              <div>
                <div className="flex items-center gap-2 flex-wrap">
                  <h3 className="font-extrabold text-sm sm:text-base text-brand-navy">
                    Active Citizen Profile Evaluation: {profile?.name || "Citizen"}
                  </h3>
                  <span className="px-2 py-0.5 rounded-md text-2xs font-extrabold bg-blue-100 text-brand-blue border border-blue-200">
                    {profile?.relationship || "Self"}
                  </span>
                  {comparisonOccupation && (
                    <span className="px-2 py-0.5 rounded-md text-2xs font-extrabold bg-amber-100 text-amber-800 border border-amber-300 flex items-center gap-1 shadow-2xs">
                      <Sparkles className="w-3 h-3 text-amber-600" />
                      Comparing: {comparisonOccupation} (Saved Profile Unchanged)
                    </span>
                  )}
                </div>
                <p className="text-2xs text-slate-500">
                  Seven primary matching fields evaluated for {profile?.name || "this beneficiary"}
                </p>
              </div>
            </div>

            {/* Profile Action Link */}
            <div className="flex items-center gap-2 shrink-0">
              <Link
                href="/profile"
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold bg-brand-blue text-white hover:bg-brand-blue-dark transition shadow-xs whitespace-nowrap"
              >
                <Edit3 className="w-3.5 h-3.5" />
                <span>Edit Profile</span>
              </Link>
              <Link
                href="/interview"
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold text-slate-700 bg-slate-100 hover:bg-slate-200 transition whitespace-nowrap"
              >
                <Sparkles className="w-3.5 h-3.5 text-brand-blue" />
                <span>AI Chatbot</span>
              </Link>
            </div>
          </div>

          {/* Seven Fields Pills Grid */}
          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-2.5 pt-1">
            <div className={`p-2.5 rounded-xl border flex flex-col justify-between ${comparisonOccupation ? "bg-amber-50/60 border-amber-300 ring-1 ring-amber-300/40" : "bg-slate-50 border-slate-200"}`}>
              <span className="text-3xs font-bold uppercase text-slate-400 tracking-wider truncate">
                Occupation
              </span>
              <span className={`text-xs font-black mt-0.5 truncate ${profile?.occupation ? "text-slate-800" : "text-amber-600 font-semibold"}`} title={profile?.occupation || "Not Specified"}>
                {profile?.occupation || "Not Specified"}
              </span>
            </div>

            <div className="p-2.5 rounded-xl bg-slate-50 border border-slate-200 flex flex-col">
              <span className="text-3xs font-bold uppercase text-slate-400 tracking-wider">Gender</span>
              <span className={`text-xs font-black mt-0.5 truncate ${profile?.gender ? "text-slate-800" : "text-amber-600 font-semibold"}`}>
                {profile?.gender || "Not Specified"}
              </span>
            </div>

            <div className="p-2.5 rounded-xl bg-slate-50 border border-slate-200 flex flex-col">
              <span className="text-3xs font-bold uppercase text-slate-400 tracking-wider">Annual Income</span>
              <span className={`text-xs font-black mt-0.5 truncate ${profile?.annualIncome ? "text-slate-800" : "text-amber-600 font-semibold"}`}>
                {profile?.annualIncome || "Not Specified"}
              </span>
            </div>

            <div className="p-2.5 rounded-xl bg-slate-50 border border-slate-200 flex flex-col">
              <span className="text-3xs font-bold uppercase text-slate-400 tracking-wider">Age</span>
              <span className={`text-xs font-black mt-0.5 ${profile?.age ? "text-slate-800" : "text-amber-600 font-semibold"}`}>
                {profile?.age ? `${profile.age} Years` : "Not Specified"}
              </span>
            </div>

            <div className="p-2.5 rounded-xl bg-slate-50 border border-slate-200 flex flex-col">
              <span className="text-3xs font-bold uppercase text-slate-400 tracking-wider">State</span>
              <span className={`text-xs font-black mt-0.5 truncate ${profile?.state ? "text-slate-800" : "text-amber-600 font-semibold"}`}>
                {profile?.state || "Not Specified"}
              </span>
            </div>

            <div className="p-2.5 rounded-xl bg-slate-50 border border-slate-200 flex flex-col">
              <span className="text-3xs font-bold uppercase text-slate-400 tracking-wider">Education</span>
              <span className={`text-xs font-black mt-0.5 truncate ${profile?.education ? "text-slate-800" : "text-slate-500"}`}>
                {profile?.education || "Not Specified"}
              </span>
            </div>

            <div className="p-2.5 rounded-xl bg-slate-50 border border-slate-200 flex flex-col">
              <span className="text-3xs font-bold uppercase text-slate-400 tracking-wider">Category</span>
              <span className="text-xs font-black text-slate-800 mt-0.5 truncate">
                {profile?.category || "General"}
              </span>
            </div>
          </div>

          {/* Quick Dynamic Gender Switch Bar */}
          <div className="pt-2 border-t border-slate-100 flex flex-wrap items-center gap-2">
            <span className="text-2xs font-extrabold text-slate-500 uppercase tracking-wider flex items-center gap-1">
              <UserCheck className="w-3 h-3 text-brand-blue" />
              <span>Gender:</span>
            </span>
            {["Male", "Female"].map((g) => {
              const isSelected = (profile?.gender || "").toLowerCase() === g.toLowerCase();
              return (
                <button
                  key={g}
                  type="button"
                  onClick={() => handleQuickGenderSwitch(g)}
                  className={`px-3 py-1 rounded-lg text-xs font-bold transition flex items-center gap-1 border ${
                    isSelected
                      ? "bg-brand-blue text-white border-brand-blue shadow-xs"
                      : "bg-slate-50 text-slate-700 border-slate-200 hover:bg-slate-100"
                  }`}
                >
                  <span>{g}</span>
                  {isSelected && <CheckCircle2 className="w-3 h-3" />}
                </button>
              );
            })}
          </div>

          {/* Quick Dynamic Occupation Comparison Bar */}
          <div className="pt-2 border-t border-slate-100 flex flex-wrap items-center gap-2">
            <span className="text-2xs font-extrabold text-slate-500 uppercase tracking-wider flex items-center gap-1">
              <Sparkles className="w-3 h-3 text-brand-blue" />
              <span>Compare Occupation:</span>
            </span>
            {["Farmer", "Teacher", "Doctor", "Housewife", "Student", "Government Employee", "Private Employee", "Self-Employed"].map((occ) => {
              const isSelected = (profile?.occupation || "").toLowerCase() === occ.toLowerCase();
              return (
                <button
                  key={occ}
                  type="button"
                  onClick={() => {
                    setShowCustomOcc(false);
                    handleQuickOccupationSwitch(occ);
                  }}
                  className={`px-3 py-1 rounded-lg text-xs font-bold transition flex items-center gap-1 border ${
                    isSelected
                      ? "bg-brand-blue text-white border-brand-blue shadow-xs"
                      : "bg-slate-50 text-slate-700 border-slate-200 hover:bg-slate-100"
                  }`}
                >
                  <span>{occ}</span>
                  {isSelected && <CheckCircle2 className="w-3 h-3" />}
                </button>
              );
            })}
            <button
              type="button"
              onClick={() => setShowCustomOcc(!showCustomOcc)}
              className={`px-3 py-1 rounded-lg text-xs font-bold transition border ${
                showCustomOcc || !["farmer", "teacher", "doctor", "housewife", "student", "government employee", "private employee", "self-employed"].includes((profile?.occupation || "").toLowerCase())
                  ? "bg-brand-navy text-white border-brand-navy shadow-xs"
                  : "bg-slate-50 text-slate-700 border-slate-200 hover:bg-slate-100"
              }`}
            >
              <span>+ Custom Other</span>
            </button>
            {comparisonOccupation && (
              <button
                type="button"
                onClick={handleResetComparison}
                className="px-3 py-1 rounded-lg text-xs font-bold transition flex items-center gap-1.5 bg-amber-100 text-amber-900 border border-amber-300 hover:bg-amber-200 shadow-2xs"
                title="Restore saved citizen profile occupation"
              >
                <RotateCcw className="w-3 h-3 text-amber-700" />
                <span>Reset to Saved ({baseProfile?.occupation || "Self"})</span>
              </button>
            )}
          </div>

          {showCustomOcc && (
            <div className="pt-2 flex items-center gap-2">
              <input
                type="text"
                value={customOccInput}
                onChange={(e) => setCustomOccInput(e.target.value)}
                placeholder="Enter custom occupation (e.g. Electrician, Artist, Lawyer)..."
                className="px-3.5 py-1.5 text-xs rounded-xl border border-brand-border focus:outline-none focus:border-brand-blue flex-1 max-w-sm"
              />
              <button
                type="button"
                onClick={() => {
                  if (customOccInput.trim()) {
                    handleQuickOccupationSwitch(customOccInput.trim());
                    setShowCustomOcc(false);
                  }
                }}
                disabled={!customOccInput.trim()}
                className="px-3 py-1.5 bg-brand-blue text-white text-xs font-bold rounded-xl hover:bg-brand-blue-dark transition disabled:opacity-50"
              >
                Apply
              </button>
            </div>
          )}
        </div>

        {/* 2. STATS & SYNC METADATA BAR */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="p-4 bg-white rounded-2xl border border-brand-border shadow-xs flex flex-col">
            <span className="text-2xs font-bold text-slate-500 uppercase tracking-wider">Total in Database</span>
            <div className="text-2xl font-black text-brand-navy mt-1">
              {(counts as any).total_in_db ?? counts.all}
            </div>
            <span className="text-3xs text-slate-400 mt-1">Real government schemes</span>
          </div>

          <div className="p-4 bg-white rounded-2xl border border-emerald-200 shadow-xs flex flex-col">
            <div className="flex items-center justify-between">
              <span className="text-2xs font-bold text-emerald-800 uppercase tracking-wider">Eligible Matches</span>
              <CheckCircle2 className="w-4 h-4 text-emerald-600" />
            </div>
            <div className="text-2xl font-black text-emerald-700 mt-1">
              {counts.eligible}
            </div>
            <span className="text-3xs text-emerald-600 mt-1">100% criteria verified</span>
          </div>

          <div className="p-4 bg-white rounded-2xl border border-amber-200 shadow-xs flex flex-col">
            <div className="flex items-center justify-between">
              <span className="text-2xs font-bold text-amber-800 uppercase tracking-wider">Needs Verification</span>
              <AlertCircle className="w-4 h-4 text-amber-600" />
            </div>
            <div className="text-2xl font-black text-amber-700 mt-1">
              {counts.possibly_eligible}
            </div>
            <span className="text-3xs text-amber-600 mt-1">Pending document/land check</span>
          </div>

          <div className="p-4 bg-white rounded-2xl border border-slate-200 shadow-xs flex flex-col">
            <div className="flex items-center justify-between">
              <span className="text-2xs font-bold text-slate-500 uppercase tracking-wider">Source Status</span>
              <ShieldCheck className="w-4 h-4 text-emerald-600" />
            </div>
            <div className="text-xs font-extrabold text-slate-800 mt-2 truncate">
              {syncMeta.status === "ready" ? "Verified Live" : syncMeta.status}
            </div>
            <span className="text-3xs text-slate-400 mt-1">
              {syncMeta.last_verified_date ? `Verified: ${syncMeta.last_verified_date}` : "Live Probed"}
            </span>
          </div>
        </div>

        {/* 3. FILTER TABS */}
        <div className="flex items-center gap-2 overflow-x-auto pb-1 sm:pb-0 scrollbar-none">
          <button
            onClick={() => setActiveFilter("eligible")}
            className={`px-3.5 py-2 rounded-xl text-xs sm:text-sm font-bold transition whitespace-nowrap ${
              activeFilter === "eligible"
                ? "bg-emerald-600 text-white shadow-sm"
                : "bg-white text-emerald-700 hover:bg-emerald-50 border border-emerald-200"
            }`}
          >
            Eligible Schemes ({counts.eligible})
          </button>
          <button
            onClick={() => setActiveFilter("all")}
            className={`px-3.5 py-2 rounded-xl text-xs sm:text-sm font-bold transition whitespace-nowrap ${
              activeFilter === "all"
                ? "bg-brand-navy text-white shadow-sm"
                : "bg-white text-slate-600 hover:bg-slate-50 border border-brand-border"
            }`}
          >
            All Relevant Schemes ({counts.all})
          </button>
          <button
            onClick={() => setActiveFilter("possibly_eligible")}
            className={`px-3.5 py-2 rounded-xl text-xs sm:text-sm font-bold transition whitespace-nowrap ${
              activeFilter === "possibly_eligible"
                ? "bg-amber-600 text-white shadow-sm"
                : "bg-white text-amber-800 hover:bg-amber-50 border border-amber-200"
            }`}
          >
            Needs Verification ({counts.possibly_eligible})
          </button>
          <button
            onClick={() => setActiveFilter("not_eligible")}
            className={`px-3.5 py-2 rounded-xl text-xs sm:text-sm font-bold transition whitespace-nowrap ${
              activeFilter === "not_eligible"
                ? "bg-rose-600 text-white shadow-sm"
                : "bg-white text-slate-600 hover:bg-slate-50 border border-brand-border"
            }`}
          >
            Not Eligible ({counts.not_eligible})
          </button>
        </div>

        {/* 5. RECOMMENDATIONS LIST */}
        <div className="space-y-4">
          {loading ? (
            <div className="p-12 text-center bg-white rounded-2xl border border-brand-border space-y-3">
              <RefreshCw className="w-6 h-6 text-brand-blue animate-spin mx-auto" />
              <p className="text-slate-600 font-bold text-sm">Evaluating 6-field deterministic eligibility...</p>
            </div>
          ) : schemes.length > 0 ? (
            <>
              {schemes.slice(0, visibleLimit).map((scheme) => (
                <SchemeCard key={scheme.id || scheme.slug} scheme={scheme} />
              ))}

              {schemes.length > visibleLimit && (
                <div className="pt-2 text-center">
                  <button
                    onClick={() => setVisibleLimit((prev) => prev + 10)}
                    className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-white hover:bg-slate-50 border border-brand-border text-brand-navy font-bold text-xs shadow-xs transition hover:shadow-sm"
                  >
                    <Layers className="w-4 h-4 text-brand-blue" />
                    <span>See More Schemes ({schemes.length - visibleLimit} more available)</span>
                    <ArrowRight className="w-3.5 h-3.5 text-slate-400" />
                  </button>
                </div>
              )}

              {/* Free Tier Limit - OTT-style CTA to unlock all schemes */}
              {!isPremium && totalMatchingCount > schemes.length && (
                <div className="mt-6 p-6 sm:p-8 rounded-3xl bg-gradient-to-br from-slate-900 via-slate-900 to-amber-950 text-white border border-amber-500/30 shadow-2xl relative overflow-hidden">
                  <div className="absolute top-0 right-0 -mr-16 -mt-16 w-64 h-64 bg-amber-500/10 rounded-full blur-3xl pointer-events-none" />
                  
                  <div className="relative z-10 flex flex-col md:flex-row items-center justify-between gap-6">
                    <div className="space-y-2 text-center md:text-left">
                      <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-amber-500/20 border border-amber-400/40 text-amber-300 text-xs font-black uppercase tracking-wider">
                        <Lock className="w-3.5 h-3.5 text-amber-400" />
                        <span>Free Tier Limit: Viewing 5 of {totalMatchingCount} Schemes</span>
                      </div>
                      <h3 className="text-xl sm:text-2xl font-black text-white tracking-tight">
                        Unlock All {totalMatchingCount} Matching Schemes
                      </h3>
                      <p className="text-xs sm:text-sm text-slate-300 max-w-xl">
                        Free accounts can view complete details of only the first 5 schemes. Upgrade to <strong className="text-amber-400">Yojana Hunter Premium</strong> to browse every scheme, download step-by-step application forms, and unlock unlimited benefits.
                      </p>
                    </div>

                    <div className="shrink-0 flex flex-col sm:flex-row items-center gap-3 w-full md:w-auto">
                      <button
                        onClick={() => setSubscriptionModalOpen(true)}
                        className="w-full sm:w-auto px-6 py-3.5 rounded-2xl bg-gradient-to-r from-amber-500 via-amber-400 to-amber-500 hover:from-amber-400 hover:to-amber-300 text-slate-950 font-black text-sm shadow-lg shadow-amber-500/25 flex items-center justify-center gap-2.5 transition transform hover:-translate-y-0.5 active:translate-y-0"
                      >
                        <Crown className="w-4 h-4 text-slate-950" />
                        <span>See More Schemes</span>
                        <ArrowRight className="w-4 h-4 text-slate-950" />
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </>
          ) : (
            <div className="p-12 text-center bg-white rounded-2xl border border-brand-border space-y-4">
              <div className="w-12 h-12 rounded-full bg-blue-50 text-brand-blue flex items-center justify-center mx-auto">
                <AlertCircle className="w-6 h-6" />
              </div>
              <div className="space-y-1">
                <h3 className="text-base font-bold text-brand-navy">
                  No matching schemes with verified official links were found for the information provided.
                </h3>
                <p className="text-xs sm:text-sm text-slate-500 max-w-md mx-auto">
                  Please review your details or try again later. We only display schemes that strictly match verified eligibility criteria and have verified official government portal links.
                </p>
              </div>
              <div className="flex items-center justify-center gap-3 flex-wrap">
                <button
                  onClick={handleResetFilters}
                  className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-bold text-brand-blue bg-blue-50 hover:bg-blue-100 transition"
                >
                  <RotateCcw className="w-3.5 h-3.5" />
                  <span>Reset all filters</span>
                </button>
                <Link
                  href="/profile"
                  className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-bold text-white bg-brand-navy hover:bg-brand-navy/90 transition"
                >
                  <span>Update Profile</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </Link>
              </div>
            </div>
          )}
        </div>

        {/* Subscription OTT Modal */}
        <SubscriptionModal
          isOpen={subscriptionModalOpen}
          onClose={() => setSubscriptionModalOpen(false)}
          onSubscriptionUpdated={loadData}
          totalMatchingCount={totalMatchingCount}
          accessibleCount={schemes.length}
        />

      </div>
    </main>
  );
}

export default function SchemesPage() {
  return (
    <ProtectedRoute>
      <SchemesContent />
    </ProtectedRoute>
  );
}
