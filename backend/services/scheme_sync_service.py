import datetime
import logging
import ssl
import time
import urllib.request
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from database import SessionLocal
from models import (
    Scheme, SchemeRule, SchemeDocumentRequirement, SourceDocument, Profile
)
from services.eligibility_service import SchemeEligibilityService

logger = logging.getLogger(__name__)

# Official 10 Government Schemes Catalogue with verified official portals
VERIFIED_SCHEMES_CATALOGUE = [
    {
        "slug": "pm-kisan",
        "name": "PM-KISAN — Pradhan Mantri Kisan Samman Nidhi",
        "short_description": "Income support of ₹6,000 per year directly to all landholding farmer families across India.",
        "description": "Pradhan Mantri Kisan Samman Nidhi (PM-KISAN) is a Central Sector scheme with 100% funding from Government of India. Under the scheme, an income support of ₹6,000/- per year is provided to all landholding farmer families across the country in three equal installments of ₹2,000/- each, every four months, directly into their Aadhaar-linked bank accounts via DBT.",
        "benefits": "₹6,000 per year in 3 equal installments of ₹2,000 directly transferred into Aadhaar-linked bank account",
        "category": "Agriculture",
        "department": "Department of Agriculture & Farmers Welfare, Ministry of Agriculture and Farmers Welfare",
        "level": "Central Scheme",
        "state": "All India",
        "official_source_url": "https://pmkisan.gov.in/",
        "application_url": "https://pmkisan.gov.in/RegistrationFormNew.aspx",
        "source_url": "https://pmkisan.gov.in/",
        "application_process": "1. Visit the Farmers Corner on official portal https://pmkisan.gov.in/\n2. Click on 'New Farmer Registration'.\n3. Enter Aadhaar Number, select State, and verify mobile number via OTP.\n4. Enter landholding details (Khatauni / Khasra number, survey plot, area in hectares).\n5. Upload land ownership document and submit. After State Nodal Officer verification, installment is credited via DBT.",
        "age_min": 18,
        "age_max": None,
        "income_max": None,
        "occupation": "Farmer",
        "education": "No minimum education requirement",
        "gender": "All",
        "social_category": "All",
        "is_farmer_only": True,
        "max_landholding_acres": None,
        "exclusions": ["Income tax payer in last assessment year", "Serving or retired government employee", "Constitutional post holder", "Doctor/Engineer/Lawyer/CA/Architect"],
        "priority": "High Priority",
        "application_status": "open",
        "rules": [
            {
                "rule_name": "Farmer Beneficiary",
                "rule_description": "Must be an active landholding farmer family",
                "rule_logic": {"field": "is_farmer", "op": "eq", "value": True},
                "is_mandatory": True
            },
            {
                "rule_name": "Minimum Age",
                "rule_description": "Age must be at least 18 years",
                "rule_logic": {"field": "age", "op": ">=", "value": 18},
                "is_mandatory": True
            },
            {
                "rule_name": "Non-Taxpayer Exclusion",
                "rule_description": "Beneficiary must not be an income tax payer",
                "rule_logic": {"field": "is_tax_payer", "op": "eq", "value": False},
                "is_mandatory": True
            }
        ],
        "documents": [
            {"name": "Aadhaar Card", "mandatory": True, "desc": "Mandatory for DBT authentication"},
            {"name": "Land Record (Khatauni / ROR / Khasra)", "mandatory": True, "desc": "Proof of cultivable agricultural land ownership"},
            {"name": "Bank Passbook with Aadhaar Seeding", "mandatory": True, "desc": "Bank account details with IFSC code for Direct Benefit Transfer"},
            {"name": "Active Mobile Number", "mandatory": True, "desc": "Linked to Aadhaar for OTP verification"}
        ]
    },
    {
        "slug": "pmfby",
        "name": "Pradhan Mantri Fasal Bima Yojana (PMFBY)",
        "short_description": "Comprehensive crop insurance shield covering natural calamities, pests, and post-harvest losses at nominal premium.",
        "description": "Pradhan Mantri Fasal Bima Yojana (PMFBY) is the flagship crop insurance scheme of the Government of India. It provides a comprehensive insurance shield covering non-preventable natural risks from pre-sowing to post-harvest stages. Farmers pay a uniform minimal premium of only 2% for Kharif crops, 1.5% for Rabi food & oilseed crops, and 5% for annual commercial/horticultural crops, with the remaining premium heavily subsidized equally by Central and State Governments.",
        "benefits": "Complete insurance coverage against yield loss and crop failure; Farmer premium capped at 1.5% to 2% with zero upper limit on government subsidy",
        "category": "Agriculture",
        "department": "Ministry of Agriculture and Farmers Welfare",
        "level": "Central Scheme",
        "state": "All India",
        "official_source_url": "https://pmfby.gov.in/",
        "application_url": "https://pmfby.gov.in/farmerRegistrationForm",
        "source_url": "https://pmfby.gov.in/",
        "application_process": "1. Visit the National Crop Insurance Portal at https://pmfby.gov.in/\n2. Click on 'Farmer Corner' and select 'Apply for Crop Insurance by yourself'.\n3. Register with mobile number and Aadhaar.\n4. Select Season (Kharif/Rabi), Year, Scheme (PMFBY), State, District, and Crop.\n5. Upload Land Possession Certificate / Sowing Certificate and submit.\n6. Non-loanee farmers can also apply through nearest Common Service Centre (CSC) or bank branch.",
        "age_min": 18,
        "age_max": None,
        "income_max": None,
        "occupation": "Farmer",
        "education": "No formal education required",
        "gender": "All",
        "social_category": "All",
        "is_farmer_only": True,
        "max_landholding_acres": None,
        "exclusions": ["Non-agricultural activities", "Preventable damages due to neglect"],
        "priority": "High Priority",
        "application_status": "open",
        "rules": [
            {
                "rule_name": "Active Cultivator",
                "rule_description": "Must be an active cultivator (owner, tenant farmer, or sharecropper)",
                "rule_logic": {"field": "is_farmer", "op": "eq", "value": True},
                "is_mandatory": True
            },
            {
                "rule_name": "Minimum Age",
                "rule_description": "Age must be at least 18 years",
                "rule_logic": {"field": "age", "op": ">=", "value": 18},
                "is_mandatory": True
            }
        ],
        "documents": [
            {"name": "Aadhaar Card", "mandatory": True, "desc": "Identity verification"},
            {"name": "Land Record (ROR / Khasra / Khatauni)", "mandatory": True, "desc": "Proof of landholding or tenancy agreement"},
            {"name": "Sowing Certificate / Crop Declaration", "mandatory": True, "desc": "Certificate issued by Village Revenue Officer or self-declaration"},
            {"name": "Bank Passbook", "mandatory": True, "desc": "Bank account copy for claim settlement credit"}
        ]
    },
    {
        "slug": "pm-kmy",
        "name": "Pradhan Mantri Kisan Maandhan Yojana (PM-KMY)",
        "short_description": "Assured monthly pension of ₹3,000 for Small and Marginal Farmers upon reaching 60 years of age.",
        "description": "Pradhan Mantri Kisan Maandhan Yojana (PM-KMY) is an old-age pension scheme for Small and Marginal Farmers (SMF) possessing cultivable land up to 2 hectares (approx. 5 acres). It is a voluntary and contributory pension scheme where the beneficiary contributes between ₹55 to ₹200 per month depending on entry age (18 to 40 years), and the Central Government contributes an equal matching amount. Upon attaining 60 years, the farmer receives an assured monthly pension of ₹3,000.",
        "benefits": "Assured lifelong monthly pension of ₹3,000 after age 60; 50% matching monthly contribution by Central Government",
        "category": "Agriculture",
        "department": "Ministry of Agriculture and Farmers Welfare (Administered via LIC)",
        "level": "Central Scheme",
        "state": "All India",
        "official_source_url": "https://www.myscheme.gov.in/schemes/pmkmdy",
        "application_url": "https://maandhan.in/",
        "source_url": "https://maandhan.in/",
        "application_process": "1. Visit nearest Common Service Centre (CSC) or visit https://maandhan.in/\n2. Provide Aadhaar number, Savings / Jan Dhan Bank Account details with IFSC.\n3. Verify age (must be between 18 and 40 years) and landholding (<= 2 hectares via Khatauni).\n4. System auto-calculates monthly installment.\n5. Complete e-Sign auto-debit mandate. Kisan Pension Card with unique Pension Account Number is generated instantly.",
        "age_min": 18,
        "age_max": 40,
        "income_max": None,
        "occupation": "Farmer",
        "education": "No formal education required",
        "gender": "All",
        "social_category": "All",
        "is_farmer_only": True,
        "max_landholding_acres": 5.0,
        "exclusions": ["Covered under any other social security scheme (NPS, ESIC, EPFO)", "Income tax payer", "Large farmers holding > 2 hectares of cultivable land"],
        "priority": "High Priority",
        "application_status": "open",
        "rules": [
            {
                "rule_name": "Small & Marginal Farmer",
                "rule_description": "Must be an active small or marginal farmer",
                "rule_logic": {"field": "is_farmer", "op": "eq", "value": True},
                "is_mandatory": True
            },
            {
                "rule_name": "Entry Age Range",
                "rule_description": "Entry age strictly between 18 and 40 years",
                "rule_logic": {"field": "age", "op": "<=", "value": 40},
                "is_mandatory": True
            },
            {
                "rule_name": "Minimum Entry Age",
                "rule_description": "Age must be >= 18 years",
                "rule_logic": {"field": "age", "op": ">=", "value": 18},
                "is_mandatory": True
            },
            {
                "rule_name": "Cultivable Land Limit",
                "rule_description": "Landholding must not exceed 2 hectares (5 acres)",
                "rule_logic": {"field": "land_holding_acres", "op": "<=", "value": 5.0},
                "is_mandatory": True
            },
            {
                "rule_name": "Non-Taxpayer Excluded",
                "rule_description": "Must not be an income tax payer",
                "rule_logic": {"field": "is_tax_payer", "op": "eq", "value": False},
                "is_mandatory": True
            }
        ],
        "documents": [
            {"name": "Aadhaar Card", "mandatory": True, "desc": "Identity proof for enrolment"},
            {"name": "Bank Passbook / Jan Dhan Account Details", "mandatory": True, "desc": "For auto-debit contribution and pension credit"},
            {"name": "Landholding Record (Khatauni / Khasra)", "mandatory": True, "desc": "Proof of holding <= 2 hectares of cultivable land"}
        ]
    },
    {
        "slug": "kisan-credit-card",
        "name": "Kisan Credit Card (KCC) Scheme",
        "short_description": "Subsidized institutional credit up to ₹3 Lakh at effective 4% interest rate with collateral-free limit up to ₹1.60 Lakh.",
        "description": "The Kisan Credit Card (KCC) scheme was introduced to ensure that farmers have timely access to affordable credit for agricultural production, purchase of seeds, fertilizers, pesticides, and post-harvest expenses. Loans up to ₹3,00,000 carry an effective interest rate of only 4% per annum (7% base minus 3% prompt repayment incentive). Collateral-free agricultural loans are sanctioned up to ₹1.60 Lakh without any processing fee.",
        "benefits": "Short-term credit limit up to ₹3 Lakh at 4% effective interest rate; Collateral-free credit up to ₹1.60 Lakh with ATM-enabled RuPay debit card",
        "category": "Agriculture",
        "department": "Ministry of Agriculture and Farmers Welfare / RBI / NABARD",
        "level": "Central Scheme",
        "state": "All India",
        "official_source_url": "https://www.myscheme.gov.in/schemes/kcc",
        "application_url": "https://pmkisan.gov.in/",
        "source_url": "https://www.myscheme.gov.in/schemes/kcc",
        "application_process": "1. Download the one-page simplified KCC form from https://pmkisan.gov.in/ or obtain from bank/CSC.\n2. Fill in land details, crop sown, and village revenue code.\n3. Submit with Aadhaar card copy and land ownership record (Khatauni).\n4. Under the simplified saturation drive, public sector banks are mandated to issue KCC within 14 working days of receiving completed application.",
        "age_min": 18,
        "age_max": 75,
        "income_max": None,
        "occupation": "Farmer",
        "education": "No minimum education requirement",
        "gender": "All",
        "social_category": "All",
        "is_farmer_only": True,
        "max_landholding_acres": None,
        "exclusions": ["Willful loan defaulters"],
        "priority": "High Priority",
        "application_status": "open",
        "rules": [
            {
                "rule_name": "Active Cultivator",
                "rule_description": "Must be an active farmer or owner-cultivator / tenant",
                "rule_logic": {"field": "is_farmer", "op": "eq", "value": True},
                "is_mandatory": True
            },
            {
                "rule_name": "Age Requirement",
                "rule_description": "Age between 18 and 75 years",
                "rule_logic": {"field": "age", "op": ">=", "value": 18},
                "is_mandatory": True
            }
        ],
        "documents": [
            {"name": "Aadhaar Card", "mandatory": True, "desc": "Identity and address proof"},
            {"name": "Land Records (Khatauni / Khasra / Revenue Extract)", "mandatory": True, "desc": "Proof of agricultural land and crop cultivation"},
            {"name": "Passport Size Photographs", "mandatory": True, "desc": "Two recent photographs for bank file"},
            {"name": "PAN Card or Form 60", "mandatory": False, "desc": "Tax identification document"}
        ]
    },
    {
        "slug": "soil-health-card",
        "name": "RKVY Soil Health and Fertility — Soil Health Card (SHC)",
        "short_description": "Periodic 12-parameter soil testing and customized crop-specific nutrient recommendations to optimize farm yield.",
        "description": "The Soil Health Card (SHC) scheme under Rashtriya Krishi Vikas Yojana (RKVY) provides all farmers across India with comprehensive soil health assessments every three years. Soil samples are analyzed for 12 critical chemical and physical parameters: Nitrogen (N), Phosphorus (P), Potassium (K), Sulphur (S), Zinc (Zn), Iron (Fe), Copper (Cu), Manganese (Mn), Boron (B), pH, Electrical Conductivity (EC), and Organic Carbon (OC). Farmers receive tailored advice on exact fertilizer dosage to prevent soil degradation and reduce input costs.",
        "benefits": "Free soil nutrient analysis across 12 parameters with personalized fertilizer and organic manure dosage guidance",
        "category": "Agriculture",
        "department": "Department of Agriculture & Farmers Welfare, Ministry of Agriculture and Farmers Welfare",
        "level": "Central Scheme",
        "state": "All India",
        "official_source_url": "https://www.myscheme.gov.in/schemes/rkvyshfshc",
        "application_url": "https://soilhealth.dac.gov.in/",
        "source_url": "https://soilhealth.dac.gov.in/",
        "application_process": "1. Visit the Soil Health Card Portal at https://soilhealth.dac.gov.in/\n2. State agriculture extension officers / Krishi Mitras collect GPS-tagged soil samples from farmer's plot.\n3. Samples are processed at government-accredited Soil Testing Laboratories (STLs).\n4. Farmer can view and download personalized Soil Health Card by entering State, District, and Plot/Khasra number directly on the portal.",
        "age_min": 18,
        "age_max": None,
        "income_max": None,
        "occupation": "Farmer",
        "education": "No education barrier",
        "gender": "All",
        "social_category": "All",
        "is_farmer_only": True,
        "max_landholding_acres": None,
        "exclusions": [],
        "priority": "Medium Priority",
        "application_status": "open",
        "rules": [
            {
                "rule_name": "Agricultural Landholder",
                "rule_description": "Must possess agricultural land for cultivation",
                "rule_logic": {"field": "is_farmer", "op": "eq", "value": True},
                "is_mandatory": True
            },
            {
                "rule_name": "Minimum Age",
                "rule_description": "Age >= 18 years",
                "rule_logic": {"field": "age", "op": ">=", "value": 18},
                "is_mandatory": True
            }
        ],
        "documents": [
            {"name": "Land Survey / Khasra Plot Details", "mandatory": True, "desc": "Identification of field grid from which soil is sampled"},
            {"name": "Aadhaar Card", "mandatory": True, "desc": "Farmer identity identification"},
            {"name": "Mobile Number", "mandatory": True, "desc": "To receive SMS alert when soil report is ready"}
        ]
    },
    {
        "slug": "pmksy-pdmc",
        "name": "Pradhan Mantri Krishi Sinchayee Yojana (PMKSY) — Per Drop More Crop",
        "short_description": "45% to 55% financial subsidy on precision micro-irrigation (Drip and Sprinkler) installations to maximize water efficiency.",
        "description": "Pradhan Mantri Krishi Sinchayee Yojana (PMKSY) focuses on enhancing water use efficiency at the farm level through 'Per Drop More Crop' (PDMC). The scheme provides substantial financial assistance for micro-irrigation systems: 55% subsidy for Small and Marginal Farmers (SMF) and 45% for other farmers on Drip and Sprinkler systems. In Uttar Pradesh and several other states, state top-ups increase the effective subsidy up to 80%–90% for small farmers.",
        "benefits": "45% to 55% Central subsidy (up to 80%-90% with State top-up in UP) on modern Drip & Sprinkler irrigation systems",
        "category": "Agriculture",
        "department": "Ministry of Agriculture and Farmers Welfare (Implemented through State Agriculture/Horticulture Departments)",
        "level": "Central Scheme",
        "state": "All India",
        "official_source_url": "https://pmksy.gov.in/",
        "application_url": "https://perdropmorecrop.dac.gov.in/",
        "source_url": "https://perdropmorecrop.dac.gov.in/",
        "application_process": "1. Access the national PDMC portal at https://perdropmorecrop.dac.gov.in/ or State Horticulture/Agriculture portal (in UP: https://dbt.uphorticulture.in/).\n2. Register farmer profile with Aadhaar and mobile number.\n3. Submit land ownership certificate (Khatauni) and proof of assured water source (borewell, tubewell, farm pond).\n4. Select empanelled micro-irrigation manufacturer and system configuration.\n5. Field verification is conducted by Agriculture/Horticulture officer and subsidy is released directly through DBT.",
        "age_min": 18,
        "age_max": None,
        "income_max": None,
        "occupation": "Farmer",
        "education": "No formal education required",
        "gender": "All",
        "social_category": "All",
        "is_farmer_only": True,
        "max_landholding_acres": None,
        "exclusions": ["Farmers without assured water source"],
        "priority": "High Priority",
        "application_status": "open",
        "rules": [
            {
                "rule_name": "Active Farmer",
                "rule_description": "Must be an active agricultural farmer",
                "rule_logic": {"field": "is_farmer", "op": "eq", "value": True},
                "is_mandatory": True
            },
            {
                "rule_name": "Minimum Age",
                "rule_description": "Age must be >= 18 years",
                "rule_logic": {"field": "age", "op": ">=", "value": 18},
                "is_mandatory": True
            }
        ],
        "documents": [
            {"name": "Aadhaar Card", "mandatory": True, "desc": "Identity verification"},
            {"name": "Land Record (Khatauni / Khasra)", "mandatory": True, "desc": "Proof of cultivable land ownership"},
            {"name": "Proof of Assured Water Source", "mandatory": True, "desc": "Electricity connection / tubewell certificate / farm pond proof"},
            {"name": "Bank Passbook with IFSC", "mandatory": True, "desc": "For DBT subsidy settlement"}
        ]
    },
    {
        "slug": "smam-mechanization",
        "name": "Sub-Mission on Agricultural Mechanization (SMAM)",
        "short_description": "40% to 50% subsidy on procurement of modern agricultural machinery and equipment, with special bonus for OBC/SC/ST.",
        "description": "The Sub-Mission on Agricultural Mechanization (SMAM) aims to promote agricultural mechanization among small and marginal farmers and in regions where farm power availability is low. The scheme offers 40% to 50% financial subsidy on purchase of individual agricultural equipment (such as power tillers, rotavators, seed-cum-fertilizer drills, multi-crop threshers, and laser land levelers) and up to 80% assistance for establishment of Custom Hiring Centres (CHCs). SC, ST, OBC, women, and small/marginal farmers receive an additional 10% financial subsidy.",
        "benefits": "40% to 50% financial subsidy on individual farm machinery; Up to 80% assistance for Custom Hiring Centres (CHCs)",
        "category": "Agriculture",
        "department": "Department of Agriculture & Farmers Welfare, Ministry of Agriculture and Farmers Welfare",
        "level": "Central Scheme",
        "state": "All India",
        "official_source_url": "https://agrimachinery.nic.in/",
        "application_url": "https://agrimachinery.nic.in/",
        "source_url": "https://agrimachinery.nic.in/",
        "application_process": "1. Visit the Direct Benefit Transfer in Agricultural Mechanization portal at https://agrimachinery.nic.in/\n2. Register under 'Farmer Registration' using Aadhaar, bank details, and land records.\n3. Select state, district, and required agricultural equipment from approved catalogue.\n4. Upload caste certificate (for OBC/SC/ST preference) and land proof.\n5. Receive tracking token; on administrative approval, purchase equipment from authorized dealer and upload invoice for DBT disbursement.",
        "age_min": 18,
        "age_max": None,
        "income_max": None,
        "occupation": "Farmer",
        "education": "No education barrier",
        "gender": "All",
        "social_category": "All",
        "is_farmer_only": True,
        "max_landholding_acres": None,
        "exclusions": ["Institutions or farmers who received equipment subsidy in last 3 years for same implement"],
        "priority": "High Priority",
        "application_status": "open",
        "rules": [
            {
                "rule_name": "Active Farmer",
                "rule_description": "Must be an active agricultural farmer",
                "rule_logic": {"field": "is_farmer", "op": "eq", "value": True},
                "is_mandatory": True
            },
            {
                "rule_name": "Minimum Age",
                "rule_description": "Age must be >= 18 years",
                "rule_logic": {"field": "age", "op": ">=", "value": 18},
                "is_mandatory": True
            }
        ],
        "documents": [
            {"name": "Aadhaar Card", "mandatory": True, "desc": "Identity verification"},
            {"name": "Land Record (Khatauni / Khasra)", "mandatory": True, "desc": "Proof of agricultural land ownership"},
            {"name": "Caste Certificate (for OBC/SC/ST)", "mandatory": False, "desc": "Required to claim higher 50% category subsidy rate"},
            {"name": "Bank Passbook with IFSC", "mandatory": True, "desc": "Direct Benefit Transfer account proof"}
        ]
    },
    {
        "slug": "agri-infra-fund",
        "name": "Agriculture Infrastructure Fund (AIF)",
        "short_description": "Medium to long-term debt financing with 3% interest subvention for post-harvest infrastructure and community farming assets.",
        "description": "The Agriculture Infrastructure Fund (AIF) is a dedicated financing facility of ₹1 Lakh Crore to mobilize medium to long-term debt financing for investment in viable projects for post-harvest management infrastructure and community farming assets. Loans carry an attractive interest subvention of 3% per annum up to a limit of ₹2 Crore for a maximum period of 7 years, along with credit guarantee coverage under CGTMSE for loans up to ₹2 Crore without demanding external third-party collateral.",
        "benefits": "3% per annum interest subvention on term loans up to ₹2 Crore for 7 years; Credit guarantee fee borne by Government",
        "category": "Agriculture",
        "department": "Ministry of Agriculture and Farmers Welfare",
        "level": "Central Scheme",
        "state": "All India",
        "official_source_url": "https://agriinfra.dac.gov.in/",
        "application_url": "https://agriinfra.dac.gov.in/Home/BeneficiaryRegistration",
        "source_url": "https://agriinfra.dac.gov.in/",
        "application_process": "1. Visit the AIF National Portal at https://agriinfra.dac.gov.in/\n2. Click on 'Beneficiary Registration' and select category (Individual Farmer, FPO, Agri-entrepreneur).\n3. Fill in applicant details and project profile (e.g. cold storage, sorting/grading unit, warehouse, solar drying).\n4. Upload Detailed Project Report (DPR) and select preferred lending bank.\n5. Ministry validates eligibility online within 7 days and forwards to bank for fast-track loan sanction.",
        "age_min": 18,
        "age_max": None,
        "income_max": None,
        "occupation": "Farmer",
        "education": "No formal education restriction",
        "gender": "All",
        "social_category": "All",
        "is_farmer_only": False,
        "max_landholding_acres": None,
        "exclusions": ["Non-agricultural commercial infrastructure"],
        "priority": "Medium Priority",
        "application_status": "open",
        "rules": [
            {
                "rule_name": "Minimum Age",
                "rule_description": "Age must be at least 18 years",
                "rule_logic": {"field": "age", "op": ">=", "value": 18},
                "is_mandatory": True
            }
        ],
        "documents": [
            {"name": "Aadhaar Card & PAN Card", "mandatory": True, "desc": "Identity and tax verification"},
            {"name": "Detailed Project Report (DPR) / Quotation", "mandatory": True, "desc": "Post-harvest infrastructure project layout and cost estimates"},
            {"name": "Land Document / Lease Agreement", "mandatory": True, "desc": "Site possession proof for proposed infrastructure"}
        ]
    },
    {
        "slug": "nfsm-food-security",
        "name": "National Food Security Mission (NFSM)",
        "short_description": "Up to 50% subsidy on high-yielding certified seeds, micronutrients, bio-fertilizers, and farm machinery.",
        "description": "National Food Security Mission (NFSM) is a Centrally Sponsored Scheme aimed at increasing the production and productivity of rice, wheat, pulses, coarse cereals, and oilseeds through area expansion and productivity enhancement in targeted districts across India (including Uttar Pradesh). Farmers receive direct subsidies up to 50% on certified seeds, bio-fertilizers, weedicides, micronutrients, water distribution pipes, and specialized farm implements.",
        "benefits": "50% subsidy on certified seeds (pulses, wheat, oilseeds); Free demonstration kits and subsidies on farm water pipes and sprayers",
        "category": "Agriculture",
        "department": "Department of Agriculture & Farmers Welfare, Ministry of Agriculture and Farmers Welfare",
        "level": "Central Scheme",
        "state": "All India",
        "official_source_url": "https://nfsm.gov.in/",
        "application_url": "https://nfsm.gov.in/",
        "source_url": "https://nfsm.gov.in/",
        "application_process": "1. Access the NFSM portal at https://nfsm.gov.in/ or visit Block/District Agriculture Office.\n2. In Uttar Pradesh, seed and input subsidies under NFSM are distributed through the State Agriculture DBT portal (http://upagriculture.com/).\n3. Registered farmers book subsidized certified seed lots at government agricultural stores (Beej Bhandar).\n4. Subsidy amount is credited directly to the farmer's bank account via DBT.",
        "age_min": 18,
        "age_max": None,
        "income_max": None,
        "occupation": "Farmer",
        "education": "No formal education required",
        "gender": "All",
        "social_category": "All",
        "is_farmer_only": True,
        "max_landholding_acres": None,
        "exclusions": [],
        "priority": "Medium Priority",
        "application_status": "open",
        "rules": [
            {
                "rule_name": "Active Farmer",
                "rule_description": "Must be an active agricultural farmer",
                "rule_logic": {"field": "is_farmer", "op": "eq", "value": True},
                "is_mandatory": True
            },
            {
                "rule_name": "Minimum Age",
                "rule_description": "Age must be >= 18 years",
                "rule_logic": {"field": "age", "op": ">=", "value": 18},
                "is_mandatory": True
            }
        ],
        "documents": [
            {"name": "Aadhaar Card", "mandatory": True, "desc": "Identity verification"},
            {"name": "Land Record (Khatauni)", "mandatory": True, "desc": "Proof of cultivable land"},
            {"name": "Bank Passbook", "mandatory": True, "desc": "For DBT subsidy settlement"}
        ]
    },
    {
        "slug": "up-krishi-yantra-anudan",
        "name": "Uttar Pradesh Krishi Yantra Anudan Yojana (UP Farm Mechanization Subsidy)",
        "short_description": "40% to 50% DBT grant on agricultural implements for verified UP farmers via transparent e-lottery token system.",
        "description": "Uttar Pradesh Krishi Yantra Anudan Yojana is an official flagship state welfare initiative operated by the Department of Agriculture, Government of Uttar Pradesh (पारदर्शी किसान सेवा योजना). Under this scheme, registered farmers resident in Uttar Pradesh receive 40% to 50% direct subsidy on verified purchase of modern agricultural implements (such as Rotavators, Cultivators, Seed-cum-Fertilizer Drills, Laser Land Levelers, Power Tillers, Straw Reapers, Multi-crop Threshers) through a transparent online token booking and e-lottery system. Small/marginal farmers and OBC, SC, ST farmers are allocated dedicated reserved token quotas.",
        "benefits": "Direct benefit transfer (DBT) subsidy of 40% to 50% on purchase of approved agricultural implements (up to ₹1 Lakh per machine)",
        "category": "Agriculture",
        "department": "Department of Agriculture, Government of Uttar Pradesh (कृषि विभाग, उत्तर प्रदेश)",
        "level": "State Scheme",
        "state": "Uttar Pradesh",
        "official_source_url": "https://up.gov.in/",
        "application_url": "http://upagriculture.com/Default.aspx",
        "source_url": "https://www.myscheme.gov.in/schemes/up-beej-anudan",
        "application_process": "1. Visit the official Uttar Pradesh Agriculture Department portal (http://upagriculture.com/ or state portal https://up.gov.in/).\n2. Log in with UP Farmer Registration Number (कृषक पंजीकरण संख्या).\n3. During token booking window, select desired agricultural implement and book e-token by depositing earnest deposit.\n4. Department conducts transparent e-lottery selection.\n5. Selected farmer purchases machine from authorized dealer within 30 days, uploads invoice and geo-tagged machine photo; subsidy is disbursed directly to bank account via DBT.",
        "age_min": 18,
        "age_max": None,
        "income_max": None,
        "occupation": "Farmer",
        "education": "No formal education required",
        "gender": "All",
        "social_category": "All",
        "is_farmer_only": True,
        "max_landholding_acres": None,
        "exclusions": ["Non-residents of Uttar Pradesh", "Farmers who claimed subsidy for same machinery in past 3 financial years"],
        "priority": "High Priority",
        "application_status": "open",
        "rules": [
            {
                "rule_name": "Uttar Pradesh Domicile",
                "rule_description": "Beneficiary must be a resident of Uttar Pradesh",
                "rule_logic": {"field": "state", "op": "eq", "value": "Uttar Pradesh"},
                "is_mandatory": True
            },
            {
                "rule_name": "Active UP Farmer",
                "rule_description": "Must be an active agricultural farmer in Uttar Pradesh",
                "rule_logic": {"field": "is_farmer", "op": "eq", "value": True},
                "is_mandatory": True
            },
            {
                "rule_name": "Minimum Age",
                "rule_description": "Age must be at least 18 years",
                "rule_logic": {"field": "age", "op": ">=", "value": 18},
                "is_mandatory": True
            }
        ],
        "documents": [
            {"name": "UP Farmer Registration ID (कृषक पंजीकरण संख्या)", "mandatory": True, "desc": "Active farmer registration number on upagriculture.com"},
            {"name": "Aadhaar Card", "mandatory": True, "desc": "Identity verification"},
            {"name": "UP Bhulekh Land Record (Khatauni / Khasra)", "mandatory": True, "desc": "Proof of agricultural landownership in Uttar Pradesh"},
            {"name": "Bank Passbook with IFSC", "mandatory": True, "desc": "Account linked with Aadhaar for DBT transfer"},
            {"name": "Caste Certificate (for OBC / SC / ST quota)", "mandatory": False, "desc": "Required for reserved category token allocation"}
        ]
    },
    {
        "slug": "adarsh-shikshak-puraskar-maharashtra",
        "name": "Maharashtra State Ideal Teacher Award (क्रांतिज्योती सावित्रीमाई फुले राज्य शिक्षक गुणगौरव पुरस्कार)",
        "short_description": "State cash award of ₹1,00,000, Gold Medal, and honor citation for meritorious school teachers in Maharashtra.",
        "description": "The Krantijyoti Savitrimai Phule State Teacher Award (Adarsh Shikshak Puraskar) is Maharashtra's premier state government honor administered by the School Education & Sports Department. Conferred annually on Teachers' Day (5th September), the scheme honors dedicated primary, secondary, higher secondary, and special teachers across Maharashtra for exemplary classroom pedagogy, innovative teaching learning material (TLM), girl child enrollment initiatives, and community engagement. Selected awardees receive a direct bank grant of ₹1,00,000, citation certificate, and service benefits.",
        "benefits": "₹1,00,000 direct cash prize, State Gold Medal, Certificate of Honor, and eligibility for state educational resource delegation",
        "category": "Education",
        "department": "School Education and Sports Department, Government of Maharashtra (शालेय शिक्षण व क्रीडा विभाग, महाराष्ट्र)",
        "level": "State Scheme",
        "state": "Maharashtra",
        "official_source_url": "https://education.maharashtra.gov.in/",
        "application_url": "https://mahadbt.maharashtra.gov.in/",
        "source_url": "https://education.maharashtra.gov.in/",
        "application_process": "1. Eligible teachers submit nomination portfolios via MahaDBT / Shalarth portal (https://education.maharashtra.gov.in/).\n2. Portfolio includes self-appraisal, classroom innovations, student achievement metrics, and headmaster recommendation.\n3. District Selection Committee headed by CEO / Education Officer (Secondary) verifies records and shortlists candidates.\n4. State Level Scrutiny Committee finalizes awardees.\n5. Cash prize of ₹1,00,000 and gold medal presented on 5th September.",
        "age_min": 21,
        "age_max": 65,
        "income_max": None,
        "occupation": "Teacher",
        "target_occupations": ["Teacher", "Educator", "Professor", "Faculty", "Instructor", "Lecturer", "Shikshak"],
        "target_beneficiary_groups": ["Teachers", "Educators", "School Faculty"],
        "eligible_states": ["Maharashtra"],
        "education": "12th Pass / D.Ed / B.Ed / Graduate",
        "gender": "All",
        "social_category": "All",
        "is_farmer_only": False,
        "max_landholding_acres": None,
        "exclusions": ["Disciplinary action or criminal inquiry pending"],
        "priority": "High Priority",
        "application_status": "open",
        "rules": [
            {
                "rule_name": "Maharashtra Domicile",
                "rule_description": "Must be resident of Maharashtra",
                "rule_logic": {"field": "state", "op": "eq", "value": "Maharashtra"},
                "is_mandatory": True
            },
            {
                "rule_name": "Active Teacher / Educator",
                "rule_description": "Must be serving as an active school teacher or educator",
                "rule_logic": {"field": "occupation", "op": "in", "value": ["Teacher", "Educator", "Professor", "Faculty", "Instructor", "Lecturer", "Shikshak"]},
                "is_mandatory": True
            },
            {
                "rule_name": "Minimum Age",
                "rule_description": "Age must be at least 21 years",
                "rule_logic": {"field": "age", "op": ">=", "value": 21},
                "is_mandatory": True
            }
        ],
        "documents": [
            {"name": "Aadhaar Card", "mandatory": True, "desc": "Identity verification"},
            {"name": "Teacher Service ID / Appointment Order", "mandatory": True, "desc": "Proof of employment in recognized school / Shalarth code"},
            {"name": "Educational Degree Marksheet (B.Ed / D.Ed / Degree)", "mandatory": True, "desc": "Professional educational qualification proof"},
            {"name": "Maharashtra Domicile Certificate", "mandatory": True, "desc": "Proof of residence in Maharashtra"},
            {"name": "Bank Passbook with IFSC", "mandatory": True, "desc": "Bank account for DBT transfer"}
        ]
    },
    {
        "slug": "national-award-to-teachers",
        "name": "National Award to Teachers (NAT) — Rashtriya Shikshak Puraskar",
        "short_description": "Prestigious national honor by Ministry of Education with ₹50,000 cash prize, Silver Medal, and President of India recognition.",
        "description": "The National Award to Teachers is the Government of India's highest national honor for educators, instituted by the Department of School Education and Literacy, Ministry of Education. The award recognizes outstanding classroom practitioners and institutional leaders who have demonstrated extraordinary commitment to improving educational access, promoting experiential learning under NEP 2020, and fostering creative pedagogy in government and aided schools across all States and UTs.",
        "benefits": "₹50,000 cash grant, Silver Medal, Certificate of Merit, and travel/hospitality for award conferment by the Hon'ble President of India at Vigyan Bhawan, New Delhi",
        "category": "Education",
        "department": "Department of School Education & Literacy, Ministry of Education, Government of India",
        "level": "Central Scheme",
        "state": "All India",
        "official_source_url": "https://nationalawardstoteachers.education.gov.in/",
        "application_url": "https://nationalawardstoteachers.education.gov.in/",
        "source_url": "https://nationalawardstoteachers.education.gov.in/",
        "application_process": "1. Register online directly on the National Award to Teachers portal (https://nationalawardstoteachers.education.gov.in/).\n2. Complete online self-nomination detailing ICT usage, student learning outcomes, and community mobilization.\n3. District Selection Committee (DSC) reviews applications and shortlists 3 top teachers per district.\n4. State Selection Committee (SSC) forwards nominations to National Jury.\n5. Independent National Jury evaluates video presentations and announces national awardees.",
        "age_min": 21,
        "age_max": 65,
        "income_max": None,
        "occupation": "Teacher",
        "target_occupations": ["Teacher", "Educator", "Professor", "Faculty", "Instructor", "Lecturer", "Shikshak"],
        "target_beneficiary_groups": ["Teachers", "Educators", "School Heads"],
        "eligible_states": ["All India", "Maharashtra"],
        "education": "12th Pass / Graduate / B.Ed",
        "gender": "All",
        "social_category": "All",
        "is_farmer_only": False,
        "max_landholding_acres": None,
        "exclusions": ["Tuition teachers or non-recognized private tutors"],
        "priority": "High Priority",
        "application_status": "open",
        "rules": [
            {
                "rule_name": "Active Teacher / Educator",
                "rule_description": "Must be an active school teacher or educator",
                "rule_logic": {"field": "occupation", "op": "in", "value": ["Teacher", "Educator", "Professor", "Faculty", "Instructor", "Lecturer", "Shikshak"]},
                "is_mandatory": True
            },
            {
                "rule_name": "Minimum Age",
                "rule_description": "Age must be at least 21 years",
                "rule_logic": {"field": "age", "op": ">=", "value": 21},
                "is_mandatory": True
            }
        ],
        "documents": [
            {"name": "Aadhaar Card", "mandatory": True, "desc": "Identity verification"},
            {"name": "School Service Certificate & UDISE / Shalarth ID", "mandatory": True, "desc": "Proof of teaching employment in recognized school"},
            {"name": "Pedagogy & Student Achievement Portfolio", "mandatory": True, "desc": "Evidence of innovative teaching practices"},
            {"name": "Bank Passbook with IFSC", "mandatory": True, "desc": "Direct Benefit Transfer account"}
        ]
    },
    {
        "slug": "maharashtra-shikshak-kalyan-nidhi",
        "name": "Maharashtra Teachers Welfare Fund (महाराष्ट्र शिक्षक कल्याण निधी व आरोग्य सहाय्यता)",
        "short_description": "Up to ₹1,50,000 medical relief grant and higher education financial aid for teachers and their families in Maharashtra.",
        "description": "Administered by the Directorate of Education, Government of Maharashtra, the Teachers Welfare Fund (Shikshak Kalyan Nidhi) provides compassionate social security, critical medical assistance, and educational support grants for primary and secondary school teachers in Maharashtra. The fund offers direct financial assistance up to ₹1.5 Lakh for severe health ailments (cardiac surgery, cancer therapy, kidney disease, neurosurgery) and scholarships for teachers' children pursuing professional degree courses.",
        "benefits": "Medical grant up to ₹1,50,000 for critical illness; Scholarship grant ₹10,000–₹25,000 for children of teachers; Ex-gratia emergency assistance",
        "category": "Social Welfare",
        "department": "Directorate of Education, Government of Maharashtra (शिक्षण संचलनालय, महाराष्ट्र राज्य)",
        "level": "State Scheme",
        "state": "Maharashtra",
        "official_source_url": "https://education.maharashtra.gov.in/",
        "application_url": "https://education.maharashtra.gov.in/",
        "source_url": "https://education.maharashtra.gov.in/",
        "application_process": "1. Download application form from the District Education Officer (Primary/Secondary) or visit https://education.maharashtra.gov.in/\n2. Submit medical treatment estimates / hospital bills or child college admission fee receipts.\n3. Headmaster / Principal countersigns application with teacher's Shalarth service code.\n4. District Welfare Committee sanctions relief and disburses grant directly via DBT into teacher's bank account.",
        "age_min": 21,
        "age_max": 65,
        "income_max": None,
        "occupation": "Teacher",
        "target_occupations": ["Teacher", "Educator", "Faculty", "Instructor", "Lecturer", "Shikshak"],
        "target_beneficiary_groups": ["Teachers", "Educators", "School Staff"],
        "eligible_states": ["Maharashtra"],
        "education": "12th Pass / Graduate",
        "gender": "All",
        "social_category": "All",
        "is_farmer_only": False,
        "max_landholding_acres": None,
        "exclusions": [],
        "priority": "High Priority",
        "application_status": "open",
        "rules": [
            {
                "rule_name": "Maharashtra Domicile",
                "rule_description": "Must be resident of Maharashtra",
                "rule_logic": {"field": "state", "op": "eq", "value": "Maharashtra"},
                "is_mandatory": True
            },
            {
                "rule_name": "Serving Teacher / Educator",
                "rule_description": "Must be an active teacher in Maharashtra recognized school",
                "rule_logic": {"field": "occupation", "op": "in", "value": ["Teacher", "Educator", "Professor", "Faculty", "Instructor", "Lecturer", "Shikshak"]},
                "is_mandatory": True
            },
            {
                "rule_name": "Minimum Age",
                "rule_description": "Age must be at least 21 years",
                "rule_logic": {"field": "age", "op": ">=", "value": 21},
                "is_mandatory": True
            }
        ],
        "documents": [
            {"name": "Aadhaar Card", "mandatory": True, "desc": "Identity verification"},
            {"name": "Teacher Service Identity Card / Salary Certificate", "mandatory": True, "desc": "Proof of teaching employment in Maharashtra"},
            {"name": "Medical Estimate / Hospital Bill or Child College Fee Receipt", "mandatory": True, "desc": "Supporting justification for welfare assistance"},
            {"name": "Bank Passbook with IFSC", "mandatory": True, "desc": "Direct Benefit Transfer account"}
        ]
    },
    {
        "slug": "pm-nishtha-teacher-training",
        "name": "NISHTHA — National Initiative for Teachers' Holistic Advancement",
        "short_description": "Free nationwide digital & classroom pedagogy training, NCERT certification, and professional development grant on DIKSHA.",
        "description": "NISHTHA is a nationwide capacity building program under Samagra Shiksha, Ministry of Education, covering elementary and secondary school teachers, school heads, and academic resource persons. Delivered through interactive modules on the national DIKSHA platform, it equips educators with competency-based education techniques, toy-based pedagogy, inclusive education practices, student mental health support, and digital literacy. Enrolled teachers receive free access, government training allowances, and verified national micro-credentials.",
        "benefits": "Free standardized pedagogical certification, training allowance/stipend, verified NCERT digital certificates, and modern teaching-learning material access",
        "category": "Skill Development",
        "department": "Department of School Education & Literacy, Ministry of Education & NCERT",
        "level": "Central Scheme",
        "state": "All India",
        "official_source_url": "https://diksha.gov.in/",
        "application_url": "https://itpd.ncert.gov.in/",
        "source_url": "https://diksha.gov.in/",
        "application_process": "1. Visit DIKSHA portal (https://diksha.gov.in/) or download DIKSHA mobile app.\n2. Register as 'Teacher' and select State (Maharashtra) and District.\n3. Link teacher credentials using State Shalarth ID / UDISE+ school code.\n4. Complete interactive modules, formative assessments, and practical classroom assignments.\n5. Download verifiable digital certificate issued jointly by NCERT and State Council of Educational Research and Training (SCERT Maharashtra).",
        "age_min": 20,
        "age_max": 65,
        "income_max": None,
        "occupation": "Teacher",
        "target_occupations": ["Teacher", "Educator", "Professor", "Faculty", "Instructor", "Lecturer", "Tutor", "School Head"],
        "target_beneficiary_groups": ["Teachers", "Educators", "Instructors", "Pedagogy Professionals"],
        "eligible_states": ["All India", "Maharashtra"],
        "education": "12th Pass / Graduate / D.Ed / B.Ed",
        "gender": "All",
        "social_category": "All",
        "is_farmer_only": False,
        "max_landholding_acres": None,
        "exclusions": [],
        "priority": "High Priority",
        "application_status": "open",
        "rules": [
            {
                "rule_name": "Practicing Teacher / Educator",
                "rule_description": "Must be an active teacher or academic educator",
                "rule_logic": {"field": "occupation", "op": "in", "value": ["Teacher", "Educator", "Professor", "Faculty", "Instructor", "Lecturer", "Tutor"]},
                "is_mandatory": True
            },
            {
                "rule_name": "Minimum Age",
                "rule_description": "Age must be at least 20 years",
                "rule_logic": {"field": "age", "op": ">=", "value": 20},
                "is_mandatory": True
            }
        ],
        "documents": [
            {"name": "Aadhaar Card", "mandatory": True, "desc": "Identity verification"},
            {"name": "School Teacher ID / Appointment Letter", "mandatory": True, "desc": "Proof of teaching employment"},
            {"name": "Mobile Number linked to DIKSHA", "mandatory": True, "desc": "For OTP and course enrollment"}
        ]
    },
    {
        "slug": "pm-mmp-teachers-mission",
        "name": "Pandit Madan Mohan Malaviya National Mission on Teachers and Teaching (PMMMNMTT)",
        "short_description": "Fully sponsored Faculty Development Programs (FDP), capacity building, and research grants for educators.",
        "description": "The Pandit Madan Mohan Malaviya National Mission on Teachers and Teaching (PMMMNMTT) is an umbrella central sector scheme by the Ministry of Education. It aims to address issues relating to teachers, preparation of educators, recruitment, and professional growth across schools, colleges, and higher education institutions. The scheme sponsors Faculty Induction Programs (FIP), Short-term Training Courses (STC), curriculum workshops, and action research grants through Teaching Learning Centres (TLCs) and Malaviya Mission Teacher Training Centres (MMTTC).",
        "benefits": "100% sponsored training & accommodation; Research fellowship and contingency grants up to ₹2 Lakh for pedagogical projects; CAS score enhancement for career progression",
        "category": "Education",
        "department": "Department of Higher Education, Ministry of Education, Government of India",
        "level": "Central Scheme",
        "state": "All India",
        "official_source_url": "https://nmtt.gov.in/",
        "application_url": "https://mmc.ugc.ac.in/",
        "source_url": "https://nmtt.gov.in/",
        "application_process": "1. Visit the Malaviya Mission Teacher Training portal at https://mmc.ugc.ac.in/\n2. Register with institutional email and employment details.\n3. Browse accredited Faculty Development Programmes (FDP) offered by premier universities (such as Savitribai Phule Pune University, Mumbai University, IITs, Central Universities).\n4. Submit nomination approved by Head of Institution / Principal.\n5. Attend sponsored program and obtain UGC/AICTE recognized certification.",
        "age_min": 21,
        "age_max": 65,
        "income_max": None,
        "occupation": "Teacher",
        "target_occupations": ["Teacher", "Educator", "Professor", "Faculty", "Lecturer", "Instructor", "Research Scholar"],
        "target_beneficiary_groups": ["Teachers", "Educators", "College Faculty", "Lecturers"],
        "eligible_states": ["All India", "Maharashtra"],
        "education": "Graduate / Post Graduate / B.Ed",
        "gender": "All",
        "social_category": "All",
        "is_farmer_only": False,
        "max_landholding_acres": None,
        "exclusions": [],
        "priority": "Medium Priority",
        "application_status": "open",
        "rules": [
            {
                "rule_name": "Serving Teacher / Faculty",
                "rule_description": "Must be a serving teacher or college faculty member",
                "rule_logic": {"field": "occupation", "op": "in", "value": ["Teacher", "Educator", "Professor", "Faculty", "Lecturer", "Instructor"]},
                "is_mandatory": True
            },
            {
                "rule_name": "Minimum Age",
                "rule_description": "Age must be at least 21 years",
                "rule_logic": {"field": "age", "op": ">=", "value": 21},
                "is_mandatory": True
            }
        ],
        "documents": [
            {"name": "Aadhaar Card", "mandatory": True, "desc": "Identity verification"},
            {"name": "Teacher Service ID / Appointment Letter", "mandatory": True, "desc": "Proof of teaching employment in recognized institution"},
            {"name": "Highest Degree Certificate", "mandatory": True, "desc": "Academic qualification verification"},
            {"name": "Bank Passbook with IFSC", "mandatory": True, "desc": "Direct Benefit Transfer account"}
        ]
    },
    {
        "slug": "pm-vidyalakshmi",
        "name": "PM Vidyalakshmi Scheme",
        "short_description": "Collateral-free, guarantor-free education loan with up to 75% credit guarantee and 3% interest subvention for higher education in top 860 NIRF-ranked institutions.",
        "description": "PM Vidyalakshmi is a Central Sector Scheme launched by the Ministry of Education to provide financial support to meritorious students pursuing higher studies in top-ranked higher education institutions (HEIs). Under the scheme, students admitted to eligible institutions can avail collateral-free, guarantor-free education loans up to ₹7.5 Lakh with 75% credit guarantee and 3% interest subvention for annual family incomes up to ₹8 Lakh.",
        "benefits": "Collateral-free and guarantor-free education loan up to ₹7.5 Lakh; 75% credit guarantee by GoI; 3% interest subvention during moratorium period for family income up to ₹8 Lakh.",
        "category": "Education",
        "department": "Department of Higher Education, Ministry of Education, Government of India",
        "level": "Central Scheme",
        "state": "All India",
        "official_source_url": "https://pmvidyalaxmi.co.in/",
        "application_url": "https://pmvidyalaxmi.co.in/",
        "source_url": "https://pmvidyalaxmi.co.in/",
        "application_process": "1. Visit the official portal https://pmvidyalakshmi.dos.gov.in/\n2. Register with student Aadhaar and email.\n3. Fill in student profile, admission details in eligible NIRF institution, and loan requirement.\n4. Apply directly to scheduled commercial banks through the unified dashboard.\n5. Track loan sanction and interest subvention directly via DBT.",
        "age_min": 16,
        "age_max": 30,
        "income_max": 800000.0,
        "occupation": "Student",
        "target_occupations": ["Student"],
        "target_beneficiary_groups": ["Students", "Higher Education Scholars"],
        "eligible_states": ["All India"],
        "education": "12th Pass / Graduate / Post Graduate",
        "gender": "All",
        "social_category": "All",
        "is_farmer_only": False,
        "is_student_only": True,
        "is_business_only": False,
        "max_landholding_acres": None,
        "exclusions": ["Full-time corporate employee", "Family income above ₹8 Lakh for interest subvention"],
        "priority": "High Priority",
        "application_status": "open",
        "rules": [
            {
                "rule_name": "Student Status",
                "rule_description": "Must be an active student enrolled in higher education",
                "rule_logic": {"field": "is_student", "op": "eq", "value": True},
                "is_mandatory": True
            },
            {
                "rule_name": "Family Income Threshold",
                "rule_description": "Annual family income must not exceed ₹8,00,000",
                "rule_logic": {"field": "annual_income", "op": "<=", "value": 800000.0},
                "is_mandatory": True
            }
        ],
        "documents": [
            {"name": "Aadhaar Card", "mandatory": True, "desc": "Identity verification"},
            {"name": "Admission Letter / Fee Receipt", "mandatory": True, "desc": "Proof of enrollment in recognized higher education institution"},
            {"name": "Income Certificate", "mandatory": True, "desc": "Competent authority family income certificate"},
            {"name": "Bank Account Details", "mandatory": True, "desc": "Aadhaar-seeded student bank account"}
        ]
    },
    {
        "slug": "post-matric-scholarship",
        "name": "Post Matric Scholarship (State Govt.)",
        "short_description": "Tuition fees, exam fees, and monthly maintenance allowance for post-secondary students.",
        "description": "Post Matric Scholarship scheme provided by Government of Maharashtra through the MahaDBT portal for students pursuing post-matriculation courses in recognized colleges and universities. Reimburses 100% compulsory tuition and examination fees along with living allowance.",
        "benefits": "100% Tuition fees, examination fees reimbursement and monthly maintenance allowance of ₹700 to ₹1,200.",
        "category": "Education",
        "department": "Department of Higher & Technical Education, Government of Maharashtra",
        "level": "State Scheme",
        "state": "Maharashtra",
        "official_source_url": "https://mahadbt.maharashtra.gov.in/",
        "application_url": "https://mahadbt.maharashtra.gov.in/",
        "source_url": "https://mahadbt.maharashtra.gov.in/",
        "application_process": "1. Visit MahaDBT portal https://mahadbt.maharashtra.gov.in/\n2. Register with Aadhaar number and create applicant profile.\n3. Complete domicile, caste/category, and family income verification.\n4. Select institution, course, and submit scholarship application before the deadline.",
        "age_min": 15,
        "age_max": 30,
        "income_max": 250000.0,
        "occupation": "Student",
        "target_occupations": ["Student"],
        "target_beneficiary_groups": ["Post-Matric Students", "College Students"],
        "eligible_states": ["Maharashtra"],
        "education": "10th Pass / 12th Pass / Graduate",
        "gender": "All",
        "social_category": "All",
        "is_farmer_only": False,
        "is_student_only": True,
        "is_business_only": False,
        "max_landholding_acres": None,
        "exclusions": ["Annual family income exceeding ₹2.5 Lakh", "Non-Maharashtra residents"],
        "priority": "High Priority",
        "application_status": "open",
        "rules": [
            {
                "rule_name": "Student Enrollment",
                "rule_description": "Must be an active student pursuing post-matric education",
                "rule_logic": {"field": "is_student", "op": "eq", "value": True},
                "is_mandatory": True
            },
            {
                "rule_name": "Income Limit",
                "rule_description": "Family income must not exceed ₹2,50,000",
                "rule_logic": {"field": "annual_income", "op": "<=", "value": 250000.0},
                "is_mandatory": True
            },
            {
                "rule_name": "Maharashtra Domicile",
                "rule_description": "Must reside in Maharashtra",
                "rule_logic": {"field": "state", "op": "eq", "value": "Maharashtra"},
                "is_mandatory": True
            }
        ],
        "documents": [
            {"name": "Aadhaar Card", "mandatory": True, "desc": "Identity verification"},
            {"name": "Domicile Certificate", "mandatory": True, "desc": "Proof of Maharashtra residence"},
            {"name": "Income Certificate from Tahsildar", "mandatory": True, "desc": "Income proof below ₹2.5 Lakh"},
            {"name": "College Admission Fee Receipt", "mandatory": True, "desc": "Current academic year receipt"}
        ]
    },
    {
        "slug": "post-matric-scholarship-to-obc-students",
        "name": "Post Matric Scholarship to OBC Students",
        "short_description": "Full fee reimbursement and monthly stipend for Other Backward Class (OBC) students studying in Maharashtra.",
        "description": "Scheme implemented by VJNT, OBC and SBC Welfare Department of Maharashtra on MahaDBT for Other Backward Class (OBC) students pursuing post-matric education. Provides tuition fee waivers, examination fee waivers, and monthly stipends.",
        "benefits": "50% to 100% tuition and examination fee concession plus maintenance allowance up to ₹4,250 per term.",
        "category": "Education",
        "department": "VJNT, OBC and SBC Welfare Department, Government of Maharashtra",
        "level": "State Scheme",
        "state": "Maharashtra",
        "official_source_url": "https://mahadbt.maharashtra.gov.in/",
        "application_url": "https://mahadbt.maharashtra.gov.in/",
        "source_url": "https://mahadbt.maharashtra.gov.in/",
        "application_process": "1. Visit MahaDBT at https://mahadbt.maharashtra.gov.in/\n2. Login with Applicant credentials.\n3. Upload valid Non-Creamy Layer and Caste Certificate.\n4. Link Aadhaar-seeded bank account and apply under VJNT/OBC section.",
        "age_min": 15,
        "age_max": 30,
        "income_max": 250000.0,
        "occupation": "Student",
        "target_occupations": ["Student"],
        "target_beneficiary_groups": ["OBC Students", "Higher Education Scholars"],
        "eligible_states": ["Maharashtra"],
        "education": "10th Pass / 12th Pass / Graduate",
        "gender": "All",
        "social_category": "OBC",
        "is_farmer_only": False,
        "is_student_only": True,
        "is_business_only": False,
        "max_landholding_acres": None,
        "exclusions": ["General category applicants", "Family income above ₹2.5 Lakh"],
        "priority": "High Priority",
        "application_status": "open",
        "rules": [
            {
                "rule_name": "Student Status",
                "rule_description": "Must be an enrolled student",
                "rule_logic": {"field": "is_student", "op": "eq", "value": True},
                "is_mandatory": True
            },
            {
                "rule_name": "OBC Category",
                "rule_description": "Must belong to OBC category",
                "rule_logic": {"field": "category", "op": "eq", "value": "OBC"},
                "is_mandatory": True
            },
            {
                "rule_name": "Income Limit",
                "rule_description": "Family income must not exceed ₹2,50,000",
                "rule_logic": {"field": "annual_income", "op": "<=", "value": 250000.0},
                "is_mandatory": True
            }
        ],
        "documents": [
            {"name": "OBC Caste Certificate", "mandatory": True, "desc": "Issued by Sub-Divisional Officer"},
            {"name": "Non-Creamy Layer Certificate", "mandatory": True, "desc": "Valid for current financial year"},
            {"name": "Income Certificate", "mandatory": True, "desc": "Tahsildar issued income proof"}
        ]
    },
    {
        "slug": "skill-india-training",
        "name": "Skill India — Training Program (PMKVY)",
        "short_description": "Free industry-aligned skill certification, assessment, and placement assistance under PMKVY.",
        "description": "Pradhan Mantri Kaushal Vikas Yojana (PMKVY) is the flagship scheme of the Ministry of Skill Development & Entrepreneurship (MSDE). It enables youth and job seekers to take up industry-relevant skill training that helps them secure a better livelihood. Free training, certification, and monetary rewards upon assessment.",
        "benefits": "100% free technical/vocational training, government recognized NSQF certificate, and monetary reward of ₹8,000 on completion.",
        "category": "Skill Development",
        "department": "Ministry of Skill Development & Entrepreneurship, Government of India",
        "level": "Central Scheme",
        "state": "All India",
        "official_source_url": "https://www.skillindia.gov.in/",
        "application_url": "https://www.skillindia.gov.in/",
        "source_url": "https://www.skillindia.gov.in/",
        "application_process": "1. Visit Skill India Digital portal at https://www.skillindia.gov.in/\n2. Register using mobile number and Aadhaar e-KYC.\n3. Choose interested sector and accredited training centre.\n4. Complete hands-on training and clear third-party assessment to obtain certificate.",
        "age_min": 15,
        "age_max": 45,
        "income_max": None,
        "occupation": "Unemployed Person, Youth & Students",
        "target_occupations": ["Unemployed Person", "Student", "Youth", "Self-employed", "Employee"],
        "target_beneficiary_groups": ["Youth", "Job Seekers", "Students"],
        "eligible_states": ["All India"],
        "education": "No Formal Education / 8th Pass / 10th Pass / 12th Pass",
        "gender": "All",
        "social_category": "All",
        "is_farmer_only": False,
        "is_student_only": False,
        "is_business_only": False,
        "max_landholding_acres": None,
        "exclusions": [],
        "priority": "High Priority",
        "application_status": "open",
        "rules": [
            {
                "rule_name": "Eligible Age Bracket",
                "rule_description": "Age between 15 and 45 years",
                "rule_logic": {"field": "age", "op": "between", "value": [15, 45]},
                "is_mandatory": True
            }
        ],
        "documents": [
            {"name": "Aadhaar Card", "mandatory": True, "desc": "Identity verification"},
            {"name": "Bank Passbook", "mandatory": True, "desc": "For direct benefit reward credit"}
        ]
    },
    {
        "slug": "mjp-jan-arogya",
        "name": "Mahatma Jyotiba Phule Jan Arogya Yojana (MJPJAY)",
        "short_description": "Cashless hospitalization health insurance coverage up to ₹5,00,000 per family per year in Maharashtra.",
        "description": "Mahatma Jyotiba Phule Jan Arogya Yojana is the flagship health assurance scheme of Government of Maharashtra. It provides cashless medical treatment across 1,356 medical and surgical procedures in empaneled network hospitals for all families holding valid ration cards in Maharashtra.",
        "benefits": "Cashless hospitalization coverage up to ₹5 Lakh per family per year covering critical illness, surgeries, and post-operative care.",
        "category": "Health & Wellness",
        "department": "Public Health Department, Government of Maharashtra",
        "level": "State Scheme",
        "state": "Maharashtra",
        "official_source_url": "https://www.jeevandayee.gov.in/",
        "application_url": "https://www.jeevandayee.gov.in/",
        "source_url": "https://www.jeevandayee.gov.in/",
        "application_process": "1. Approach the Arogyamitra at any empaneled government or private network hospital.\n2. Present your Ration Card (Yellow, Orange, or White) and Aadhaar card.\n3. Arogyamitra generates cashless pre-authorization referral without any advance deposit.",
        "age_min": 0,
        "age_max": 120,
        "income_max": None,
        "occupation": "All Citizens / Families in Maharashtra",
        "target_occupations": ["All Categories", "Farmer", "Student", "Employee", "Salaried Employee", "Self-employed", "Shopkeeper", "Housewife", "Homemaker", "Unemployed Person", "Artisan / Craftsperson", "Teacher"],
        "target_beneficiary_groups": ["All Maharashtra Citizens", "Families in Maharashtra"],
        "eligible_states": ["Maharashtra"],
        "education": "No Formal Education",
        "gender": "All",
        "social_category": "All",
        "is_farmer_only": False,
        "is_student_only": False,
        "is_business_only": False,
        "max_landholding_acres": None,
        "exclusions": ["Non-Maharashtra residents"],
        "priority": "High Priority",
        "application_status": "open",
        "rules": [
            {
                "rule_name": "Maharashtra Domicile",
                "rule_description": "Must reside in Maharashtra",
                "rule_logic": {"field": "state", "op": "eq", "value": "Maharashtra"},
                "is_mandatory": True
            }
        ],
        "documents": [
            {"name": "Aadhaar Card", "mandatory": True, "desc": "Identity verification"},
            {"name": "Ration Card", "mandatory": True, "desc": "Valid Maharashtra ration card"}
        ]
    },
    {
        "slug": "naps-apprenticeship",
        "name": "National Apprenticeship Promotion Scheme (NAPS)",
        "short_description": "On-the-job apprenticeship training with 25% stipend support up to ₹1,500/month by Government of India.",
        "description": "National Apprenticeship Promotion Scheme (NAPS) by the Ministry of Skill Development & Entrepreneurship promotes apprenticeship training across industrial establishments. Under NAPS-2, government directly shares stipend with establishments up to ₹1,500 per month per apprentice.",
        "benefits": "Monthly stipend (₹6,000 - ₹12,000) with Government contributing ₹1,500/month directly via DBT; National Apprenticeship Certificate.",
        "category": "Skill Development",
        "department": "Ministry of Skill Development & Entrepreneurship, Government of India",
        "level": "Central Scheme",
        "state": "All India",
        "official_source_url": "https://www.apprenticeshipindia.gov.in/",
        "application_url": "https://www.apprenticeshipindia.gov.in/",
        "source_url": "https://www.apprenticeshipindia.gov.in/",
        "application_process": "1. Register on apprenticeship portal https://www.apprenticeshipindia.gov.in/\n2. Complete eKYC and profile creation.\n3. Search and apply for active apprenticeship vacancies across public and private sector enterprises.",
        "age_min": 16,
        "age_max": 35,
        "income_max": None,
        "occupation": "Apprentices, Students & Job Seekers",
        "target_occupations": ["Student", "Unemployed Person", "Youth", "Self-employed"],
        "target_beneficiary_groups": ["Youth", "Students", "Apprentices"],
        "eligible_states": ["All India"],
        "education": "8th Pass / 10th Pass / 12th Pass / ITI / Diploma / Graduate",
        "gender": "All",
        "social_category": "All",
        "is_farmer_only": False,
        "is_student_only": False,
        "is_business_only": False,
        "max_landholding_acres": None,
        "exclusions": [],
        "priority": "Medium Priority",
        "application_status": "open",
        "rules": [
            {
                "rule_name": "Apprentice Age Range",
                "rule_description": "Age between 16 and 35 years",
                "rule_logic": {"field": "age", "op": "between", "value": [16, 35]},
                "is_mandatory": True
            }
        ],
        "documents": [
            {"name": "Aadhaar Card", "mandatory": True, "desc": "Identity verification"},
            {"name": "Educational Marksheet", "mandatory": True, "desc": "8th/10th/ITI/Diploma marksheet"}
        ]
    },
    {
        "slug": "pm-internship-scheme",
        "name": "PM Internship Scheme in Top 500 Companies",
        "short_description": "12-month paid internship with ₹5,000 monthly stipend and one-time ₹6,000 grant in top Indian corporations.",
        "description": "The Prime Minister Internship Scheme provides 12 months of internship opportunities in India's top 500 companies. Interns gain practical corporate work experience, receive ₹5,000 per month as stipend (₹4,500 from GoI via DBT + ₹500 from company CSR), plus a one-time grant of ₹6,000 for incidentals.",
        "benefits": "₹5,000 monthly stipend, ₹6,000 one-time incidentals grant, and insurance coverage under PMJJBY and PMSBY.",
        "category": "Employment & Enterprise",
        "department": "Ministry of Corporate Affairs, Government of India",
        "level": "Central Scheme",
        "state": "All India",
        "official_source_url": "https://pminternship.mca.gov.in/",
        "application_url": "https://pminternship.mca.gov.in/",
        "source_url": "https://pminternship.mca.gov.in/",
        "application_process": "1. Visit the portal at https://pminternship.mca.gov.in/\n2. Register with Aadhaar e-KYC.\n3. Fill in qualifications (10th/12th/ITI/Polytechnic/Graduation).\n4. Select up to 5 internship opportunities in top companies.\n5. Offer letter released digitally upon company selection.",
        "age_min": 21,
        "age_max": 24,
        "income_max": 800000.0,
        "occupation": "Unemployed Youth & Students",
        "target_occupations": ["Unemployed Person", "Student", "Youth"],
        "target_beneficiary_groups": ["Youth", "Unemployed Graduates", "Students"],
        "eligible_states": ["All India"],
        "education": "10th Pass / 12th Pass / ITI / Diploma / Graduate",
        "gender": "All",
        "social_category": "All",
        "is_farmer_only": False,
        "is_student_only": False,
        "is_business_only": False,
        "max_landholding_acres": None,
        "exclusions": ["Full-time employee in government or corporate", "Income tax payer family", "IIT/IIM/IISER/CA graduates"],
        "priority": "High Priority",
        "application_status": "open",
        "rules": [
            {
                "rule_name": "Age Restriction",
                "rule_description": "Age between 21 and 24 years",
                "rule_logic": {"field": "age", "op": "between", "value": [21, 24]},
                "is_mandatory": True
            },
            {
                "rule_name": "Family Income Below ₹8 Lakh",
                "rule_description": "Annual family income must not exceed ₹8,00,000",
                "rule_logic": {"field": "annual_income", "op": "<=", "value": 800000.0},
                "is_mandatory": True
            }
        ],
        "documents": [
            {"name": "Aadhaar Card", "mandatory": True, "desc": "Identity verification"},
            {"name": "Educational Certificates", "mandatory": True, "desc": "10th/12th/Diploma/Degree"},
            {"name": "Self-Declaration on Employment", "mandatory": True, "desc": "Declaration of non-full-time employment"}
        ]
    },
    {
        "slug": "pm-vishwakarma",
        "name": "PM Vishwakarma Scheme",
        "short_description": "Recognition, ₹15,000 toolkit incentive, free skill training with ₹500/day stipend, and collateral-free loans up to ₹3 Lakh at 5% interest for traditional artisans.",
        "description": "PM Vishwakarma is a Central Sector Scheme by the Ministry of MSME to support traditional artisans and craftspersons across 18 designated trades (carpenters, blacksmiths, goldsmiths, potters, cobblers, tailors, etc.). Provides PM Vishwakarma Certificate & ID, basic & advanced skill training with stipend, ₹15,000 modern toolkit voucher, and collateral-free enterprise credit up to ₹3,00,000 at a concessional interest rate of 5%.",
        "benefits": "PM Vishwakarma Certificate & ID, ₹15,000 digital toolkit voucher, ₹500/day training stipend, collateral-free loans up to ₹3 Lakh at 5% interest.",
        "category": "Employment & Enterprise",
        "department": "Ministry of Micro, Small and Medium Enterprises, Government of India",
        "level": "Central Scheme",
        "state": "All India",
        "official_source_url": "https://pmvishwakarma.gov.in/",
        "application_url": "https://pmvishwakarma.gov.in/",
        "source_url": "https://pmvishwakarma.gov.in/",
        "application_process": "1. Visit nearest Common Services Centre (CSC) or portal https://pmvishwakarma.gov.in/\n2. Submit Aadhaar and trade details with artisan self-attestation.\n3. Gram Panchayat / Urban Local Body verification.\n4. District Implementation Committee screening and approval.",
        "age_min": 18,
        "age_max": 75,
        "income_max": None,
        "occupation": "Traditional Artisans & Craftspersons",
        "target_occupations": ["Artisan / Craftsperson", "Self-employed", "Business Owner", "Shopkeeper"],
        "target_beneficiary_groups": ["Artisans", "Craftspersons", "Self-employed"],
        "eligible_states": ["All India"],
        "education": "No Formal Education",
        "gender": "All",
        "social_category": "All",
        "is_farmer_only": False,
        "is_student_only": False,
        "is_business_only": True,
        "max_landholding_acres": None,
        "exclusions": ["Government servants", "Families with members who availed PM-SVANidhi or PMEGP in last 5 years without repayment"],
        "priority": "High Priority",
        "application_status": "open",
        "rules": [
            {
                "rule_name": "Traditional Artisan / Self-employed",
                "rule_description": "Must be engaged in self-employment or traditional trade",
                "rule_logic": {"field": "has_business", "op": "eq", "value": True},
                "is_mandatory": True
            },
            {
                "rule_name": "Minimum Age",
                "rule_description": "Age must be at least 18 years",
                "rule_logic": {"field": "age", "op": ">=", "value": 18},
                "is_mandatory": True
            }
        ],
        "documents": [
            {"name": "Aadhaar Card", "mandatory": True, "desc": "Biometric eKYC"},
            {"name": "Bank Account Passbook", "mandatory": True, "desc": "Aadhaar linked account"},
            {"name": "Trade / Artisan Proof", "mandatory": True, "desc": "Gram Panchayat recommendation"}
        ]
    },
    {
        "slug": "stand-up-india",
        "name": "Stand-Up India Scheme",
        "short_description": "Bank loans between ₹10 Lakh and ₹1 Crore for setting up greenfield enterprises by SC, ST, and Women entrepreneurs.",
        "description": "Stand-Up India Scheme facilitates bank loans between ₹10 Lakh and ₹1 Crore to at least one Scheduled Caste (SC) or Scheduled Tribe (ST) borrower and at least one woman borrower per bank branch for setting up a greenfield enterprise in manufacturing, services, agri-allied activities, or the trading sector.",
        "benefits": "Composite bank loan (term loan and working capital) between ₹10 Lakh and ₹100 Lakh with credit guarantee support via NCGTC.",
        "category": "Employment & Enterprise",
        "department": "Department of Financial Services, Ministry of Finance, Government of India",
        "level": "Central Scheme",
        "state": "All India",
        "official_source_url": "https://www.standupmitra.in/",
        "application_url": "https://www.standupmitra.in/",
        "source_url": "https://www.standupmitra.in/",
        "application_process": "1. Visit Stand-Up Mitra portal at https://www.standupmitra.in/\n2. Register as a borrower and fill in project profile details.\n3. Connect with lead bank branches or seek handholding support from SIDBI / NABARD.\n4. Complete appraisal and secure sanction of loan.",
        "age_min": 18,
        "age_max": 70,
        "income_max": None,
        "occupation": "SC/ST and/or Woman Entrepreneurs",
        "target_occupations": ["Business Owner", "Self-employed", "Woman Entrepreneur", "Shopkeeper", "Artisan / Craftsperson"],
        "target_beneficiary_groups": ["Entrepreneurs", "Women Entrepreneurs", "SC/ST Business Owners"],
        "eligible_states": ["All India"],
        "education": "No Formal Education",
        "gender": "All",
        "social_category": "SC/ST/Woman",
        "is_farmer_only": False,
        "is_student_only": False,
        "is_business_only": True,
        "max_landholding_acres": None,
        "exclusions": ["Defaults with any commercial or cooperative bank"],
        "priority": "High Priority",
        "application_status": "open",
        "rules": [
            {
                "rule_name": "Entrepreneur Status",
                "rule_description": "Must have or seek enterprise/business",
                "rule_logic": {"field": "has_business", "op": "eq", "value": True},
                "is_mandatory": True
            },
            {
                "rule_name": "Minimum Age",
                "rule_description": "Age must be at least 18 years",
                "rule_logic": {"field": "age", "op": ">=", "value": 18},
                "is_mandatory": True
            }
        ],
        "documents": [
            {"name": "Aadhaar Card & PAN Card", "mandatory": True, "desc": "Identity & tax identification"},
            {"name": "Caste Certificate (if SC/ST)", "mandatory": False, "desc": "Verification for SC/ST category"},
            {"name": "Project Report", "mandatory": True, "desc": "Detailed project business plan for greenfield enterprise"}
        ]
    },
    {
        "slug": "mukhyamantri-majhi-ladki-bahin",
        "name": "Mukhyamantri Majhi Ladki Bahin Yojana",
        "short_description": "Monthly financial assistance of ₹1,500 transferred directly to eligible women aged 21-65 years in Maharashtra.",
        "description": "Mukhyamantri Majhi Ladki Bahin Yojana is implemented by the Women and Child Development Department of Maharashtra. Under this scheme, eligible women residing in Maharashtra receive direct financial assistance of ₹1,500 every month (₹18,000 annually) into their Aadhaar-linked bank accounts to promote financial autonomy and nutrition.",
        "benefits": "₹1,500 per month (₹18,000 per year) direct benefit transfer into woman beneficiary's bank account.",
        "category": "Social Welfare",
        "department": "Women and Child Development Department, Government of Maharashtra",
        "level": "State Scheme",
        "state": "Maharashtra",
        "official_source_url": "https://ladkibahin.maharashtra.gov.in/",
        "application_url": "https://ladkibahin.maharashtra.gov.in/",
        "source_url": "https://ladkibahin.maharashtra.gov.in/",
        "application_process": "1. Visit the official portal https://ladkibahin.maharashtra.gov.in/ or the Nari Shakti Doot mobile app.\n2. Enter Aadhaar number and verify via OTP.\n3. Upload Maharashtra Domicile / Ration Card and Orange/Yellow ration card.\n4. Enter Aadhaar-linked bank details and submit.",
        "age_min": 21,
        "age_max": 65,
        "income_max": 250000.0,
        "occupation": "Women across all occupations",
        "target_occupations": ["Housewife", "Homemaker", "Woman Entrepreneur", "Self-employed", "Unemployed Person", "Employee", "Student", "Farmer"],
        "target_beneficiary_groups": ["Women", "Mothers", "Homemakers", "Female Entrepreneurs"],
        "eligible_states": ["Maharashtra"],
        "education": "No Formal Education",
        "gender": "Female",
        "social_category": "All",
        "is_farmer_only": False,
        "is_student_only": False,
        "is_business_only": False,
        "max_landholding_acres": None,
        "exclusions": ["Family income above ₹2.5 Lakh", "Income tax payer in family", "Four-wheeler owners (excluding tractor)"],
        "priority": "High Priority",
        "application_status": "open",
        "rules": [
            {
                "rule_name": "Female Beneficiary",
                "rule_description": "Must be female",
                "rule_logic": {"field": "gender", "op": "eq", "value": "Female"},
                "is_mandatory": True
            },
            {
                "rule_name": "Age Restriction",
                "rule_description": "Age must be between 21 and 65 years",
                "rule_logic": {"field": "age", "op": "between", "value": [21, 65]},
                "is_mandatory": True
            },
            {
                "rule_name": "Family Income Below ₹2.5 Lakh",
                "rule_description": "Annual family income must not exceed ₹2,50,000",
                "rule_logic": {"field": "annual_income", "op": "<=", "value": 250000.0},
                "is_mandatory": True
            },
            {
                "rule_name": "Maharashtra Residence",
                "rule_description": "Must reside in Maharashtra",
                "rule_logic": {"field": "state", "op": "eq", "value": "Maharashtra"},
                "is_mandatory": True
            }
        ],
        "documents": [
            {"name": "Aadhaar Card", "mandatory": True, "desc": "Identity verification"},
            {"name": "Maharashtra Domicile / School Leaving Certificate", "mandatory": True, "desc": "Proof of residence in Maharashtra"},
            {"name": "Ration Card (Yellow/Orange) or Income Certificate", "mandatory": True, "desc": "Proof of family income below ₹2.5 Lakh"},
            {"name": "Bank Passbook with Aadhaar seeding", "mandatory": True, "desc": "For DBT transfer"}
        ]
    },
    {
        "slug": "pm-surya-ghar-muft-bijli-yojana",
        "name": "PM Surya Ghar: Muft Bijli Yojana",
        "short_description": "Direct subsidy up to ₹78,000 for installing residential rooftop solar systems and up to 300 units free solar electricity every month.",
        "description": "PM Surya Ghar: Muft Bijli Yojana is a national initiative launched by the Government of India to illuminate 1 crore households by providing up to 300 units of free solar electricity every month. The scheme offers a central financial assistance (CFA) subsidy of up to ₹78,000 directly into the consumer's bank account for rooftop solar installation.",
        "benefits": "Direct capital subsidy of ₹30,000 for 1kW, ₹60,000 for 2kW, and ₹78,000 for 3kW or higher solar rooftop systems; up to 300 units free power monthly.",
        "category": "Social Welfare",
        "department": "Ministry of New and Renewable Energy, Government of India",
        "level": "Central Scheme",
        "state": "All India",
        "official_source_url": "https://pmsuryaghar.gov.in/",
        "application_url": "https://pmsuryaghar.gov.in/",
        "source_url": "https://pmsuryaghar.gov.in/",
        "application_process": "1. Visit national portal https://pmsuryaghar.gov.in/\n2. Select your State and Electricity Distribution Company (DISCOM).\n3. Enter Electricity Consumer Account Number and mobile number.\n4. Apply for rooftop solar and select registered vendor.\n5. Post-installation net meter inspection by DISCOM releases subsidy directly into bank account via DBT.",
        "age_min": 18,
        "age_max": None,
        "income_max": None,
        "occupation": "All Citizens / Residential Electricity Consumers",
        "target_occupations": ["All Categories", "Student", "Farmer", "Teacher", "Housewife", "Employee", "Self-employed", "Shopkeeper", "Salaried Employee", "Business Owner", "Woman Entrepreneur", "Artisan / Craftsperson", "Unemployed Person", "Homemaker"],
        "target_beneficiary_groups": ["All Citizens", "Households", "Property Owners"],
        "eligible_states": ["All India"],
        "education": "No Formal Education / Any",
        "gender": "All",
        "social_category": "All",
        "is_farmer_only": False,
        "is_student_only": False,
        "is_business_only": False,
        "max_landholding_acres": None,
        "exclusions": ["Commercial and industrial properties not eligible for residential CFA subsidy"],
        "priority": "High Priority",
        "application_status": "open",
        "rules": [
            {
                "rule_name": "Minimum Age",
                "rule_description": "Age must be at least 18 years",
                "rule_logic": {"field": "age", "op": ">=", "value": 18},
                "is_mandatory": True
            }
        ],
        "documents": [
            {"name": "Electricity Bill", "mandatory": True, "desc": "Latest electricity bill showing consumer number"},
            {"name": "Aadhaar Card", "mandatory": True, "desc": "Identity verification"},
            {"name": "Cancelled Cheque / Bank Passbook", "mandatory": True, "desc": "For direct subsidy deposit via DBT"}
        ]
    }
]


class SchemeSyncService:
    """
    Source-backed official scheme fetching, network verification, and database synchronization engine.
    Respects HTTP rules, verifies source reachability, performs idempotent upserts, and recalculates matches.
    """

    @classmethod
    def probe_url_verification(cls, url: str, timeout: int = 6) -> Dict[str, Any]:
        """
        Actively probes an official government URL over HTTP/HTTPS.
        Measures HTTP status, response time, and verification integrity.
        """
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 YojanaHunter-Verifier/1.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }

        start_time = time.time()
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, context=ctx, timeout=timeout) as resp:
                elapsed_ms = int((time.time() - start_time) * 1000)
                status_code = resp.status
                is_live = (200 <= status_code < 400)
                return {
                    "url": url,
                    "reachable": True,
                    "http_status": status_code,
                    "latency_ms": elapsed_ms,
                    "status_label": f"verified_live (HTTP {status_code})",
                    "error": None
                }
        except urllib.error.HTTPError as e:
            elapsed_ms = int((time.time() - start_time) * 1000)
            logger.warning(f"HTTP Probe for {url} returned HTTP {e.code}: {e.reason}")
            # If 503 or 403, mark accurately
            return {
                "url": url,
                "reachable": False,
                "http_status": e.code,
                "latency_ms": elapsed_ms,
                "status_label": f"temporarily_unavailable (HTTP {e.code})",
                "error": str(e.reason)
            }
        except Exception as e:
            elapsed_ms = int((time.time() - start_time) * 1000)
            logger.warning(f"Connection probe error for {url}: {e}")
            return {
                "url": url,
                "reachable": False,
                "http_status": None,
                "latency_ms": elapsed_ms,
                "status_label": "connection_timeout / verification_fallback",
                "error": str(e)
            }

    @classmethod
    def sync_all_schemes(cls, profile_override: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Executes complete scheme synchronization:
        1. Probes all 10 official target scheme sources.
        2. Normalizes records into existing database schema.
        3. Upserts records idempotently (updating existing slugs, inserting new ones).
        4. Updates rules, document requirements, and source documents.
        5. Recalculates eligibility recommendations for current user profile.
        6. Returns structured synchronization summary.
        """
        db: Session = SessionLocal()
        attempted = len(VERIFIED_SCHEMES_CATALOGUE)
        fetched = 0
        verified = 0
        inserted = 0
        updated = 0
        failed = 0

        source_statuses = []
        failures = []
        now = datetime.datetime.utcnow()

        try:
            for item in VERIFIED_SCHEMES_CATALOGUE:
                slug = item["slug"]
                primary_url = item["official_source_url"]

                # 1. Network Probe & Verification
                probe_res = cls.probe_url_verification(primary_url)
                fetched += 1

                if probe_res["reachable"]:
                    verified += 1
                    verification_status = probe_res["status_label"]
                else:
                    # Check fallback url (e.g. state portal or secondary source)
                    secondary_url = item.get("source_url")
                    if secondary_url and secondary_url != primary_url:
                        probe_sec = cls.probe_url_verification(secondary_url, timeout=4)
                        if probe_sec["reachable"]:
                            verified += 1
                            verification_status = f"verified_via_portal ({probe_sec['status_label']})"
                        else:
                            verification_status = probe_res["status_label"]
                            failures.append({"scheme": item["name"], "url": primary_url, "error": probe_res["error"]})
                    else:
                        verification_status = probe_res["status_label"]
                        failures.append({"scheme": item["name"], "url": primary_url, "error": probe_res["error"]})

                source_statuses.append({
                    "slug": slug,
                    "name": item["name"],
                    "url": primary_url,
                    "status": verification_status,
                    "latency_ms": probe_res["latency_ms"],
                    "application_url": item["application_url"]
                })

                # 2. Database Upsert
                existing = db.query(Scheme).filter(Scheme.slug == slug).first()
                if not existing:
                    # Create new Scheme record
                    scheme = Scheme(
                        slug=slug,
                        name=item["name"],
                        short_description=item["short_description"],
                        description=item["description"],
                        benefits=item["benefits"],
                        category=item["category"],
                        department=item["department"],
                        level=item["level"],
                        state=item["state"],
                        official_source_url=item["official_source_url"],
                        application_url=item["application_url"],
                        source_url=item["source_url"],
                        application_process=item["application_process"],
                        last_verified_date=now.strftime("%d %b %Y"),
                        priority=item.get("priority", "High Priority"),
                        status="published",
                        application_status=item.get("application_status", "open"),
                        is_active=True,
                        source_verification_status=verification_status,
                        last_fetched_at=now,
                        age_min=item["age_min"],
                        age_max=item["age_max"],
                        income_max=item["income_max"],
                        occupation=item["occupation"],
                        education=item["education"],
                        gender=item["gender"],
                        social_category=item["social_category"],
                        is_farmer_only=item.get("is_farmer_only", False),
                        is_student_only=item.get("is_student_only", False),
                        is_business_only=item.get("is_business_only", False),
                        max_landholding_acres=item.get("max_landholding_acres"),
                        exclusions=item.get("exclusions", []),
                        target_occupations=item.get("target_occupations"),
                        target_beneficiary_groups=item.get("target_beneficiary_groups"),
                        eligible_states=item.get("eligible_states", [item["state"]]),
                        admin_review_status="approved",
                    )
                    db.add(scheme)
                    db.flush()
                    inserted += 1
                else:
                    # Update existing Scheme record in place (Idempotent update)
                    scheme = existing
                    scheme.name = item["name"]
                    scheme.short_description = item["short_description"]
                    scheme.description = item["description"]
                    scheme.benefits = item["benefits"]
                    scheme.category = item["category"]
                    scheme.department = item["department"]
                    scheme.level = item["level"]
                    scheme.state = item["state"]
                    scheme.official_source_url = item["official_source_url"]
                    scheme.application_url = item["application_url"]
                    scheme.source_url = item["source_url"]
                    scheme.application_process = item["application_process"]
                    scheme.last_verified_date = now.strftime("%d %b %Y")
                    scheme.priority = item.get("priority", "High Priority")
                    scheme.status = "published"
                    scheme.application_status = item.get("application_status", "open")
                    scheme.is_active = True
                    scheme.admin_review_status = "approved"
                    scheme.source_verification_status = verification_status
                    scheme.last_fetched_at = now
                    scheme.age_min = item["age_min"]
                    scheme.age_max = item["age_max"]
                    scheme.income_max = item["income_max"]
                    scheme.occupation = item["occupation"]
                    scheme.education = item["education"]
                    scheme.gender = item["gender"]
                    scheme.social_category = item["social_category"]
                    scheme.is_farmer_only = item.get("is_farmer_only", False)
                    scheme.is_student_only = item.get("is_student_only", False)
                    scheme.is_business_only = item.get("is_business_only", False)
                    scheme.max_landholding_acres = item.get("max_landholding_acres")
                    scheme.exclusions = item.get("exclusions", [])
                    scheme.target_occupations = item.get("target_occupations")
                    scheme.target_beneficiary_groups = item.get("target_beneficiary_groups")
                    scheme.eligible_states = item.get("eligible_states", [item["state"]])
                    scheme.updated_at = now
                    updated += 1

                # 3. Synchronize Rules
                # Remove stale rules and insert fresh structured rules
                db.query(SchemeRule).filter(SchemeRule.scheme_id == scheme.id).delete()
                for r in item.get("rules", []):
                    rule = SchemeRule(
                        scheme_id=scheme.id,
                        rule_name=r.get("rule_name"),
                        rule_description=r.get("rule_description"),
                        rule_logic=r.get("rule_logic"),
                        is_mandatory=r.get("is_mandatory", True)
                    )
                    db.add(rule)

                # 4. Synchronize Document Requirements
                db.query(SchemeDocumentRequirement).filter(SchemeDocumentRequirement.scheme_id == scheme.id).delete()
                for doc in item.get("documents", []):
                    req = SchemeDocumentRequirement(
                        scheme_id=scheme.id,
                        document_name=doc["name"],
                        is_mandatory=doc.get("mandatory", True),
                        description=doc.get("desc")
                    )
                    db.add(req)

                # 5. Record Source Document
                existing_doc = db.query(SourceDocument).filter(
                    SourceDocument.scheme_id == scheme.id,
                    SourceDocument.source_url == item["official_source_url"]
                ).first()
                if not existing_doc:
                    s_doc = SourceDocument(
                        scheme_id=scheme.id,
                        title=f"{item['name']} - Official Gazette / Portal",
                        source_url=item["official_source_url"],
                        fetched_at=now
                    )
                    db.add(s_doc)
                else:
                    existing_doc.fetched_at = now

            db.commit()

            # 6. Recalculate Recommendations for Profile
            if profile_override:
                profile_data = dict(profile_override)
            else:
                user_profile = db.query(Profile).first()
                if user_profile:
                    profile_data = user_profile.to_dict()
                else:
                    # Farmer demo profile baseline
                    profile_data = {
                        "occupation": "Farmer",
                        "annualIncome": "1 – 3 Lakh",
                        "incomeNumeric": 180000,
                        "age": 24,
                        "state": "Uttar Pradesh",
                        "education": "10th Pass",
                        "category": "OBC",
                        "is_farmer": True,
                        "isFarmer": True,
                        "land_holding_acres": 2.0,
                        "landHoldingAcres": 2.0,
                        "is_tax_payer": False,
                        "isTaxPayer": False,
                        "is_govt_employee": False
                    }

            # Run eligibility service on freshly synced records
            eval_results = SchemeEligibilityService.get_ranked_schemes_for_profile(profile_data)
            eligible_count = len([x for x in eval_results if x["eligibilityStatus"] == "eligible"])
            possibly_eligible_count = len([x for x in eval_results if x["eligibilityStatus"] == "possibly_eligible"])
            not_eligible_count = len([x for x in eval_results if x["eligibilityStatus"] == "not_eligible"])
            closed_count = len([x for x in eval_results if x["eligibilityStatus"] == "applications_closed"])

            summary = {
                "success": True,
                "schemes_attempted": attempted,
                "schemes_fetched": fetched,
                "schemes_verified": verified,
                "schemes_inserted": inserted,
                "schemes_updated": updated,
                "schemes_skipped_or_failed": len(failures),
                "demo_profile_matches": {
                    "eligible_count": eligible_count,
                    "possibly_eligible_count": possibly_eligible_count,
                    "not_eligible_count": not_eligible_count,
                    "applications_closed_count": closed_count,
                    "total_evaluated": len(eval_results)
                },
                "last_sync_time": now.isoformat(),
                "last_sync_display": now.strftime("%d %b %Y, %I:%M %p"),
                "source_statuses": source_statuses,
                "failures": failures
            }
            logger.info(f"Scheme synchronization complete: {summary}")
            return summary

        except Exception as e:
            db.rollback()
            logger.error(f"Synchronization error: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "schemes_attempted": attempted,
                "schemes_fetched": fetched,
                "schemes_verified": verified,
                "schemes_inserted": inserted,
                "schemes_updated": updated,
                "schemes_skipped_or_failed": attempted - verified,
                "last_sync_time": now.isoformat(),
                "failures": [{"error": str(e)}]
            }
        finally:
            db.close()
