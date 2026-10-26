"use client";

import React, { useState, useEffect } from "react";
import { 
  X, 
  Sparkles, 
  Crown, 
  CheckCircle2, 
  AlertCircle, 
  Clock, 
  ShieldCheck, 
  ArrowRight, 
  Lock, 
  Info, 
  Check, 
  RotateCcw,
  RefreshCw,
  Zap,
  CreditCard,
  Building
} from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { 
  fetchSubscriptionPlans, 
  fetchMySubscriptionStatus, 
  submitSubscriptionRequest, 
  cancelSubscriptionRequest,
  initiateSubscriptionCheckout,
  verifySubscriptionPayment,
  loadRazorpayCheckoutScript,
  reportPaymentFailure,
  subscribeToSubscriptionUpdates
} from "@/services/subscriptionService";
import { 
  SubscriptionPlan, 
  PlanComparisonRow, 
  UserSubscriptionStatus, 
  SubscriptionPlanId 
} from "@/types/subscription";

interface SubscriptionModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubscriptionUpdated?: () => void;
  initialPlanId?: SubscriptionPlanId;
  totalMatchingCount?: number;
  accessibleCount?: number;
}

export function SubscriptionModal({
  isOpen,
  onClose,
  onSubscriptionUpdated,
  initialPlanId = "yearly",
  totalMatchingCount,
  accessibleCount = 5
}: SubscriptionModalProps) {
  const { user, profile } = useAuth();
  const [plans, setPlans] = useState<SubscriptionPlan[]>([]);
  const [comparison, setComparison] = useState<PlanComparisonRow[]>([]);
  const [status, setStatus] = useState<UserSubscriptionStatus | null>(null);
  const [selectedPlanId, setSelectedPlanId] = useState<SubscriptionPlanId>(initialPlanId);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [cancelling, setCancelling] = useState(false);

  // Confirmation modal state & form fields
  const [showConfirm, setShowConfirm] = useState(false);
  const [feedback, setFeedback] = useState<{ type: "success" | "error" | "info"; message: string } | null>(null);
  const [phoneNumber, setPhoneNumber] = useState("");
  const [phoneError, setPhoneError] = useState<string | null>(null);
  const [paymentMethod, setPaymentMethod] = useState<"upi" | "card" | "netbanking">("upi");
  const [bankName, setBankName] = useState("");
  const [bankAccountType, setBankAccountType] = useState<"savings" | "current">("savings");
  const [formError, setFormError] = useState<string | null>(null);
  const [notes, setNotes] = useState("");

  const loadPlansAndStatus = async () => {
    setLoading(true);
    setFeedback(null);
    try {
      const [plansData, userStatus] = await Promise.all([
        fetchSubscriptionPlans(),
        fetchMySubscriptionStatus()
      ]);
      setPlans(plansData.plans);
      setComparison(plansData.comparison);
      setStatus(userStatus);

      if (userStatus?.approved_for_payment) {
        setSelectedPlanId((userStatus.approved_for_payment.planId as SubscriptionPlanId) || "yearly");
      } else if (userStatus?.pending_request) {
        setSelectedPlanId((userStatus.pending_request.planId as SubscriptionPlanId) || "yearly");
      }
    } catch {
      // Fallback handled in services
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      loadPlansAndStatus();
      setShowConfirm(false);
      setFeedback(null);
    }
  }, [isOpen]);

  // Real-time status update listener
  useEffect(() => {
    if (!isOpen) return;

    const unsubscribe = subscribeToSubscriptionUpdates((event) => {
      if (event.type === "payment_approved") {
        setFeedback({
          type: "success",
          message: "🎉 Subscription approved & activated! All government schemes unlocked."
        });
        loadPlansAndStatus();
        if (onSubscriptionUpdated) onSubscriptionUpdated();
      } else if (event.type === "payment_rejected") {
        const reason = event.data?.rejection_reason || event.data?.rejectionReason || "Request rejected by administrator.";
        setFeedback({
          type: "error",
          message: `Subscription request rejected: ${reason}`
        });
        loadPlansAndStatus();
      } else if (event.type === "poll_sync" && event.data) {
        const s: UserSubscriptionStatus = event.data;
        if (s.is_premium && !status?.is_premium) {
          setFeedback({
            type: "success",
            message: "🎉 Your subscription is now active! All schemes unlocked."
          });
          setStatus(s);
          if (onSubscriptionUpdated) onSubscriptionUpdated();
        }
      }
    });

    return () => {
      unsubscribe();
    };
  }, [isOpen, status]);

  if (!isOpen) return null;

  const selectedPlan = plans.find((p) => p.id === selectedPlanId) || plans[0];

  const handleOpenConfirm = (planId: SubscriptionPlanId) => {
    setSelectedPlanId(planId);
    setShowConfirm(true);
    setFeedback(null);
    setFormError(null);
    setPhoneError(null);
    // Explicitly empty phone number: Never prefill from profile/stored user data
    setPhoneNumber("");
  };

  /**
   * Executes authentic Razorpay Checkout modal
   */
  const executeRazorpayCheckout = async (planId: string) => {
    setFormError(null);
    setPhoneError(null);

    const cleanPhone = phoneNumber.trim().replace(/\D/g, "");
    if (!cleanPhone || cleanPhone.length !== 10 || !["6", "7", "8", "9"].includes(cleanPhone[0])) {
      setPhoneError("Please enter a valid 10-digit mobile number");
      return;
    }

    setSubmitting(true);
    setFeedback(null);

    // 1. Ensure Razorpay SDK script is available
    const isScriptLoaded = await loadRazorpayCheckoutScript();
    if (!isScriptLoaded) {
      setSubmitting(false);
      setFeedback({
        type: "error",
        message: "Unable to load Razorpay payment SDK. Please verify internet connectivity."
      });
      return;
    }

    // 2. Initialize checkout session via Flask backend
    const initRes = await initiateSubscriptionCheckout(
      planId,
      cleanPhone
    );

    if (!initRes.success || !initRes.data) {
      setSubmitting(false);
      let errorMsg = initRes.message || "Failed to initialize payment checkout.";
      if (initRes.diagnostic?.action_required) {
        errorMsg += `\n\nAction Required: ${initRes.diagnostic.action_required}`;
      }
      setFeedback({
        type: "error",
        message: errorMsg
      });
      return;
    }

    const checkoutData = initRes.data;

    // 3. Configure and open official Razorpay Checkout modal
    const options: any = {
      key: checkoutData.key_id,
      amount: checkoutData.amount_in_paise,
      currency: checkoutData.currency || "INR",
      name: "Yojana Hunter",
      description: `${checkoutData.plan_name} (${selectedPlan?.duration_label || "Access"})`,
      image: "/favicon.ico",
      handler: async function (response: any) {
        setVerifying(true);
        setFeedback({
          type: "info",
          message: "Verifying payment signature with Razorpay..."
        });

        const verifyRes = await verifySubscriptionPayment({
          razorpay_payment_id: response.razorpay_payment_id,
          razorpay_order_id: response.razorpay_order_id || checkoutData.order_id,
          razorpay_subscription_id: response.razorpay_subscription_id || checkoutData.subscription_id,
          razorpay_signature: response.razorpay_signature
        });

        setVerifying(false);
        setSubmitting(false);

        if (verifyRes.success) {
          setShowConfirm(false);
          setFeedback({
            type: "success",
            message: "🎉 Payment verified successfully! Your subscription is now active."
          });
          const updatedStatus = await fetchMySubscriptionStatus();
          setStatus(updatedStatus);
          if (onSubscriptionUpdated) onSubscriptionUpdated();
        } else {
          setFeedback({
            type: "error",
            message: verifyRes.message || "Payment verification failed."
          });
        }
      },
      prefill: {
        name: checkoutData.user?.name || "",
        email: checkoutData.user?.email || "",
        contact: checkoutData.user?.contact || ""
      },
      notes: {
        subscription_id: checkoutData.subscription_id || "",
        order_id: checkoutData.order_id || "",
        plan_id: checkoutData.plan_id || "",
        plan_name: checkoutData.plan_name || "",
        request_id: String(checkoutData.request_id || "")
      },
      // Priority display configuration for dynamic UPI QR Code and essential instruments
      config: {
        display: {
          blocks: {
            upi_qr: {
              name: "Pay via UPI QR / Apps",
              instruments: [
                {
                  method: "upi",
                  flows: ["qr", "intent", "collect"]
                }
              ]
            },
            other: {
              name: "Cards & Other Methods",
              instruments: [
                { method: "card" },
                { method: "netbanking" },
                { method: "wallet" }
              ]
            }
          },
          sequence: ["block.upi_qr", "block.other"],
          preferences: {
            show_default_blocks: true
          }
        }
      },
      theme: {
        color: "#f59e0b"
      },
      modal: {
        ondismiss: function () {
          setSubmitting(false);
          setFeedback({
            type: "info",
            message: "Checkout window closed. No payment was charged."
          });
        }
      }
    };

    if (checkoutData.order_id && checkoutData.order_id.startsWith("order_")) {
      options.order_id = checkoutData.order_id;
      options.amount = checkoutData.amount_in_paise;
      options.currency = checkoutData.currency || "INR";
    } else if (checkoutData.subscription_id && checkoutData.subscription_id.startsWith("sub_") && !checkoutData.order_id) {
      options.subscription_id = checkoutData.subscription_id;
      // For standalone Razorpay Subscriptions without an order_id
      delete options.amount;
      delete options.currency;
    } else if (checkoutData.order_id) {
      options.order_id = checkoutData.order_id;
      options.amount = checkoutData.amount_in_paise;
      options.currency = checkoutData.currency || "INR";
    }

    try {
      const rzp = new (window as any).Razorpay(options);

      rzp.on("payment.failed", async function (resp: any) {
        setSubmitting(false);
        const err = resp?.error || {};
        const code = err.code || "PAYMENT_FAILED";
        const description = err.description || "Payment was declined by bank or gateway.";
        const source = err.source || "gateway";
        const step = err.step || "payment_authorization";
        const reason = err.reason || "unknown";

        try {
          await reportPaymentFailure({
            subscription_id: checkoutData.subscription_id,
            payment_id: err.metadata?.payment_id,
            error_code: code,
            error_description: description,
            error_source: source,
            error_step: step,
            error_reason: reason
          });
        } catch {
          // non-blocking
        }

        setFeedback({
          type: "error",
          message: `Payment Failed: ${description}. Please retry with another payment method in Razorpay.`
        });
      });

      rzp.open();
    } catch (err: any) {
      setSubmitting(false);
      setFeedback({
        type: "error",
        message: `Failed to open Razorpay checkout: ${err?.message || "Unknown error"}`
      });
    }
  };

  const handleCancelRequest = async (requestId: number) => {
    setCancelling(true);
    try {
      const res = await cancelSubscriptionRequest(requestId);
      if (res.success) {
        setFeedback({ type: "info", message: "Subscription request cancelled." });
        loadPlansAndStatus();
      } else {
        setFeedback({ type: "error", message: res.message });
      }
    } catch {
      setFeedback({ type: "error", message: "Failed to cancel request." });
    } finally {
      setCancelling(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-md overflow-y-auto animate-in fade-in duration-200">
      <div 
        className="relative w-full max-w-4xl bg-slate-900 border border-slate-800 rounded-3xl shadow-2xl shadow-amber-500/10 overflow-hidden my-8"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Top Header Banner */}
        <div className="relative px-6 py-6 border-b border-slate-800 bg-gradient-to-r from-amber-500/10 via-slate-900 to-amber-500/5">
          <div className="flex items-start justify-between">
            <div className="space-y-1">
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-amber-500/10 border border-amber-500/20 text-amber-300 text-xs font-semibold">
                <Crown className="w-3.5 h-3.5" />
                <span>Yojana Hunter Premium Pass</span>
              </div>
              <h2 className="text-xl sm:text-2xl font-black text-white tracking-tight">
                Unlock All Matching Government Schemes
              </h2>
              <p className="text-xs sm:text-sm text-slate-400">
                Direct application links, document checklists, and eligibility AI criteria for every scheme.
              </p>
            </div>
            <button
              onClick={onClose}
              className="p-2 rounded-2xl bg-slate-800/80 hover:bg-slate-700 text-slate-400 hover:text-white transition"
              aria-label="Close modal"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Scheme count pill */}
          {totalMatchingCount !== undefined && totalMatchingCount > accessibleCount && (
            <div className="mt-4 p-3 rounded-2xl bg-amber-500/10 border border-amber-500/30 flex items-center justify-between text-xs">
              <div className="flex items-center gap-2 text-amber-200">
                <Sparkles className="w-4 h-4 text-amber-400 shrink-0" />
                <span>
                  You have matched <strong>{totalMatchingCount} schemes</strong> based on your profile!
                  Currently, free citizens can view the first <strong>{accessibleCount} schemes</strong>.
                </span>
              </div>
              <span className="hidden sm:inline-block px-2.5 py-1 rounded-lg bg-amber-400 text-slate-950 font-black text-2xs uppercase tracking-wider">
                {totalMatchingCount - accessibleCount} Locked
              </span>
            </div>
          )}
        </div>

        {/* Modal Body */}
        <div className="p-6 space-y-6 max-h-[75vh] overflow-y-auto">
          {/* Notifications / Feedback Banner */}
          {feedback && (
            <div
              className={`p-4 rounded-2xl flex items-start gap-3 text-xs leading-relaxed transition ${
                feedback.type === "success"
                  ? "bg-emerald-500/10 border border-emerald-500/30 text-emerald-300"
                  : feedback.type === "error"
                  ? "bg-rose-500/10 border border-rose-500/30 text-rose-300"
                  : "bg-amber-500/10 border border-amber-500/30 text-amber-200"
              }`}
            >
              {feedback.type === "success" ? (
                <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0 mt-0.5" />
              ) : feedback.type === "error" ? (
                <AlertCircle className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
              ) : (
                <Info className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
              )}
              <div className="flex-1 whitespace-pre-line">{feedback.message}</div>
              <button
                onClick={() => setFeedback(null)}
                className="text-slate-400 hover:text-white"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          )}

          {/* ACTIVE SUBSCRIPTION BANNER */}
          {status?.is_premium && status.active_subscription && (
            <div className="p-5 rounded-2xl bg-gradient-to-r from-emerald-950/60 via-slate-900 to-emerald-950/40 border border-emerald-500/40 text-emerald-300 space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                  <span className="font-extrabold text-white text-sm">
                    Active Plan: {status.active_subscription.planName}
                  </span>
                </div>
                <span className="px-2.5 py-1 rounded-full bg-emerald-500/20 text-emerald-300 font-bold text-xs">
                  Premium Active
                </span>
              </div>
              <p className="text-xs text-slate-300">
                You have unrestricted access to all matched schemes, official portal links, checklists, and automated eligibility advice.
              </p>
              {status.days_remaining !== null && (
                <div className="flex items-center gap-2 text-2xs text-emerald-400 font-medium pt-1">
                  <Clock className="w-3.5 h-3.5" />
                  <span>
                    Valid until {new Date(status.active_subscription.expiresAt || "").toLocaleDateString()} ({status.days_remaining} days remaining)
                  </span>
                </div>
              )}
            </div>
          )}

          {/* APPROVED FOR PAYMENT BANNER */}
          {!status?.is_premium && status?.approved_for_payment && (
            <div className="p-5 rounded-2xl bg-gradient-to-r from-amber-950/70 via-slate-900 to-amber-950/50 border border-amber-400/80 text-amber-200 space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 font-black text-amber-300">
                  <Zap className="w-5 h-5 text-amber-400" />
                  <span>Request Approved: Ready for Payment</span>
                </div>
                <span className="px-2.5 py-1 rounded-full bg-amber-400/20 text-amber-300 font-extrabold text-xs">
                  Approved
                </span>
              </div>
              <p className="text-xs text-slate-300 leading-relaxed">
                Your request for <strong>{status.approved_for_payment.planName} (₹{status.approved_for_payment.amount})</strong> has been approved by the administrator. Proceed to complete payment via Razorpay.
              </p>
              <div className="flex items-center gap-3 pt-1">
                <button
                  onClick={() => handleOpenConfirm(status.approved_for_payment!.planId as SubscriptionPlanId)}
                  disabled={submitting || verifying}
                  className="px-6 py-2.5 rounded-xl text-xs font-black bg-gradient-to-r from-amber-400 via-amber-300 to-amber-500 hover:from-amber-300 hover:to-amber-400 text-slate-950 shadow-lg shadow-amber-500/20 transition flex items-center gap-2"
                >
                  <Lock className="w-3.5 h-3.5" />
                  <span>Proceed to Razorpay Payment (₹{status.approved_for_payment.amount})</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          )}

          {/* PENDING REQUEST BANNER */}
          {!status?.is_premium && !status?.approved_for_payment && status?.pending_request && (
            <div className="p-4 rounded-2xl bg-slate-800/80 border border-slate-700/80 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
              <div className="flex items-center gap-2.5 text-slate-300">
                <Clock className="w-4 h-4 text-amber-400 shrink-0" />
                <div>
                  <span className="font-bold text-white">
                    Pending Subscription: {status.pending_request.planName}
                  </span>
                  <p className="text-2xs text-slate-400">
                    Direct payment is available. You can complete checkout directly below.
                  </p>
                </div>
              </div>
              <button
                onClick={() => handleCancelRequest(status.pending_request!.id)}
                disabled={cancelling}
                className="self-start sm:self-auto px-3 py-1.5 rounded-xl text-2xs font-bold text-rose-300 hover:text-white bg-rose-500/10 hover:bg-rose-500/20 border border-rose-500/20 transition"
              >
                {cancelling ? "Cancelling..." : "Cancel Request"}
              </button>
            </div>
          )}

          {/* PRICING PLANS GRID */}
          {loading ? (
            <div className="py-12 flex flex-col items-center justify-center gap-3 text-slate-400">
              <RefreshCw className="w-8 h-8 animate-spin text-amber-400" />
              <p className="text-xs font-medium">Loading subscription plans...</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {plans.map((plan) => {
                const isSelected = selectedPlanId === plan.id;
                const isActiveForThis = status?.is_premium && status.active_subscription?.planId === plan.id;
                const isApprovedForThis = !status?.is_premium && status?.approved_for_payment?.planId === plan.id;
                const isPendingForThis = !status?.is_premium && status?.pending_request?.planId === plan.id;

                return (
                  <div
                    key={plan.id}
                    onClick={() => setSelectedPlanId(plan.id)}
                    className={`relative p-5 rounded-3xl border transition flex flex-col justify-between cursor-pointer ${
                      isSelected
                        ? "bg-slate-800/90 border-amber-400/80 shadow-lg shadow-amber-500/10"
                        : "bg-slate-900/60 border-slate-800 hover:border-slate-700 hover:bg-slate-800/40"
                    }`}
                  >
                    {/* Badge */}
                    {plan.popular && (
                      <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-0.5 rounded-full bg-gradient-to-r from-amber-400 to-amber-500 text-slate-950 font-black text-3xs uppercase tracking-wider shadow-md">
                        {plan.badge || "Most Popular"}
                      </div>
                    )}

                    <div className="space-y-4">
                      <div className="flex items-start justify-between">
                        <div>
                          <h3 className="font-extrabold text-white text-base">
                            {plan.name}
                          </h3>
                          <p className="text-2xs text-slate-400 font-medium">
                            {plan.duration_label} ({plan.duration_days} days)
                          </p>
                        </div>
                        <div className="text-right">
                          <span className="text-2xl font-black text-amber-400">
                            ₹{plan.price}
                          </span>
                          <span className="text-3xs text-slate-500 block">INR</span>
                        </div>
                      </div>

                      <p className="text-xs text-slate-300 leading-relaxed border-t border-slate-800/60 pt-3">
                        {plan.description}
                      </p>

                      <ul className="space-y-2 text-2xs text-slate-300">
                        {plan.features.slice(0, 4).map((f, i) => (
                          <li key={i} className="flex items-start gap-2">
                            <Check className="w-3.5 h-3.5 text-amber-400 shrink-0 mt-0.5" />
                            <span>{f}</span>
                          </li>
                        ))}
                      </ul>
                    </div>

                    <div className="pt-6">
                      {isActiveForThis ? (
                        <button
                          disabled
                          className="w-full py-2.5 rounded-2xl font-bold text-xs bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 cursor-default"
                        >
                          Current Active Plan
                        </button>
                      ) : (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleOpenConfirm(plan.id);
                          }}
                          className={`w-full py-2.5 rounded-2xl font-black text-xs transition flex items-center justify-center gap-2 shadow-md ${
                            isSelected
                              ? "bg-gradient-to-r from-amber-400 to-amber-500 hover:from-amber-300 hover:to-amber-400 text-slate-950 shadow-amber-500/20"
                              : "bg-slate-700 hover:bg-slate-600 text-white"
                          }`}
                        >
                          <span>Subscribe with Razorpay</span>
                          <ArrowRight className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* CONFIRMATION / PROCEED MODAL OVERLAY */}
          {showConfirm && selectedPlan && (
            <div className="p-6 rounded-3xl bg-slate-800/95 border border-amber-400/80 shadow-2xl space-y-4 animate-in zoom-in-95 duration-150">
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-amber-400/20 text-amber-400 flex items-center justify-center font-bold">
                    <Crown className="w-5 h-5" />
                  </div>
                  <div>
                    <h3 className="text-base font-extrabold text-white">
                      Subscribe: {selectedPlan.name}
                    </h3>
                    <p className="text-xs text-slate-400">
                      Amount: ₹{selectedPlan.price} • Duration: {selectedPlan.duration_days} Days ({selectedPlan.duration_label})
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => setShowConfirm(false)}
                  className="text-slate-400 hover:text-white"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              {/* Authenticated Citizen Details */}
              <div className="p-4 rounded-2xl bg-slate-900/90 border border-slate-700/80 text-xs space-y-1.5 text-slate-300">
                <div className="flex items-center justify-between">
                  <span className="text-3xs font-extrabold uppercase text-slate-400 tracking-wider">
                    Authenticated Citizen Details
                  </span>
                  <span className="px-2 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 font-bold text-3xs">
                    Verified Account
                  </span>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 pt-1 text-2xs">
                  <div>
                    <span className="text-slate-500">Name: </span>
                    <strong className="text-white">{user?.name || profile?.full_name || "Citizen"}</strong>
                  </div>
                  <div>
                    <span className="text-slate-500">User ID: </span>
                    <strong className="text-amber-400 font-mono">#{user?.id ?? "—"}</strong>
                  </div>
                  <div>
                    <span className="text-slate-500">Email: </span>
                    <strong className="text-slate-200">{user?.email || "—"}</strong>
                  </div>
                  <div>
                    <span className="text-slate-500">Selected Plan: </span>
                    <strong className="text-amber-300">{selectedPlan.name} (₹{selectedPlan.price})</strong>
                  </div>
                </div>
              </div>

              {/* Form Validation Error Banner */}
              {formError && (
                <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 shrink-0 text-rose-400" />
                  <span>{formError}</span>
                </div>
              )}

              {/* Phone Number Input */}
              <div className="space-y-1.5">
                <label className="text-2xs font-bold text-slate-300 block">
                  Enter your mobile number for Razorpay Checkout <span className="text-rose-400">*</span>
                </label>
                <div className="relative">
                  <span className="absolute left-3 top-1/2 -translate-y-1/2 text-xs font-bold text-slate-500">
                    +91
                  </span>
                  <input
                    type="tel"
                    maxLength={10}
                    placeholder="10-digit mobile number"
                    value={phoneNumber}
                    autoFocus
                    onChange={(e) => {
                      const val = e.target.value.replace(/\D/g, "").slice(0, 10);
                      setPhoneNumber(val);
                      if (val.length === 10) setPhoneError(null);
                    }}
                    className="w-full pl-12 pr-3.5 py-2.5 text-xs bg-slate-900 border border-slate-700 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-amber-400"
                  />
                </div>
                {phoneError ? (
                  <p className="text-3xs text-rose-400 font-medium">{phoneError}</p>
                ) : (
                  <p className="text-3xs text-slate-400">
                    Your number is used in-memory for the Razorpay gateway session and is never stored in the database.
                  </p>
                )}
              </div>

              {/* Security notice */}
              <div className="p-3 rounded-xl bg-slate-900/60 border border-slate-800 text-3xs text-slate-400 flex items-start gap-2">
                <ShieldCheck className="w-3.5 h-3.5 text-amber-400 shrink-0 mt-0.5" />
                <span>
                  Official Razorpay TEST MODE Checkout • Instant activation upon verified payment • No admin approval required.
                </span>
              </div>

              {/* Modal Actions */}
              <div className="flex flex-wrap items-center justify-end gap-2.5 pt-2">
                <button
                  type="button"
                  onClick={() => setShowConfirm(false)}
                  disabled={submitting || verifying}
                  className="px-4 py-2.5 rounded-xl text-xs font-bold text-slate-400 hover:text-white hover:bg-slate-700/60 transition"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={() => executeRazorpayCheckout(selectedPlan.id)}
                  disabled={submitting || verifying}
                  className="px-6 py-2.5 rounded-xl text-xs font-black bg-gradient-to-r from-amber-400 via-amber-300 to-amber-500 hover:from-amber-300 hover:to-amber-400 text-slate-950 shadow-md shadow-amber-500/20 transition flex items-center gap-2 disabled:opacity-50"
                >
                  {submitting || verifying ? (
                    <>
                      <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                      <span>{verifying ? "Verifying..." : "Opening Razorpay..."}</span>
                    </>
                  ) : (
                    <>
                      <Lock className="w-3.5 h-3.5" />
                      <span>Proceed to Razorpay (₹{selectedPlan.price})</span>
                      <ArrowRight className="w-3.5 h-3.5" />
                    </>
                  )}
                </button>
              </div>
            </div>
          )}

          {/* FREE VS PREMIUM COMPARISON TABLE */}
          {comparison.length > 0 && (
            <div className="pt-4 space-y-3">
              <div className="flex items-center justify-between">
                <h4 className="text-xs font-black uppercase tracking-wider text-slate-400">
                  Feature Comparison: Free Citizen vs Premium Pass
                </h4>
              </div>

              <div className="overflow-x-auto rounded-2xl border border-slate-800 bg-slate-900/60">
                <table className="w-full text-left text-xs border-collapse">
                  <thead>
                    <tr className="border-b border-slate-800 bg-slate-800/40 text-2xs font-black uppercase text-slate-400">
                      <th className="py-3 px-4">Feature</th>
                      <th className="py-3 px-4 text-slate-400">Free Citizen Tier</th>
                      <th className="py-3 px-4 text-amber-300 font-bold bg-amber-500/10">Premium Citizen Pass</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60 text-slate-300">
                    {comparison.map((row, i) => (
                      <tr key={i} className="hover:bg-slate-800/20 transition">
                        <td className="py-3 px-4 font-medium text-white">{row.feature}</td>
                        <td className="py-3 px-4 text-slate-400">{row.free}</td>
                        <td className="py-3 px-4 font-bold text-amber-300 bg-amber-500/5">{row.premium}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-slate-800/80 bg-slate-950/60 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs text-slate-400">
          <div className="flex items-center gap-2">
            <Lock className="w-3.5 h-3.5 text-amber-400" />
            <span>Secured by Razorpay • UPI AutoPay / Cards / Netbanking • 256-Bit SSL Encryption</span>
          </div>
          <button
            onClick={onClose}
            className="text-xs font-bold text-slate-300 hover:text-white"
          >
            Close Window
          </button>
        </div>
      </div>
    </div>
  );
}
