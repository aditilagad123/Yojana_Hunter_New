"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { GraduationCap, Award, Wrench, FileWarning, BookOpen, AlertCircle, Sparkles, ArrowRight, ShieldCheck, Bookmark, Loader2, ExternalLink } from "lucide-react";
import { Scheme } from "@/types/scheme";
import { EligibilityBadge } from "./EligibilityBadge";
import { useAuth } from "@/context/AuthContext";
import { saveScheme, removeSavedScheme, checkIsSaved } from "@/services/savedSchemeService";

interface Props {
  scheme: Scheme;
}

export const SchemeCard: React.FC<Props> = ({ scheme }) => {
  const router = useRouter();
  const { isAuthenticated } = useAuth();
  const [isSaved, setIsSaved] = useState(Boolean((scheme as any).isSaved));
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (isAuthenticated && (scheme as any).isSaved === undefined) {
      checkIsSaved(scheme.slug || scheme.id).then(setIsSaved);
    }
  }, [isAuthenticated, scheme]);

  const handleToggleBookmark = async (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (!isAuthenticated) {
      router.push("/login?redirect=/schemes");
      return;
    }
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
  const getIcon = () => {
    switch (scheme.id) {
      case "pm-vidyalakshmi":
        return (
          <div className="w-12 h-12 rounded-xl bg-amber-50 border border-amber-200 flex items-center justify-center shrink-0">
            <GraduationCap className="w-6 h-6 text-amber-600" />
          </div>
        );
      case "post-matric-scholarship":
        return (
          <div className="w-12 h-12 rounded-xl bg-emerald-50 border border-emerald-200 flex items-center justify-center shrink-0">
            <BookOpen className="w-6 h-6 text-emerald-600" />
          </div>
        );
      case "skill-india-training":
        return (
          <div className="w-12 h-12 rounded-xl bg-orange-50 border border-orange-200 flex items-center justify-center shrink-0">
            <Wrench className="w-6 h-6 text-orange-600" />
          </div>
        );
      case "mjp-jan-arogya":
        return (
          <div className="w-12 h-12 rounded-xl bg-rose-50 border border-rose-200 flex items-center justify-center shrink-0">
            <FileWarning className="w-6 h-6 text-rose-600" />
          </div>
        );
      default:
        return (
          <div className="w-12 h-12 rounded-xl bg-blue-50 border border-blue-200 flex items-center justify-center shrink-0">
            <Award className="w-6 h-6 text-brand-blue" />
          </div>
        );
    }
  };

  const getApplicationWindowBadge = () => {
    if (!scheme.applicationStatus || scheme.applicationStatus === "open") return null;
    if (scheme.applicationStatus === "closed") {
      return (
        <span className="px-2 py-0.5 rounded-md text-3xs font-bold uppercase tracking-wider bg-rose-50 text-rose-700 border border-rose-200">
          Closed
        </span>
      );
    }
    if (scheme.applicationStatus === "closing_soon") {
      return (
        <span className="px-2 py-0.5 rounded-md text-3xs font-bold uppercase tracking-wider bg-amber-50 text-amber-700 border border-amber-200">
          Closing Soon
        </span>
      );
    }
    if (scheme.applicationStatus === "upcoming") {
      return (
        <span className="px-2 py-0.5 rounded-md text-3xs font-bold uppercase tracking-wider bg-blue-50 text-blue-700 border border-blue-200">
          Upcoming
        </span>
      );
    }
    return null;
  };


  return (
    <div className="p-4 sm:p-5 bg-white rounded-2xl border border-brand-border shadow-card hover:shadow-card-hover transition-all flex flex-col sm:flex-row sm:items-center justify-between gap-4">
      {/* Left side content */}
      <div className="flex items-start gap-4 flex-1 min-w-0">
        {getIcon()}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2.5 flex-wrap">
            <Link
              href={`/schemes/${scheme.slug || scheme.id}`}
              className="hover:text-brand-blue transition"
            >
              <h3 className="font-bold text-base sm:text-lg text-brand-navy">
                {scheme.name}
              </h3>
            </Link>
            <EligibilityBadge status={scheme.eligibilityStatus} size="sm" />
            {getApplicationWindowBadge()}
          </div>

          {/* Department & State Sub-badge */}
          <div className="mt-1 flex items-center gap-2 text-2xs text-slate-500 flex-wrap">
            <span className="font-medium text-slate-600">{scheme.department || "Government of India"}</span>
            <span>·</span>
            <span className="px-2 py-0.5 rounded bg-slate-100 text-slate-700 font-semibold">
              {scheme.level || "Central Scheme"} ({scheme.state || "All India"})
            </span>
            <span className="inline-flex items-center gap-1 text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200 font-semibold">
              <ShieldCheck className="w-3 h-3 text-emerald-600" />
              <span>Verified Official Source</span>
            </span>
          </div>

          <p className="mt-1.5 text-xs sm:text-sm text-slate-600 line-clamp-2">
            {scheme.shortDescription}
          </p>

          {/* Why you match snippet */}
          {scheme.whyMatched && (
            <div className="mt-2 text-xs text-slate-700 bg-blue-50/60 p-2.5 rounded-xl border border-blue-100 flex items-start gap-2">
              <Sparkles className="w-3.5 h-3.5 text-brand-blue shrink-0 mt-0.5" />
              <span className="line-clamp-2">{scheme.whyMatched}</span>
            </div>
          )}

          {/* Missing info prompt */}
          {scheme.missingInformation && scheme.missingInformation.length > 0 && scheme.eligibilityStatus !== "not_eligible" && (
            <div className="mt-1.5 text-2xs font-medium text-amber-800 bg-amber-50/70 px-2.5 py-1 rounded-lg border border-amber-200 flex items-center gap-1.5">
              <AlertCircle className="w-3 h-3 text-amber-600 shrink-0" />
              <span>Action needed: {scheme.missingInformation[0]}</span>
            </div>
          )}

          <div className="mt-2.5 flex items-center gap-4 text-xs flex-wrap">
            {scheme.benefit && (
              <span className="text-slate-600 font-medium">
                Benefit: <span className="font-semibold text-slate-900">{scheme.benefit}</span>
              </span>
            )}

            {scheme.criteria && scheme.criteria.find((c: any) => c.id === "c_occupation") && (
              <span className="font-medium text-slate-700 bg-slate-100 px-2 py-0.5 rounded border border-slate-200 text-2xs">
                Target: {scheme.criteria.find((c: any) => c.id === "c_occupation")?.condition}
              </span>
            )}

            {scheme.matchScore !== undefined && scheme.eligibilityStatus !== "not_eligible" && scheme.eligibilityStatus !== "ineligible" && (
              <span className="font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                Match Score: {scheme.matchScore}%
              </span>
            )}

            {scheme.ineligibleReason && (
              <span className="font-medium text-rose-700 bg-rose-50 px-2 py-0.5 rounded border border-rose-200">
                Reason: {scheme.ineligibleReason}
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Right Action Options */}
      <div className="shrink-0 flex sm:flex-col items-center sm:items-end justify-between sm:justify-center gap-2 pt-2 sm:pt-0 border-t sm:border-t-0 border-slate-100">
        <div className="flex items-center gap-2 flex-wrap sm:flex-nowrap justify-end">
          {/* Option 1: Save */}
          <button
            onClick={handleToggleBookmark}
            disabled={saving}
            title={isSaved ? "Saved to your bookmarks" : "Save this scheme"}
            className={`p-2 rounded-lg transition border ${
              isSaved
                ? "bg-amber-50 text-amber-600 border-amber-200 hover:bg-amber-100"
                : "bg-slate-50 text-slate-400 border-slate-200 hover:text-brand-blue hover:bg-slate-100"
            }`}
          >
            {saving ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Bookmark className={`w-3.5 h-3.5 ${isSaved ? "fill-current" : ""}`} />
            )}
          </button>

          {/* Option 2: View Details */}
          <Link
            href={`/schemes/${scheme.slug || scheme.id}`}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold text-slate-700 bg-slate-100 hover:bg-slate-200 border border-slate-200 transition"
            title="View scheme eligibility and details"
          >
            <span>View Details</span>
          </Link>

          {/* Main Action: Verified Official Destination URL */}
          {(scheme.applicationUrl || scheme.officialUrl) && (
            <a
              href={scheme.applicationUrl || scheme.officialUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-bold text-white bg-brand-blue hover:bg-brand-blue-dark shadow-xs transition"
              title={`Open official portal for ${scheme.name}`}
            >
              <span>
                {scheme.applicationUrl && scheme.applicationUrl !== scheme.officialUrl
                  ? "Apply Online"
                  : "Official Portal"}
              </span>
              <ExternalLink className="w-3.5 h-3.5" />
            </a>
          )}
        </div>
      </div>
    </div>
  );
};

