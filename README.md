# Yojana Hunter 🇮🇳

> **Beyond Searching Schemes, Getting Citizens the Benefits They Deserve**  
> An intelligent, full-stack platform for government scheme discovery, conversational eligibility matching, admin review, and citizen application assistance.

---

## 📌 Project Overview

**Yojana Hunter** is designed to connect Indian citizens (farmers, students, teachers, housewives, entrepreneurs, artisans, and disadvantaged groups) with the welfare schemes they legitimately qualify for.

Rather than relying on generic keyword searches or hallucination-prone chatbots, Yojana Hunter utilizes:
1. **Conversational Citizen Interviews**: Guided multi-lingual questionnaire capturing verified socioeconomic profile details.
2. **Deterministic Hybrid Rule Engine**: A dual-layered matching pipeline where structured eligibility criteria (age, annual income, state, occupation, education, caste category, land holding) are deterministically evaluated by the `RuleEngine` and `SchemeEligibilityService`, while Gemini AI generates human-friendly match explanations.
3. **AI-Powered Scheme Discovery**: Automated retrieval and extraction of new government schemes using Google Gemini (`gemini-2.5-flash` / `gemini-3.5-flash-lite`) with Google Search grounding.
4. **Admin Approval Gate**: Strict human-in-the-loop workflow where discovered schemes must be reviewed, verified for official portal URLs, and approved before surfacing to citizens.
5. **Dynamic Occupation Comparison**: Citizens can instantly simulate different careers (e.g., Farmer, Teacher, Student, Housewife, Doctor) to see matching schemes without modifying their saved database profile.
6. **Subscription Management**: Razorpay-integrated subscription plans with e-mandate support, webhooks, and administrative review.

---

## 🧱 Technology Stack

| Layer | Technology |
| :--- | :--- |
| **Frontend Framework** | [Next.js 14](https://nextjs.org/) (App Router, React 18, TypeScript) |
| **Styling & UI** | [Tailwind CSS 3](https://tailwindcss.com/), [Lucide React Icons](https://lucide.dev/) |
| **Backend Framework** | [Flask 3.x](https://flask.palletsprojects.com/) (Python 3.10+ / 3.13) |
| **Database & ORM** | [PostgreSQL 15+](https://www.postgresql.org/) via [SQLAlchemy 2.0](https://www.sqlalchemy.org/) & `psycopg` |
| **AI & LLM Services** | [Google Gen AI SDK](https://github.com/google-gemini/generative-ai-python) (`gemini-2.5-flash` / `gemini-3.5-flash-lite`) |
| **Payment Gateway** | [Razorpay](https://razorpay.com/) (Test Mode: Subscriptions, Orders, Webhook signatures) |
| **Authentication** | JWT (JSON Web Tokens), `bcrypt` password hashing, multi-tenant profile isolation |
| **Testing** | `pytest`, Python `unittest`, `requests` integration tests, TypeScript compiler (`tsc`) |

---

## 🗂️ Repository Structure

```
Yojana_Hunter_New/
├── .gitignore                   # Excludes secrets, local DB dumps, venv, and build artifacts
├── .env.example                 # Root configuration template for all environment variables
├── README.md                    # Project overview, setup instructions, and architecture guide
├── ARCHITECTURE.md              # Detailed architectural design and system workflows
├── PROJECT_REQUIREMENTS_DOCUMENT.md # Full product requirements specification
├── USER_STORIES.md              # User personas, acceptance criteria, and traceability
├── docker-compose.yml           # Container orchestration configuration
├── frontend/                    # Next.js 14 Single-Page Application
│   ├── .env.local.example       # Frontend environment template
│   ├── package.json             # Node dependencies and build scripts
│   ├── tsconfig.json            # TypeScript configuration
│   ├── tailwind.config.js       # Tailwind CSS theme and color tokens
│   ├── public/                  # Static assets and public images
│   └── src/
│       ├── app/                 # Next.js App Router (Citizen & Admin routes)
│       │   ├── page.tsx         # Landing page
│       │   ├── schemes/         # Schemes catalog & eligibility recommendation view
│       │   ├── profile/         # Citizen profile & family member manager
│       │   ├── interview/       # Conversational AI onboarding interview
│       │   └── admin/           # Admin portal (Discovery, Scheme Manager, Subscriptions)
│       ├── components/          # Reusable UI cards, headers, modals, filters
│       ├── services/            # API clients (schemes, profile, admin, subscriptions)
│       ├── context/             # React Context (AuthContext)
│       └── types/               # TypeScript interface definitions
├── backend/                     # Flask 3.x REST API Gateway
│   ├── .env.example             # Backend environment template
│   ├── requirements.txt         # Python dependencies
│   ├── app.py                   # Application factory, CORS setup, and entrypoint
│   ├── config.py                # Environment configuration loader
│   ├── database.py              # SQLAlchemy database engine and scoped session
│   ├── init_db.py               # Database initialization and seed runner
│   ├── models/                  # SQLAlchemy ORM entities (User, Profile, Scheme, Subscription)
│   ├── routes/                  # API Blueprints (/api/auth, /api/schemes, /api/admin, etc.)
│   ├── services/                # Core business logic:
│   │   ├── eligibility_service.py # Two-stage deterministic matching pipeline
│   │   ├── rule_engine.py       # Strict rule validator (age, income, state, occupation)
│   │   ├── gemini_service.py    # Search-grounded scheme discovery & explanations
│   │   ├── scheme_sync_service.py # Canonical government scheme synchronization
│   │   ├── portal_health_service.py # Official URL verification and latency checker
│   │   └── razorpay_service.py  # Razorpay order, subscription, and webhook verification
│   └── utils/                   # Authentication helpers, JWT decorators, activity logger
├── tests/                       # Automated test suites
│   ├── test_rule_engine.py      # Rule engine boundary tests
│   ├── test_smart_matching.py   # Scheme matching and ranking verification
│   ├── test_gemini_service.py   # Gemini API client, retries, and quota fallbacks
│   ├── test_personalized_filtering.py # Multi-persona demographic tests
│   └── test_portal_navigation_and_eligibility.py # URL verification and navigation tests
└── docs/                        # Additional architectural and API documentation
```

---

## ⚙️ Prerequisites

Before setting up the project locally, ensure you have:
- **Node.js**: `v18.17.0` or later (LTS recommended)
- **Python**: `3.10`, `3.11`, `3.12`, or `3.13`
- **PostgreSQL**: `15`, `16`, `17`, or `18` running locally or accessible via network
- **Git**: Installed and configured
- *(Optional)* **Google Gemini API Key**: From [Google AI Studio](https://aistudio.google.com/) for online scheme discovery
- *(Optional)* **Razorpay Test Keys**: From [Razorpay Dashboard](https://dashboard.razorpay.com/) for subscription testing

---

## 🚀 Getting Started

### 1. Database Setup (PostgreSQL)

Open PostgreSQL CLI (`psql`) or pgAdmin and create the database:

```sql
CREATE DATABASE yojana_hunter;
```

---

### 2. Backend Setup

1. **Navigate to the backend directory**:
   ```bash
   cd backend
   ```

2. **Create and activate a Python virtual environment**:
   - **Windows**:
     ```bash
     python -m venv .venv
     .venv\Scripts\activate
     ```
   - **Linux / macOS**:
     ```bash
     python3 -m venv .venv
     source .venv/bin/activate
     ```

3. **Install backend dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**:
   Copy the backend template:
   ```bash
   cp .env.example .env
   ```
   Edit `backend/.env` with your PostgreSQL password:
   ```env
   DATABASE_URL=postgresql+psycopg://postgres:your_password@localhost:5432/yojana_hunter
   SECRET_KEY=generate-a-secure-random-secret-key
   GEMINI_API_KEY=your_gemini_api_key_here
   ```

5. **Initialize and seed the database**:
   ```bash
   python init_db.py
   ```
   *This creates all tables (Users, Profiles, Schemes, Subscriptions, AuditLogs) and populates the database with verified government schemes (PM-KISAN, PM Vidyalakshmi, PM Surya Ghar, Ayushman Bharat, etc.).*

6. **Start the Flask backend server**:
   ```bash
   python app.py
   ```
   *The backend will start at `http://127.0.0.1:5000`.* Verify health at `http://127.0.0.1:5000/api/health`.

---

### 3. Frontend Setup

1. **Navigate to the frontend directory** (in a new terminal):
   ```bash
   cd frontend
   ```

2. **Install Node.js dependencies**:
   ```bash
   npm install
   ```

3. **Configure environment variables**:
   Copy the frontend template:
   ```bash
   cp .env.local.example .env.local
   ```
   Ensure `frontend/.env.local` points to your running backend:
   ```env
   NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:5000/api
   NEXT_PUBLIC_RAZORPAY_KEY_ID=rzp_test_your_key_id_here
   ```

4. **Start the Next.js development server**:
   ```bash
   npm run dev
   ```
   *The frontend will run at `http://localhost:3000`.*

---

## 🧪 Running Automated Tests

### 1. 10-Scenario End-to-End Persona Verification
Verifies personalized matching for Students, Farmers, Teachers, Housewives, Shopkeepers, High-Income Taxpayers, and dynamic career switches:
```bash
python backend/test_all_10_scenarios.py
```

### 2. Backend Pytest Suites
Run unit and integration test suites:
```bash
pytest tests/test_rule_engine.py
pytest tests/test_smart_matching.py
pytest tests/test_gemini_service.py
pytest tests/test_personalized_filtering.py
pytest tests/test_portal_navigation_and_eligibility.py
pytest tests/test_deduplication_and_approval_workflow.py
```

### 3. Frontend TypeScript & Build Validation
Verify that the frontend builds cleanly without TypeScript or routing errors:
```bash
cd frontend
npx tsc --noEmit
npm run build
```

---

## 🔐 Security & Data Protection Best Practices

- **Zero Secret Exposure**: `.gitignore` is strictly configured to prevent `.env`, `.env.local`, DB dumps, private keys, and user logs from ever being staged or committed.
- **Passwords**: Hashed with salt using standard `bcrypt` before storage.
- **Role-Based Access Control**: Separate permissions for `citizen` and `admin` roles, enforced via JWT middleware in `backend/utils/auth.py`.
- **Deterministic Safeguard**: Gemini AI can explain or recommend, but the deterministic `RuleEngine` acts as the single source of truth for qualification decisions.

---

## 📄 License & Compliance

Yojana Hunter is developed to assist citizens in accessing legitimate public benefits. All scheme citations link directly to verified official central and state government portals (`.gov.in` / `.nic.in`).
