"use client";

import React, { useState, useEffect, useMemo } from "react";
import Link from "next/link";
import { 
  Bot, 
  Layers, 
  Bookmark, 
  Download, 
  CheckCircle2, 
  AlertTriangle, 
  XCircle, 
  ArrowRight, 
  Clock, 
  Sparkles,
  ChevronRight,
  ShieldCheck,
  UserCheck,
  Award,
  Users,
  Plus,
  Edit3,
  Trash2,
  Heart,
  Crown,
  RefreshCw,
  CreditCard
} from "lucide-react";
import { fetchMySubscriptionStatus, subscribeToSubscriptionUpdates } from "@/services/subscriptionService";
import { UserSubscriptionStatus } from "@/types/subscription";
import { SubscriptionModal } from "@/components/subscription/SubscriptionModal";
import { ResponsiveContainer, PieChart, Pie, Cell, Tooltip } from "recharts";
import { getStoredProfile } from "@/lib/storage";
import { UserProfile, UserActivity, UserLevelInfo } from "@/types/profile";
import { getSchemes } from "@/services/schemeService";
import { fetchUserActivities, fetchUserLevel, deleteProfile } from "@/services/profileService";
import { calculateUserLevel } from "@/lib/userLevel";
import { Scheme } from "@/types/scheme";
import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import { useAuth } from "@/context/AuthContext";
import { FamilyProfileSwitcher } from "@/components/profile/FamilyProfileSwitcher";
import { FamilyProfileModal } from "@/components/profile/FamilyProfileModal";

const CATEGORY_PALETTE = [
  "#2563EB", // Brand Blue
  "#2DC6B1", // Teal
  "#F59E0B", // Amber
  "#8B5CF6", // Purple
  "#EC4899", // Pink
  "#10B981", // Emerald
  "#6366F1", // Indigo
  "#0EA5E9", // Sky
  "#F97316", // Orange
  "#94A3B8", // Slate
];

const RELATION_ICONS: Record<string, string> = {
  Self: "👤",
  Father: "👨",
  Mother: "👩",
  Child: "🧒",
  Spouse: "💍",
  Other: "🤝",
};

function DashboardContent() {
  const { 
    user, 
    profile: authProfile, 
    familyProfiles, 
    switchActiveProfile, 
    refreshFamilyProfiles 
  } = useAuth();
  
  const [profile, setProfile] = useState<UserProfile>(authProfile || getStoredProfile());
  const [mounted, setMounted] = useState(false);
  const [schemes, setSchemes] = useState<Scheme[]>([]);
  const [counts, setCounts] = useState({ total: 0, eligible: 0, almost: 0, ineligible: 0 });
  const [loading, setLoading] = useState(true);
  const [activities, setActivities] = useState<UserActivity[]>([]);
  const [activitiesLoading, setActivitiesLoading] = useState(true);
  const [userLevel, setUserLevel] = useState<UserLevelInfo | null>(null);

  // Modal State
  const [modalOpen, setModalOpen] = useState(false);
  const [editingTarget, setEditingTarget] = useState<UserProfile | null>(null);

  // Subscription & Real-Time Payment Lifecycle State
  const [subscriptionOverview, setSubscriptionOverview] = useState<UserSubscriptionStatus | null>(null);
  const [subModalOpen, setSubModalOpen] = useState(false);

  // Load subscription status and subscribe to real-time SSE stream
  useEffect(() => {
    let unsubscribe: (() => void) | null = null;

    async function initSubscription() {
      try {
        const status = await fetchMySubscriptionStatus();
        if (status) {
          setSubscriptionOverview(status);
        }
      } catch (e) {
        console.debug("Subscription status fetch notice:", e);
      }

      unsubscribe = subscribeToSubscriptionUpdates((event) => {
        fetchMySubscriptionStatus().then((updated) => {
          if (updated) setSubscriptionOverview(updated);
        });
      });
    }

    initSubscription();

    return () => {
      if (unsubscribe) unsubscribe();
    };
  }, []);

  useEffect(() => {
    const active = authProfile || getStoredProfile(user?.id);
    setProfile(active);
    setMounted(true);

    const isCompleted = Boolean(
      active?.isProfileSaved ||
      (active?.occupation && active?.state && active?.age && active.age > 0 && (active?.completenessPercent || 0) > 0)
    );

    async function loadData() {
      setLoading(true);
      setActivitiesLoading(true);
      try {
        if (!isCompleted) {
          // If profile is not completed yet, keep dashboard metrics clean/zeroed
          setSchemes([]);
          setCounts({ total: 0, eligible: 0, almost: 0, ineligible: 0 });
          setActivities([]);
          setUserLevel(calculateUserLevel(active, 0));
          return;
        }

        const [schemesData, realActivities, remoteLevel] = await Promise.all([
          getSchemes("all", undefined, "all", "all", active),
          fetchUserActivities(),
          fetchUserLevel(active?.id)
        ]);

        if (schemesData) {
          setSchemes(schemesData);
          setCounts({
            total: schemesData.length,
            eligible: schemesData.filter((s) => s.eligibilityStatus === "eligible").length,
            almost: schemesData.filter((s) => s.eligibilityStatus === "possibly_eligible" || (s as any).legacyEligibilityStatus === "almost").length,
            ineligible: schemesData.filter((s) => s.eligibilityStatus === "not_eligible" || (s as any).legacyEligibilityStatus === "ineligible").length,
          });
        }

        if (realActivities) {
          setActivities(realActivities);
        }

        if (remoteLevel) {
          setUserLevel(remoteLevel);
        } else {
          setUserLevel(calculateUserLevel(active, realActivities?.length || 0));
        }
      } catch (err) {
        console.error("Failed to load dashboard data:", err);
      } finally {
        setLoading(false);
        setActivitiesLoading(false);
      }
    }
    loadData();
  }, [authProfile, user]);

  // Compute dynamic user display name without hardcoded fallbacks
  const displayName = useMemo(() => {
    if (profile?.name && profile.name.trim()) {
      return profile.name.trim().split(" ")[0];
    }
    if (authProfile?.name && authProfile.name.trim()) {
      return authProfile.name.trim().split(" ")[0];
    }
    if (user?.name && user.name.trim()) {
      return user.name.trim().split(" ")[0];
    }
    if (user?.email) {
      return user.email.split("@")[0];
    }
    return "Citizen";
  }, [profile, authProfile, user]);

  // Dynamic category distribution computed from schemes
  const categoryDistribution = useMemo(() => {
    if (!schemes || schemes.length === 0) return [];
    const catMap: Record<string, number> = {};
    schemes.forEach((s) => {
      const cat = (s.category && s.category.trim()) || "General / Other";
      catMap[cat] = (catMap[cat] || 0) + 1;
    });

    return Object.entries(catMap).map(([name, count], index) => ({
      name,
      count,
      fill: CATEGORY_PALETTE[index % CATEGORY_PALETTE.length],
    }));
  }, [schemes]);

  // Dynamically recalculate user level when relevant data (profile, activities, counts) changes
  const computedUserLevel = useMemo(() => {
    if (userLevel) return userLevel;
    return calculateUserLevel(profile, activities.length, 0, 0);
  }, [userLevel, profile, activities]);

  const stats = [
    { label: "Total Schemes Found", value: counts.total, color: "text-brand-blue", bg: "bg-blue-50/70 border-blue-100" },
    { label: "Eligible", value: counts.eligible, color: "text-emerald-600", bg: "bg-emerald-50/70 border-emerald-100", icon: CheckCircle2 },
    { label: "Almost Eligible", value: counts.almost, color: "text-amber-600", bg: "bg-amber-50/70 border-amber-100", icon: AlertTriangle },
    { label: "Not Eligible", value: counts.ineligible, color: "text-rose-600", bg: "bg-rose-50/70 border-rose-100", icon: XCircle },
  ];

  const topOpportunities = schemes.slice(0, 3).map((s) => ({
    id: s.slug || s.id,
    name: s.name,
    match: `${s.matchScore || 100}% Match`,
    priority: s.priority || "High Priority",
    badgeColor: "bg-amber-50 text-amber-700 border-amber-200",
  }));

  const quickActions = [
    { title: "Continue Interview", href: "/interview", icon: Bot, color: "text-teal-600 bg-teal-50" },
    { title: "View All Schemes", href: "/schemes", icon: Layers, color: "text-brand-blue bg-blue-50" },
    { title: "Saved Schemes", href: "/saved-schemes", icon: Bookmark, color: "text-emerald-600 bg-emerald-50" },
    { title: "Download Reports", href: "/application-draft", icon: Download, color: "text-purple-600 bg-purple-50" },
  ];

  const handleDeleteProfile = async (targetId: number, name: string) => {
    if (!window.confirm(`Are you sure you want to remove the profile for ${name}?`)) return;
    const ok = await deleteProfile(targetId);
    if (ok) {
      await refreshFamilyProfiles();
    }
  };

  const isProfileCompleted = Boolean(
    profile?.isProfileSaved ||
    (profile?.occupation && profile?.state && profile?.age && profile.age > 0 && (profile?.completenessPercent || 0) > 0)
  );

  return (
    <main className="flex-1 bg-brand-bg py-8 px-4 sm:px-6 lg:px-8">
      <div className="max-w-6xl mx-auto space-y-6">
        
        {/* Personalized Greeting Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="space-y-1">
            <h1 className="text-2xl sm:text-3xl font-black text-brand-navy tracking-tight flex items-center gap-2">
              <span>Hello, {displayName}</span>
              <span className="inline-block animate-wave">👋</span>
            </h1>
            <p className="text-xs sm:text-sm text-slate-500">
              {isProfileCompleted ? (
                <>Here&apos;s your personalized welfare scheme journey for <span className="font-bold text-slate-700">{profile?.name || "yourself"}</span> ({profile?.relationship || "Self"})</>
              ) : (
                <>Welcome! Complete your citizen profile to calculate eligibility scores and discover tailored schemes.</>
              )}
            </p>
          </div>

          <div className="flex items-center gap-2">
            {isProfileCompleted ? (
              <Link
                href="/schemes"
                className="inline-flex items-center gap-1.5 px-4 py-2 bg-brand-blue hover:bg-brand-blue-dark text-white rounded-xl text-xs sm:text-sm font-bold shadow-xs transition"
              >
                <span>Explore Top Matches</span>
                <ArrowRight className="w-4 h-4" />
              </Link>
            ) : (
              <Link
                href="/profile"
                className="inline-flex items-center gap-1.5 px-4 py-2 bg-brand-blue hover:bg-brand-blue-dark text-white rounded-xl text-xs sm:text-sm font-bold shadow-xs transition"
              >
                <span>Complete Profile</span>
                <ArrowRight className="w-4 h-4" />
              </Link>
            )}
          </div>
        </div>

        {/* Profile Completion Call to Action for Incomplete Profiles */}
        {!isProfileCompleted && (
          <div className="p-5 sm:p-6 rounded-2xl bg-gradient-to-r from-blue-50 via-teal-50 to-indigo-50 border-2 border-brand-blue/30 shadow-card flex flex-col sm:flex-row sm:items-center justify-between gap-4 animate-fadeIn">
            <div className="flex items-start gap-3.5">
              <div className="w-11 h-11 rounded-2xl bg-brand-blue text-white flex items-center justify-center shrink-0 shadow-sm mt-0.5">
                <Sparkles className="w-5 h-5 text-teal-300" />
              </div>
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <h3 className="text-sm sm:text-base font-black text-brand-navy">
                    Complete Your Citizen Profile
                  </h3>
                  <span className="px-2 py-0.5 rounded-full text-3xs font-extrabold bg-amber-100 text-amber-800 border border-amber-300">
                    Profile Pending
                  </span>
                </div>
                <p className="text-xs text-slate-600 max-w-2xl leading-relaxed">
                  Your profile details (occupation, age, education, and state) have not been saved yet. Complete your profile to calculate eligibility scores, unlock tailored welfare schemes, and start tracking applications.
                </p>
              </div>
            </div>
            <Link
              href="/profile"
              className="inline-flex items-center justify-center gap-2 px-4 py-2.5 bg-brand-blue hover:bg-brand-blue-dark text-white rounded-xl text-xs sm:text-sm font-bold shadow-xs transition shrink-0"
            >
              <span>Complete Profile Now</span>
              <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
        )}

        {/* REAL-TIME SUBSCRIPTION & PAYMENT LIFECYCLE BANNER */}
        {subscriptionOverview?.is_premium ? (
          <div className="p-5 rounded-2xl bg-gradient-to-r from-emerald-950 via-slate-900 to-brand-navy border border-emerald-500/30 text-white shadow-card flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="flex items-center gap-3.5">
              <div className="w-12 h-12 rounded-2xl bg-gradient-to-tr from-amber-400 to-amber-200 text-slate-950 flex items-center justify-center shrink-0 shadow-lg shadow-amber-400/20">
                <Crown className="w-6 h-6 text-slate-950" />
              </div>
              <div className="space-y-0.5">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-black text-white">
                    {subscriptionOverview.active_subscription?.planName || "Premium Access Active"}
                  </span>
                  <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-3xs font-black bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                    <span>Payment Approved</span>
                  </span>
                </div>
                <p className="text-xs text-slate-300">
                  Unlimited scheme access unlocked • {subscriptionOverview.days_remaining !== null ? `${subscriptionOverview.days_remaining} days validity remaining` : "Active pass"}
                </p>
              </div>
            </div>
            <button
              onClick={() => setSubModalOpen(true)}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-white/10 hover:bg-white/20 text-white text-xs font-bold transition border border-white/10 shrink-0"
            >
              <span>Manage Plan</span>
            </button>
          </div>
        ) : subscriptionOverview?.has_awaiting_admin_approval ? (
          <div className="p-5 rounded-2xl bg-amber-50/90 border border-amber-300 shadow-card text-amber-950 flex flex-col sm:flex-row sm:items-center justify-between gap-4 animate-in fade-in">
            <div className="flex items-start gap-3.5">
              <div className="w-10 h-10 rounded-2xl bg-amber-200/70 text-amber-900 flex items-center justify-center shrink-0 mt-0.5">
                <Clock className="w-5 h-5 text-amber-800" />
              </div>
              <div className="space-y-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm font-black text-amber-950">
                    Your payment request is awaiting admin review
                  </span>
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-3xs font-black bg-emerald-100 text-emerald-800 border border-emerald-300">
                    <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                    <span>Payment Verified</span>
                  </span>
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-3xs font-black bg-amber-200 text-amber-900">
                    <span className="w-1.5 h-1.5 rounded-full bg-amber-600 animate-ping"></span>
                    <span>Awaiting Admin Approval</span>
                  </span>
                </div>
                <p className="text-xs text-amber-800 leading-relaxed">
                  Your payment for <strong className="font-bold">{subscriptionOverview.awaiting_admin_approval?.planName}</strong> (₹{subscriptionOverview.awaiting_admin_approval?.amount}) has been cryptographically verified by the backend. Once the administrator approves it, your premium access will activate automatically in real-time without refreshing.
                </p>
                <div className="flex items-center gap-3 text-3xs text-amber-700 font-mono pt-0.5">
                  <span>Ref: {subscriptionOverview.awaiting_admin_approval?.razorpayOrderId || subscriptionOverview.awaiting_admin_approval?.razorpayPaymentId || `Req #${subscriptionOverview.awaiting_admin_approval?.id}`}</span>
                  <span>•</span>
                  <span>Live Stream Connected</span>
                </div>
              </div>
            </div>
          </div>
        ) : subscriptionOverview?.latest_request?.adminApprovalStatus === "rejected" || subscriptionOverview?.latest_request?.adminApprovalStatus === "ADMIN_REJECTED" ? (
          <div className="p-5 rounded-2xl bg-rose-50/90 border border-rose-200 shadow-card text-rose-950 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="flex items-start gap-3.5">
              <div className="w-10 h-10 rounded-2xl bg-rose-100 text-rose-700 flex items-center justify-center shrink-0 mt-0.5">
                <XCircle className="w-5 h-5 text-rose-600" />
              </div>
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-black text-rose-950">
                    Payment Request Rejected
                  </span>
                  <span className="px-2 py-0.5 rounded-full text-3xs font-black bg-rose-200 text-rose-900">
                    Payment Rejected
                  </span>
                </div>
                <p className="text-xs text-rose-800">
                  {subscriptionOverview.latest_request.rejectionReason || "Your payment request was not approved by the administrator. The plan remains inactive."}
                </p>
              </div>
            </div>
            <button
              onClick={() => setSubModalOpen(true)}
              className="inline-flex items-center gap-1.5 px-4 py-2 bg-rose-600 hover:bg-rose-700 text-white rounded-xl text-xs font-bold transition shrink-0 shadow-xs"
            >
              <span>Choose Subscription Plan</span>
            </button>
          </div>
        ) : subscriptionOverview?.latest_request?.paymentStatus === "PAYMENT_FAILED" ? (
          <div className="p-5 rounded-2xl bg-rose-50/90 border border-rose-200 shadow-card text-rose-950 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="flex items-start gap-3.5">
              <div className="w-10 h-10 rounded-2xl bg-rose-100 text-rose-700 flex items-center justify-center shrink-0 mt-0.5">
                <AlertTriangle className="w-5 h-5 text-rose-600" />
              </div>
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-black text-rose-950">
                    Payment Failed
                  </span>
                  <span className="px-2 py-0.5 rounded-full text-3xs font-black bg-rose-200 text-rose-900">
                    Payment Failed
                  </span>
                </div>
                <p className="text-xs text-rose-800">
                  {subscriptionOverview.latest_request.failureReason || "Bank verification or payment was declined. You can retry with any supported payment method."}
                </p>
              </div>
            </div>
            <button
              onClick={() => setSubModalOpen(true)}
              className="inline-flex items-center gap-1.5 px-4 py-2 bg-rose-600 hover:bg-rose-700 text-white rounded-xl text-xs font-bold transition shrink-0 shadow-xs"
            >
              <span>Retry Payment</span>
            </button>
          </div>
        ) : (
          <div className="p-4 sm:p-5 rounded-2xl bg-gradient-to-r from-amber-500/10 via-brand-blue/5 to-teal-500/10 border border-amber-200/80 shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-xl bg-amber-100 text-amber-800 flex items-center justify-center shrink-0">
                <Crown className="w-5 h-5 text-amber-600" />
              </div>
              <div>
                <p className="text-xs sm:text-sm font-extrabold text-brand-navy">
                  Unlock 100% of Matching Schemes with Premium Pass
                </p>
                <p className="text-2xs sm:text-xs text-slate-500">
                  Access all central &amp; state benefits beyond the 5-scheme free tier. Plans start at ₹50/month.
                </p>
              </div>
            </div>
            <button
              onClick={() => setSubModalOpen(true)}
              className="inline-flex items-center gap-1.5 px-4 py-2 bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-400 hover:to-amber-500 text-white rounded-xl text-xs font-black shadow-xs transition shrink-0"
            >
              <Crown className="w-3.5 h-3.5" />
              <span>View Subscription Plans</span>
            </button>
          </div>
        )}

        {/* 1. BENEFICIARY PROFILE SWITCHER BAR */}
        <FamilyProfileSwitcher 
          onProfileChanged={(newProfile) => {
            setProfile(newProfile);
          }}
        />

        {/* 2. DEDICATED FAMILY & BENEFICIARY PROFILES MANAGER SECTION */}
        <div className="p-5 sm:p-6 bg-white rounded-2xl border border-brand-border shadow-card space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-100">
            <div className="space-y-0.5">
              <div className="flex items-center gap-2">
                <Users className="w-5 h-5 text-brand-blue" />
                <h2 className="text-base sm:text-lg font-black text-brand-navy">
                  Family & Beneficiary Profiles
                </h2>
                <span className="px-2 py-0.5 rounded-full text-2xs font-extrabold bg-blue-50 text-brand-blue border border-blue-200">
                  {familyProfiles?.length || 1} Saved
                </span>
              </div>
              <p className="text-xs text-slate-500">
                Select any person to calculate scheme eligibility and view personalized recommendations for them.
              </p>
            </div>

            <button
              type="button"
              onClick={() => {
                setEditingTarget(null);
                setModalOpen(true);
              }}
              className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-bold bg-brand-blue hover:bg-brand-blue-dark text-white shadow-2xs transition self-start sm:self-auto shrink-0"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Add Family Member</span>
            </button>
          </div>

          {/* Grid of Saved Profiles */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3.5">
            {familyProfiles && familyProfiles.length > 0 ? (
              familyProfiles.map((p) => {
                const rel = p.relationship || "Self";
                const icon = RELATION_ICONS[rel] || "👤";
                const isSelected = profile && (
                  (p.id && profile.id && p.id === profile.id) ||
                  (p.name === profile.name && rel === profile.relationship)
                );

                return (
                  <div
                    key={p.id || `${rel}-${p.name}`}
                    className={`p-4 rounded-2xl border transition-all flex flex-col justify-between space-y-3 ${
                      isSelected
                        ? "bg-blue-50/40 border-brand-blue shadow-xs ring-2 ring-brand-blue/20"
                        : "bg-slate-50/60 hover:bg-white border-slate-200 hover:border-slate-300 hover:shadow-xs"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-center gap-2.5">
                        <div className="w-10 h-10 rounded-2xl bg-white border border-slate-200 flex items-center justify-center text-xl shadow-2xs shrink-0">
                          {icon}
                        </div>
                        <div>
                          <h4 className="font-extrabold text-sm text-brand-navy leading-tight">
                            {p.name || p.fullName || "Citizen"}
                          </h4>
                          <span className={`inline-block mt-0.5 px-2 py-0.5 rounded-md text-2xs font-extrabold ${
                            rel === "Self" ? "bg-blue-100 text-brand-blue" :
                            rel === "Father" ? "bg-amber-100 text-amber-800" :
                            rel === "Mother" ? "bg-rose-100 text-rose-800" :
                            rel === "Child" ? "bg-emerald-100 text-emerald-800" :
                            rel === "Spouse" ? "bg-purple-100 text-purple-800" :
                            "bg-slate-200 text-slate-700"
                          }`}>
                            {rel}
                          </span>
                        </div>
                      </div>

                      {isSelected && (
                        <span className="flex items-center gap-1 text-2xs font-bold text-emerald-700 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded-full">
                          <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                          <span>Active</span>
                        </span>
                      )}
                    </div>

                    {/* Criteria Details */}
                    <div className="grid grid-cols-2 gap-1.5 text-xs text-slate-600 bg-white/80 p-2.5 rounded-xl border border-slate-100">
                      <div>
                        <span className="text-3xs uppercase font-bold text-slate-400 block">Occupation</span>
                        <span className="font-semibold text-slate-800 truncate block">{p.occupation || "Not Specified"}</span>
                      </div>
                      <div>
                        <span className="text-3xs uppercase font-bold text-slate-400 block">Age & State</span>
                        <span className="font-semibold text-slate-800 truncate block">
                          {p.age ? `${p.age} yrs` : "—"} • {p.state || "India"}
                        </span>
                      </div>
                    </div>

                    {/* Card Actions */}
                    <div className="flex items-center justify-between gap-2 pt-1 border-t border-slate-200/60">
                      <div className="flex items-center gap-1">
                        <button
                          type="button"
                          onClick={() => {
                            setEditingTarget(p);
                            setModalOpen(true);
                          }}
                          className="p-1.5 rounded-lg text-slate-500 hover:text-brand-blue hover:bg-white transition"
                          title="Edit Details"
                        >
                          <Edit3 className="w-3.5 h-3.5" />
                        </button>
                        {p.relationship !== "Self" && (
                          <button
                            type="button"
                            onClick={() => p.id && handleDeleteProfile(p.id, p.name)}
                            className="p-1.5 rounded-lg text-slate-400 hover:text-rose-600 hover:bg-white transition"
                            title="Delete Profile"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        )}
                      </div>

                      {isSelected ? (
                        <Link
                          href="/schemes"
                          className="inline-flex items-center gap-1 px-3 py-1.5 rounded-xl text-xs font-bold bg-brand-blue text-white shadow-2xs hover:bg-brand-blue-dark transition"
                        >
                          <span>View Schemes</span>
                          <ArrowRight className="w-3 h-3" />
                        </Link>
                      ) : (
                        <button
                          type="button"
                          onClick={() => switchActiveProfile(p)}
                          className="inline-flex items-center gap-1 px-3 py-1.5 rounded-xl text-xs font-bold bg-white hover:bg-blue-50 text-brand-blue border border-brand-blue/30 transition shadow-2xs"
                        >
                          <span>Select Profile</span>
                        </button>
                      )}
                    </div>
                  </div>
                );
              })
            ) : (
              <div className="col-span-full p-6 text-center text-slate-400 text-xs font-semibold">
                Loading saved family profiles...
              </div>
            )}
          </div>
        </div>

        {/* Dynamic Citizen User Level Progression Banner */}
        <div className="p-4 sm:p-5 bg-white rounded-2xl border border-brand-border shadow-card flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
          <div className="flex items-center gap-3.5">
            <div className={`w-12 h-12 rounded-2xl flex items-center justify-center shadow-xs shrink-0 ${
              (computedUserLevel?.level || 1) >= 4 ? "bg-amber-100 text-amber-700" :
              (computedUserLevel?.level || 1) >= 3 ? "bg-indigo-100 text-indigo-700" :
              (computedUserLevel?.level || 1) >= 2 ? "bg-teal-100 text-teal-700" :
              "bg-blue-100 text-brand-blue"
            }`}>
              <Award className="w-6 h-6" />
            </div>
            <div className="space-y-0.5">
              <div className="flex items-center gap-2">
                <span className="text-2xs font-extrabold uppercase tracking-wider text-slate-400">
                  Dynamic Citizen Level
                </span>
                <span className={`px-2 py-0.5 rounded-full text-2xs font-black border ${
                  (computedUserLevel?.level || 1) === 5 ? "bg-amber-50 text-amber-700 border-amber-200" :
                  (computedUserLevel?.level || 1) === 4 ? "bg-purple-50 text-purple-700 border-purple-200" :
                  (computedUserLevel?.level || 1) === 3 ? "bg-indigo-50 text-indigo-700 border-indigo-200" :
                  (computedUserLevel?.level || 1) === 2 ? "bg-teal-50 text-teal-700 border-teal-200" :
                  "bg-blue-50 text-brand-blue border-blue-200"
                }`}>
                  Level {computedUserLevel?.level || 1} • {computedUserLevel?.levelName || "New Citizen"}
                </span>
              </div>
              <p className="text-xs sm:text-sm font-extrabold text-brand-navy">
                {computedUserLevel?.score || 0} / 100 Experience Points
              </p>
            </div>
          </div>

          <div className="w-full md:w-72 space-y-1.5">
            <div className="flex items-center justify-between text-2xs font-bold">
              <span className="text-slate-500">Progression</span>
              <span className="text-brand-blue">
                {computedUserLevel?.pointsToNext ? `${computedUserLevel.pointsToNext} pts to Level ${(computedUserLevel?.level || 1) + 1}` : "Top Level Champion"}
              </span>
            </div>
            <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
              <div
                className="bg-gradient-to-r from-brand-blue to-teal-500 h-2 rounded-full transition-all duration-700"
                style={{ width: `${Math.min(100, Math.max(5, computedUserLevel?.score || 10))}%` }}
              />
            </div>
            <div className="flex items-center justify-between text-3xs text-slate-400">
              <span>Profile: {computedUserLevel?.breakdown?.profilePoints || 0}pts</span>
              <span>Activities: {computedUserLevel?.breakdown?.activityPoints || 0}pts</span>
              <span>Saved: {computedUserLevel?.breakdown?.savedSchemesPoints || 0}pts</span>
            </div>
          </div>
        </div>

        {/* 4 Summary Cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 sm:gap-4">
          {stats.map((st) => (
            <div
              key={st.label}
              className={`p-4 sm:p-5 rounded-2xl bg-white border border-brand-border shadow-card flex flex-col justify-between`}
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-slate-500">{st.label}</span>
                {st.icon && <st.icon className={`w-4 h-4 ${st.color}`} />}
              </div>
              <div className={`text-2xl sm:text-3xl font-black mt-3 ${st.color}`}>
                {st.value}
              </div>
            </div>
          ))}
        </div>

        {/* Middle Section: Top 3 Opportunities & Quick Actions */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Top 3 Opportunities (7 cols) */}
          <div className="lg:col-span-7 p-6 bg-white rounded-2xl border border-brand-border shadow-card space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <h2 className="text-base sm:text-lg font-extrabold text-brand-navy">
                  Top Opportunities for {profile?.name || "You"}
                </h2>
                <span className="text-2xs font-extrabold px-2 py-0.5 rounded-md bg-slate-100 text-slate-600">
                  {profile?.relationship || "Self"}
                </span>
              </div>
              <Link href="/schemes" className="text-xs font-bold text-brand-blue hover:underline">
                View all ({counts.total})
              </Link>
            </div>

            {topOpportunities.length > 0 ? (
              <div className="space-y-3">
                {topOpportunities.map((opp, idx) => (
                  <Link
                    key={opp.id}
                    href={`/schemes/${opp.id}`}
                    className="p-3.5 rounded-xl border border-brand-border hover:border-blue-300 hover:bg-blue-50/30 transition flex items-center justify-between gap-3 group"
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-7 h-7 rounded-full bg-emerald-100 text-emerald-800 font-extrabold text-xs flex items-center justify-center shrink-0">
                        {idx + 1}
                      </div>
                      <div>
                        <h3 className="font-bold text-xs sm:text-sm text-brand-navy group-hover:text-brand-blue transition">
                          {opp.name}
                        </h3>
                        <p className="text-[11px] font-semibold text-emerald-600">
                          {opp.match}
                        </p>
                      </div>
                    </div>

                    <div className="flex items-center gap-2">
                      <span className={`px-2.5 py-1 rounded-full text-[11px] font-bold border ${opp.badgeColor}`}>
                        {opp.priority}
                      </span>
                      <ChevronRight className="w-4 h-4 text-slate-400 group-hover:translate-x-1 transition-transform" />
                    </div>
                  </Link>
                ))}
              </div>
            ) : (
              <div className="p-8 text-center space-y-3 border border-dashed rounded-xl bg-slate-50/50">
                <p className="text-sm font-bold text-brand-navy">
                  No matching opportunities calculated yet
                </p>
                <p className="text-xs text-slate-500 max-w-md mx-auto">
                  Please complete your profile details (occupation, state, and age) to evaluate your eligibility against central &amp; state government schemes.
                </p>
                <Link
                  href="/profile"
                  className="inline-flex items-center gap-1.5 mt-2 px-4 py-2 text-xs font-bold text-white bg-brand-blue rounded-xl hover:bg-brand-blue-dark transition shadow-2xs"
                >
                  <span>Complete Your Profile</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </Link>
              </div>
            )}
          </div>

          {/* Quick Actions (5 cols) */}
          <div className="lg:col-span-5 p-6 bg-white rounded-2xl border border-brand-border shadow-card space-y-4">
            <h2 className="text-base sm:text-lg font-extrabold text-brand-navy">
              Quick Actions
            </h2>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {quickActions.map((qa) => {
                const Icon = qa.icon;
                return (
                  <Link
                    key={qa.title}
                    href={qa.href}
                    className="p-3.5 rounded-xl border border-brand-border bg-slate-50/50 hover:bg-white hover:border-brand-blue hover:shadow-card transition flex flex-col justify-between group"
                  >
                    <div className={`w-9 h-9 rounded-lg flex items-center justify-center mb-2.5 ${qa.color}`}>
                      <Icon className="w-4 h-4" />
                    </div>
                    <span className="text-xs font-bold text-brand-navy group-hover:text-brand-blue transition">
                      {qa.title}
                    </span>
                  </Link>
                );
              })}
            </div>
          </div>
        </div>

        {/* Bottom Section: Category Distribution & Recent Activity */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Scheme Category Distribution (7 cols) */}
          <div className="lg:col-span-7 p-6 bg-white rounded-2xl border border-brand-border shadow-card space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-base sm:text-lg font-extrabold text-brand-navy">
                Schemes by Category for {profile?.name || "Beneficiary"}
              </h2>
              <span className="text-xs text-slate-500 font-semibold">
                {schemes.length} total schemes
              </span>
            </div>

            {categoryDistribution.length > 0 ? (
              <div className="flex flex-col sm:flex-row items-center gap-6">
                <div className="w-48 h-48 relative">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={categoryDistribution}
                        cx="50%"
                        cy="50%"
                        innerRadius={50}
                        outerRadius={80}
                        paddingAngle={3}
                        dataKey="count"
                      >
                        {categoryDistribution.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={entry.fill} />
                        ))}
                      </Pie>
                      <Tooltip />
                    </PieChart>
                  </ResponsiveContainer>
                </div>

                <div className="flex-1 grid grid-cols-2 gap-2 w-full">
                  {categoryDistribution.map((cat) => (
                    <div key={cat.name} className="flex items-center gap-2 p-1.5 rounded-lg hover:bg-slate-50 text-xs">
                      <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: cat.fill }} />
                      <span className="text-slate-600 font-medium truncate flex-1">{cat.name}</span>
                      <span className="font-extrabold text-brand-navy shrink-0">{cat.count}</span>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <p className="text-xs text-slate-400 py-8 text-center italic">
                No category metrics available yet.
              </p>
            )}
          </div>

          {/* Real User Activities (5 cols) */}
          <div className="lg:col-span-5 p-6 bg-white rounded-2xl border border-brand-border shadow-card space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-base sm:text-lg font-extrabold text-brand-navy">
                Recent Activity
              </h2>
              <span className="text-xs text-slate-500 font-semibold">
                {activities.length} entries
              </span>
            </div>

            <div className="space-y-3 max-h-72 overflow-y-auto pr-1">
              {activitiesLoading ? (
                <div className="p-4 text-center text-xs text-slate-400 font-semibold animate-pulse">
                  Loading activity log...
                </div>
              ) : activities.length > 0 ? (
                activities.slice(0, 5).map((act) => (
                  <div key={act.id} className="p-3 rounded-xl border border-brand-border/70 bg-slate-50/50 flex items-start gap-3">
                    <div className="w-2 h-2 rounded-full bg-brand-blue mt-1.5 shrink-0" />
                    <div className="flex-1 min-w-0">
                      <h4 className="text-xs font-bold text-brand-navy truncate">
                        {act.title}
                      </h4>
                      <div className="flex items-center gap-2 mt-0.5 text-3xs text-slate-400">
                        <span className="font-medium text-slate-500">{act.category}</span>
                        <span>•</span>
                        <span className="flex items-center gap-0.5">
                          <Clock className="w-2.5 h-2.5" />
                          <span>{act.timeAgo}</span>
                        </span>
                      </div>
                    </div>
                  </div>
                ))
              ) : (
                <div className="p-4 text-center text-xs text-slate-400 font-semibold">
                  No recent activity recorded yet.
                </div>
              )}
            </div>
          </div>
        </div>

      </div>

      {/* Modal for adding or editing beneficiary */}
      <FamilyProfileModal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        editProfile={editingTarget}
        onProfileSaved={(saved) => {
          setProfile(saved);
        }}
      />

      {/* Subscription Plans & Checkout Modal */}
      <SubscriptionModal
        isOpen={subModalOpen}
        onClose={() => setSubModalOpen(false)}
        onSubscriptionUpdated={() => {
          fetchMySubscriptionStatus().then((updated) => {
            if (updated) setSubscriptionOverview(updated);
          });
        }}
      />
    </main>
  );
}

export default function DashboardPage() {
  return (
    <ProtectedRoute>
      <DashboardContent />
    </ProtectedRoute>
  );
}
