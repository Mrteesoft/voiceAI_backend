# FastAPI AI Assistant Backend MVP

This is a small Python + FastAPI backend that shows how to build the system around an existing AI model.

It demonstrates:

- an API layer with FastAPI
- persistent chat sessions with PostgreSQL
- a retrieval step that adds business context before model inference
- a pluggable model adapter you can swap for a real provider later
- a WebSocket endpoint for streaming responses in real time
- an asynchronous message queue for text and voice jobs
- persisted knowledge documents and chunks in PostgreSQL
- pgvector-backed embedding storage and semantic retrieval
- interaction pipeline runs and stage events for API, voice, retrieval, model, and business layers
- mock speech-to-text and text-to-speech adapters for audio-shaped voice requests
- request timing and logging for performance visibility
- paginated read paths and bounded model history windows
- a small pytest suite for core service behavior
- Prometheus metrics for scrape-based monitoring
- Grafana provisioning files and a starter dashboard
- OpenTelemetry tracing export over OTLP
- Sentry error and performance hooks
- ECS JSON logging for ELK/EFK shippers
- optional Datadog and New Relic agent bootstrap

## Request Flow

1. A client sends a message to `POST /api/v1/chat`
2. The backend creates or loads a chat session
3. The user message is stored in PostgreSQL
4. The interaction pipeline normalizes input, attaches platform metadata, and records stage events
5. A retrieval service searches `knowledge_chunks.embedding` with `pgvector` cosine distance and falls back to local lexical search if vector search is unavailable
6. A business-logic adapter decides which downstream integrations or workflows should be involved
7. A model adapter generates the assistant reply
8. For voice requests, a voice adapter prepares the reply for audio transport
9. The assistant reply and pipeline run are stored and returned to the client

## Project Layout

```text
app/
  api/routes/         # HTTP endpoints
  core/               # settings
  db/                 # database setup and ORM models
  schemas/            # request/response models
  services/           # chat orchestration, retrieval, queues, model adapter
  main.py             # FastAPI app entry point
requirements.txt
.env.example
```

## Run It

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload
```

Open the docs at `http://127.0.0.1:8000/docs`.

Each HTTP response also includes:

- `X-Request-ID`
- `X-Process-Time-Ms`

Metrics are exposed at `http://127.0.0.1:8000/metrics`.

## Example Requests

Create a new chat session:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/api/v1/chat `
  -ContentType application/json `
  -Body '{"user_id":"demo-user","message":"How would this backend support an AI assistant?"}'
```

Continue an existing session:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/api/v1/chat `
  -ContentType application/json `
  -Body '{"user_id":"demo-user","session_id":"REPLACE_SESSION_ID","message":"Add voice support next."}'
```

Fetch conversation history:

```powershell
Invoke-RestMethod `
  -Method Get `
  -Uri http://127.0.0.1:8000/api/v1/chat/REPLACE_SESSION_ID
```

Queue an asynchronous text job:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/api/v1/messages/jobs `
  -ContentType application/json `
  -Body '{"user_id":"demo-user","message":"Explain the async worker flow.","channel":"text"}'
```

Queue an asynchronous voice job:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/api/v1/messages/jobs `
  -ContentType application/json `
  -Body '{"user_id":"demo-user","message":"This is a voice transcript placeholder.","channel":"voice"}'
```

Add a knowledge document:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/api/v1/knowledge/documents `
  -ContentType application/json `
  -Body '{"title":"faq","content":"Use WebSockets for streaming tokens and a queue for transcription jobs.","source_type":"manual"}'
```

Run the full cross-platform interaction pipeline:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/api/v1/interactions `
  -ContentType application/json `
  -Body '{"user_id":"demo-user","message":"Schedule a payment reminder.","channel":"voice","platform":"ivr","metadata":{"locale":"en-NG"}}'
```

Run the interaction pipeline with inline audio input:

```powershell
$audio = [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes("Schedule a payment reminder for tomorrow morning."))
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/api/v1/interactions `
  -ContentType application/json `
  -Body "{`"user_id`":`"demo-user`",`"message`":`"`",`"channel`":`"voice`",`"platform`":`"web`",`"audio_input`":{`"audio_base64`":`"$audio`",`"audio_format`":`"wav`",`"sample_rate_hz`":16000}}"
```

Configure PostgreSQL and pgvector in `.env`:

```env
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/assistant_db
EMBEDDING_BACKEND=hash
EMBEDDING_DIMENSIONS=384
```

Search the persisted retrieval store:

```powershell
Invoke-RestMethod `
  -Method Get `
  -Uri "http://127.0.0.1:8000/api/v1/knowledge/search?query=streaming"
```

Stream over WebSocket:

```text
ws://127.0.0.1:8000/api/v1/ws/chat
```

Send JSON like:

```json
{
  "user_id": "demo-user",
  "message": "Explain streaming and async queues.",
  "channel": "text"
}
```

## What To Replace In A Real System

- swap the mock model adapter for OpenAI, Anthropic, Gemini, or a self-hosted model
- replace the local hash embedding generator with a real embedding model
- replace the in-process queue with Redis, RabbitMQ, Kafka, or a managed broker
- add auth, rate limiting, audio ingestion, and observability
- add migrations for schema evolution instead of relying only on startup `create_all`
- replace the demo voice adapter with real STT/TTS or a realtime multimodal model
- connect the business-logic adapter to your CRM, ticketing, billing, or scheduling systems

## Observability

- The app can emit to multiple observability backends, but they are env-toggled because running every vendor at once is usually for comparison or learning, not normal production practice.
- Prometheus: the app mounts `/metrics`; sample scrape config is in `observability/prometheus/prometheus.yml`.
- Grafana: datasource and dashboard provisioning files live under `observability/grafana/`.
- OpenTelemetry: set `OTEL_ENABLED=true` and point `OTEL_EXPORTER_OTLP_ENDPOINT` at your collector, for example `http://localhost:4318`.
- Sentry: set `SENTRY_ENABLED=true` and `SENTRY_DSN`.
- ELK/EFK: logs can be written to `./logs/app.log` in ECS JSON format and shipped using `observability/filebeat/filebeat.yml` or `observability/fluent-bit/fluent-bit.conf`.
- Datadog: set `DATADOG_ENABLED=true` and provide `DD_SERVICE`, `DD_ENV`, and `DD_VERSION`.
- New Relic: set `NEW_RELIC_ENABLED=true` and provide `NEW_RELIC_CONFIG_FILE` or the equivalent environment variables.

## Code Quality And Performance

- The app logs request duration and flags slow requests using `SLOW_REQUEST_THRESHOLD_MS`.
- Prometheus metrics track request count, request latency, in-progress requests, queue depth, async job status, and WebSocket events.
- Chat history passed to the model is capped with `MODEL_HISTORY_WINDOW_SIZE` so prompts do not grow forever.
- History, document listing, and retrieval search endpoints use bounded limits instead of unbounded reads.
- Composite indexes are defined for common access patterns in the message, queue, and knowledge tables.
- Interaction runs persist stage events so API, voice, retrieval, model, and business steps can be inspected after the request completes.
- Inline audio input is accepted as base64 for the demo pipeline; the current STT/TTS path is mocked so you can understand the backend shape before wiring a real provider.
- Run tests with `pytest`.

## pgvector Notes

- The app now expects PostgreSQL as the main database and stores embeddings in `knowledge_chunks.embedding`.
- On PostgreSQL startup, it runs `CREATE EXTENSION IF NOT EXISTS vector` before creating tables.
- The default embedding generator is a deterministic local hash embedder for learning purposes; replace it with a real embedding provider for production.
- If vector search is unavailable, retrieval falls back to the local lexical scorer so the demo still runs.
#   v o i c e A I _ b a c k e n d  
 