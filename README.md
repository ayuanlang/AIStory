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

## KIE Data Import

KIE standard dictionary and mapping data are not loaded during deployment startup.
They are also excluded from system config sync import/export APIs.

Run the import manually when needed:

```bash
cd backend
python apply_kie_system_data_standard_seed.py
```

If configuration CSV files are uploaded first, load from uploaded file paths:

```bash
cd backend
python apply_kie_system_data_standard_seed.py \
   --dict-csv uploads/kie/_kie_system_data_standard_dictionary.csv \
   --map-csv uploads/kie/_kie_system_to_model_enum_mapping.csv
```

## Webhook Signature Verification

The backend supports HMAC verification for provider callbacks.

Relevant environment variables:

- `WEBHOOK_HMAC_KEY`: shared secret used to verify callback signatures.
- `WEBHOOK_HMAC_ALLOW_UNSIGNED`: whether callbacks without signature verification are accepted. Default is `1`.
- `WEBHOOK_TIMESTAMP_MAX_SKEW_SECONDS`: maximum allowed timestamp skew for signed callbacks. Default is `300`.

Recommended production configuration:

```bash
WEBHOOK_HMAC_KEY=replace-with-a-long-random-secret
WEBHOOK_HMAC_ALLOW_UNSIGNED=0
WEBHOOK_TIMESTAMP_MAX_SKEW_SECONDS=300
```

Current behavior if `WEBHOOK_HMAC_KEY` is empty:

- When `WEBHOOK_HMAC_ALLOW_UNSIGNED=1`, the server logs a warning and accepts unsigned callbacks.
- When `WEBHOOK_HMAC_ALLOW_UNSIGNED=0`, unsigned callbacks are rejected because no verification key is configured.

Signed callbacks are expected to include these headers:

- `x-webhook-timestamp`
- `x-webhook-signature`
