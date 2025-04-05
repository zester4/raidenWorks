# Raiden Agent

An autonomous web automation agent powered by LLMs.

## Overview

Raiden takes natural language instructions and executes them by controlling a web browser instance. It aims to be a robust, scalable, and secure tool for automating complex web tasks.

## Features (Planned)

*   Natural Language Understanding via Google Gemini
*   Robust browser control via Playwright
*   Session-based stateful execution
*   Vision-enhanced interaction (Optional)
*   Secure credential management
*   REST API for integration
*   Installable Python client library (`raiden-agent`)

## Setup & Installation

*(Instructions will be added here)*

## Usage

*(API usage and client library examples will be added here)*

## Development

*(Setup instructions for developers will be added here)*

## Architecture

*(Link to architecture diagram or description will be added here)*



raiden-agent/                     # Root directory of the project repository
│
├── raiden/                     # Main Python package source code (installable part eventually)
│   │
│   ├── api/                    # FastAPI application: Endpoints, request/response models
│   │   ├── __init__.py
│   │   ├── dependencies.py     # Common API dependencies (e.g., get_session_manager)
│   │   ├── endpoints/          # Directory for API route modules
│   │   │   ├── __init__.py
│   │   │   └── sessions.py     # Endpoints related to /sessions
│   │   ├── models/             # Pydantic models for API request/response data validation
│   │   │   ├── __init__.py
│   │   │   └── session_models.py
│   │   └── main.py             # FastAPI app factory and main entry point for the service
│   │
│   ├── browser/                # Browser Control Layer (BCL) - Playwright interactions
│   │   ├── __init__.py
│   │   ├── actions/            # Modules for specific browser actions
│   │   │   ├── __init__.py
│   │   │   ├── base_action.py  # Optional base class for actions
│   │   │   ├── click.py
│   │   │   ├── navigate.py
│   │   │   ├── type.py
│   │   │   ├── scroll.py
│   │   │   ├── extract.py
│   │   │   ├── screenshot.py
│   │   │   └── vision.py       # Placeholder for vision-based interactions
│   │   ├── driver.py           # Manages Playwright browser instances, contexts, pages
│   │   ├── exceptions.py       # Custom exceptions for browser operations
│   │   └── selectors.py        # Utilities for handling element selectors (CSS, XPath, etc.)
│   │
│   ├── core/                   # Core application logic, decoupled from API and Browser
│   │   ├── __init__.py
│   │   ├── config.py           # Pydantic-based settings management (loads from .env)
│   │   ├── constants.py        # Application-wide constants (e.g., Status strings)
│   │   ├── models/             # Core internal Pydantic data models
│   │   │   ├── __init__.py
│   │   │   └── internal_models.py # E.g., Plan, ActionStep, SessionState internal representation
│   │   ├── orchestration/      # Task execution orchestration logic
│   │   │   ├── __init__.py
│   │   │   └── orchestrator.py
│   │   ├── planning/           # Planning logic interacting with Gemini
│   │   │   ├── __init__.py
│   │   │   ├── llm_client.py   # Wrapper around Gemini API client
│   │   │   └── planner.py      # Constructs prompts, parses plans
│   │   └── session/            # Session state management
│   │       ├── __init__.py
│   │       ├── manager.py      # Interface for session CRUD operations
│   │       └── storage/        # Adapters for different storage backends
│   │           ├── __init__.py
│   │           ├── base_storage.py # Abstract base class
│   │           ├── redis_storage.py # Redis implementation
│   │           └── postgres_storage.py # Postgres implementation (for history)
│   │
│   ├── security/               # Security components (e.g., credential fetching)
│   │   ├── __init__.py
│   │   └── credential_manager.py # Interface to secure stores like Vault
│   │
│   └── utils/                  # Common utility functions and modules
│       ├── __init__.py
│       ├── logging_setup.py    # Centralized logging configuration
│       └── helpers.py          # Miscellaneous helper functions
│
├── tests/                      # Directory for automated tests
│   ├── __init__.py
│   ├── conftest.py             # Pytest fixtures
│   ├── unit/                   # Unit tests (testing components in isolation)
│   │   ├── __init__.py
│   │   ├── api/
│   │   ├── browser/
│   │   └── core/
│   ├── integration/            # Integration tests (testing component interactions)
│   │   ├── __init__.py
│   │   └── test_session_flow.py
│   └── e2e/                    # End-to-end tests (testing the full system via API)
│       ├── __init__.py
│       └── test_basic_tasks.py
│
├── docs/                       # Project documentation (Sphinx or MkDocs source)
│   ├── conf.py                 # Example Sphinx config
│   └── index.rst               # Example Sphinx index
│
├── .env.example                # Template for required environment variables
├── .gitignore                  # Standard Python gitignore
├── Dockerfile                  # To build the Raiden backend service container
├── docker-compose.yml          # For local development (runs service, Redis, Postgres)
├── pyproject.toml              # PEP 621: Project metadata, dependencies, build config
├── README.md                   # Project overview, setup, usage instructions
└── setup.py                    # Optional, can be useful for editable installs or complex builds alongside pyproject.toml


======================================

docker-compose up -d redis postgres