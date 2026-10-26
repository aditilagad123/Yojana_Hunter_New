"use client";

import React, { useState, useEffect } from "react";
import { 
  Crown, 
  CheckCircle2, 
  XCircle, 
  Clock, 
  AlertCircle, 
  Search, 
  RefreshCw, 
  Filter, 
  User, 
  Calendar, 
  IndianRupee, 
  ShieldCheck, 
  FileText,
  X,
  AlertTriangle,
  HelpCircle,
  Eye,
  CreditCard,
  Building,
  Check,
  ExternalLink,
  RotateCcw
} from "lucide-react";
import { 
  fetchAdminSubscriptions, 
  approveSubscription, 
  rejectSubscription,
  markPaymentFailed,
  markUnderReview,
  verifyGatewayStatus,
  recordAdminOutcomeSuccess,
  recordAdminOutcomeMandateFailed,
  recordAdminOutcomeFailed,
  authorizeRetryMandate
} from "@/services/subscriptionService";
import { 
  SubscriptionRequestRecord, 
  SubscriptionAdminStats 
} from "@/types/subscription";

type AdminFilterTab = "all" | "pending" | "review" | "approved" | "active" | "mandate_failed" | "failed";

export default function AdminSubscriptionsPage() {
  const [requests, setRequests] = useState<SubscriptionRequestRecord[]>([]);
  const [stats, setStats] = useState<SubscriptionAdminStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoadingId, setActionLoadingId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [successToast, setSuccessToast] = useState<string | null>(null);

  // Filters & Search
  const [activeTab, setActiveTab] = useState<AdminFilterTab>("pending");
  const [searchQuery, setSearchQuery] = useState("");

  // Modals State
  const [rejectModalReq, setRejectModalReq] = useState<SubscriptionRequestRecord | null>(null);
  const [rejectionReason, setRejectionReason] = useState("");

  const [markFailedModalReq, setMarkFailedModalReq] = useState<SubscriptionRequestRecord | null>(null);
  const [failureReason, setFailureReason] = useState("");

  const [reviewModalReq, setReviewModalReq] = useState<SubscriptionRequestRecord | null>(null);
  const [reviewNotes, setReviewNotes] = useState("");

  const [approveModalReq, setApproveModalReq] = useState<SubscriptionRequestRecord | null>(null);
  const [approvalNotes, setApprovalNotes] = useState("");

  // Admin Outcome Validation Modals State (Options A, B, C & Retry Mandate)
  const [outcomeSuccessModalReq, setOutcomeSuccessModalReq] = useState<SubscriptionRequestRecord | null>(null);
  const [outcomeSuccessNotes, setOutcomeSuccessNotes] = useState("");

  const [outcomeMandateFailedModalReq, setOutcomeMandateFailedModalReq] = useState<SubscriptionRequestRecord | null>(null);
  const [outcomeMandateFailedReason, setOutcomeMandateFailedReason] = useState("");
  const [outcomeMandateFailedNotes, setOutcomeMandateFailedNotes] = useState("");

  const [outcomeFailedModalReq, setOutcomeFailedModalReq] = useState<SubscriptionRequestRecord | null>(null);
  const [outcomeFailedReason, setOutcomeFailedReason] = useState("");
  const [outcomeFailedNotes, setOutcomeFailedNotes] = useState("");

  const [retryMandateModalReq, setRetryMandateModalReq] = useState<SubscriptionRequestRecord | null>(null);
  const [retryMandateNotes, setRetryMandateNotes] = useState("");

  const loadData = async (filterTab: string = activeTab) => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchAdminSubscriptions(filterTab);
      if (data) {
        setRequests(data.requests || []);
        setStats(data.stats || null);
      }
    } catch (err: any) {
      setError(err?.message || "Failed to load subscription requests from backend.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData(activeTab);
  }, [activeTab]);

  const handleOpenApproveModal = (req: SubscriptionRequestRecord) => {
    setApproveModalReq(req);
    setApprovalNotes("");
  };

  const handleConfirmApprove = async () => {
    if (!approveModalReq) return;
    const displayName = approveModalReq.userName || approveModalReq.user?.name || `User #${approveModalReq.userId}`;
    setActionLoadingId(approveModalReq.id);
    try {
      const res = await approveSubscription(approveModalReq.id, approvalNotes.trim());
      setSuccessToast(res.message || `Authorized payment workflow for ${displayName}! Customer can now proceed to payment.`);
      setTimeout(() => setSuccessToast(null), 6000);
      setApproveModalReq(null);
      await loadData(activeTab);
    } catch (err: any) {
      alert(`Approval failed: ${err?.message || "Internal server error"}`);
    } finally {
      setActionLoadingId(null);
    }
  };

  const handleOpenRejectModal = (req: SubscriptionRequestRecord) => {
    setRejectModalReq(req);
    setRejectionReason("");
  };

  const handleConfirmReject = async () => {
    if (!rejectModalReq) return;
    const displayName = rejectModalReq.userName || rejectModalReq.user?.name || `User #${rejectModalReq.userId}`;
    setActionLoadingId(rejectModalReq.id);
    try {
      const res = await rejectSubscription(rejectModalReq.id, rejectionReason.trim());
      setSuccessToast(res.message || `Rejected request for ${displayName}.`);
      setTimeout(() => setSuccessToast(null), 5000);
      setRejectModalReq(null);
      await loadData(activeTab);
    } catch (err: any) {
      alert(`Rejection failed: ${err?.message || "Internal server error"}`);
    } finally {
      setActionLoadingId(null);
    }
  };

  const handleOpenMarkFailedModal = (req: SubscriptionRequestRecord) => {
    setMarkFailedModalReq(req);
    setFailureReason("");
  };

  const handleConfirmMarkFailed = async () => {
    if (!markFailedModalReq) return;
    setActionLoadingId(markFailedModalReq.id);
    try {
      const res = await markPaymentFailed(markFailedModalReq.id, failureReason.trim());
      setSuccessToast(res.message || `Payment marked as failed.`);
      setTimeout(() => setSuccessToast(null), 5000);
      setMarkFailedModalReq(null);
      await loadData(activeTab);
    } catch (err: any) {
      alert(`Mark failed action error: ${err?.message || "Internal server error"}`);
    } finally {
      setActionLoadingId(null);
    }
  };

  const handleOpenReviewModal = (req: SubscriptionRequestRecord) => {
    setReviewModalReq(req);
    setReviewNotes("");
  };

  const handleConfirmReview = async () => {
    if (!reviewModalReq) return;
    setActionLoadingId(reviewModalReq.id);
    try {
      const res = await markUnderReview(reviewModalReq.id, reviewNotes.trim());
      setSuccessToast(res.message || `Request placed under administrative review.`);
      setTimeout(() => setSuccessToast(null), 5000);
      setReviewModalReq(null);
      await loadData(activeTab);
    } catch (err: any) {
      alert(`Review action error: ${err?.message || "Internal server error"}`);
    } finally {
      setActionLoadingId(null);
    }
  };

  const handleVerifyGateway = async (req: SubscriptionRequestRecord) => {
    setActionLoadingId(req.id);
    try {
      const res = await verifyGatewayStatus(req.id);
      setSuccessToast(res.message || "Gateway status verified successfully with Razorpay.");
      setTimeout(() => setSuccessToast(null), 6000);
      await loadData(activeTab);
    } catch (err: any) {
      alert(`Gateway check failed: ${err?.message || "Internal server error"}`);
    } finally {
      setActionLoadingId(null);
    }
  };

  // Option A Handler: Payment Successful
  const handleOpenOutcomeSuccessModal = (req: SubscriptionRequestRecord) => {
    setOutcomeSuccessModalReq(req);
    setOutcomeSuccessNotes("");
  };

  const handleConfirmOutcomeSuccess = async () => {
    if (!outcomeSuccessModalReq) return;
    setActionLoadingId(outcomeSuccessModalReq.id);
    try {
      const res = await recordAdminOutcomeSuccess(outcomeSuccessModalReq.id, outcomeSuccessNotes.trim());
      if (res.success) {
        setSuccessToast(res.message || `Option A applied: Payment & e-Mandate confirmed successful for #${outcomeSuccessModalReq.id}.`);
        setTimeout(() => setSuccessToast(null), 6000);
        setOutcomeSuccessModalReq(null);
        await loadData(activeTab);
      } else {
        alert(res.message || "Failed to confirm payment success");
      }
    } catch (err: any) {
      alert(`Option A error: ${err?.message || "Internal server error"}`);
    } finally {
      setActionLoadingId(null);
    }
  };

  // Option B Handler: Payment Successful but e-Mandate Failed
  const handleOpenOutcomeMandateFailedModal = (req: SubscriptionRequestRecord) => {
    setOutcomeMandateFailedModalReq(req);
    setOutcomeMandateFailedReason("Payment captured successfully, but bank recurring e-Mandate registration failed / declined by issuing bank.");
    setOutcomeMandateFailedNotes("");
  };

  const handleConfirmOutcomeMandateFailed = async () => {
    if (!outcomeMandateFailedModalReq) return;
    setActionLoadingId(outcomeMandateFailedModalReq.id);
    try {
      const res = await recordAdminOutcomeMandateFailed(
        outcomeMandateFailedModalReq.id,
        outcomeMandateFailedReason.trim(),
        outcomeMandateFailedNotes.trim()
      );
      if (res.success) {
        setSuccessToast(res.message || `Option B applied: Payment recorded as successful but e-Mandate failed for #${outcomeMandateFailedModalReq.id}.`);
        setTimeout(() => setSuccessToast(null), 6000);
        setOutcomeMandateFailedModalReq(null);
        await loadData(activeTab);
      } else {
        alert(res.message || "Failed to record mandate failure");
      }
    } catch (err: any) {
      alert(`Option B error: ${err?.message || "Internal server error"}`);
    } finally {
      setActionLoadingId(null);
    }
  };

  // Option C Handler: Payment Failed
  const handleOpenOutcomeFailedModal = (req: SubscriptionRequestRecord) => {
    setOutcomeFailedModalReq(req);
    setOutcomeFailedReason("Payment authorization declined by issuing bank or gateway.");
    setOutcomeFailedNotes("");
  };

  const handleConfirmOutcomeFailed = async () => {
    if (!outcomeFailedModalReq) return;
    setActionLoadingId(outcomeFailedModalReq.id);
    try {
      const res = await recordAdminOutcomeFailed(
        outcomeFailedModalReq.id,
        outcomeFailedReason.trim(),
        outcomeFailedNotes.trim()
      );
      if (res.success) {
        setSuccessToast(res.message || `Option C applied: Payment marked as failed for #${outcomeFailedModalReq.id}.`);
        setTimeout(() => setSuccessToast(null), 6000);
        setOutcomeFailedModalReq(null);
        await loadData(activeTab);
      } else {
        alert(res.message || "Failed to record payment failure");
      }
    } catch (err: any) {
      alert(`Option C error: ${err?.message || "Internal server error"}`);
    } finally {
      setActionLoadingId(null);
    }
  };

  // Authorize Retry Mandate Handler
  const handleOpenRetryMandateModal = (req: SubscriptionRequestRecord) => {
    setRetryMandateModalReq(req);
    setRetryMandateNotes("Authorized citizen to retry payment or e-mandate.");
  };

  const handleConfirmRetryMandate = async () => {
    if (!retryMandateModalReq) return;
    setActionLoadingId(retryMandateModalReq.id);
    try {
      const res = await authorizeRetryMandate(retryMandateModalReq.id, retryMandateNotes.trim());
      if (res.success) {
        setSuccessToast(res.message || `Retry authorized for request #${retryMandateModalReq.id}. Citizen can now retry without duplicate charges.`);
        setTimeout(() => setSuccessToast(null), 6000);
        setRetryMandateModalReq(null);
        await loadData(activeTab);
      } else {
        alert(res.message || "Failed to authorize retry");
      }
    } catch (err: any) {
      alert(`Retry authorize error: ${err?.message || "Internal server error"}`);
    } finally {
      setActionLoadingId(null);
    }
  };

  // Filtered requests by search query
  const filteredRequests = requests.filter((r) => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    const name = (r.userName || r.user?.name || "").toLowerCase();
    const email = (r.userEmail || r.user?.email || "").toLowerCase();
    const plan = (r.planName || "").toLowerCase();
    const subId = (r.razorpaySubscriptionId || "").toLowerCase();
    const payId = (r.razorpayPaymentId || "").toLowerCase();
    return (
      name.includes(q) ||
      email.includes(q) ||
      plan.includes(q) ||
      subId.includes(q) ||
      payId.includes(q) ||
      r.id.toString().includes(q)
    );
  });

  return (
    <div className="max-w-7xl mx-auto space-y-8 p-4 sm:p-6 lg:p-8">
      {/* Top Banner / Title */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="px-2.5 py-0.5 rounded-md text-2xs font-extrabold uppercase bg-amber-50 text-amber-800 border border-amber-200 flex items-center gap-1">
              <Crown className="w-3.5 h-3.5 text-amber-600" />
              Admin Controlled Payment Approval
            </span>
            <span className="text-2xs text-slate-500">
              Secured Razorpay e-Mandate Pipeline
            </span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-black text-brand-navy tracking-tight mt-1">
            Subscription Plan &amp; Payment Approval
          </h1>
          <p className="text-xs sm:text-sm text-slate-500 mt-1">
            Review user requests, authorize payment workflows, verify gateway e-mandates, and inspect payment audit logs.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => loadData(activeTab)}
            disabled={loading}
            className="inline-flex items-center gap-1.5 px-4 py-2.5 bg-white hover:bg-slate-50 border border-brand-border text-slate-700 rounded-xl text-xs sm:text-sm font-bold shadow-xs transition"
          >
            <RefreshCw className={`w-4 h-4 text-brand-blue ${loading ? "animate-spin" : ""}`} />
            <span>Refresh Records</span>
          </button>
        </div>
      </div>

      {/* Success Alert Toast */}
      {successToast && (
        <div className="p-4 rounded-2xl bg-emerald-50 border border-emerald-200 text-emerald-900 text-xs sm:text-sm font-bold flex items-center justify-between gap-3 shadow-xs">
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-5 h-5 text-emerald-600 shrink-0" />
            <span>{successToast}</span>
          </div>
          <button onClick={() => setSuccessToast(null)} className="text-emerald-700 hover:text-emerald-900 text-xs">
            Dismiss
          </button>
        </div>
      )}

      {/* Error Alert */}
      {error && (
        <div className="p-4 rounded-2xl bg-rose-50 border border-rose-200 flex items-center justify-between gap-4 text-rose-700 text-xs sm:text-sm">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-5 h-5 shrink-0 text-rose-500" />
            <span className="font-medium">{error}</span>
          </div>
          <button
            onClick={() => loadData(activeTab)}
            className="text-xs font-bold underline hover:text-rose-900"
          >
            Retry
          </button>
        </div>
      )}

      {/* 5 Stats Cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3.5">
        {/* Total */}
        <div className="p-4 rounded-2xl bg-white border border-brand-border shadow-xs space-y-1">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-3xs font-extrabold uppercase tracking-wider">Total Requests</span>
            <FileText className="w-4 h-4 text-slate-400" />
          </div>
          <p className="text-2xl font-black text-brand-navy">
            {stats ? stats.total : "—"}
          </p>
          <p className="text-3xs text-slate-500">All submitted requests</p>
        </div>

        {/* Pending Review */}
        <div className="p-4 rounded-2xl bg-amber-50/60 border border-amber-200 shadow-xs space-y-1">
          <div className="flex items-center justify-between text-amber-700">
            <span className="text-3xs font-extrabold uppercase tracking-wider">Pending Review</span>
            <Clock className="w-4 h-4 text-amber-600" />
          </div>
          <p className="text-2xl font-black text-amber-800">
            {stats ? stats.pending : "—"}
          </p>
          <p className="text-3xs text-amber-600 font-medium">Awaiting admin authorization</p>
        </div>

        {/* Approved for Payment */}
        <div className="p-4 rounded-2xl bg-blue-50/60 border border-blue-200 shadow-xs space-y-1">
          <div className="flex items-center justify-between text-blue-700">
            <span className="text-3xs font-extrabold uppercase tracking-wider">Approved for Pay</span>
            <ShieldCheck className="w-4 h-4 text-blue-600" />
          </div>
          <p className="text-2xl font-black text-blue-800">
            {stats ? stats.approved : "—"}
          </p>
          <p className="text-3xs text-blue-600 font-medium">Citizen authorized to pay</p>
        </div>

        {/* Paid & Active */}
        <div className="p-4 rounded-2xl bg-emerald-50/60 border border-emerald-200 shadow-xs space-y-1">
          <div className="flex items-center justify-between text-emerald-700">
            <span className="text-3xs font-extrabold uppercase tracking-wider">Paid &amp; Active</span>
            <CheckCircle2 className="w-4 h-4 text-emerald-600" />
          </div>
          <p className="text-2xl font-black text-emerald-800">
            {stats ? (stats.active ?? 0) : "—"}
          </p>
          <p className="text-3xs text-emerald-600 font-medium">Payment verified &amp; live</p>
        </div>

        {/* Failed / Rejected */}
        <div className="p-4 rounded-2xl bg-rose-50/60 border border-rose-200 shadow-xs space-y-1">
          <div className="flex items-center justify-between text-rose-700">
            <span className="text-3xs font-extrabold uppercase tracking-wider">Failed / Rejected</span>
            <XCircle className="w-4 h-4 text-rose-600" />
          </div>
          <p className="text-2xl font-black text-rose-800">
            {stats ? (stats.failed || 0) + (stats.rejected || 0) : "—"}
          </p>
          <p className="text-3xs text-rose-600 font-medium">Declined or failed payments</p>
        </div>
      </div>

      {/* Main Content Area: Filter Tabs & Search */}
      <div className="bg-white rounded-2xl border border-brand-border shadow-card overflow-hidden">
        {/* Table Controls */}
        <div className="p-4 sm:p-5 border-b border-slate-100 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          {/* Status Tabs */}
          <div className="flex items-center gap-1.5 p-1 bg-slate-100 rounded-xl overflow-x-auto">
            <button
              onClick={() => setActiveTab("pending")}
              className={`px-3 py-1.5 rounded-lg text-xs font-bold transition flex items-center gap-1.5 whitespace-nowrap ${
                activeTab === "pending"
                  ? "bg-white text-amber-800 shadow-xs"
                  : "text-slate-600 hover:text-brand-navy"
              }`}
            >
              <Clock className="w-3.5 h-3.5 text-amber-600" />
              <span>Pending Review</span>
              {stats && stats.pending > 0 && (
                <span className="px-1.5 py-0.2 rounded-full text-3xs font-black bg-amber-200 text-amber-900">
                  {stats.pending}
                </span>
              )}
            </button>

            <button
              onClick={() => setActiveTab("approved")}
              className={`px-3 py-1.5 rounded-lg text-xs font-bold transition flex items-center gap-1.5 whitespace-nowrap ${
                activeTab === "approved"
                  ? "bg-white text-blue-800 shadow-xs"
                  : "text-slate-600 hover:text-brand-navy"
              }`}
            >
              <ShieldCheck className="w-3.5 h-3.5 text-blue-600" />
              <span>Approved for Pay</span>
              {stats && stats.approved > 0 && (
                <span className="px-1.5 py-0.2 rounded-full text-3xs font-black bg-blue-200 text-blue-900">
                  {stats.approved}
                </span>
              )}
            </button>

            <button
              onClick={() => setActiveTab("active")}
              className={`px-3 py-1.5 rounded-lg text-xs font-bold transition flex items-center gap-1.5 whitespace-nowrap ${
                activeTab === "active"
                  ? "bg-white text-emerald-800 shadow-xs"
                  : "text-slate-600 hover:text-brand-navy"
              }`}
            >
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
              <span>Paid &amp; Active</span>
              {Boolean(stats && typeof stats.active === "number" && stats.active > 0) && (
                <span className="px-1.5 py-0.2 rounded-full text-3xs font-black bg-emerald-200 text-emerald-900">
                  {stats!.active}
                </span>
              )}
            </button>

            <button
              onClick={() => setActiveTab("review")}
              className={`px-3 py-1.5 rounded-lg text-xs font-bold transition flex items-center gap-1.5 whitespace-nowrap ${
                activeTab === "review"
                  ? "bg-white text-purple-800 shadow-xs"
                  : "text-slate-600 hover:text-brand-navy"
              }`}
            >
              <HelpCircle className="w-3.5 h-3.5 text-purple-600" />
              <span>Under Review</span>
              {Boolean(stats && typeof stats.review === "number" && stats.review > 0) && (
                <span className="px-1.5 py-0.2 rounded-full text-3xs font-black bg-purple-200 text-purple-900">
                  {stats!.review}
                </span>
              )}
            </button>

            <button
              onClick={() => setActiveTab("mandate_failed")}
              className={`px-3 py-1.5 rounded-lg text-xs font-bold transition flex items-center gap-1.5 whitespace-nowrap ${
                activeTab === "mandate_failed"
                  ? "bg-white text-amber-800 shadow-xs"
                  : "text-slate-600 hover:text-brand-navy"
              }`}
            >
              <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
              <span>Mandate Failed</span>
            </button>

            <button
              onClick={() => setActiveTab("failed")}
              className={`px-3 py-1.5 rounded-lg text-xs font-bold transition flex items-center gap-1.5 whitespace-nowrap ${
                activeTab === "failed"
                  ? "bg-white text-rose-800 shadow-xs"
                  : "text-slate-600 hover:text-brand-navy"
              }`}
            >
              <XCircle className="w-3.5 h-3.5 text-rose-600" />
              <span>Failed / Rejected</span>
            </button>

            <button
              onClick={() => setActiveTab("all")}
              className={`px-3 py-1.5 rounded-lg text-xs font-bold transition flex items-center gap-1.5 whitespace-nowrap ${
                activeTab === "all"
                  ? "bg-white text-brand-navy shadow-xs"
                  : "text-slate-600 hover:text-brand-navy"
              }`}
            >
              <span>All ({stats?.total || 0})</span>
            </button>
          </div>

          {/* Search Box */}
          <div className="relative w-full sm:w-72">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search user, plan, ref ID..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-4 py-2 text-xs bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-brand-blue/30 focus:border-brand-blue"
            />
          </div>
        </div>

        {/* Requests List Table */}
        {loading ? (
          <div className="p-12 text-center space-y-3">
            <RefreshCw className="w-6 h-6 text-brand-blue animate-spin mx-auto" />
            <p className="text-slate-500 font-bold text-xs">Loading subscription records from PostgreSQL...</p>
          </div>
        ) : filteredRequests.length === 0 ? (
          <div className="p-12 text-center space-y-3">
            <div className="w-12 h-12 rounded-full bg-slate-100 text-slate-400 flex items-center justify-center mx-auto">
              <Crown className="w-6 h-6" />
            </div>
            <p className="text-slate-600 font-bold text-sm">No subscription requests found in this filter.</p>
            <p className="text-xs text-slate-400">
              {activeTab === "pending"
                ? "All user subscription requests have been reviewed!"
                : "No records match the current status or search query."}
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 border-b border-slate-100 text-slate-500 font-extrabold uppercase text-3xs tracking-wider">
                <tr>
                  <th className="py-3 px-4">User Name &amp; ID</th>
                  <th className="py-3 px-4">Subscription Plan</th>
                  <th className="py-3 px-4">Duration</th>
                  <th className="py-3 px-4">Amount</th>
                  <th className="py-3 px-4">Request Date &amp; Time</th>
                  <th className="py-3 px-4">Payment Ref / Order ID</th>
                  <th className="py-3 px-4">Payment Verification</th>
                  <th className="py-3 px-4">Admin Decision</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filteredRequests.map((req) => {
                  const uName = req.userName || req.user?.name || `User #${req.userId}`;
                  const uEmail = req.userEmail || req.user?.email || `ID: ${req.userId}`;
                  
                  // Verification status
                  const isVerified = req.paymentVerificationStatus === "verified" || req.paymentStatus === "PAYMENT_SUCCESS";
                  const isVerificationFailed = req.paymentVerificationStatus === "failed" || req.paymentStatus === "PAYMENT_FAILED";
                  
                  // Admin decision status
                  const adminStatus = (req.adminApprovalStatus || "pending").toLowerCase();
                  const isApproved = adminStatus === "approved" || adminStatus === "admin_approved" || adminStatus === "approved_for_payment";
                  const isRejected = adminStatus === "rejected" || adminStatus === "admin_rejected";
                  const isPending = !isApproved && !isRejected;

                  // Formatted Date & Time
                  const reqDateTime = req.requestedAt 
                    ? new Date(req.requestedAt).toLocaleString("en-IN", { 
                        day: "2-digit", 
                        month: "short", 
                        year: "numeric", 
                        hour: "2-digit", 
                        minute: "2-digit" 
                      })
                    : "—";

                  return (
                    <tr key={req.id} className="hover:bg-slate-50/70 transition">
                      {/* 1. User Name & Existing User ID */}
                      <td className="py-3.5 px-4">
                        <div className="flex items-center gap-2.5">
                          <span className="px-1.5 py-0.5 rounded text-3xs font-black bg-slate-100 text-slate-700 border border-slate-200">
                            #{req.id}
                          </span>
                          <div>
                            <p className="font-extrabold text-brand-navy text-xs">
                              {uName}
                            </p>
                            <p className="text-3xs text-slate-400 font-medium">
                              {uEmail} • <span className="font-bold text-slate-600">User ID: #{req.userId}</span>
                            </p>
                          </div>
                        </div>
                      </td>

                      {/* 2. Selected Subscription Plan */}
                      <td className="py-3.5 px-4">
                        <div className="flex items-center gap-1.5">
                          <Crown className="w-3.5 h-3.5 text-amber-500 shrink-0" />
                          <span className="font-bold text-slate-800">{req.planName}</span>
                        </div>
                        <span className="text-3xs text-slate-400 uppercase tracking-wider font-semibold">
                          {req.planId}
                        </span>
                      </td>

                      {/* 3. Plan Duration */}
                      <td className="py-3.5 px-4">
                        <div className="font-bold text-slate-800">
                          {req.durationDays} Days
                        </div>
                        <div className="text-3xs text-slate-400 font-medium">
                          {req.planId === "yearly" ? "12 Months" : req.planId === "two_months" ? "2 Months" : "1 Month"}
                        </div>
                      </td>

                      {/* 4. Plan Amount */}
                      <td className="py-3.5 px-4">
                        <div className="font-black text-slate-900 text-sm">
                          ₹{req.amount}
                        </div>
                        <div className="text-3xs text-slate-400 uppercase font-semibold">
                          {req.currency || "INR"} (Validated)
                        </div>
                      </td>

                      {/* 5. Request Date & Time */}
                      <td className="py-3.5 px-4">
                        <div className="text-xs font-semibold text-slate-700 flex items-center gap-1">
                          <Calendar className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                          <span>{reqDateTime}</span>
                        </div>
                        {req.reviewedAt && (
                          <div className="text-3xs text-slate-400 mt-0.5">
                            Decided: {new Date(req.reviewedAt).toLocaleDateString("en-IN", { day: "numeric", month: "short" })}
                          </div>
                        )}
                      </td>

                      {/* 6. Payment Reference or Razorpay Order ID */}
                      <td className="py-3.5 px-4 space-y-0.5">
                        {req.razorpayOrderId ? (
                          <div className="text-3xs font-mono font-bold text-slate-800 bg-slate-100 px-1.5 py-0.5 rounded inline-block truncate max-w-[150px]" title={req.razorpayOrderId}>
                            {req.razorpayOrderId}
                          </div>
                        ) : req.razorpayPaymentId ? (
                          <div className="text-3xs font-mono font-bold text-slate-800 bg-slate-100 px-1.5 py-0.5 rounded inline-block truncate max-w-[150px]" title={req.razorpayPaymentId}>
                            Pay: {req.razorpayPaymentId}
                          </div>
                        ) : (
                          <div className="text-3xs text-slate-400">
                            Awaiting order creation
                          </div>
                        )}
                        {(req.bankName || req.paymentMethod) && (
                          <div className="text-3xs text-slate-500 font-medium">
                            {req.bankName || req.paymentMethod} {req.bankAccountType ? `(${req.bankAccountType})` : ""}
                          </div>
                        )}
                      </td>

                      {/* 7. Payment Verification Status */}
                      <td className="py-3.5 px-4">
                        {isVerified ? (
                          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-3xs font-black bg-emerald-50 text-emerald-800 border border-emerald-200">
                            <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                            <span>Verified</span>
                          </span>
                        ) : isVerificationFailed ? (
                          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-3xs font-black bg-rose-50 text-rose-800 border border-rose-200">
                            <XCircle className="w-3 h-3 text-rose-600" />
                            <span>Failed</span>
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-3xs font-black bg-amber-50 text-amber-800 border border-amber-200">
                            <Clock className="w-3 h-3 text-amber-600" />
                            <span>Pending</span>
                          </span>
                        )}
                      </td>

                      {/* 8. Admin Decision Status */}
                      <td className="py-3.5 px-4">
                        {isApproved ? (
                          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-3xs font-black bg-emerald-100 text-emerald-800 border border-emerald-300">
                            <ShieldCheck className="w-3 h-3 text-emerald-700" />
                            <span>Approved</span>
                          </span>
                        ) : isRejected ? (
                          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-3xs font-black bg-rose-100 text-rose-800 border border-rose-300">
                            <XCircle className="w-3 h-3 text-rose-700" />
                            <span>Rejected</span>
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-3xs font-black bg-amber-100 text-amber-800 border border-amber-300">
                            <Clock className="w-3 h-3 text-amber-700" />
                            <span>Pending Review</span>
                          </span>
                        )}
                        {req.isActive && (
                          <div className="text-3xs font-black text-emerald-600 mt-1 flex items-center gap-1">
                            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
                            <span>Active Plan</span>
                          </div>
                        )}
                      </td>

                      {/* 9. Actions: Lifecycle-based Admin Controls */}
                      <td className="py-3.5 px-4 text-right">
                        <div className="flex items-center justify-end gap-2 flex-wrap">
                          {/* 1. If Pending Review: Approve for Pay and Reject */}
                          {isPending && (
                            <>
                              <button
                                onClick={() => handleOpenApproveModal(req)}
                                disabled={actionLoadingId === req.id}
                                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-extrabold text-3xs shadow-xs transition disabled:opacity-50"
                                title="Approve for Payment (Authorizes citizen to proceed to payment)"
                              >
                                <ShieldCheck className="w-3.5 h-3.5" />
                                <span>Approve for Pay</span>
                              </button>

                              <button
                                onClick={() => handleOpenRejectModal(req)}
                                disabled={actionLoadingId === req.id}
                                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 font-extrabold text-3xs transition disabled:opacity-50"
                                title="Reject Request"
                              >
                                <XCircle className="w-3.5 h-3.5 text-rose-600" />
                                <span>Reject</span>
                              </button>
                            </>
                          )}

                          {/* 2. If Approved for Pay & Not Yet Active: Mark Successful, Mark Failed, Reject */}
                          {isApproved && !req.isActive && (
                            <>
                              <button
                                onClick={() => handleOpenOutcomeSuccessModal(req)}
                                disabled={actionLoadingId === req.id}
                                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white font-extrabold text-3xs shadow-xs transition disabled:opacity-50"
                                title="Mark Payment Successful (Verifies gateway transaction & activates subscription)"
                              >
                                <CheckCircle2 className="w-3.5 h-3.5" />
                                <span>Mark Payment Successful</span>
                              </button>

                              <button
                                onClick={() => handleOpenOutcomeFailedModal(req)}
                                disabled={actionLoadingId === req.id}
                                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 font-extrabold text-3xs transition disabled:opacity-50"
                                title="Mark Payment Failed"
                              >
                                <XCircle className="w-3.5 h-3.5 text-rose-600" />
                                <span>Mark Payment Failed</span>
                              </button>

                              <button
                                onClick={() => handleOpenRejectModal(req)}
                                disabled={actionLoadingId === req.id}
                                className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-300 font-extrabold text-3xs transition disabled:opacity-50"
                                title="Reject Request"
                              >
                                <X className="w-3.5 h-3.5 text-slate-600" />
                                <span>Reject</span>
                              </button>
                            </>
                          )}

                          {/* 3. If Mandate Failed: Authorize Retry */}
                          {req.mandateStatus === "MANDATE_FAILED" && (
                            <button
                              onClick={() => handleOpenRetryMandateModal(req)}
                              disabled={actionLoadingId === req.id}
                              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-amber-500 hover:bg-amber-600 text-slate-950 font-extrabold text-3xs shadow-xs transition disabled:opacity-50"
                              title="Authorize Citizen to Retry Payment or e-Mandate"
                            >
                              <RotateCcw className="w-3.5 h-3.5" />
                              <span>Authorize Retry</span>
                            </button>
                          )}

                          {/* 4. Gateway verify fallback query button */}
                          {(req.isActive || req.razorpayOrderId || req.razorpayPaymentId) && (
                            <button
                              onClick={() => handleVerifyGateway(req)}
                              disabled={actionLoadingId === req.id}
                              className="inline-flex items-center gap-1 px-2 py-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-300 font-bold text-3xs transition disabled:opacity-50"
                              title="Query Razorpay API to check real-time gateway status"
                            >
                              <RefreshCw className={`w-3 h-3 ${actionLoadingId === req.id ? "animate-spin" : ""}`} />
                              <span>Verify</span>
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Approve for Payment Confirmation Modal */}
      {approveModalReq && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs">
          <div className="w-full max-w-md bg-white rounded-3xl p-6 shadow-2xl border border-brand-border space-y-4">
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-2xl bg-blue-50 text-blue-600 flex items-center justify-center shrink-0">
                  <ShieldCheck className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-extrabold text-base text-brand-navy">Approve for Payment</h3>
                  <p className="text-2xs text-slate-500">Authorize citizen to proceed with Razorpay payment workflow</p>
                </div>
              </div>
              <button
                onClick={() => setApproveModalReq(null)}
                className="p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-3 rounded-xl bg-slate-50 border border-slate-200 text-xs text-slate-700 space-y-1">
              <div><strong>User:</strong> {approveModalReq.userName || approveModalReq.user?.name || `User #${approveModalReq.userId}`} ({approveModalReq.userEmail || approveModalReq.user?.email || `ID: ${approveModalReq.userId}`})</div>
              <div><strong>User ID:</strong> #{approveModalReq.userId}</div>
              <div><strong>Selected Plan:</strong> {approveModalReq.planName} (₹{approveModalReq.amount} / {approveModalReq.durationDays} Days)</div>
              {approveModalReq.phoneNumber && (
                <div><strong>Phone Number:</strong> {approveModalReq.phoneNumber}</div>
              )}
              {approveModalReq.paymentMethod && (
                <div><strong>Payment Method:</strong> {approveModalReq.paymentMethod} {approveModalReq.bankName ? `(${approveModalReq.bankName})` : ""}</div>
              )}
            </div>

            <div className="p-3 rounded-xl bg-blue-50 border border-blue-200 text-xs text-blue-900 space-y-1">
              <p className="font-bold flex items-center gap-1.5">
                <ShieldCheck className="w-4 h-4 text-blue-600 shrink-0" />
                <span>Approval Policy</span>
              </p>
              <p className="text-3xs text-blue-800 leading-normal">
                Approving this request sets its status to Approved for Pay. The citizen will be authorized to proceed to Razorpay checkout. The subscription is NOT marked paid until the backend verifies payment.
              </p>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-bold text-slate-700 block">
                Administrative Approval Note (Optional):
              </label>
              <input
                type="text"
                value={approvalNotes}
                onChange={(e) => setApprovalNotes(e.target.value)}
                placeholder="e.g. Authorized citizen to proceed with checkout..."
                className="w-full p-2.5 text-xs bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-400 focus:border-blue-400"
              />
            </div>

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                onClick={() => setApproveModalReq(null)}
                className="px-4 py-2 rounded-xl text-xs font-bold text-slate-600 hover:bg-slate-100 transition"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmApprove}
                disabled={actionLoadingId === approveModalReq.id}
                className="px-5 py-2 rounded-xl text-xs font-black text-white bg-blue-600 hover:bg-blue-700 shadow-xs transition disabled:opacity-50"
              >
                {actionLoadingId === approveModalReq.id ? "Approving..." : "Approve for Pay"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Reject Payment Confirmation Modal */}
      {rejectModalReq && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs">
          <div className="w-full max-w-md bg-white rounded-3xl p-6 shadow-2xl border border-brand-border space-y-4">
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-2xl bg-rose-50 text-rose-600 flex items-center justify-center shrink-0">
                  <AlertTriangle className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-extrabold text-base text-brand-navy">Reject Payment</h3>
                  <p className="text-2xs text-slate-500">Record rejection status in PostgreSQL and notify citizen</p>
                </div>
              </div>
              <button
                onClick={() => setRejectModalReq(null)}
                className="p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-3 rounded-xl bg-slate-50 border border-slate-200 text-xs text-slate-700 space-y-1">
              <div><strong>User:</strong> {rejectModalReq.userName || rejectModalReq.user?.name || `User #${rejectModalReq.userId}`} ({rejectModalReq.userEmail || rejectModalReq.user?.email || `ID: ${rejectModalReq.userId}`})</div>
              <div><strong>User ID:</strong> #{rejectModalReq.userId}</div>
              <div><strong>Selected Plan:</strong> {rejectModalReq.planName} (₹{rejectModalReq.amount} / {rejectModalReq.durationDays} Days)</div>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-bold text-slate-700 block">
                Rejection Reason (Required):
              </label>
              <textarea
                value={rejectionReason}
                onChange={(e) => setRejectionReason(e.target.value)}
                placeholder="e.g. Unverified bank authorization, citizen requested cancellation, suspicious activity..."
                className="w-full p-3 text-xs bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-rose-400 focus:border-rose-400 min-h-[90px]"
              />
              <p className="text-3xs text-slate-400">
                This rejection status and timestamp will be saved in PostgreSQL and immediately sent to the user's dashboard.
              </p>
            </div>

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                onClick={() => setRejectModalReq(null)}
                className="px-4 py-2 rounded-xl text-xs font-bold text-slate-600 hover:bg-slate-100 transition"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmReject}
                disabled={actionLoadingId === rejectModalReq.id || !rejectionReason.trim()}
                className="px-5 py-2 rounded-xl text-xs font-black text-white bg-rose-600 hover:bg-rose-700 shadow-xs transition disabled:opacity-50"
              >
                {actionLoadingId === rejectModalReq.id ? "Rejecting..." : "Reject Payment"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Mark Failed Modal */}
      {markFailedModalReq && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs">
          <div className="w-full max-w-md bg-white rounded-3xl p-6 shadow-2xl border border-brand-border space-y-4">
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-2xl bg-rose-50 text-rose-600 flex items-center justify-center shrink-0">
                  <XCircle className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-extrabold text-base text-brand-navy">Mark Payment as Failed</h3>
                  <p className="text-2xs text-slate-500">Record a confirmed failure or authorized failure decision</p>
                </div>
              </div>
              <button
                onClick={() => setMarkFailedModalReq(null)}
                className="p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-bold text-slate-700 block">
                Failure Reason / Details:
              </label>
              <textarea
                value={failureReason}
                onChange={(e) => setFailureReason(e.target.value)}
                placeholder="e.g. Bank authorization timed out, e-mandate rejected by NPCI, expired payment session..."
                className="w-full p-3 text-xs bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-rose-400 focus:border-rose-400 min-h-[90px]"
              />
            </div>

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                onClick={() => setMarkFailedModalReq(null)}
                className="px-4 py-2 rounded-xl text-xs font-bold text-slate-600 hover:bg-slate-100 transition"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmMarkFailed}
                disabled={actionLoadingId === markFailedModalReq.id}
                className="px-5 py-2 rounded-xl text-xs font-black text-white bg-rose-600 hover:bg-rose-700 shadow-xs transition disabled:opacity-50"
              >
                {actionLoadingId === markFailedModalReq.id ? "Saving..." : "Confirm Payment Failure"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Mark for Review Modal */}
      {reviewModalReq && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs">
          <div className="w-full max-w-md bg-white rounded-3xl p-6 shadow-2xl border border-brand-border space-y-4">
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-2xl bg-purple-50 text-purple-600 flex items-center justify-center shrink-0">
                  <HelpCircle className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-extrabold text-base text-brand-navy">Place Request Under Review</h3>
                  <p className="text-2xs text-slate-500">Hold request when gateway response is unclear or verification is needed</p>
                </div>
              </div>
              <button
                onClick={() => setReviewModalReq(null)}
                className="p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-bold text-slate-700 block">
                Review Notes:
              </label>
              <textarea
                value={reviewNotes}
                onChange={(e) => setReviewNotes(e.target.value)}
                placeholder="e.g. Awaiting bank reconciliation, user contact verification pending..."
                className="w-full p-3 text-xs bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-purple-400 focus:border-purple-400 min-h-[90px]"
              />
            </div>

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                onClick={() => setReviewModalReq(null)}
                className="px-4 py-2 rounded-xl text-xs font-bold text-slate-600 hover:bg-slate-100 transition"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmReview}
                disabled={actionLoadingId === reviewModalReq.id}
                className="px-5 py-2 rounded-xl text-xs font-black text-white bg-purple-600 hover:bg-purple-700 shadow-xs transition disabled:opacity-50"
              >
                {actionLoadingId === reviewModalReq.id ? "Saving..." : "Place Under Review"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Option A Modal: Payment Successful */}
      {outcomeSuccessModalReq && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs">
          <div className="w-full max-w-md bg-white rounded-3xl p-6 shadow-2xl border border-brand-border space-y-4">
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-2xl bg-emerald-50 text-emerald-600 flex items-center justify-center shrink-0">
                  <CheckCircle2 className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-extrabold text-base text-brand-navy">Option A: Payment Successful</h3>
                  <p className="text-2xs text-slate-500">Confirm payment and activate subscription access</p>
                </div>
              </div>
              <button
                onClick={() => setOutcomeSuccessModalReq(null)}
                className="p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-3 rounded-xl bg-slate-50 border border-slate-200 text-xs text-slate-700 space-y-1">
              <div><strong>User:</strong> {outcomeSuccessModalReq.userName || outcomeSuccessModalReq.user?.name || `User #${outcomeSuccessModalReq.userId}`} ({outcomeSuccessModalReq.userEmail || outcomeSuccessModalReq.user?.email || `ID: ${outcomeSuccessModalReq.userId}`})</div>
              <div><strong>Plan:</strong> {outcomeSuccessModalReq.planName} (₹{outcomeSuccessModalReq.amount} / {outcomeSuccessModalReq.durationDays} Days)</div>
              {outcomeSuccessModalReq.razorpayPaymentId && (
                <div className="text-3xs font-mono text-slate-500">Gateway Pay ID: {outcomeSuccessModalReq.razorpayPaymentId}</div>
              )}
            </div>

            <div className="p-3 rounded-xl bg-emerald-50 border border-emerald-200 text-xs text-emerald-900 space-y-1">
              <p className="font-bold flex items-center gap-1.5">
                <ShieldCheck className="w-4 h-4 text-emerald-600 shrink-0" />
                <span>Financial &amp; Access Verification</span>
              </p>
              <p className="text-3xs text-emerald-800 leading-normal">
                Applying Option A sets Payment Status to Captured and Mandate Status to Active. The citizen&apos;s subscription will be immediately unlocked for {outcomeSuccessModalReq.durationDays} days.
              </p>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-bold text-slate-700 block">
                Administrative Notes (Optional):
              </label>
              <input
                type="text"
                value={outcomeSuccessNotes}
                onChange={(e) => setOutcomeSuccessNotes(e.target.value)}
                placeholder="e.g. Bank authorization verified via Razorpay webhook..."
                className="w-full p-2.5 text-xs bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-emerald-400 focus:border-emerald-400"
              />
            </div>

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                onClick={() => setOutcomeSuccessModalReq(null)}
                className="px-4 py-2 rounded-xl text-xs font-bold text-slate-600 hover:bg-slate-100 transition"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmOutcomeSuccess}
                disabled={actionLoadingId === outcomeSuccessModalReq.id}
                className="px-5 py-2 rounded-xl text-xs font-black text-white bg-emerald-600 hover:bg-emerald-700 shadow-xs transition disabled:opacity-50"
              >
                {actionLoadingId === outcomeSuccessModalReq.id ? "Activating..." : "Confirm Payment Successful"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Option B Modal: Payment Successful but e-Mandate Failed */}
      {outcomeMandateFailedModalReq && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs">
          <div className="w-full max-w-md bg-white rounded-3xl p-6 shadow-2xl border border-brand-border space-y-4">
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-2xl bg-amber-50 text-amber-600 flex items-center justify-center shrink-0">
                  <AlertTriangle className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-extrabold text-base text-brand-navy">Option B: Mandate Failed</h3>
                  <p className="text-2xs text-slate-500">Payment captured, but bank recurring e-mandate registration failed</p>
                </div>
              </div>
              <button
                onClick={() => setOutcomeMandateFailedModalReq(null)}
                className="p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-3 rounded-xl bg-slate-50 border border-slate-200 text-xs text-slate-700 space-y-1">
              <div><strong>User:</strong> {outcomeMandateFailedModalReq.userName || outcomeMandateFailedModalReq.user?.name || `User #${outcomeMandateFailedModalReq.userId}`}</div>
              <div><strong>Plan:</strong> {outcomeMandateFailedModalReq.planName} (₹{outcomeMandateFailedModalReq.amount})</div>
            </div>

            <div className="p-3 rounded-xl bg-amber-50 border border-amber-200 text-xs text-amber-900 space-y-1">
              <p className="font-bold flex items-center gap-1.5">
                <AlertCircle className="w-4 h-4 text-amber-600 shrink-0" />
                <span>Separation of Payment &amp; Mandate Status</span>
              </p>
              <p className="text-3xs text-amber-800 leading-normal">
                Payment status will be recorded as SUCCESS, but recurring mandate status will be marked as FAILED. The subscription will remain INACTIVE until an authorized retry is completed to avoid duplicate charges or invalid access.
              </p>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-bold text-slate-700 block">
                Mandate Failure Reason (Required):
              </label>
              <textarea
                value={outcomeMandateFailedReason}
                onChange={(e) => setOutcomeMandateFailedReason(e.target.value)}
                placeholder="e.g. NPCI registration declined, issuing bank netbanking mandate timeout..."
                className="w-full p-3 text-xs bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-amber-400 focus:border-amber-400 min-h-[70px]"
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-bold text-slate-700 block">
                Administrative Notes (Optional):
              </label>
              <input
                type="text"
                value={outcomeMandateFailedNotes}
                onChange={(e) => setOutcomeMandateFailedNotes(e.target.value)}
                placeholder="e.g. Citizen contacted; UPI AutoPay retry recommended..."
                className="w-full p-2.5 text-xs bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-amber-400 focus:border-amber-400"
              />
            </div>

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                onClick={() => setOutcomeMandateFailedModalReq(null)}
                className="px-4 py-2 rounded-xl text-xs font-bold text-slate-600 hover:bg-slate-100 transition"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmOutcomeMandateFailed}
                disabled={actionLoadingId === outcomeMandateFailedModalReq.id || !outcomeMandateFailedReason.trim()}
                className="px-5 py-2 rounded-xl text-xs font-black text-white bg-amber-600 hover:bg-amber-700 shadow-xs transition disabled:opacity-50"
              >
                {actionLoadingId === outcomeMandateFailedModalReq.id ? "Saving..." : "Record Option B"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Option C Modal: Payment Failed */}
      {outcomeFailedModalReq && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs">
          <div className="w-full max-w-md bg-white rounded-3xl p-6 shadow-2xl border border-brand-border space-y-4">
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-2xl bg-rose-50 text-rose-600 flex items-center justify-center shrink-0">
                  <XCircle className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-extrabold text-base text-brand-navy">Option C: Payment Failed</h3>
                  <p className="text-2xs text-slate-500">Record payment and mandate failure without activation</p>
                </div>
              </div>
              <button
                onClick={() => setOutcomeFailedModalReq(null)}
                className="p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-3 rounded-xl bg-slate-50 border border-slate-200 text-xs text-slate-700 space-y-1">
              <div><strong>User:</strong> {outcomeFailedModalReq.userName || outcomeFailedModalReq.user?.name || `User #${outcomeFailedModalReq.userId}`}</div>
              <div><strong>Plan:</strong> {outcomeFailedModalReq.planName} (₹{outcomeFailedModalReq.amount})</div>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-bold text-slate-700 block">
                Payment Failure Reason:
              </label>
              <textarea
                value={outcomeFailedReason}
                onChange={(e) => setOutcomeFailedReason(e.target.value)}
                placeholder="e.g. Card limit exceeded, OTP timeout, insufficient balance..."
                className="w-full p-3 text-xs bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-rose-400 focus:border-rose-400 min-h-[70px]"
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-bold text-slate-700 block">
                Administrative Notes (Optional):
              </label>
              <input
                type="text"
                value={outcomeFailedNotes}
                onChange={(e) => setOutcomeFailedNotes(e.target.value)}
                placeholder="e.g. User advised to retry using alternative payment method..."
                className="w-full p-2.5 text-xs bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-rose-400 focus:border-rose-400"
              />
            </div>

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                onClick={() => setOutcomeFailedModalReq(null)}
                className="px-4 py-2 rounded-xl text-xs font-bold text-slate-600 hover:bg-slate-100 transition"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmOutcomeFailed}
                disabled={actionLoadingId === outcomeFailedModalReq.id || !outcomeFailedReason.trim()}
                className="px-5 py-2 rounded-xl text-xs font-black text-white bg-rose-600 hover:bg-rose-700 shadow-xs transition disabled:opacity-50"
              >
                {actionLoadingId === outcomeFailedModalReq.id ? "Saving..." : "Record Payment Failed"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Authorize Retry Mandate Modal */}
      {retryMandateModalReq && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs">
          <div className="w-full max-w-md bg-white rounded-3xl p-6 shadow-2xl border border-brand-border space-y-4">
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-2xl bg-indigo-50 text-indigo-600 flex items-center justify-center shrink-0">
                  <RotateCcw className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-extrabold text-base text-brand-navy">Authorize Citizen Retry</h3>
                  <p className="text-2xs text-slate-500">Allow safe re-attempt of e-mandate without duplicate charges</p>
                </div>
              </div>
              <button
                onClick={() => setRetryMandateModalReq(null)}
                className="p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-3 rounded-xl bg-slate-50 border border-slate-200 text-xs text-slate-700 space-y-1">
              <div><strong>User:</strong> {retryMandateModalReq.userName || retryMandateModalReq.user?.name || `User #${retryMandateModalReq.userId}`}</div>
              <div><strong>Plan:</strong> {retryMandateModalReq.planName} (₹{retryMandateModalReq.amount})</div>
              {retryMandateModalReq.failureReason && (
                <div className="text-3xs text-rose-600">Prior Issue: {retryMandateModalReq.failureReason}</div>
              )}
            </div>

            <div className="p-3 rounded-xl bg-indigo-50 border border-indigo-200 text-xs text-indigo-900 space-y-1">
              <p className="font-bold flex items-center gap-1.5">
                <ShieldCheck className="w-4 h-4 text-indigo-600 shrink-0" />
                <span>Safe Retry Protocol</span>
              </p>
              <p className="text-3xs text-indigo-800 leading-normal">
                Sets approval status to REQUIRES_RETRY and resets mandate to MANDATE_PENDING. The citizen will see an active retry prompt in their portal. Duplicate payments are strictly prevented.
              </p>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-bold text-slate-700 block">
                Administrative Instruction / Note:
              </label>
              <input
                type="text"
                value={retryMandateNotes}
                onChange={(e) => setRetryMandateNotes(e.target.value)}
                placeholder="e.g. Please retry using UPI AutoPay or debit card..."
                className="w-full p-2.5 text-xs bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-400 focus:border-indigo-400"
              />
            </div>

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                onClick={() => setRetryMandateModalReq(null)}
                className="px-4 py-2 rounded-xl text-xs font-bold text-slate-600 hover:bg-slate-100 transition"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmRetryMandate}
                disabled={actionLoadingId === retryMandateModalReq.id}
                className="px-5 py-2 rounded-xl text-xs font-black text-white bg-indigo-600 hover:bg-indigo-700 shadow-xs transition disabled:opacity-50"
              >
                {actionLoadingId === retryMandateModalReq.id ? "Authorizing..." : "Authorize Safe Retry"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
