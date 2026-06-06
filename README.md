# DevLens

**An AI-powered developer evaluation and profiling system that automatically extracts and scores developer profiles from CVs.**

DevLens uses advanced LLM technology to intelligently parse CVs, extract comprehensive developer profiles, and provide multi-dimensional scoring across various competency areas. Perfect for technical recruiting, talent assessment, and developer profiling workflows.

## Features

- **🎯 Automated CV Parsing**: Extract structured developer information from PDF CVs using intelligent LLM-powered parsing
- **📊 Multi-Module Scoring**: Evaluate developers across multiple dimensions:
  - Technical Skills Assessment
  - Experience & Project Work
  - Education & Certifications
  - Engineering Practices
  - Role-Specific Fit
  - Code Quality & CV Quality Metrics
- **🔍 Role-Based Evaluation**: Tailor assessments for different developer roles (e.g., Full-Stack, Backend, Frontend, DevOps, etc.)
- **📈 Comprehensive Profiles**: Generate detailed developer profiles with structured data extraction
- **🔄 Pipeline Status Tracking**: Monitor CV processing progress through extraction and scoring phases
- **⚡ Powered by LangGraph**: Uses LangGraph workflows for robust, multi-step evaluation pipelines
- **🤖 Multiple LLM Providers**: Support for OpenAI and AWS LLMs for flexible deployment

## Project Structure

```
DevLens/
├── backend/                    # Python FastAPI backend
│   ├── app/
│   │   ├── main.py            # FastAPI application entry point
│   │   ├── config.py          # Configuration management
│   │   ├── routers/           # API endpoints
│   │   │   └── candidates.py  # CV upload & candidate endpoints
│   │   ├── services/          # Core business logic
│   │   │   ├── llm_client.py # LLM provider integration
│   │   │   ├── pdf_parser.py # PDF extraction
│   │   │   ├── extractor.py  # Profile extraction logic
│   │   │   └── pipeline.py    # Processing pipeline orchestration
│   │   └── schemas/           # Pydantic models
│   ├── developer/             # Developer evaluation module
│   │   ├── service.py         # Evaluation orchestration
│   │   ├── extraction.py      # Profile extraction
│   │   ├── models.py          # Developer profile data models
│   │   └── scoring/           # Scoring modules
│   │       ├── technical_skill.py
│   │       ├── experience.py
│   │       ├── education_certifications.py
│   │       ├── engineering_practices.py
│   │       ├── role_fit.py
│   │       └── aggregate.py   # Overall score aggregation
│   ├── storage/               # Persistent storage
│   │   ├── *.json            # Processed profiles & results
│   │   └── jobs/             # Job/role metadata
│   └── requirements.txt        # Python dependencies
├── frontend/                   # React.js frontend
│   ├── src/
│   │   ├── main.jsx          # React entry point
│   │   ├── styles.css        # Application styling
│   │   └── workspaceUtils.mjs # Utility functions
│   ├── package.json           # Node.js dependencies
│   └── index.html             # HTML template
├── stitch/                     # Design & UI resources
│   ├── DESIGN.md              # Design system documentation
│   └── code.html              # Design components
├── pr.ipynb                    # Jupyter notebook for analysis/prototyping
├── run_backend.ps1            # PowerShell script to start backend
└── README.md                   # This file
```

## Tech Stack

### Backend
- **Framework**: FastAPI (Python)
- **PDF Processing**: PyMuPDF
- **LLM Orchestration**: LangGraph
- **LLM Providers**: 
  - OpenAI (GPT models)
  - AWS (Bedrock)
- **Data Validation**: Pydantic
- **Server**: Uvicorn

### Frontend
- **Framework**: React 19
- **Build Tool**: Vite 7
- **UI Icons**: Lucide React
- **Language**: JavaScript/TypeScript

## Getting Started

### Prerequisites
- Python 3.10+
- Node.js 18+
- LLM API credentials (OpenAI and/or AWS)

### Backend Setup

1. **Install dependencies**:
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

2. **Configure environment variables** (create `.env` file):
   ```env
   OPENAI_API_KEY=your_openai_key
   AWS_ACCESS_KEY_ID=your_aws_key
   AWS_SECRET_ACCESS_KEY=your_aws_secret
   ```

3. **Start the backend**:
   ```bash
   # Using PowerShell
   .\run_backend.ps1
   
   # Or directly
   uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
   ```

The API will be available at `http://127.0.0.1:8000`

### Frontend Setup

1. **Install dependencies**:
   ```bash
   cd frontend
   npm install
   ```

2. **Start development server**:
   ```bash
   npm run dev
   ```

The application will be available at `http://127.0.0.1:5173`

## Deployment on Render

This repository is configured for a single Render Web Service on the free plan. The service uses Docker so the React frontend is built first, then FastAPI serves both the API and the compiled frontend from the same Render URL.

### Files used by Render

- `render.yaml` - Render Blueprint for a free Docker web service.
- `Dockerfile` - Multi-stage build for `frontend` and `backend`.
- `.dockerignore` - Keeps local secrets, virtualenvs, node modules, and runtime storage out of the Docker build context.

### Required Render environment variables

Set these in the Render Blueprint creation flow or in the Render dashboard:

```env
OPENROUTER_KEY=your_openrouter_api_key
OPENROUTER_MODEL=openai/gpt-4o-mini
OPENROUTER_API_BASE=https://openrouter.ai/api/v1
```

For Supabase-backed jobs and score persistence, also set:

```env
SUPABASE_URL=your_supabase_project_url
SUPABASE_SERVICE_ROLE_KEY=your_supabase_service_role_key
```

Optional cache:

```env
DEVLENS_REDIS_URL=your_render_key_value_or_redis_url
```

If you prefer AWS Bedrock instead of OpenRouter, add the normal AWS credentials and region variables in Render:

```env
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
AWS_REGION=us-east-1
BEDROCK_MODEL_ID=your_bedrock_model_id
```

### Deploy steps

1. Push this repo to GitHub. Do not commit `.env`.
2. In Render, choose **New > Blueprint** and connect the GitHub repository.
3. Render will detect `render.yaml`; choose the `free` instance type if prompted.
4. Enter the secret environment variable values when Render asks for them.
5. After deploy, open the Render service URL. The API health check is available at `/health`.

Render free web services spin down after idle time and use an ephemeral filesystem. Uploaded PDFs and JSON files stored locally can disappear after restarts, redeploys, or spin-downs, so use Supabase/Redis-backed persistence for anything you need to keep.

## API Endpoints

### Health & Debug
- `GET /health` - API health status
- `GET /debug/llm` - LLM provider status

### Candidates & CV Processing
- `GET /roles` - Available evaluation roles
- `POST /candidates/upload` - Upload CV (PDF)
  - Parameters: `file` (PDF), `target_role` (string)
  - Returns: `candidate_id` and initial pipeline status
- `GET /candidates/{candidate_id}/status` - Get processing status
- `GET /candidates/{candidate_id}/result` - Get evaluation results

## Usage Workflow

1. **Upload CV**: User uploads a PDF CV and selects a target role
2. **Extraction Phase**: Backend parses PDF and extracts structured developer profile using LLMs
3. **Scoring Phase**: Multi-module scoring agents evaluate the candidate across different dimensions
4. **Results**: Generate comprehensive score summary with module-level and overall grades
5. **Display**: Frontend presents the developer profile and scores

## Scoring Modules

The system evaluates developers across these modules:
- **Technical Skills**: Programming languages, frameworks, tools proficiency
- **Experience**: Years of experience, project complexity, role progression
- **Education**: Degrees, certifications, continuous learning
- **Engineering Practices**: Code quality awareness, testing, architecture knowledge
- **Role Fit**: Alignment with specific job role requirements
- **CV Quality**: Clarity, completeness, professionalism of CV presentation

Each module produces a score and contributes to the overall developer assessment.

## Development

### Running Tests
```bash
cd backend
pytest tests/
```

### Notebook Exploration
The `pr.ipynb` Jupyter notebook can be used for:
- Testing LLM integrations
- Analyzing extracted profiles
- Prototyping new scoring modules
- Data exploration

## Architecture Highlights

- **Asynchronous Processing**: CV processing runs in background tasks for better UX
- **LangGraph Workflows**: Robust, stateful multi-step evaluation pipelines
- **Modular Scoring**: Each scoring dimension is independently pluggable
- **Persistent Storage**: JSON-based storage for profiles and results
- **CORS-Enabled**: Frontend and backend can run independently

## Configuration

Key configuration files:
- `backend/app/config.py` - Application settings
- `backend/app/constants/roles.py` - Available evaluation roles
- `stitch/DESIGN.md` - UI design system

## Logging

Logs are configured at startup with:
- Format: `%(asctime)s %(levelname)s [%(name)s] %(message)s`
- Level: INFO (can be adjusted in code)

## Future Enhancements

Potential improvements:
- Database integration (replace JSON storage)
- Caching layer for LLM responses
- Batch processing for multiple CVs
- Advanced filtering and analytics dashboard
- Custom role templates
- A/B testing for scoring models

## License

[Add appropriate license]

## Contact

[Add contact information]
