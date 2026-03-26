Section 1 — Problem Statement
The concept first:
Imagine you're building Swiggy. You have 5 different backend services:

Order Service → needs to send "order confirmed" message
Payment Service → needs to send "payment received" message
Delivery Service → needs to send "rider picked up your order" message

If each service independently calls SendGrid, Twilio, Firebase on its own — you get this mess:
Order Service    ──→ SendGrid (email)
Payment Service  ──→ Twilio (SMS)
Delivery Service ──→ Firebase (push)
Auth Service     ──→ SendGrid (email)
Problems with this:

Code is duplicated across every service
No central place to track "was this notification delivered?"
If SendGrid changes their API, you update 5 services not 1
No rate limiting — you could spam a user accidentally

The solution is one dedicated Notification Service that every other service talks to:
Order Service    ──→
Payment Service  ──→  Notification Service  ──→ Email/SMS/Push
Delivery Service ──→
Now you understand WHY this service exists. Here's how to write it:
markdown
## 1. Problem Statement

Modern applications need to communicate with users across multiple 
channels — Email, SMS, and Push notifications. When multiple backend 
services (orders, payments, delivery) each implement their own 
notification logic, it leads to duplicated code, inconsistent delivery, 
and zero visibility into what was sent and when.

This Notification Service solves that by acting as a single, central 
system responsible for receiving notification requests, rendering 
templates, dispatching messages across channels, tracking delivery 
status, and handling failures with automatic retries.

Section 2 — Functional Requirements
The concept first:
Functional requirements answer: "What must this system DO?"
Think of it as a contract. If someone gives you money to build this, what exactly are they paying for? Be specific. Vague requirements = vague systems = failed interviews.
For our service, think through: what actions can a user/service perform? What must the system guarantee?
markdown
## 2. Functional Requirements

- Accept notification requests via REST API with a JSON payload
- Support 3 channels: Email, SMS, and Push notifications
- Support reusable templates with dynamic variable substitution
  (e.g. "Hello {{name}}, your order {{order_id}} is confirmed")
- Process notifications asynchronously — API returns immediately,
  sending happens in the background
- Track delivery status per notification:
  PENDING → QUEUED → SENT → DELIVERED / FAILED
- Automatically retry failed notifications up to 3 times
  with exponential backoff (1s, 10s, 60s)
- Rate limit notifications per user per channel
  (e.g. max 10 notifications/min per user)
- Move permanently failed notifications to a Dead Letter Queue (DLQ)
  for manual inspection
- Provide API endpoints to query notification status and history

Section 3 — Non-Functional Requirements
The concept first:
Non-functional requirements answer: "How well must the system perform?"
These are what separate a toy project from a production system. Every number here will be questioned in an interview — so understand where each number comes from.

10,000 notifications/minute — that's ~167/second. Realistic for a mid-size app like Razorpay or Zomato at peak hours. Kafka handles this easily.
< 200ms API response — the API just saves to DB and publishes to Kafka. It doesn't wait for the email to actually send. So 200ms is very achievable.
99.9% uptime — that's ~8.7 hours downtime per year. Standard SLA for internal services.

markdown

## 3. Non-Functional Requirements

- Throughput: Handle 10,000 notifications/minute at peak load
- API Latency: REST API must respond in under 200ms
  (async dispatch — does not wait for actual delivery)
- Availability: 99.9% uptime
- Durability: No notification should ever be silently dropped —
  every failure must be logged and retryable
- Scalability: Workers must be horizontally scalable
  (run multiple instances to handle more load)
- Observability: Every notification must be traceable end-to-end
  via status tracking and delivery logs

Section 4 — Out of Scope
The concept first:
This section is underrated. In interviews, saying "this is out of scope for v1" shows maturity. It tells the interviewer you understand that systems are built incrementally and you're not trying to boil the ocean.
It also protects you — if someone asks "what about user preferences?" you can say "deliberately out of scope, here's why."
markdown

## 4. Out of Scope (v1)

- User preference management (opt-outs, do-not-disturb hours)
- Multi-tenancy (serving multiple companies from one instance)
- Real-time WebSocket or in-app notifications
- A/B testing on notification templates
- Analytics dashboard for open rates / click rates
- Billing and usage metering
```

---

## Section 5 — High Level Architecture

**The concept first:**

This is the most important section. Draw the journey of a notification from the moment an API call comes in to the moment it reaches the user's phone/inbox.

Here's the journey step by step:
```
Step 1: Client calls POST /notifications
Step 2: FastAPI validates the request, saves to PostgreSQL as PENDING
Step 3: FastAPI publishes an event to Kafka topic (e.g. "notifications.email")
Step 4: FastAPI returns 202 Accepted immediately — job done for the API
Step 5: Email Worker is listening on Kafka topic "notifications.email"
Step 6: Worker picks up the event, renders the template, calls SendGrid
Step 7: Worker updates notification status in PostgreSQL to SENT or FAILED
Step 8: If FAILED, worker retries. After 3 failures → publishes to DLQ topic
Redis sits on the side handling two things:

Rate limiting — checking "has this user sent too many notifications?"
Template caching — so workers don't query PostgreSQL for the same template 1000 times

markdown

## 5. High-Level Architecture
```
                        ┌─────────────────────────────────┐
                        │         FastAPI Service          │
Client ──── HTTP ──────▶│  - Validates request             │
                        │  - Saves notification to DB      │
                        │  - Publishes event to Kafka      │
                        │  - Returns 202 Accepted          │
                        └────────────┬────────────────────┘
                                     │
                              ┌──────▼──────┐
                              │    Kafka     │
                              │   (Topics)   │
                              └──┬───┬───┬──┘
                                 │   │   │
                    ┌────────────┘   │   └────────────┐
                    ▼                ▼                 ▼
             ┌────────────┐  ┌────────────┐  ┌─────────────┐
             │Email Worker│  │ SMS Worker │  │ Push Worker │
             │ (SendGrid) │  │  (Twilio)  │  │   (FCM)     │
             └─────┬──────┘  └─────┬──────┘  └──────┬──────┘
                   │               │                 │
                   └───────────────┼─────────────────┘
                                   │
                          ┌────────▼────────┐
                          │   PostgreSQL     │
                          │ (update status)  │
                          └─────────────────┘

           Redis (used by both API and Workers)
           ├── Rate limiting (per user per channel)
           └── Template caching
```

Section 6 — API Design
The concept first:
API design is about defining the contract between your service and whoever calls it. Every endpoint needs: method, path, who calls it, and what it does.
The key design decision here is POST /notifications returns 202, not 200.

200 OK means "I did the thing"
202 Accepted means "I received your request and will do the thing"

Since we're async (the notification isn't sent yet when we respond), 202 is the correct and honest response code. Interviewers love this detail.
markdown

## 6. API Design

| Method | Endpoint                | Auth Required | Description                          |
|--------|-------------------------|---------------|--------------------------------------|
| POST   | /auth/register          | No            | Register a new user                  |
| POST   | /auth/login             | No            | Login, returns JWT access token      |
| POST   | /notifications          | Yes           | Submit a notification request        |
|        |                         |               | Returns 202 Accepted (async)         |
| GET    | /notifications/{id}     | Yes           | Get status of a specific notification|
| GET    | /notifications          | Yes           | List notifications (paginated)       |
| POST   | /templates              | Yes           | Create a reusable template           |
| GET    | /templates              | Yes           | List all templates                   |
| GET    | /templates/{id}         | Yes           | Get a specific template              |

### Sample Request — POST /notifications
{
    "template_id": "uuid-here",
    "channel": "email",
    "recipient": "user@example.com",
    "variables": {
        "name": "Pratham",
        "order_id": "ORD-12345"
    }
}

### Sample Response — 202 Accepted
{
    "notification_id": "uuid-here",
    "status": "PENDING",
    "message": "Notification queued for delivery"
}

Section 7 — Data Models
The concept first:
Data models define what gets stored in PostgreSQL. Think of each model as a table. Before writing code, you need to know: what tables exist, what columns they have, and how they relate to each other.
We have 4 tables:

users — who is authenticated to use this service
templates — reusable message templates
notifications — every notification request ever made
delivery_logs — every delivery attempt (for retry tracking)

markdown

## 7. Data Models

### users
| Column          | Type      | Notes                    |
|-----------------|-----------|--------------------------|
| id              | UUID (PK) | Primary key              |
| email           | VARCHAR   | Unique                   |
| hashed_password | VARCHAR   | bcrypt hashed            |
| is_active       | BOOLEAN   | Default true             |
| created_at      | TIMESTAMP | Auto set on creation     |

### templates
| Column     | Type      | Notes                              |
|------------|-----------|------------------------------------|
| id         | UUID (PK) | Primary key                        |
| name       | VARCHAR   | e.g. "order_confirmation"          |
| channel    | VARCHAR   | email / sms / push                 |
| subject    | VARCHAR   | Email subject (null for SMS/push)  |
| body       | TEXT      | Template with {{variable}} syntax  |
| created_at | TIMESTAMP | Auto set on creation               |

### notifications
| Column       | Type      | Notes                              |
|--------------|-----------|------------------------------------|
| id           | UUID (PK) | Primary key                        |
| user_id      | UUID (FK) | References users.id                |
| template_id  | UUID (FK) | References templates.id            |
| channel      | VARCHAR   | email / sms / push                 |
| recipient    | VARCHAR   | email address / phone / device token|
| status       | VARCHAR   | PENDING/QUEUED/SENT/DELIVERED/FAILED|
| variables    | JSONB     | {"name": "Pratham", "order": "123"}|
| idempotency_key | VARCHAR| Unique — prevents duplicate sends  |
| scheduled_at | TIMESTAMP | When to send (null = send now)     |
| sent_at      | TIMESTAMP | When actually sent                 |
| created_at   | TIMESTAMP | Auto set on creation               |

### delivery_logs
| Column          | Type      | Notes                         |
|-----------------|-----------|-------------------------------|
| id              | UUID (PK) | Primary key                   |
| notification_id | UUID (FK) | References notifications.id   |
| attempt_number  | INTEGER   | 1, 2, or 3                    |
| status          | VARCHAR   | SENT / FAILED                 |
| error_message   | TEXT      | Error detail if failed        |
| attempted_at    | TIMESTAMP | When this attempt was made    |

Section 8 — Key Design Decisions
The concept first:
This is the section interviewers drill into hardest. "Why Kafka and not RabbitMQ?" "Why PostgreSQL and not MongoDB?" "Why Redis for rate limiting?"
You must have a clear, confident answer for every choice. Here they are:
markdown

## 8. Key Design Decisions

### Why Kafka instead of RabbitMQ or Celery? 
Kafka gives us durability + replay. If a worker crashes mid-processing,
the message is not lost — Kafka retains it and the worker picks it up
again on restart. RabbitMQ deletes messages once consumed. Celery is
great for simple tasks but lacks Kafka's durability guarantees at scale.

### Why PostgreSQL instead of MongoDB?
Notifications and users are relational data — a notification belongs to
a user and references a template. PostgreSQL's ACID guarantees mean we
will never lose a notification record or create a duplicate. MongoDB's
flexible schema offers no advantage here and sacrifices consistency.

### Why Redis for rate limiting?
Redis INCR + EXPIRE is atomic — in a single operation we can increment
a counter and set its expiry. This gives us a fast, thread-safe sliding
window rate limiter with sub-millisecond latency. No other tool matches
this simplicity for rate limiting.

### Why async processing (Kafka workers)?
Sending an email via SendGrid or SMS via Twilio involves an HTTP call
to a third-party API that can take 100ms to 2000ms. Doing this
synchronously inside the API request would make our API slow and
fragile. Kafka workers decouple sending from accepting — the API always
responds in under 200ms regardless of third-party latency.

### Why idempotency keys?
If a client sends the same notification request twice (network retry,
bug), we must not send the user two emails. The idempotency_key field
is unique in the database — the second request will fail with a
duplicate key error, protecting the user from duplicates.

Section 9 — Delivery Status Flow
markdown

## 9. Delivery Status Flow

PENDING   — notification saved to DB, not yet published to Kafka
    ↓
QUEUED    — published to Kafka, worker has picked it up
    ↓
SENT      — third-party API (SendGrid/Twilio/FCM) accepted the request
    ↓
DELIVERED — third-party confirmed delivery (webhook callback)
    ↓
FAILED    — all 3 retry attempts exhausted → moved to DLQ

Section 10 — Tech Stack
markdown

## 10. Technology Stack

| Layer         | Technology           | Reason                                    |
|---------------|----------------------|-------------------------------------------|
| API           | FastAPI (Python)     | Async, fast, auto OpenAPI docs at /docs   |
| Database      | PostgreSQL           | ACID, relational, battle-tested           |
| Migrations    | Alembic              | Version-controlled DB schema changes      |
| Message Queue | Kafka                | Durable, high-throughput, replayable      |
| Cache         | Redis                | Rate limiting + template caching          |
| Auth          | JWT (python-jose)    | Stateless, industry standard              |
| Email         | SendGrid             | Reliable delivery, generous free tier     |
| SMS           | Twilio               | Industry standard for SMS                 |
| Push          | Firebase FCM         | Free, supports iOS + Android              |
| Containers    | Docker + Compose     | Consistent dev and prod environments      |
| Cloud         | AWS (EC2 + RDS)      | Industry standard, what companies use     |
| CI/CD         | GitHub Actions       | Free, integrated with GitHub              |

Section 11 — Folder Structure
markdown

## 11. Planned Folder Structure

notification-service/
├── app/
│   ├── api/
│   │   ├── routes/
│   │   │   ├── auth.py          # /auth/register, /auth/login
│   │   │   ├── notifications.py # /notifications endpoints
│   │   │   └── templates.py     # /templates endpoints
│   │   └── dependencies.py      # JWT auth dependency, DB session
│   ├── core/
│   │   ├── config.py            # All env variables (pydantic-settings)
│   │   ├── security.py          # Password hashing, JWT creation
│   │   └── database.py          # SQLAlchemy engine + session
│   ├── models/
│   │   └── models.py            # All SQLAlchemy table definitions
│   ├── schemas/
│   │   └── schemas.py           # All Pydantic request/response models
│   ├── services/
│   │   └── notification.py      # Business logic layer
│   ├── workers/
│   │   ├── email_worker.py      # Kafka consumer → SendGrid
│   │   ├── sms_worker.py        # Kafka consumer → Twilio
│   │   └── push_worker.py       # Kafka consumer → FCM
│   └── main.py                  # FastAPI app entry point
├── tests/
├── docker/
├── alembic/                     # DB migration files (auto-generated)
├── .env.example
├── .gitignore
├── docker-compose.yml
├── requirements.txt
└── DESIGN.md
