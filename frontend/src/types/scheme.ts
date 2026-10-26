export type EligibilityStatus = 
  | 'eligible' 
  | 'possibly_eligible' 
  | 'not_eligible' 
  | 'eligibility_unknown' 
  | 'applications_closed' 
  | 'almost' 
  | 'ineligible';

export type ApplicationWindowStatus = 'open' | 'closing_soon' | 'closed' | 'upcoming';

export interface EligibilityCriterion {
  id: string;
  name: string;
  condition: string;
  userValue?: string;
  passed: boolean;
}

export type SchemeStatus = 'draft' | 'published' | 'archived';

export interface SourceReference {
  official_url?: string;
  application_url?: string;
  source_url?: string;
  last_verified_date?: string;
  is_verified?: boolean;
}

export interface Scheme {
  id: string;
  numericId?: number;
  slug?: string;
  name: string;
  shortDescription: string;
  description: string;
  category: string;
  department: string;
  level: string; // e.g. "Central Scheme", "State Scheme", "District Scheme"
  state?: string;
  status?: SchemeStatus;
  applicationStatus?: ApplicationWindowStatus;
  isActive?: boolean;
  eligibilityStatus: EligibilityStatus;
  matchScore: number; // e.g. 100, 90, 75, 40
  benefit: string; // e.g. "Up to ₹6.5 Lakh", "₹5,000 – ₹20,000"
  benefits?: string;
  matchReason?: string;
  whyMatched?: string;
  requirementsSatisfied?: string[];
  requirementsNotSatisfied?: string[];
  missingInformation?: string[];
  ineligibleReason?: string;
  officialUrl: string;
  applicationUrl?: string;
  alternativeUrl?: string;
  portalStatus?: 'reachable' | 'temporarily_unavailable' | 'redirected' | 'unverified';
  portalStatusMessage?: string;
  sourceUrl?: string;
  sourceVerificationStatus?: string;
  lastFetchedAt?: string;
  applicationProcess?: string;
  lastVerifiedDate: string;
  criteria: EligibilityCriterion[];
  requiredDocuments: string[];
  sourceReference?: SourceReference;
  priority?: 'High Priority' | 'Medium Priority' | 'Low Priority';
  ageMin?: number | null;
  ageMax?: number | null;
  incomeMax?: number | null;
  occupation?: string | null;
  education?: string | null;
  gender?: string;
  socialCategory?: string;
  isFarmerOnly?: boolean;
  maxLandholdingAcres?: number | null;
  isStudentOnly?: boolean;
  isBusinessOnly?: boolean;
  isDisabilityRequired?: boolean;
  exclusions?: string[];
  startDate?: string | null;
  endDate?: string | null;
  verificationNotes?: string;
  groundingMetadata?: Record<string, any>;
  discoveryJobId?: number;
  adminReviewStatus?: string;
  rejectionReason?: string;
  citations?: Array<{ id: number; sourceTitle: string; sourceUrl: string; excerpt: string; confidenceScore: number }>;
  isLocked?: boolean;
  lockMessage?: string;
  rank?: number;
  createdAt?: string | null;
  updatedAt?: string | null;
}

export type { SchemeCitation } from './admin';
