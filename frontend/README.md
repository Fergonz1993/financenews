# Financial News Platform - React Frontend

This is the React-based frontend for the Financial News Analysis Platform. It provides a modern, responsive interface for viewing and analyzing financial news data.

## Features

- **Modern UI**: Clean, responsive interface using Material UI
- **Interactive Dashboard**: Data visualization with Chart.js
- **Article Management**: Browse, filter, and read detailed article summaries
- **Analytics**: View sentiment analysis, source distribution, and trending topics

## Directory Structure

```
frontend/
├── public/                 # Static files
├── src/                    # Source code
│   ├── api/                # API service layer
│   ├── components/         # Reusable UI components
│   └── pages/              # Page components
├── package.json            # Dependencies and scripts
└── README.md               # Documentation
```

## Prerequisites

- Node.js 16.x or higher
- npm 8.x or higher
- Backend API running (see instructions below)

## Installation

1. Install dependencies:
   ```bash
   cd frontend
   npm install
   ```

2. Start the development server:
   ```bash
   npm start
   ```

3. The app will be available at [http://localhost:3000](http://localhost:3000)

## Backend API Setup

The React frontend connects to a FastAPI backend. To run the backend:

1. From the project root directory, create a virtual environment (if not already done):
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install backend dependencies:
   ```bash
   pip install -e .
   ```

3. Start the FastAPI server:
   ```bash
   cd src/financial_news
   uvicorn api.main:app --reload --port 8000
   ```

4. The API will be available at [http://localhost:8000](http://localhost:8000)
   - API documentation: [http://localhost:8000/docs](http://localhost:8000/docs)

## Building for Production

To create a production build:

```bash
npm run build
```

This will create optimized files in the `build` directory that can be served by any static file server.

## Environment Variables

The following environment variables can be used to configure the frontend:

- `REACT_APP_API_URL`: The URL of the backend API (default: http://localhost:8000/api)

Create a `.env` file in the frontend directory to set these variables.
