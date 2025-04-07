# Raiden Agent

An autonomous web automation agent powered by LLMs.

## Overview

Raiden takes natural language instructions and executes them by controlling a web browser instance. It aims to be a robust, scalable, and secure tool for automating complex web tasks.

## Features

- 🧠 Natural Language Understanding via Google Gemini
- 🎭 Robust browser control via Playwright
- 🔄 Session-based stateful execution
- 👁️ Vision-enhanced interaction (Optional)
- 🔐 Secure credential management
- 🌐 REST API for integration
- 📦 Installable Python client library (`raiden-agent`)

## Installation

### Using pip

```bash
pip install raiden-agent
```

### From Source

```bash
git clone https://github.com/yourusername/raiden-agent.git
cd raiden-agent
pip install -e .
```

### Requirements

- Python 3.9 or higher
- PostgreSQL database
- Redis instance (for session management)
- Google Cloud project with Gemini API enabled

## Configuration

1. Create a `.env` file based on `.env.example`:

```env
# Database
POSTGRES_DSN=postgresql+asyncpg://user:password@localhost:5432/raiden

# Redis (Session Cache)
REDIS_DSN=redis://localhost:6379/0

# Google Cloud / Gemini
GEMINI_API_KEY=your_api_key
GEMINI_PROJECT_ID=your_project_id
GEMINI_LOCATION=us-central1  # or your preferred region

# API Security
ALLOWED_ORIGINS=http://localhost:3000,https://yourdomain.com
```

2. Install browser dependencies:
```bash
playwright install
playwright install-deps
```

3. Run database migrations:
```bash
alembic upgrade head
```

## Usage

### Starting the Server

```bash
uvicorn raiden.api.main:app --host 0.0.0.0 --port 8000
```

### Using Docker Compose

```bash
docker-compose up -d
```

### API Examples

1. Create a new automation session:
```python
import httpx

async with httpx.AsyncClient() as client:
    response = await client.post(
        "http://localhost:8000/sessions",
        json={
            "user_prompt": "Search for 'Python web automation' on Google",
            "session_config": {
                "headless": True,
                "use_vision": False
            }
        }
    )
    session_id = response.json()["session_id"]
```

2. Check session status:
```python
status_response = await client.get(f"http://localhost:8000/sessions/{session_id}")
```

3. Provide user input when requested:
```python
await client.post(
    f"http://localhost:8000/sessions/{session_id}/respond",
    json={"user_response": "Click the third search result"}
)
```

## Development

### Setting Up Development Environment

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
```

2. Install development dependencies:
```bash
pip install -e ".[dev]"
```

3. Set up pre-commit hooks:
```bash
pre-commit install
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=raiden

# Run specific test types
pytest tests/unit
pytest tests/integration
pytest tests/e2e
```

## Architecture

The Raiden Agent follows a modular architecture with these key components:

1. **API Layer** (`raiden.api`)
   - FastAPI application handling HTTP requests
   - Request/response validation
   - Session management endpoints

2. **Browser Control Layer** (`raiden.browser`)
   - Playwright integration
   - Action implementations (click, type, navigate, etc.)
   - Robust retry mechanisms

3. **Core Logic** (`raiden.core`)
   - Task planning and orchestration
   - Session state management
   - Configuration handling

4. **Storage** (`raiden.core.session.storage`)
   - Redis for active session cache
   - PostgreSQL for session history

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and linting
5. Submit a pull request

## License

MIT License - see LICENSE file for details

## Project Status

- [x] Core functionality
- [x] Basic browser actions
- [x] Session management
- [x] Database integration
- [x] API endpoints
- [ ] Advanced vision features
- [ ] Complete test coverage
- [ ] Production deployment guides

## Support

- Documentation: [Link to docs when available]
- Issue Tracker: [GitHub Issues]
- Discord: [Link when available]
