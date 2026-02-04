# AI Story

AI Story is an intelligent tool for film production, simplifying the process from script to storyboard using AI.

## Project Structure

- `backend/`: FastAPI backend service
- `frontend/`: React + Vite frontend application

## Getting Started

### Prerequisites

- Python 3.8+
- Node.js 16+

### Setup & Run

#### Backend (Terminal 1)

1. Navigate to the backend directory:
   ```bash
   cd backend
   ```
2. Install dependencies (if not already done):
   ```bash
   pip install -r requirements.txt
   ```
3. Run the server:
   ```bash
   python -m app.main
   ```
   The API will start at `http://localhost:8000`.

#### Frontend (Terminal 2)

1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```
2. Install dependencies (if not already done):
   ```bash
   npm install
   ```
3. Run the development server:
   ```bash
   npm run dev
   ```
   The application will be available at `http://localhost:5173`.
