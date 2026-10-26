export type SubscriptionPlanId = "monthly" | "two_months" | "yearly";

export interface SubscriptionPlan {
  id: SubscriptionPlanId;
  name: string;
  price: number;
  currency: string;
  duration_days: number;
  duration_label: string;
  popular?: boolean;
  badge?: string;
  description: string;
  features: string[];
}

export interface PlanComparisonRow {
  feature: string;
  free: string;
  premium: string;
}

export interface SubscriptionPlansResponse {
  plans: SubscriptionPlan[];
  comparison: PlanComparisonRow[];
  free_limit: number;
}

export type SubscriptionStatus = 
  | "pending" 
  | "approved" 
  | "rejected" 
  | "cancelled"
  | "Pending" 
  | "Approved" 
  | "Rejected" 
  | "Cancelled";

export interface SubscriptionRequestRecord {
  id: number;
  userId: number;
  planId: string;
  planName: string;
  amount: number;
  amountInPaise?: number;
  currency: string;
  durationDays: number;
  status: SubscriptionStatus;
  adminApprovalStatus?: 
    | "pending"
    | "approved"
    | "rejected"
    | "PENDING_ADMIN_REVIEW" 
    | "PENDING_ADMIN_APPROVAL" 
    | "APPROVED_FOR_PAYMENT" 
    | "ADMIN_APPROVED" 
    | "REJECTED" 
    | "ADMIN_REJECTED" 
    | "UNDER_REVIEW" 
    | "REQUIRES_RETRY" 
    | string;
  paymentVerificationStatus?: "pending" | "verified" | "failed" | string;
  adminDecision?: string | null;
  bankName?: string | null;
  bankAccountType?: string | null;
  mandateStatus?: "MANDATE_PENDING" | "MANDATE_ACTIVE" | "MANDATE_FAILED" | string;
  paymentStatus?: "PAYMENT_PENDING" | "PAYMENT_SUCCESS" | "PAYMENT_FAILED" | string;
  paymentMethod?: string | null;
  failureReason?: string | null;
  razorpayOrderId?: string | null;
  razorpaySubscriptionId?: string | null;
  razorpayPaymentId?: string | null;
  rejectionReason?: string | null;
  adminNotes?: string | null;
  requestedAt: string;
  reviewedAt?: string | null;
  reviewedByAdminId?: number | null;
  startsAt?: string | null;
  expiresAt?: string | null;
  isActive: boolean;
  user?: {
    id: number;
    email?: string;
    mobile?: string;
    name: string;
  };
  phoneNumber?: string | null;
  paymentVerifiedAt?: string | null;
  activatedAt?: string | null;
  createdAt?: string | null;
  userName?: string;
  userEmail?: string;
}

export interface UserSubscriptionStatus {
  is_premium: boolean;
  tier: "free" | "premium";
  free_limit: number;
  active_subscription?: SubscriptionRequestRecord | null;
  days_remaining?: number | null;
  awaiting_admin_approval?: SubscriptionRequestRecord | null;
  has_awaiting_admin_approval?: boolean;
  pending_request?: SubscriptionRequestRecord | null;
  has_pending_request?: boolean;
  approved_for_payment?: SubscriptionRequestRecord | null;
  has_approved_payment_request?: boolean;
  latest_request?: SubscriptionRequestRecord | null;
}

export interface SubscriptionAdminStats {
  total: number;
  pending: number;
  approved: number;
  rejected: number;
  review?: number;
  failed?: number;
  mandate_failed?: number;
  active?: number;
}

export interface AdminSubscriptionListResponse {
  requests: SubscriptionRequestRecord[];
  stats: SubscriptionAdminStats;
}

export interface RazorpayCheckoutInitResponse {
  success: boolean;
  message: string;
  key_id: string;
  order_id?: string;
  subscription_id?: string;
  request_id?: number;
  plan_id: string;
  plan_name: string;
  amount: number;
  amount_in_paise: number;
  currency: string;
  bank_name?: string;
  bank_account_type?: string;
  payment_method?: string;
  user?: {
    name?: string;
    email?: string;
    contact?: string;
    mobile?: string;
  };
}

export interface RazorpayPaymentCallback {
  razorpay_payment_id: string;
  razorpay_order_id?: string;
  razorpay_subscription_id?: string;
  razorpay_signature: string;
}

export interface RazorpayVerifyResponse {
  success: boolean;
  message: string;
  is_premium: boolean;
  awaiting_admin_approval?: boolean;
  payment_verification_status?: string;
  admin_approval_status?: string;
  subscription?: SubscriptionRequestRecord;
}
