import { apiFetch, apiFetchDetailed, getAuthToken } from "@/lib/api";
import { 
  SubscriptionPlansResponse, 
  UserSubscriptionStatus, 
  SubscriptionRequestRecord, 
  AdminSubscriptionListResponse,
  RazorpayCheckoutInitResponse,
  RazorpayPaymentCallback,
  RazorpayVerifyResponse
} from "@/types/subscription";
import { getAdminToken, clearAdminAuth } from "@/services/adminService";

const API_BASE_URL = typeof window !== 'undefined' ? '/api' : (process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:5000/api');

/**
 * Fetch available subscription plans and comparison matrix (Public/Citizen)
 */
export async function fetchSubscriptionPlans(): Promise<SubscriptionPlansResponse> {
  try {
    const data = await apiFetch<SubscriptionPlansResponse>("/subscriptions/plans");
    if (data && data.plans) return data;
    throw new Error("Invalid plans data received");
  } catch (error) {
    console.warn("Failed to fetch subscription plans, using fallback configuration:", error);
    return {
      plans: [
        {
          id: "monthly",
          name: "Monthly Access",
          price: 50,
          currency: "INR",
          duration_days: 30,
          duration_label: "1 Month",
          popular: false,
          badge: "Flexible",
          description: "Ideal for immediate scheme applications and fast verification.",
          features: [
            "Full access to all matching government schemes (unlimited)",
            "Instant AI eligibility evaluation & detailed criteria breakdown",
            "Direct application portal links & procedure guidance",
            "Complete document checklists for every scheme",
            "Priority scheme update notifications",
            "30 days uninterrupted validity"
          ]
        },
        {
          id: "two_months",
          name: "2 Months Standard",
          price: 100,
          currency: "INR",
          duration_days: 60,
          duration_label: "2 Months",
          popular: false,
          badge: "Standard",
          description: "Perfect for seasonal schemes and continuous tracking across cycles.",
          features: [
            "Full access to all matching government schemes (unlimited)",
            "Instant AI eligibility evaluation & detailed criteria breakdown",
            "Direct application portal links & procedure guidance",
            "Complete document checklists for every scheme",
            "Multi-scheme tracking & application reminders",
            "60 days uninterrupted validity"
          ]
        },
        {
          id: "yearly",
          name: "Yearly Premium Pass",
          price: 500,
          currency: "INR",
          duration_days: 365,
          duration_label: "12 Months (1 Year)",
          popular: true,
          badge: "Best Value (Save ₹100)",
          description: "Complete year-round coverage for your entire family across Central and State schemes.",
          features: [
            "Full access to all matching government schemes (unlimited)",
            "Instant AI eligibility evaluation & detailed criteria breakdown",
            "Direct application portal links & procedure guidance",
            "Complete document checklists for every scheme",
            "Priority AI scheme discovery alerts for newly launched schemes",
            "Dedicated family benefit tracking",
            "365 days uninterrupted full access"
          ]
        }
      ],
      comparison: [
        { feature: "View Matching Scheme Count", free: "Yes (Total count shown)", premium: "Yes (Total count shown)" },
        { feature: "Accessible Scheme Details", free: "First 5 matching schemes", premium: "All matching schemes (Unlimited)" },
        { feature: "Official Application Portal Links", free: "First 5 schemes only", premium: "All verified government schemes" },
        { feature: "Required Document Checklists", free: "First 5 schemes only", premium: "Full checklists for all schemes" },
        { feature: "Detailed Eligibility Explanations", free: "First 5 schemes only", premium: "Instant AI explanations on every scheme" },
        { feature: "Application Tracking & Drafts", free: "Limited", premium: "Unlimited draft and application tracking" },
        { feature: "New Scheme Launch Alerts", free: "Standard", premium: "Priority automated alerts" }
      ],
      free_limit: 5
    };
  }
}

/**
 * Fetch current user's subscription tier and active subscription status
 */
export async function fetchMySubscriptionStatus(): Promise<UserSubscriptionStatus> {
  try {
    const data = await apiFetch<UserSubscriptionStatus>("/subscriptions/my-status");
    if (data) return data;
  } catch (error) {
    console.warn("Could not fetch my subscription status:", error);
  }
  return {
    is_premium: false,
    tier: "free",
    free_limit: 5,
    active_subscription: null,
    pending_request: null,
    latest_request: null
  };
}

export interface SubscriptionRequestPayload {
  planId: string;
  phoneNumber?: string;
  bankName?: string;
  bankAccountType?: string;
  paymentMethod?: string;
  adminNotes?: string;
}

/**
 * Submit a subscription request (awaiting manual admin review & approval)
 */
export async function submitSubscriptionRequest(
  payloadOrPlanId: string | SubscriptionRequestPayload, 
  adminNotes?: string
): Promise<{ success: boolean; message: string; request?: SubscriptionRequestRecord }> {
  try {
    const payload = typeof payloadOrPlanId === "string" 
      ? { planId: payloadOrPlanId, adminNotes }
      : payloadOrPlanId;

    const data = await apiFetch<{ message: string; request: SubscriptionRequestRecord }>("/subscriptions/request", {
      method: "POST",
      body: JSON.stringify(payload)
    });
    return {
      success: true,
      message: data.message || "Your subscription request has been submitted. Please wait for admin review.",
      request: data.request
    };
  } catch (err: any) {
    return {
      success: false,
      message: err.message || "Failed to submit subscription request."
    };
  }
}

/**
 * Cancel a pending subscription request
 */
export async function cancelSubscriptionRequest(
  requestId: number
): Promise<{ success: boolean; message: string }> {
  try {
    const data = await apiFetch<{ message: string }>("/subscriptions/cancel", {
      method: "POST",
      body: JSON.stringify({ requestId })
    });
    return {
      success: true,
      message: data.message || "Subscription request cancelled."
    };
  } catch (err: any) {
    return {
      success: false,
      message: err.message || "Failed to cancel subscription request."
    };
  }
}

/**
 * Dynamically loads the official Razorpay Checkout SDK script
 */
export function loadRazorpayCheckoutScript(): Promise<boolean> {
  return new Promise((resolve) => {
    if (typeof window === "undefined") {
      resolve(false);
      return;
    }
    if ((window as any).Razorpay) {
      resolve(true);
      return;
    }
    const script = document.createElement("script");
    script.src = "https://checkout.razorpay.com/v1/checkout.js";
    script.async = true;
    script.onload = () => resolve(true);
    script.onerror = () => {
      console.error("Failed to load Razorpay Checkout SDK");
      resolve(false);
    };
    document.body.appendChild(script);
  });
}

export interface RazorpayCheckoutInitResult {
  success: boolean;
  data?: RazorpayCheckoutInitResponse;
  message: string;
  requires_admin_approval?: boolean;
  diagnostic?: {
    operation?: string;
    status_code?: number;
    error_code?: string;
    description?: string;
    action_required?: string;
  };
}

/**
 * Initiates Razorpay Subscription Checkout session from Flask backend
 * Validates server-side pricing, records non-sensitive bank choices, and accepts temporary phone for gateway prefill ONLY.
 */
export async function initiateSubscriptionCheckout(
  planId: string,
  phoneNumber?: string,
  bankName?: string,
  bankAccountType?: string,
  paymentMethod?: string
): Promise<RazorpayCheckoutInitResult> {
  const res = await apiFetchDetailed<any>("/subscriptions/checkout", {
    method: "POST",
    body: JSON.stringify({ 
      planId, 
      phone_number: phoneNumber?.trim() || undefined,
      bank_name: bankName || undefined,
      bank_account_type: bankAccountType || undefined,
      payment_method: paymentMethod || undefined
    })
  });

  if (res.data && (res.data.order_id || res.data.subscription_id) && res.data.key_id) {
    return {
      success: true,
      data: res.data as RazorpayCheckoutInitResponse,
      message: res.data.message || "Checkout session initialized."
    };
  }

  const requiresApproval = Boolean(
    res.data?.requires_admin_approval || 
    res.data?.details?.requires_admin_approval ||
    res.status === 403
  );

  const diagnostic = res.data?.diagnostic || res.data?.details?.diagnostic;

  return {
    success: false,
    message: res.error || res.data?.message || "Failed to initialize payment session. Please verify server connection.",
    requires_admin_approval: requiresApproval,
    diagnostic
  };
}

/**
 * Verifies Razorpay payment signature in the backend.
 * Sets verification status to verified and marks admin review as pending.
 * Does NOT activate subscription until admin approval.
 */
export async function verifySubscriptionPayment(
  callbackData: RazorpayPaymentCallback
): Promise<RazorpayVerifyResponse> {
  const res = await apiFetchDetailed<RazorpayVerifyResponse>("/subscriptions/verify", {
    method: "POST",
    body: JSON.stringify({
      razorpay_payment_id: callbackData.razorpay_payment_id,
      razorpay_order_id: callbackData.razorpay_order_id,
      razorpay_subscription_id: callbackData.razorpay_subscription_id,
      razorpay_signature: callbackData.razorpay_signature
    })
  });

  if (res.data && res.data.success) {
    return res.data;
  }

  return {
    success: false,
    message: res.error || res.data?.message || "Payment signature verification failed.",
    is_premium: false,
    awaiting_admin_approval: false
  };
}

/**
 * Subscribes to real-time subscription lifecycle events using Server-Sent Events (SSE).
 * Falls back gracefully to periodic polling if EventSource is unavailable or disconnects.
 */
export function subscribeToSubscriptionUpdates(
  onEvent: (event: { type: string; userId?: number; data?: any }) => void
): () => void {
  if (typeof window === "undefined") {
    return () => {};
  }

  const token = getAuthToken() || "";
  let eventSource: EventSource | null = null;
  let pollInterval: any = null;

  try {
    const sseUrl = `${API_BASE_URL}/subscriptions/stream-status${token ? `?token=${encodeURIComponent(token)}` : ""}`;
    eventSource = new EventSource(sseUrl);

    eventSource.onmessage = (e) => {
      try {
        if (!e.data || e.data.startsWith(":")) return;
        const parsed = JSON.parse(e.data);
        onEvent(parsed);
      } catch (err) {
        console.debug("SSE parse warning:", err);
      }
    };

    eventSource.onerror = () => {
      // Graceful fallback to polling if SSE connection drops
      if (eventSource) {
        eventSource.close();
        eventSource = null;
      }
      if (!pollInterval) {
        pollInterval = setInterval(async () => {
          try {
            const status = await fetchMySubscriptionStatus();
            onEvent({ type: "poll_sync", data: status });
          } catch (e) {
            // ignore network glitch
          }
        }, 3000);
      }
    };
  } catch (err) {
    console.debug("EventSource error, starting fallback poll:", err);
    pollInterval = setInterval(async () => {
      try {
        const status = await fetchMySubscriptionStatus();
        onEvent({ type: "poll_sync", data: status });
      } catch (e) {
        // ignore
      }
    }, 3000);
  }

  return () => {
    if (eventSource) {
      eventSource.close();
      eventSource = null;
    }
    if (pollInterval) {
      clearInterval(pollInterval);
      pollInterval = null;
    }
  };
}

/**
 * Records an isolated payment failure, bank decline, or e-mandate error for current citizen
 */
export async function reportPaymentFailure(details: {
  subscription_id?: string;
  payment_id?: string;
  error_code?: string;
  error_description?: string;
  error_source?: string;
  error_step?: string;
  error_reason?: string;
  bank?: string;
  payment_method?: string;
}): Promise<{ success: boolean; message: string; subscription?: SubscriptionRequestRecord }> {
  try {
    const res = await apiFetchDetailed<{ success: boolean; message: string; subscription?: SubscriptionRequestRecord }>("/subscriptions/report-failure", {
      method: "POST",
      body: JSON.stringify(details)
    });
    return {
      success: true,
      message: res.data?.message || "Payment failure recorded safely.",
      subscription: res.data?.subscription
    };
  } catch (err: any) {
    return {
      success: false,
      message: err.message || "Failed to record payment failure."
    };
  }
}

// ==========================================
// ADMIN SUBSCRIPTION MANAGEMENT METHODS
// ==========================================

async function adminApiCall<T>(
  endpoint: string, 
  options: RequestInit = {}
): Promise<{ data: T | null; error?: string }> {
  const token = getAdminToken();
  const headers: HeadersInit = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(options.headers || {})
  };

  const url = `${API_BASE_URL}${endpoint.startsWith('/') ? '' : '/'}${endpoint}`;

  try {
    const response = await fetch(url, { ...options, headers });
    let json: any = null;
    try {
      json = await response.json();
    } catch {
      json = null;
    }

    if (!response.ok) {
      if (response.status === 401 && typeof window !== "undefined") {
        clearAdminAuth();
        window.location.href = "/admin/login?expired=true";
      }
      return { data: null, error: json?.message || json?.error || `HTTP ${response.status}` };
    }

    return { data: json as T };
  } catch (err: any) {
    return { data: null, error: err.message || "Network error" };
  }
}

/**
 * Fetch all subscription requests for Admin management
 */
export async function fetchAdminSubscriptions(
  statusFilter?: string, 
  searchQuery?: string
): Promise<AdminSubscriptionListResponse | null> {
  const params = new URLSearchParams();
  if (statusFilter && statusFilter !== "all") params.set("status", statusFilter);
  if (searchQuery && searchQuery.trim()) params.set("q", searchQuery.trim());

  const qs = params.toString() ? `?${params.toString()}` : "";
  const res = await adminApiCall<AdminSubscriptionListResponse>(`/admin/subscriptions${qs}`);
  return res.data;
}

/**
 * Approve a subscription request for payment initiation (Admin only)
 * Authorizes payment workflow to proceed; does NOT mark payment successful directly.
 */
export async function approveSubscription(
  requestId: number,
  adminNotes?: string
): Promise<{ success: boolean; message: string; subscription?: SubscriptionRequestRecord }> {
  const res = await adminApiCall<{ message: string; subscription: SubscriptionRequestRecord }>(
    `/admin/subscriptions/${requestId}/approve`,
    { 
      method: "POST",
      body: JSON.stringify({ admin_notes: adminNotes })
    }
  );

  if (res.data) {
    return { success: true, message: res.data.message, subscription: res.data.subscription };
  }
  return { success: false, message: res.error || "Failed to approve subscription" };
}

/**
 * Reject a subscription request (Admin only)
 */
export async function rejectSubscription(
  requestId: number, 
  reason?: string
): Promise<{ success: boolean; message: string; subscription?: SubscriptionRequestRecord }> {
  const res = await adminApiCall<{ message: string; subscription: SubscriptionRequestRecord }>(
    `/admin/subscriptions/${requestId}/reject`,
    {
      method: "POST",
      body: JSON.stringify({ reason })
    }
  );

  if (res.data) {
    return { success: true, message: res.data.message, subscription: res.data.subscription };
  }
  return { success: false, message: res.error || "Failed to reject subscription" };
}

/**
 * Mark a payment request failed (Admin only)
 */
export async function markPaymentFailed(
  requestId: number,
  reason?: string,
  adminNotes?: string
): Promise<{ success: boolean; message: string; subscription?: SubscriptionRequestRecord }> {
  const res = await adminApiCall<{ message: string; subscription: SubscriptionRequestRecord }>(
    `/admin/subscriptions/${requestId}/mark-failed`,
    {
      method: "POST",
      body: JSON.stringify({ failure_reason: reason, admin_notes: adminNotes })
    }
  );

  if (res.data) {
    return { success: true, message: res.data.message, subscription: res.data.subscription };
  }
  return { success: false, message: res.error || "Failed to mark payment as failed" };
}

/**
 * Mark a payment request under administrative review (Admin only)
 */
export async function markUnderReview(
  requestId: number,
  adminNotes?: string
): Promise<{ success: boolean; message: string; subscription?: SubscriptionRequestRecord }> {
  const res = await adminApiCall<{ message: string; subscription: SubscriptionRequestRecord }>(
    `/admin/subscriptions/${requestId}/mark-review`,
    {
      method: "POST",
      body: JSON.stringify({ admin_notes: adminNotes })
    }
  );

  if (res.data) {
    return { success: true, message: res.data.message, subscription: res.data.subscription };
  }
  return { success: false, message: res.error || "Failed to mark request for review" };
}

/**
 * Verify actual gateway transaction status with Razorpay (Admin only)
 */
export async function verifyGatewayStatus(
  requestId: number
): Promise<{ success: boolean; message: string; subscription?: SubscriptionRequestRecord }> {
  const res = await adminApiCall<{ message: string; subscription: SubscriptionRequestRecord }>(
    `/admin/subscriptions/${requestId}/verify-gateway`,
    { method: "POST" }
  );

  if (res.data) {
    return { success: true, message: res.data.message, subscription: res.data.subscription };
  }
  return { success: false, message: res.error || "Failed to verify gateway status" };
}

/**
 * Admin Option A: Record Payment Successful & Activate Subscription
 */
export async function recordAdminOutcomeSuccess(
  requestId: number,
  adminNotes?: string
): Promise<{ success: boolean; message: string; subscription?: SubscriptionRequestRecord }> {
  const res = await adminApiCall<{ message: string; subscription: SubscriptionRequestRecord }>(
    `/admin/subscriptions/${requestId}/outcome/success`,
    {
      method: "POST",
      body: JSON.stringify({ admin_notes: adminNotes })
    }
  );

  if (res.data) {
    return { success: true, message: res.data.message, subscription: res.data.subscription };
  }
  return { success: false, message: res.error || "Failed to record payment success" };
}

/**
 * Admin Option B: Record Payment Successful but e-Mandate Failed
 * Keeps subscription inactive pending mandate resolution.
 */
export async function recordAdminOutcomeMandateFailed(
  requestId: number,
  failureReason?: string,
  adminNotes?: string
): Promise<{ success: boolean; message: string; subscription?: SubscriptionRequestRecord }> {
  const res = await adminApiCall<{ message: string; subscription: SubscriptionRequestRecord }>(
    `/admin/subscriptions/${requestId}/outcome/mandate-failed`,
    {
      method: "POST",
      body: JSON.stringify({ failure_reason: failureReason, admin_notes: adminNotes })
    }
  );

  if (res.data) {
    return { success: true, message: res.data.message, subscription: res.data.subscription };
  }
  return { success: false, message: res.error || "Failed to record mandate failure" };
}

/**
 * Admin Option C: Record Payment Failed
 * Records failure reason without false activation.
 */
export async function recordAdminOutcomeFailed(
  requestId: number,
  failureReason?: string,
  adminNotes?: string
): Promise<{ success: boolean; message: string; subscription?: SubscriptionRequestRecord }> {
  const res = await adminApiCall<{ message: string; subscription: SubscriptionRequestRecord }>(
    `/admin/subscriptions/${requestId}/outcome/failed`,
    {
      method: "POST",
      body: JSON.stringify({ failure_reason: failureReason, admin_notes: adminNotes })
    }
  );

  if (res.data) {
    return { success: true, message: res.data.message, subscription: res.data.subscription };
  }
  return { success: false, message: res.error || "Failed to record payment failure" };
}

/**
 * Admin Action: Authorize Citizen to Retry Payment or e-Mandate
 * Sets status to REQUIRES_RETRY without double charging.
 */
export async function authorizeRetryMandate(
  requestId: number,
  adminNotes?: string
): Promise<{ success: boolean; message: string; subscription?: SubscriptionRequestRecord }> {
  const res = await adminApiCall<{ message: string; subscription: SubscriptionRequestRecord }>(
    `/admin/subscriptions/${requestId}/retry-mandate`,
    {
      method: "POST",
      body: JSON.stringify({ admin_notes: adminNotes })
    }
  );

  if (res.data) {
    return { success: true, message: res.data.message, subscription: res.data.subscription };
  }
  return { success: false, message: res.error || "Failed to authorize retry" };
}

// Convenient aliases
export const fetchAdminSubscriptionRequests = fetchAdminSubscriptions;
export const approveSubscriptionRequest = approveSubscription;
export const rejectSubscriptionRequest = rejectSubscription;

