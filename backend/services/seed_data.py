import logging
from database import SessionLocal
from models import (
    User, Profile, Scheme, SchemeRule, SchemeDocumentRequirement,
    UserDocument, Application
)

logger = logging.getLogger(__name__)

SCHEMES_DATA = [
    {
        "slug": "pm-vidyalakshmi",
        "name": "PM Vidyalakshmi Scheme",
        "short_description": "Education loan for higher studies",
        "description": "A single window electronic platform for students seeking education loans and scholarships. Covers course fees, living expenses, and tuition assistance for higher technical education.",
        "category": "Education",
        "department": "Ministry of Education",
        "level": "Central Scheme",
        "benefits": "Up to ₹6.5 Lakh",
        "official_source_url": "https://www.vidyalakshmi.co.in",
        "last_verified_date": "01 Oct 2026",
        "priority": "High Priority",
        "state": "All India",
        "rules": [
            {
                "rule_name": "Age Limit",
                "rule_description": "18 – 30 years",
                "rule_logic": {"field": "age", "op": "<=", "value": 30},
                "is_mandatory": True
            },
            {
                "rule_name": "Annual Family Income",
                "rule_description": "≤ 8 Lakh",
                "rule_logic": {"field": "annual_income", "op": "<=", "value": "8 Lakh"},
                "is_mandatory": True
            },
            {
                "rule_name": "Education",
                "rule_description": "12th Pass / Degree enrolled",
                "rule_logic": {"field": "education", "op": "in", "value": ["12th Pass", "Graduate", "B.E.", "Diploma", "B.Tech", "Degree"]},
                "is_mandatory": True
            },
            {
                "rule_name": "State / Nationality",
                "rule_description": "Indian Citizen (All States)",
                "rule_logic": {"field": "state", "op": "eq", "value": "All India"},
                "is_mandatory": True
            }
        ],
        "documents": ["Aadhaar Card", "Income Certificate", "Education Certificate", "Bank Passbook", "Photo"]
    },
    {
        "slug": "post-matric-scholarship",
        "name": "Post Matric Scholarship (State Govt.)",
        "short_description": "Financial support for students",
        "description": "Financial assistance provided by the Maharashtra Government to students studying in post-matriculation courses, covering tuition fee reimbursement and exam fees.",
        "category": "Education",
        "department": "Dept. of Higher & Technical Education",
        "level": "State Scheme",
        "benefits": "₹5,000 – ₹20,000",
        "official_source_url": "https://mahadbt.maharashtra.gov.in",
        "last_verified_date": "15 Sep 2026",
        "priority": "High Priority",
        "state": "Maharashtra",
        "rules": [
            {
                "rule_name": "Age Limit",
                "rule_description": "17 – 25 years",
                "rule_logic": {"field": "age", "op": "<=", "value": 25},
                "is_mandatory": True
            },
            {
                "rule_name": "Annual Family Income",
                "rule_description": "≤ 2.5 Lakh",
                "rule_logic": {"field": "annual_income", "op": "<=", "value": "2.5 Lakh"},
                "is_mandatory": True
            },
            {
                "rule_name": "Education",
                "rule_description": "Post-Matric / Degree",
                "rule_logic": {"field": "education", "op": "in", "value": ["Post-Matric", "Degree", "B.E.", "B.Tech", "Graduate"]},
                "is_mandatory": True
            },
            {
                "rule_name": "Domicile",
                "rule_description": "Maharashtra Resident",
                "rule_logic": {"field": "state", "op": "eq", "value": "Maharashtra"},
                "is_mandatory": True
            }
        ],
        "documents": ["Aadhaar Card", "Income Certificate", "Education Certificate", "Bank Passbook", "Photo"]
    },
    {
        "slug": "skill-india-training",
        "name": "Skill India — Training Program",
        "short_description": "Skill development & certification",
        "description": "Flagship scheme under PMKVY for skill development training, soft-skills enhancement, and NSQF accredited industry certification with placement support.",
        "category": "Skill Development",
        "department": "Ministry of Skill Development & Entrepreneurship",
        "level": "Central Scheme",
        "benefits": "Free Training + Certificate",
        "official_source_url": "https://www.skillindia.gov.in",
        "last_verified_date": "28 Sep 2026",
        "priority": "Medium Priority",
        "state": "All India",
        "rules": [
            {
                "rule_name": "Age Limit",
                "rule_description": "18 – 35 years",
                "rule_logic": {"field": "age", "op": "<=", "value": 35},
                "is_mandatory": True
            },
            {
                "rule_name": "Education",
                "rule_description": "10th / 12th Pass",
                "rule_logic": {"field": "education", "op": "in", "value": ["10th Pass", "12th Pass", "Graduate", "B.E."]},
                "is_mandatory": True
            },
            {
                "rule_name": "Training Center Enrollment",
                "rule_description": "Enrolled in Approved Center",
                "rule_logic": {"field": "training_enrolled", "op": "eq", "value": "true"},
                "is_mandatory": False
            }
        ],
        "documents": ["Aadhaar Card", "Education Certificate", "Photo"]
    },
    {
        "slug": "mjp-jan-arogya",
        "name": "Mahatma Jyotiba Phule Jan Arogya Yojana",
        "short_description": "Cashless health insurance coverage",
        "description": "Maharashtra state health insurance scheme offering up to ₹5 Lakh cashless coverage for identified medical procedures for low-income families.",
        "category": "Health",
        "department": "Govt. of Maharashtra",
        "level": "State Scheme",
        "benefits": "Up to ₹5 Lakh cashless treatment",
        "official_source_url": "https://www.jeevandayee.gov.in",
        "last_verified_date": "05 Oct 2026",
        "priority": "Medium Priority",
        "state": "Maharashtra",
        "rules": [
            {
                "rule_name": "Ration Card Category",
                "rule_description": "Yellow / Orange Ration Card or BPL",
                "rule_logic": {"field": "category", "op": "in", "value": ["BPL", "Antyodaya", "OBC", "SC", "ST"]},
                "is_mandatory": True
            },
            {
                "rule_name": "Domicile",
                "rule_description": "Maharashtra Resident",
                "rule_logic": {"field": "state", "op": "eq", "value": "Maharashtra"},
                "is_mandatory": True
            }
        ],
        "documents": ["Aadhaar Card", "Ration Card", "Income Certificate"]
    },
    {
        "slug": "naps-apprenticeship",
        "name": "National Apprenticeship Promotion Scheme (NAPS)",
        "short_description": "Industrial training stipend & job placement",
        "description": "Government-backed stipend sharing for graduate engineers and diploma holders in leading industrial establishments.",
        "category": "Employment",
        "department": "Ministry of Skill Development",
        "level": "Central Scheme",
        "benefits": "₹9,000 / month stipend",
        "official_source_url": "https://www.apprenticeshipindia.gov.in",
        "last_verified_date": "12 Oct 2026",
        "priority": "High Priority",
        "state": "All India",
        "rules": [
            {
                "rule_name": "Age Limit",
                "rule_description": "18 – 28 years",
                "rule_logic": {"field": "age", "op": "<=", "value": 28},
                "is_mandatory": True
            },
            {
                "rule_name": "Degree Qualification",
                "rule_description": "Diploma / Degree pursuing or completed",
                "rule_logic": {"field": "education", "op": "in", "value": ["Diploma", "Degree", "B.E.", "B.Tech", "Graduate"]},
                "is_mandatory": True
            }
        ],
        "documents": ["Aadhaar Card", "Education Certificate", "Bank Passbook"]
    },
    {
        "slug": "pm-internship-scheme",
        "name": "PM Internship Scheme in Top 500 Companies",
        "short_description": "12-month corporate internship with monthly allowance",
        "description": "Provides youth with valuable real-world business exposure in top Indian enterprises with financial support.",
        "category": "Employment",
        "department": "Ministry of Corporate Affairs",
        "level": "Central Scheme",
        "benefits": "₹5,000/mo + ₹6,000 one-time grant",
        "official_source_url": "https://pminternship.mca.gov.in",
        "last_verified_date": "10 Oct 2026",
        "priority": "High Priority",
        "state": "All India",
        "rules": [
            {
                "rule_name": "Age Limit",
                "rule_description": "21 – 24 years",
                "rule_logic": {"field": "age", "op": "<=", "value": 24},
                "is_mandatory": True
            },
            {
                "rule_name": "Family Income",
                "rule_description": "≤ 8 Lakh",
                "rule_logic": {"field": "annual_income", "op": "<=", "value": "8 Lakh"},
                "is_mandatory": True
            }
        ],
        "documents": ["Aadhaar Card", "Education Certificate", "Bank Passbook", "Photo"]
    },
    {
        "slug": "pm-vishwakarma",
        "name": "PM Vishwakarma Scheme",
        "short_description": "End-to-end support for traditional artisans & craftspeople",
        "description": "Collateral-free loans at concessional 5% interest rate, skill verification, modern toolkits incentive, and digital marketing support for 18 traditional trades.",
        "category": "Skill Development",
        "department": "Ministry of Micro, Small and Medium Enterprises",
        "level": "Central Scheme",
        "benefits": "Up to ₹3 Lakh collateral-free loan + ₹15,000 toolkit",
        "official_source_url": "https://pmvishwakarma.gov.in",
        "last_verified_date": "08 Oct 2026",
        "priority": "High Priority",
        "state": "All India",
        "rules": [
            {
                "rule_name": "Age Limit",
                "rule_description": "18 years and above",
                "rule_logic": {"field": "age", "op": ">=", "value": 18},
                "is_mandatory": True
            },
            {
                "rule_name": "Traditional Artisan / Trade",
                "rule_description": "Engaged in one of 18 traditional crafts",
                "rule_logic": {"field": "occupation", "op": "in", "value": ["Artisan", "Carpenter", "Blacksmith", "Mason", "Self-Employed"]},
                "is_mandatory": True
            }
        ],
        "documents": ["Aadhaar Card", "Trade Certificate", "Bank Passbook"]
    },
    {
        "slug": "stand-up-india",
        "name": "Stand-Up India Scheme",
        "short_description": "Bank loans for SC/ST and Women entrepreneurs",
        "description": "Facilitates bank loans between ₹10 Lakh and ₹1 Crore to at least one SC or ST borrower and at least one woman borrower per bank branch for setting up a greenfield enterprise.",
        "category": "Entrepreneurship",
        "department": "Ministry of Finance",
        "level": "Central Scheme",
        "benefits": "Bank loans ₹10 Lakh – ₹1 Crore",
        "official_source_url": "https://www.standupmitra.in",
        "last_verified_date": "10 Oct 2026",
        "priority": "Medium Priority",
        "state": "All India",
        "rules": [
            {
                "rule_name": "Category / Gender",
                "rule_description": "SC, ST, or Woman Entrepreneur",
                "rule_logic": {"field": "category", "op": "in", "value": ["SC", "ST", "Woman"]},
                "is_mandatory": True
            },
            {
                "rule_name": "Age Limit",
                "rule_description": "Above 18 years",
                "rule_logic": {"field": "age", "op": ">=", "value": 18},
                "is_mandatory": True
            }
        ],
        "documents": ["Aadhaar Card", "Caste Certificate", "Project Report", "Bank Passbook"]
    },
    {
        "slug": "adarsh-shikshak-puraskar-maharashtra",
        "name": "Maharashtra State Ideal Teacher Award (क्रांतिज्योती सावित्रीमाई फुले राज्य शिक्षक गुणगौरव पुरस्कार)",
        "short_description": "State cash award of ₹1,00,000, Gold Medal, and honor citation for meritorious school teachers in Maharashtra.",
        "description": "The Krantijyoti Savitrimai Phule State Teacher Award (Adarsh Shikshak Puraskar) is Maharashtra's premier state government honor administered by the School Education & Sports Department. Conferred annually on Teachers' Day (5th September), the scheme honors dedicated primary, secondary, higher secondary, and special teachers across Maharashtra for exemplary classroom pedagogy, innovative teaching learning material (TLM), girl child enrollment initiatives, and community engagement. Selected awardees receive a direct bank grant of ₹1,00,000, citation certificate, and service benefits.",
        "category": "Education",
        "department": "School Education and Sports Department, Government of Maharashtra (शालेय शिक्षण व क्रीडा विभाग, महाराष्ट्र)",
        "level": "State Scheme",
        "benefits": "₹1,00,000 direct cash prize, State Gold Medal, Certificate of Honor, and eligibility for state educational resource delegation",
        "official_source_url": "https://education.maharashtra.gov.in/",
        "application_url": "https://mahadbt.maharashtra.gov.in/",
        "source_url": "https://education.maharashtra.gov.in/",
        "last_verified_date": "15 Oct 2026",
        "priority": "High Priority",
        "state": "Maharashtra",
        "eligible_states": ["Maharashtra"],
        "occupation": "Teacher",
        "target_occupations": ["Teacher", "Educator", "Professor", "Faculty", "Instructor", "Lecturer", "Shikshak"],
        "target_beneficiary_groups": ["Teachers", "Educators", "School Faculty"],
        "age_min": 21,
        "age_max": 65,
        "education": "12th Pass / D.Ed / B.Ed / Graduate",
        "gender": "All",
        "social_category": "All",
        "application_process": "1. Eligible teachers submit nomination portfolios via MahaDBT / Shalarth portal (https://education.maharashtra.gov.in/).\n2. Portfolio includes self-appraisal, classroom innovations, student achievement metrics, and headmaster recommendation.\n3. District Selection Committee headed by CEO / Education Officer (Secondary) verifies records and shortlists candidates.\n4. State Level Scrutiny Committee finalizes awardees.\n5. Cash prize of ₹1,00,000 and gold medal presented on 5th September.",
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
        "documents": ["Aadhaar Card", "Teacher Service ID / Appointment Order", "Educational Degree Marksheet (B.Ed / D.Ed / Degree)", "Maharashtra Domicile Certificate", "Bank Passbook"]
    },
    {
        "slug": "national-award-to-teachers",
        "name": "National Award to Teachers (NAT) — Rashtriya Shikshak Puraskar",
        "short_description": "Prestigious national honor by Ministry of Education with ₹50,000 cash prize, Silver Medal, and President of India recognition.",
        "description": "The National Award to Teachers is the Government of India's highest national honor for educators, instituted by the Department of School Education and Literacy, Ministry of Education. The award recognizes outstanding classroom practitioners and institutional leaders who have demonstrated extraordinary commitment to improving educational access, promoting experiential learning under NEP 2020, and fostering creative pedagogy in government and aided schools across all States and UTs.",
        "category": "Education",
        "department": "Department of School Education & Literacy, Ministry of Education, Government of India",
        "level": "Central Scheme",
        "benefits": "₹50,000 cash grant, Silver Medal, Certificate of Merit, and travel/hospitality for award conferment by the Hon'ble President of India at Vigyan Bhawan, New Delhi",
        "official_source_url": "https://nationalawardstoteachers.education.gov.in/",
        "application_url": "https://nationalawardstoteachers.education.gov.in/",
        "source_url": "https://nationalawardstoteachers.education.gov.in/",
        "last_verified_date": "10 Oct 2026",
        "priority": "High Priority",
        "state": "All India",
        "eligible_states": ["All India", "Maharashtra"],
        "occupation": "Teacher",
        "target_occupations": ["Teacher", "Educator", "Professor", "Faculty", "Instructor", "Lecturer", "Shikshak"],
        "target_beneficiary_groups": ["Teachers", "Educators", "School Heads"],
        "age_min": 21,
        "age_max": 65,
        "education": "12th Pass / Graduate / B.Ed",
        "gender": "All",
        "social_category": "All",
        "application_process": "1. Register online directly on the National Award to Teachers portal (https://nationalawardstoteachers.education.gov.in/).\n2. Complete online self-nomination detailing ICT usage, student learning outcomes, and community mobilization.\n3. District Selection Committee (DSC) reviews applications and shortlists 3 top teachers per district.\n4. State Selection Committee (SSC) forwards nominations to National Jury.\n5. Independent National Jury evaluates video presentations and announces national awardees.",
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
        "documents": ["Aadhaar Card", "School Service Certificate & UDISE / Shalarth ID", "Pedagogy & Student Achievement Portfolio", "Bank Passbook"]
    },
    {
        "slug": "maharashtra-shikshak-kalyan-nidhi",
        "name": "Maharashtra Teachers Welfare Fund (महाराष्ट्र शिक्षक कल्याण निधी व आरोग्य सहाय्यता)",
        "short_description": "Up to ₹1,50,000 medical relief grant and higher education financial aid for teachers and their families in Maharashtra.",
        "description": "Administered by the Directorate of Education, Government of Maharashtra, the Teachers Welfare Fund (Shikshak Kalyan Nidhi) provides compassionate social security, critical medical assistance, and educational support grants for primary and secondary school teachers in Maharashtra. The fund offers direct financial assistance up to ₹1.5 Lakh for severe health ailments (cardiac surgery, cancer therapy, kidney disease, neurosurgery) and scholarships for teachers' children pursuing professional degree courses.",
        "category": "Social Welfare",
        "department": "Directorate of Education, Government of Maharashtra (शिक्षण संचलनालय, महाराष्ट्र राज्य)",
        "level": "State Scheme",
        "benefits": "Medical grant up to ₹1,50,000 for critical illness; Scholarship grant ₹10,000–₹25,000 for children of teachers; Ex-gratia emergency assistance",
        "official_source_url": "https://education.maharashtra.gov.in/",
        "application_url": "https://education.maharashtra.gov.in/",
        "source_url": "https://education.maharashtra.gov.in/",
        "last_verified_date": "12 Oct 2026",
        "priority": "High Priority",
        "state": "Maharashtra",
        "eligible_states": ["Maharashtra"],
        "occupation": "Teacher",
        "target_occupations": ["Teacher", "Educator", "Faculty", "Instructor", "Lecturer", "Shikshak"],
        "target_beneficiary_groups": ["Teachers", "Educators", "School Staff"],
        "age_min": 21,
        "age_max": 65,
        "education": "12th Pass / Graduate",
        "gender": "All",
        "social_category": "All",
        "application_process": "1. Download application form from the District Education Officer (Primary/Secondary) or visit https://education.maharashtra.gov.in/\n2. Submit medical treatment estimates / hospital bills or child college admission fee receipts.\n3. Headmaster / Principal countersigns application with teacher's Shalarth service code.\n4. District Welfare Committee sanctions relief and disburses grant directly via DBT into teacher's bank account.",
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
        "documents": ["Aadhaar Card", "Teacher Service Identity Card / Salary Certificate", "Medical Estimate / Hospital Bill or Child College Fee Receipt", "Bank Passbook"]
    },
    {
        "slug": "pm-nishtha-teacher-training",
        "name": "NISHTHA — National Initiative for Teachers' Holistic Advancement",
        "short_description": "Free nationwide digital & classroom pedagogy training, NCERT certification, and professional development grant on DIKSHA.",
        "description": "NISHTHA is a nationwide capacity building program under Samagra Shiksha, Ministry of Education, covering elementary and secondary school teachers, school heads, and academic resource persons. Delivered through interactive modules on the national DIKSHA platform, it equips educators with competency-based education techniques, toy-based pedagogy, inclusive education practices, student mental health support, and digital literacy. Enrolled teachers receive free access, government training allowances, and verified national micro-credentials.",
        "category": "Skill Development",
        "department": "Department of School Education & Literacy, Ministry of Education & NCERT",
        "level": "Central Scheme",
        "benefits": "Free standardized pedagogical certification, training allowance/stipend, verified NCERT digital certificates, and modern teaching-learning material access",
        "official_source_url": "https://diksha.gov.in/",
        "application_url": "https://itpd.ncert.gov.in/",
        "source_url": "https://diksha.gov.in/",
        "last_verified_date": "14 Oct 2026",
        "priority": "High Priority",
        "state": "All India",
        "eligible_states": ["All India", "Maharashtra"],
        "occupation": "Teacher",
        "target_occupations": ["Teacher", "Educator", "Professor", "Faculty", "Instructor", "Lecturer", "Tutor", "School Head"],
        "target_beneficiary_groups": ["Teachers", "Educators", "Instructors", "Pedagogy Professionals"],
        "age_min": 20,
        "age_max": 65,
        "education": "12th Pass / Graduate / D.Ed / B.Ed",
        "gender": "All",
        "social_category": "All",
        "application_process": "1. Visit DIKSHA portal (https://diksha.gov.in/) or download DIKSHA mobile app.\n2. Register as 'Teacher' and select State (Maharashtra) and District.\n3. Link teacher credentials using State Shalarth ID / UDISE+ school code.\n4. Complete interactive modules, formative assessments, and practical classroom assignments.\n5. Download verifiable digital certificate issued jointly by NCERT and State Council of Educational Research and Training (SCERT Maharashtra).",
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
        "documents": ["Aadhaar Card", "School Teacher ID / Appointment Letter", "Mobile Number linked to DIKSHA"]
    },
    {
        "slug": "pm-mmp-teachers-mission",
        "name": "Pandit Madan Mohan Malaviya National Mission on Teachers and Teaching (PMMMNMTT)",
        "short_description": "Fully sponsored Faculty Development Programs (FDP), capacity building, and research grants for educators.",
        "description": "The Pandit Madan Mohan Malaviya National Mission on Teachers and Teaching (PMMMNMTT) is an umbrella central sector scheme by the Ministry of Education. It aims to address issues relating to teachers, preparation of educators, recruitment, and professional growth across schools, colleges, and higher education institutions. The scheme sponsors Faculty Induction Programs (FIP), Short-term Training Courses (STC), curriculum workshops, and action research grants through Teaching Learning Centres (TLCs) and Malaviya Mission Teacher Training Centres (MMTTC).",
        "category": "Education",
        "department": "Department of Higher Education, Ministry of Education, Government of India",
        "level": "Central Scheme",
        "benefits": "100% sponsored training & accommodation; Research fellowship and contingency grants up to ₹2 Lakh for pedagogical projects; CAS score enhancement for career progression",
        "official_source_url": "https://nmtt.gov.in/",
        "application_url": "https://mmc.ugc.ac.in/",
        "source_url": "https://nmtt.gov.in/",
        "last_verified_date": "10 Oct 2026",
        "priority": "Medium Priority",
        "state": "All India",
        "eligible_states": ["All India", "Maharashtra"],
        "occupation": "Teacher",
        "target_occupations": ["Teacher", "Educator", "Professor", "Faculty", "Lecturer", "Instructor", "Research Scholar"],
        "target_beneficiary_groups": ["Teachers", "Educators", "College Faculty", "Lecturers"],
        "age_min": 21,
        "age_max": 65,
        "education": "Graduate / Post Graduate / B.Ed",
        "gender": "All",
        "social_category": "All",
        "application_process": "1. Visit the Malaviya Mission Teacher Training portal at https://mmc.ugc.ac.in/\n2. Register with institutional email and employment details.\n3. Browse accredited Faculty Development Programmes (FDP) offered by premier universities (such as Savitribai Phule Pune University, Mumbai University, IITs, Central Universities).\n4. Submit nomination approved by Head of Institution / Principal.\n5. Attend sponsored program and obtain UGC/AICTE recognized certification.",
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
        "documents": ["Aadhaar Card", "Teacher Service ID / Appointment Letter", "Highest Degree Certificate", "Bank Passbook"]
    },
    {
        "slug": "mukhyamantri-majhi-ladki-bahin",
        "name": "Mukhyamantri Majhi Ladki Bahin Yojana",
        "short_description": "Direct monthly financial allowance of ₹1,500 for eligible women in Maharashtra",
        "description": "Flagship Maharashtra State welfare scheme providing economic independence and nutritional support through ₹1,500 direct monthly bank transfers to married, widowed, divorced, abandoned, and destitute women aged 21-65.",
        "category": "Women & Child",
        "department": "Women and Child Development Department, Maharashtra",
        "level": "State Scheme",
        "benefits": "₹1,500 / month direct transfer (₹18,000/year)",
        "official_source_url": "https://ladkibahin.maharashtra.gov.in",
        "last_verified_date": "18 Oct 2026",
        "priority": "High Priority",
        "gender": "Female",
        "state": "Maharashtra",
        "eligible_states": ["Maharashtra"],
        "age_min": 21,
        "age_max": 65,
        "income_max": 250000.0,
        "rules": [
            {
                "rule_name": "Gender Eligibility",
                "rule_description": "Exclusively for Female / Women",
                "rule_logic": {"field": "gender", "op": "eq", "value": "Female"},
                "is_mandatory": True
            },
            {
                "rule_name": "Age Limit",
                "rule_description": "21 – 65 years",
                "rule_logic": {"field": "age", "op": "<=", "value": 65},
                "is_mandatory": True
            },
            {
                "rule_name": "State Domicile",
                "rule_description": "Resident of Maharashtra",
                "rule_logic": {"field": "state", "op": "eq", "value": "Maharashtra"},
                "is_mandatory": True
            },
            {
                "rule_name": "Family Income Limit",
                "rule_description": "Annual family income ≤ ₹2.5 Lakh",
                "rule_logic": {"field": "annual_income", "op": "<=", "value": "2.5 Lakh"},
                "is_mandatory": True
            }
        ],
        "documents": [
            "Aadhaar Card",
            "Maharashtra Domicile Certificate / Ration Card",
            "Income Certificate",
            "Bank Passbook",
            "Hamipatra (Affidavit)"
        ]
    }
]

DOCUMENTS_DATA = [
    {"doc_key": "doc-1", "name": "Aadhaar Card", "document_type": "Identity", "file_name": "aadhaar_card_masked.pdf", "file_size": "1.2 MB", "status": "uploaded", "required_for": ["PM Vidyalakshmi", "Post Matric Scholarship", "PM Vishwakarma"]},
    {"doc_key": "doc-2", "name": "Income Certificate", "document_type": "Income Proof", "file_name": "income_cert_2026.pdf", "file_size": "2.4 MB", "status": "uploaded", "required_for": ["PM Vidyalakshmi", "Post Matric Scholarship"]},
    {"doc_key": "doc-3", "name": "Degree / Education Marksheet", "document_type": "Academic", "file_name": "sem7_marksheet.pdf", "file_size": "3.1 MB", "status": "uploaded", "required_for": ["PM Vidyalakshmi", "PM Internship Scheme"]},
    {"doc_key": "doc-4", "name": "Domicile Certificate", "document_type": "Residence Proof", "file_name": "domicile_mh.pdf", "file_size": "1.8 MB", "status": "uploaded", "required_for": ["Post Matric Scholarship", "MJP Jan Arogya"]},
    {"doc_key": "doc-5", "name": "Bank Passbook", "document_type": "Financial", "file_name": "sbi_passbook.pdf", "file_size": "950 KB", "status": "uploaded", "required_for": ["PM Vidyalakshmi", "NAPS Scheme"]},
    {"doc_key": "doc-6", "name": "Passport Size Photograph", "document_type": "Photo", "file_name": "photo_white_bg.jpg", "file_size": "420 KB", "status": "uploaded", "required_for": ["All Schemes"]},
    {"doc_key": "doc-7", "name": "Caste Certificate", "document_type": "Category Proof", "file_name": None, "file_size": None, "status": "missing", "required_for": ["Stand-Up India", "Post Matric Scholarship"]},
    {"doc_key": "doc-8", "name": "Ration Card", "document_type": "Family Proof", "file_name": None, "file_size": None, "status": "missing", "required_for": ["MJP Jan Arogya"]}
]

def seed_database():
    """Seed initial user, schemes, documents, and application drafts."""
    db = SessionLocal()
    try:
        # 1. Seed or update demo user
        user = db.query(User).filter(User.email == "aditi.lagad@example.com").first()
        if not user:
            user = User(
                email="aditi.lagad@example.com",
                mobile="9876543210",
                password_hash="sha256$seededpasswordhash123",
                role="citizen",
                is_active=True
            )
            db.add(user)
            db.flush()

        # 2. Seed or update profile
        profile = db.query(Profile).filter(Profile.user_id == user.id).first()
        if not profile:
            profile = Profile(
                user_id=user.id,
                full_name="Aditi Lagad",
                age=21,
                gender="Female",
                occupation="Student",
                annual_income="< 1 Lakh",
                income_numeric=95000,
                education="B.E. (Final Year)",
                state="Maharashtra",
                district="Nashik",
                category="General",
                father_name="Santosh Lagad",
                date_of_birth="12-05-2005",
                preferred_language="en",
                completeness_percent=90
            )
            db.add(profile)
            db.flush()

        # 3. Seed Schemes
        for s_data in SCHEMES_DATA:
            scheme = db.query(Scheme).filter(Scheme.slug == s_data["slug"]).first()
            if not scheme:
                scheme = Scheme(
                    slug=s_data["slug"],
                    name=s_data["name"],
                    short_description=s_data["short_description"],
                    description=s_data["description"],
                    benefits=s_data["benefits"],
                    category=s_data["category"],
                    department=s_data["department"],
                    level=s_data["level"],
                    official_source_url=s_data["official_source_url"],
                    application_url=s_data.get("application_url", s_data["official_source_url"]),
                    source_url=s_data.get("source_url", s_data["official_source_url"]),
                    application_process=s_data.get("application_process"),
                    last_verified_date=s_data["last_verified_date"],
                    priority=s_data["priority"],
                    state=s_data["state"],
                    eligible_states=s_data.get("eligible_states", [s_data["state"]]),
                    occupation=s_data.get("occupation"),
                    target_occupations=s_data.get("target_occupations"),
                    target_beneficiary_groups=s_data.get("target_beneficiary_groups"),
                    age_min=s_data.get("age_min"),
                    age_max=s_data.get("age_max"),
                    income_max=s_data.get("income_max"),
                    education=s_data.get("education"),
                    gender=s_data.get("gender", "All"),
                    status="published",
                    admin_review_status="approved",
                    application_status=s_data.get("application_status", "open"),
                    is_active=True
                )
                db.add(scheme)
                db.flush()
            else:
                scheme.status = "published"
                scheme.admin_review_status = "approved"
                scheme.is_active = True
                if s_data.get("target_occupations"):
                    scheme.target_occupations = s_data["target_occupations"]
                if s_data.get("eligible_states"):
                    scheme.eligible_states = s_data["eligible_states"]
                if s_data.get("occupation"):
                    scheme.occupation = s_data["occupation"]
                if s_data.get("age_min") is not None:
                    scheme.age_min = s_data["age_min"]
                if s_data.get("age_max") is not None:
                    scheme.age_max = s_data["age_max"]
                if s_data.get("education"):
                    scheme.education = s_data["education"]
                if s_data.get("gender"):
                    scheme.gender = s_data["gender"]
                if s_data.get("application_process"):
                    scheme.application_process = s_data["application_process"]

            # Synchronize Rules
            db.query(SchemeRule).filter(SchemeRule.scheme_id == scheme.id).delete()
            for r in s_data["rules"]:
                rule = SchemeRule(
                    scheme_id=scheme.id,
                    rule_name=r["rule_name"],
                    rule_description=r["rule_description"],
                    rule_logic=r["rule_logic"],
                    is_mandatory=r["is_mandatory"]
                )
                db.add(rule)

            # Synchronize Required Documents
            db.query(SchemeDocumentRequirement).filter(SchemeDocumentRequirement.scheme_id == scheme.id).delete()
            for d in s_data["documents"]:
                doc_name = d["name"] if isinstance(d, dict) else d
                doc_req = SchemeDocumentRequirement(
                    scheme_id=scheme.id,
                    document_name=doc_name,
                    is_mandatory=True
                )
                db.add(doc_req)

        # 4. Seed User Documents
        for d_data in DOCUMENTS_DATA:
            existing_doc = db.query(UserDocument).filter(
                (UserDocument.user_id == user.id) & (UserDocument.doc_key == d_data["doc_key"])
            ).first()
            if not existing_doc:
                user_doc = UserDocument(
                    user_id=user.id,
                    doc_key=d_data["doc_key"],
                    name=d_data["name"],
                    document_type=d_data["document_type"],
                    file_name=d_data["file_name"],
                    file_size=d_data["file_size"],
                    status=d_data["status"],
                    required_for=d_data["required_for"],
                    is_verified=(d_data["status"] == "uploaded")
                )
                db.add(user_doc)

        # 5. Seed Demo Application
        app = db.query(Application).filter(Application.application_number == "DRAFT-2026-VL-8941").first()
        if not app:
            vl_scheme = db.query(Scheme).filter(Scheme.slug == "pm-vidyalakshmi").first()
            scheme_id = vl_scheme.id if vl_scheme else 1
            app = Application(
                application_number="DRAFT-2026-VL-8941",
                user_id=user.id,
                scheme_id=scheme_id,
                scheme_name="PM Vidyalakshmi Scheme",
                status="draft",
                applicant_name="Aditi Lagad",
                father_name="Santosh Lagad",
                date_of_birth="12-05-2005",
                education="B.E. (Final Year)",
                family_income="< 1 Lakh",
                state="Maharashtra",
                district="Nashik",
                description="Pre-filled official draft ready for download & submission."
            )
            db.add(app)

        db.commit()
        logger.info("Database seeding completed successfully.")
        return True
    except Exception as e:
        db.rollback()
        logger.error(f"Error seeding database: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()
