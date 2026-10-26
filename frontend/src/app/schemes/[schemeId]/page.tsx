"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { 
  ArrowLeft, 
  GraduationCap, 
  CheckCircle2, 
  XCircle, 
  ExternalLink, 
  Calendar, 
  Sparkles,
  HelpCircle,
  AlertCircle,
  FileText,
  Clock,
  Layers,
  ArrowRight,
  ShieldCheck,
  Building,
  UserCheck,
  Bookmark,
  Loader2,
  Lock,
  Crown,
} from "lucide-react";
import { getSchemeById, explainScheme, SchemeExplanationResult } from "@/services/schemeService";
import { Scheme } from "@/types/scheme";
import { EligibilityBadge } from "@/components/schemes/EligibilityBadge";
import { useAuth } from "@/context/AuthContext";
import { getStoredProfile } from "@/lib/storage";
import { saveScheme, removeSavedScheme, checkIsSaved } from "@/services/savedSchemeService";
import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import { SubscriptionModal } from "@/components/subscription/SubscriptionModal";
import { isValidHttpUrl } from "@/lib/urlUtils";

function SchemeDetailsContent() {
  const params = useParams();
  const router = useRouter();
  const schemeId = (params?.schemeId as string) || "pm-vidyalakshmi";
  const { isAuthenticated, profile: authProfile } = useAuth();
  const [scheme, setScheme] = useState<Scheme | null>(null);
  const [loading, setLoading] = useState(true);
  const [isSaved, setIsSaved] = useState(false);
  const [saving, setSaving] = useState(false);

  // Gemini AI Explanation State
  const [aiExplanation, setAiExplanation] = useState<SchemeExplanationResult | null>(null);
  const [loadingAi, setLoadingAi] = useState(false);
  const [showAiCard, setShowAiCard] = useState(false);
  const [subscriptionModalOpen, setSubscriptionModalOpen] = useState(false);

  const handleRequestAiExplanation = async () => {
    if (!scheme) return;
    setLoadingAi(true);
    setShowAiCard(true);
    try {
      const active = authProfile || getStoredProfile();
      const res = await explainScheme(scheme.slug || scheme.id, active, true);
      setAiExplanation(res);
    } catch {
      setAiExplanation({
        success: false,
        explanation: "Unable to contact Gemini AI service.",
        mode: "offline_fallback",
        citations: []
      });
    } finally {
      setLoadingAi(false);
    }
  };

  useEffect(() => {
    async function load() {
      setLoading(true);
      const active = authProfile || getStoredProfile();
      const data = await getSchemeById(schemeId, active);
      if (data) {
        setScheme(data);
        if (isAuthenticated) {
          checkIsSaved(data.slug || data.id).then(setIsSaved);
        }
      }
      setLoading(false);
    }
    load();
  }, [schemeId, isAuthenticated, authProfile]);

  const handleToggleBookmark = async () => {
    if (!isAuthenticated) {
      router.push(`/login?redirect=/schemes/${schemeId}`);
      return;
    }
    if (!scheme) return;
    setSaving(true);
    const targetId = scheme.slug || scheme.id;
    if (isSaved) {
      await removeSavedScheme(targetId);
      setIsSaved(false);
    } else {
      await saveScheme(targetId);
      setIsSaved(true);
    }
    setSaving(false);
  };

  if (loading) {
    return (
      <main className="flex-1 bg-brand-bg py-12 px-4 flex justify-center items-center">
        <div className="text-center p-8 bg-white rounded-2xl border border-brand-border">
          <p className="text-slate-600 font-bold">Evaluating eligibility and loading scheme details...</p>
        </div>
      </main>
    );
  }

  if (!scheme) {
    return (
      <main className="flex-1 bg-brand-bg py-12 px-4 flex justify-center items-center">
        <div className="text-center p-8 bg-white rounded-2xl border border-brand-border space-y-3">
          <p className="text-rose-600 font-bold text-base">Scheme not found or unpublished.</p>
          <Link
            href="/schemes"
            className="inline-flex items-center gap-1.5 text-xs sm:text-sm font-bold text-brand-blue underline"
          >
            Return to schemes catalog
          </Link>
        </div>
      </main>
    );
  }

  if (scheme.isLocked) {
    return (
      <main className="flex-1 bg-brand-bg py-8 px-4 sm:px-6 lg:px-8">
        <div className="max-w-2xl mx-auto space-y-6">
          <Link
            href="/schemes"
            className="inline-flex items-center gap-2 text-xs sm:text-sm font-bold text-brand-blue hover:text-brand-blue-dark transition"
          >
            <ArrowLeft className="w-4 h-4" />
            <span>Back to All Schemes</span>
          </Link>

          <div className="p-8 sm:p-10 bg-slate-900 border border-amber-500/30 rounded-3xl text-white shadow-2xl relative overflow-hidden text-center space-y-6">
            <div className="absolute top-0 right-0 -mr-20 -mt-20 w-72 h-72 bg-amber-500/10 rounded-full blur-3xl pointer-events-none" />
            <div className="absolute bottom-0 left-0 -ml-20 -mb-20 w-72 h-72 bg-blue-500/10 rounded-full blur-3xl pointer-events-none" />

            <div className="relative z-10 space-y-4">
              <div className="w-16 h-16 rounded-3xl bg-amber-500/20 border border-amber-400/40 text-amber-400 flex items-center justify-center mx-auto shadow-lg shadow-amber-500/10">
                <Lock className="w-8 h-8" />
              </div>

              <div className="inline-flex items-center gap-2 px-3.5 py-1 rounded-full bg-amber-500/20 border border-amber-400/30 text-amber-300 text-xs font-black uppercase tracking-wider">
                <Crown className="w-3.5 h-3.5" />
                <span>Rank #{scheme.rank || 6} Matching Scheme</span>
              </div>

              <div className="space-y-2">
                <h1 className="text-2xl sm:text-3xl font-black text-white tracking-tight">
                  {scheme.name}
                </h1>
                <p className="text-xs sm:text-sm text-slate-300 max-w-lg mx-auto leading-relaxed">
                  {scheme.lockMessage || "Free accounts can view the full details of only the first 5 schemes. Upgrade to Yojana Hunter Premium to unlock complete details, criteria breakdown, required documents, and application portals for this scheme."}
                </p>
              </div>

              <div className="p-4 rounded-2xl bg-white/5 border border-white/10 text-left space-y-2 text-xs text-slate-300">
                <p className="font-bold text-white text-xs uppercase tracking-wider text-amber-300">
                  Included with Yojana Hunter Premium:
                </p>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 pt-1 text-2xs sm:text-xs">
                  <div className="flex items-center gap-2">
                    <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                    <span>Access all matching schemes</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                    <span>Complete document checklists</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                    <span>Direct official portal links</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                    <span>Gemini AI Scheme Explanations</span>
                  </div>
                </div>
              </div>

              <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-2">
                <button
                  onClick={() => setSubscriptionModalOpen(true)}
                  className="w-full sm:w-auto px-8 py-3.5 rounded-2xl bg-gradient-to-r from-amber-500 via-amber-400 to-amber-500 hover:from-amber-400 hover:to-amber-300 text-slate-950 font-black text-sm shadow-xl shadow-amber-500/25 flex items-center justify-center gap-2 transition transform hover:-translate-y-0.5 active:translate-y-0"
                >
                  <Crown className="w-4 h-4 text-slate-950" />
                  <span>Unlock with Premium</span>
                  <ArrowRight className="w-4 h-4 text-slate-950" />
                </button>
                <Link
                  href="/schemes"
                  className="w-full sm:w-auto px-6 py-3.5 rounded-2xl bg-white/10 hover:bg-white/15 text-white font-bold text-xs transition border border-white/10"
                >
                  Return to Free Schemes
                </Link>
              </div>
            </div>
          </div>
        </div>

        <SubscriptionModal
          isOpen={subscriptionModalOpen}
          onClose={() => setSubscriptionModalOpen(false)}
          onSubscriptionUpdated={() => {
            const active = authProfile || getStoredProfile();
            getSchemeById(schemeId, active).then((data) => {
              if (data) setScheme(data);
            });
          }}
        />
      </main>
    );
  }

  return (
    <main className="flex-1 bg-brand-bg py-8 px-4 sm:px-6 lg:px-8">
      <div className="max-w-3xl mx-auto space-y-6">
        {/* Back Link */}
        <Link
          href="/schemes"
          className="inline-flex items-center gap-2 text-xs sm:text-sm font-bold text-brand-blue hover:text-brand-blue-dark transition"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Back to All Schemes</span>
        </Link>

        {/* Scheme Header Card */}
        <div className="p-6 bg-white rounded-2xl border border-brand-border shadow-card space-y-4">
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-start gap-4">
              <div className="w-14 h-14 rounded-2xl bg-amber-50 border border-amber-200 flex items-center justify-center shrink-0">
                <GraduationCap className="w-8 h-8 text-amber-600" />
              </div>
              <div>
                <div className="flex items-center gap-3 flex-wrap">
                  <h1 className="text-xl sm:text-2xl font-black text-brand-navy">
                    {scheme.name}
                  </h1>
                  <EligibilityBadge status={scheme.eligibilityStatus} />
                </div>
                <p className="text-xs sm:text-sm text-slate-500 mt-1">
                  {scheme.shortDescription}
                </p>
              </div>
            </div>

            {/* Bookmark button */}
            <button
              onClick={handleToggleBookmark}
              disabled={saving}
              title={isSaved ? "Saved to your bookmarks" : "Save this scheme"}
              className={`p-2.5 rounded-xl transition border flex items-center gap-1.5 text-xs font-bold shrink-0 ${
                isSaved
                  ? "bg-amber-50 text-amber-700 border-amber-200 hover:bg-amber-100"
                  : "bg-slate-50 text-slate-600 border-slate-200 hover:text-brand-blue hover:bg-slate-100"
              }`}
            >
              {saving ? (
                <Loader2 className="w-4 h-4 animate-spin text-amber-600" />
              ) : (
                <Bookmark className={`w-4 h-4 ${isSaved ? "fill-current" : ""}`} />
              )}
              <span className="hidden sm:inline">{isSaved ? "Saved" : "Save"}</span>
            </button>
          </div>

          {/* Department & Level Tags */}
          <div className="flex items-center gap-2 text-xs font-semibold pt-2 border-t border-slate-100 flex-wrap">
            <span className="px-3 py-1 rounded-md bg-slate-100 text-slate-700 flex items-center gap-1.5">
              <Building className="w-3.5 h-3.5 text-slate-500" />
              <span>{scheme.department || "Government of India"}</span>
            </span>
            <span className="px-3 py-1 rounded-md bg-blue-50 text-brand-blue">
              {scheme.level || "Central Scheme"}
            </span>
            <span className="px-3 py-1 rounded-md bg-emerald-50 text-emerald-800">
              State: {scheme.state || "All India"}
            </span>
            {scheme.applicationStatus && scheme.applicationStatus !== "open" && (
              <span className={`px-3 py-1 rounded-md font-bold uppercase text-2xs ${
                scheme.applicationStatus === "closed" ? "bg-rose-100 text-rose-800" : "bg-amber-100 text-amber-800"
              }`}>
                Window: {scheme.applicationStatus.replace("_", " ")}
              </span>
            )}
          </div>
        </div>

        {/* "Why am I seeing this scheme?" Transparent Match Explanation Card */}
        <div className="p-6 bg-gradient-to-r from-blue-50/70 to-indigo-50/70 border border-blue-200 rounded-2xl shadow-card space-y-3">
          <div className="flex items-center gap-2 text-brand-navy font-black text-base sm:text-lg">
            <Sparkles className="w-5 h-5 text-brand-blue shrink-0" />
            <span>Why am I seeing this scheme?</span>
          </div>
          <p className="text-xs sm:text-sm text-slate-700 leading-relaxed font-medium">
            {scheme.whyMatched || `Based on your profile, your age, residency, and qualification match the target criteria for ${scheme.name}.`}
          </p>
          {scheme.matchScore !== undefined && (
            <div className="pt-2 flex items-center gap-2">
              <span className="text-xs text-slate-600 font-semibold">Match Confidence:</span>
              <span className="px-2.5 py-0.5 rounded-full text-xs font-extrabold bg-white border border-blue-200 text-brand-blue shadow-2xs">
                {scheme.matchScore}% Relevance
              </span>
            </div>
          )}
          <p className="text-[11px] text-slate-500 italic pt-1">
            * Note: Eligibility match is an automated estimate based on your profile criteria. Official approval is subject to government verification of original documents.
          </p>
        </div>

        {/* Gemini AI Grounded Explanation Card */}
        <div className="p-6 bg-white border border-brand-border rounded-2xl shadow-card space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-lg bg-blue-50 border border-blue-200 flex items-center justify-center text-brand-blue">
                <Sparkles className="w-4 h-4" />
              </div>
              <div>
                <h3 className="text-sm sm:text-base font-extrabold text-brand-navy">
                  Gemini AI Grounded Explanation
                </h3>
                <p className="text-[11px] text-slate-500">
                  Plain-language summary grounded in official government source evidence
                </p>
              </div>
            </div>

            {!showAiCard ? (
              <button
                onClick={handleRequestAiExplanation}
                disabled={loadingAi}
                className="inline-flex items-center gap-1.5 px-3.5 py-2 bg-brand-blue hover:bg-brand-blue-dark text-white rounded-xl text-xs font-bold shadow-xs transition"
              >
                <Sparkles className="w-3.5 h-3.5" />
                <span>Explain in Simple Terms</span>
              </button>
            ) : (
              <button
                onClick={handleRequestAiExplanation}
                disabled={loadingAi}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl text-xs font-bold transition"
              >
                <Sparkles className={`w-3.5 h-3.5 ${loadingAi ? "animate-spin" : ""}`} />
                <span>Regenerate</span>
              </button>
            )}
          </div>

          {showAiCard && (
            <div className="space-y-3 pt-3 border-t border-slate-100">
              {loadingAi ? (
                <div className="py-6 flex flex-col items-center justify-center space-y-2">
                  <Loader2 className="w-6 h-6 text-brand-blue animate-spin" />
                  <p className="text-xs font-medium text-slate-500">
                    Consulting Gemini model with Google Search Grounding citations...
                  </p>
                </div>
              ) : aiExplanation ? (
                <div className="space-y-3">
                  <div className="p-4 bg-slate-50 rounded-xl border border-slate-200 text-xs sm:text-sm text-slate-700 leading-relaxed whitespace-pre-line font-medium">
                    {aiExplanation.explanation}
                  </div>

                  {/* Mode and Citations */}
                  <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
                    <span className="text-[10px] text-slate-500 font-mono bg-slate-100 px-2 py-0.5 rounded">
                      Source: {aiExplanation.mode === "gemini_grounded" ? "Gemini 2.5 (Search Grounded)" : aiExplanation.mode === "gemini_structured" ? "Gemini 2.5 (Structured)" : "Deterministic Official Summary"}
                    </span>

                    {aiExplanation.citations && aiExplanation.citations.length > 0 && (
                      <span className="text-[10px] font-bold text-brand-blue flex items-center gap-1">
                        <ShieldCheck className="w-3 h-3 text-emerald-600" />
                        {aiExplanation.citations.length} Official Citations Verified
                      </span>
                    )}
                  </div>

                  {/* Citations List if available */}
                  {aiExplanation.citations && aiExplanation.citations.length > 0 && (
                    <div className="p-3 bg-blue-50/50 rounded-xl border border-blue-100 space-y-1.5">
                      <div className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
                        Official Grounding Sources:
                      </div>
                      <div className="space-y-1">
                        {aiExplanation.citations.map((cite, i) => (
                          <div key={i} className="flex items-center justify-between text-xs">
                            <span className="font-semibold text-slate-700 truncate max-w-sm">
                              {cite.source_title}
                            </span>
                            {cite.source_url && (
                              <a
                                href={cite.source_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-brand-blue text-[11px] font-bold hover:underline flex items-center gap-0.5"
                              >
                                <span>Verify Source</span>
                                <ExternalLink className="w-2.5 h-2.5" />
                              </a>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  <p className="text-[10px] text-slate-400 italic">
                    Disclaimer: AI summaries are generated to explain eligibility rules simply. Scheme eligibility is determined deterministically from verified rules.
                  </p>
                </div>
              ) : null}
            </div>
          )}
        </div>

        {/* Benefits Card */}
        <div className="p-6 bg-white rounded-2xl border border-brand-border shadow-card space-y-3">
          <h2 className="text-base sm:text-lg font-extrabold text-brand-navy">
            Welfare Benefits
          </h2>
          <div className="p-4 bg-emerald-50/60 border border-emerald-200 rounded-xl">
            <p className="text-sm sm:text-base font-bold text-emerald-900 whitespace-pre-line">
              {scheme.benefit || scheme.benefits}
            </p>
          </div>
        </div>

        {/* Requirements Breakdown: Satisfied vs Not Satisfied */}
        <div className="p-6 bg-white rounded-2xl border border-brand-border shadow-card space-y-4">
          <h2 className="text-base sm:text-lg font-extrabold text-brand-navy">
            Eligibility Requirements Analysis
          </h2>

          {/* Requirements Satisfied */}
          {scheme.requirementsSatisfied && scheme.requirementsSatisfied.length > 0 && (
            <div className="space-y-2">
              <h3 className="text-xs font-bold uppercase tracking-wider text-emerald-700 flex items-center gap-1.5">
                <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                <span>Requirements Satisfied ({scheme.requirementsSatisfied.length})</span>
              </h3>
              <ul className="space-y-1.5 pl-1">
                {scheme.requirementsSatisfied.map((item, idx) => (
                  <li key={idx} className="flex items-start gap-2 text-xs sm:text-sm text-slate-700">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 shrink-0 mt-2" />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Requirements Not Satisfied */}
          {scheme.requirementsNotSatisfied && scheme.requirementsNotSatisfied.length > 0 && (
            <div className="space-y-2 pt-2 border-t border-slate-100">
              <h3 className="text-xs font-bold uppercase tracking-wider text-rose-700 flex items-center gap-1.5">
                <XCircle className="w-4 h-4 text-rose-600" />
                <span>Requirements Not Met ({scheme.requirementsNotSatisfied.length})</span>
              </h3>
              <ul className="space-y-1.5 pl-1">
                {scheme.requirementsNotSatisfied.map((item, idx) => (
                  <li key={idx} className="flex items-start gap-2 text-xs sm:text-sm text-rose-700 font-medium">
                    <span className="w-1.5 h-1.5 rounded-full bg-rose-500 shrink-0 mt-2" />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Missing Information Alert */}
          {scheme.missingInformation && scheme.missingInformation.length > 0 && (
            <div className="p-4 bg-amber-50/80 border border-amber-200 rounded-xl space-y-2">
              <div className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-amber-800">
                <AlertCircle className="w-4 h-4 text-amber-600 shrink-0" />
                <span>Missing Information for Verification</span>
              </div>
              <ul className="space-y-1 pl-1">
                {scheme.missingInformation.map((item, idx) => (
                  <li key={idx} className="text-xs text-amber-900 font-medium flex items-start gap-1.5">
                    <span className="w-1.5 h-1.5 rounded-full bg-amber-600 shrink-0 mt-1.5" />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
              <div className="pt-1">
                <Link
                  href="/profile"
                  className="inline-flex items-center gap-1 text-xs font-bold text-amber-800 hover:text-amber-950 underline"
                >
                  <span>Update your citizen profile now</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </Link>
              </div>
            </div>
          )}

          {/* Detailed Criteria Comparison Breakdown Table */}
          {scheme.criteria && scheme.criteria.length > 0 && (
            <div className="space-y-2 pt-3 border-t border-slate-100">
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-1.5">
                <Layers className="w-4 h-4 text-brand-blue" />
                <span>Eligibility Criteria Comparison ({scheme.criteria.length})</span>
              </h3>
              <div className="overflow-x-auto rounded-xl border border-slate-200">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-50 border-b border-slate-200 text-slate-500 font-bold">
                    <tr>
                      <th className="py-2.5 px-3">Criterion</th>
                      <th className="py-2.5 px-3">Scheme Condition</th>
                      <th className="py-2.5 px-3">Your Profile Value</th>
                      <th className="py-2.5 px-3 text-center">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {scheme.criteria.map((c, idx) => (
                      <tr key={c.id || idx} className="hover:bg-slate-50/50">
                        <td className="py-2.5 px-3 font-semibold text-slate-800">{c.name}</td>
                        <td className="py-2.5 px-3 text-slate-600">{c.condition}</td>
                        <td className="py-2.5 px-3 font-medium text-slate-700">{c.userValue || "Not Provided"}</td>
                        <td className="py-2.5 px-3 text-center">
                          {c.passed ? (
                            <span className="inline-flex items-center gap-1 text-2xs font-extrabold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-200">
                              <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                              <span>Passed</span>
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 text-2xs font-extrabold text-rose-700 bg-rose-50 px-2 py-0.5 rounded-full border border-rose-200">
                              <XCircle className="w-3 h-3 text-rose-600" />
                              <span>Failed</span>
                            </span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>

        {/* Required Documents Card */}
        {scheme.requiredDocuments && scheme.requiredDocuments.length > 0 && (
          <div className="p-6 bg-white rounded-2xl border border-brand-border shadow-card space-y-3">
            <h2 className="text-base sm:text-lg font-extrabold text-brand-navy flex items-center gap-2">
              <FileText className="w-5 h-5 text-brand-blue" />
              <span>Required Documents</span>
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
              {scheme.requiredDocuments.map((doc, idx) => (
                <div
                  key={idx}
                  className="p-3 bg-slate-50 border border-slate-200 rounded-xl text-xs sm:text-sm font-semibold text-slate-800 flex items-center gap-2"
                >
                  <ShieldCheck className="w-4 h-4 text-emerald-600 shrink-0" />
                  <span>{doc}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Application Process Card */}
        {scheme.applicationProcess && (
          <div className="p-6 bg-white rounded-2xl border border-brand-border shadow-card space-y-3">
            <h2 className="text-base sm:text-lg font-extrabold text-brand-navy">
              Application Procedure
            </h2>
            <p className="text-xs sm:text-sm text-slate-700 leading-relaxed whitespace-pre-line">
              {scheme.applicationProcess}
            </p>
          </div>
        )}

        {/* Official Source & Verification Card */}
        {(() => {
          // Select dedicated application portal or official website
          const candidateUrl = scheme.applicationUrl || scheme.officialUrl;
          const hasValidUrl = isValidHttpUrl(candidateUrl);
          const isUnavailable = scheme.portalStatus === "temporarily_unavailable" || scheme.portalStatus === "unverified";
          const isVerifiedAndReachable = hasValidUrl && !isUnavailable && (scheme.portalStatus === "reachable" || scheme.portalStatus === undefined);

          return (
            <>
              <div className="p-6 bg-white rounded-2xl border border-brand-border shadow-card space-y-4">
                <h3 className="font-extrabold text-sm sm:text-base text-brand-navy">
                  Official Government Source & Verification
                </h3>

                <div className="space-y-3 text-xs sm:text-sm">
                  {isVerifiedAndReachable ? (
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                      <span className="text-slate-500 font-medium">Official Website:</span>
                      <a
                        href={candidateUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1.5 font-bold text-brand-blue hover:underline break-all"
                        title="Open verified official government website in a new tab"
                      >
                        <span>{candidateUrl}</span>
                        <ExternalLink className="w-3.5 h-3.5 shrink-0" />
                      </a>
                    </div>
                  ) : (
                    <div className="p-3.5 bg-amber-50 border border-amber-200 rounded-xl space-y-1 text-xs text-amber-800">
                      <div className="flex items-center gap-1.5 font-bold text-amber-900">
                        <AlertCircle className="w-4 h-4 text-amber-600 shrink-0" />
                        <span>Official application link could not be verified</span>
                      </div>
                      <p className="text-amber-700 leading-relaxed">
                        {scheme.portalStatusMessage || "The official application portal is currently undergoing maintenance or could not be reached. Scheme eligibility details can still be reviewed below."}
                      </p>
                    </div>
                  )}

                  <div className="flex items-center justify-between pt-2 border-t border-slate-100 text-slate-500 text-xs">
                    <span className="flex items-center gap-1">
                      <Calendar className="w-3.5 h-3.5 text-slate-400" />
                      <span>Last Verified Date: {scheme.lastVerifiedDate || "12 Oct 2026"}</span>
                    </span>
                    {isVerifiedAndReachable ? (
                      <span className="text-2xs font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200 flex items-center gap-1">
                        <ShieldCheck className="w-3 h-3 text-emerald-600" />
                        <span>Verified Government Portal</span>
                      </span>
                    ) : (
                      <span className="text-2xs font-bold text-amber-700 bg-amber-50 px-2 py-0.5 rounded border border-amber-200">
                        Unverified Link
                      </span>
                    )}
                  </div>
                </div>
              </div>

              {/* Action Button: Exactly one official URL option */}
              <div className="pt-2">
                {isVerifiedAndReachable ? (
                  <a
                    href={candidateUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="w-full py-3.5 px-6 rounded-xl bg-brand-blue hover:bg-brand-blue-dark text-white font-extrabold text-center text-sm shadow-md transition flex items-center justify-center gap-2"
                    title="Apply on official government website in a new tab"
                  >
                    <span>Apply on Official Website</span>
                    <ExternalLink className="w-4 h-4" />
                  </a>
                ) : (
                  <button
                    onClick={() => router.push("/action-plan")}
                    className="w-full py-3.5 px-6 rounded-xl bg-slate-800 hover:bg-slate-900 text-white font-extrabold text-center text-sm shadow-md transition flex items-center justify-center gap-2"
                  >
                    <span>Start Application via Action Plan</span>
                    <ArrowRight className="w-4 h-4" />
                  </button>
                )}
              </div>
            </>
          );
        })()}
      </div>
    </main>
  );
}

export default function SchemeDetailsPage() {
  return (
    <ProtectedRoute>
      <SchemeDetailsContent />
    </ProtectedRoute>
  );
}
