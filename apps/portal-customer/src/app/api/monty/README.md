# Monty Copilot API

The Monty Copilot is an AI-powered sales assistant that provides contextual insights about individual leads directly within the customer portal.

## Features

- **Real AI Integration**: Uses OpenAI or Anthropic Claude for intelligent responses
- **Lead Context Injection**: Automatically fetches and injects relevant lead data into each conversation
- **Per-User Isolation**: Each user's chat history is completely isolated
- **Per-Lead Conversations**: Separate conversation history for each lead
- **Rate Limiting**: Configurable daily limits per user (default: 100 messages/day)
- **Full Security**: Authentication, authorization, and input sanitization

## API Endpoints

### POST `/api/monty/chat`

Send a message and receive an AI response with lead context.

**Request Body:**

```json
{
  "leadId": "uuid",
  "leadSource": "leads" | "staging_leads",
  "message": "What should I know about this lead?",
  "conversationHistory": [
    { "role": "user", "content": "Previous message" },
    { "role": "assistant", "content": "Previous response" }
  ]
}
```

**Response:**

```json
{
  "message": "AI response with lead insights...",
  "model": "gpt-4o-mini",
  "tokensUsed": 450,
  "rateLimit": {
    "remaining": 99,
    "limit": 100
  }
}
```

### GET `/api/monty/chat`

Fetch chat history for a specific lead.

**Query Parameters:**

- `leadId` (required): UUID of the lead
- `leadSource` (optional): "leads" or "staging_leads"
- `limit` (optional): Max messages to return (default: 50, max: 100)

**Response:**

```json
{
  "messages": [
    {
      "id": "uuid",
      "role": "user",
      "content": "Message content",
      "model": null,
      "created_at": "2025-02-04T15:00:00Z"
    }
  ]
}
```

## Environment Variables

### Required (at least one AI provider)

| Variable            | Description                  | Example       |
| ------------------- | ---------------------------- | ------------- |
| `OPENAI_API_KEY`    | OpenAI API key (preferred)   | `sk-proj-...` |
| `ANTHROPIC_API_KEY` | Anthropic API key (fallback) | `sk-ant-...`  |

### Optional

| Variable                 | Description               | Default                   |
| ------------------------ | ------------------------- | ------------------------- |
| `OPENAI_MODEL`           | OpenAI model to use       | `gpt-4o-mini`             |
| `ANTHROPIC_MODEL`        | Anthropic model to use    | `claude-3-haiku-20240307` |
| `MONTY_DAILY_RATE_LIMIT` | Messages per user per day | `100`                     |

### Required (already configured)

| Variable                        | Description               |
| ------------------------------- | ------------------------- |
| `NEXT_PUBLIC_SUPABASE_URL`      | Supabase project URL      |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase anonymous key    |
| `SUPABASE_SERVICE_ROLE_KEY`     | Supabase service role key |

## Database Schema

### `monty_chats` Table

Stores all chat messages with RLS for per-user isolation.

```sql
- id: UUID (primary key)
- user_id: UUID (references auth.users)
- client_id: UUID (references clients)
- lead_id: UUID
- lead_source: TEXT ('leads' or 'staging_leads')
- role: ENUM ('user', 'assistant', 'system')
- content: TEXT
- model: TEXT (e.g., 'gpt-4o-mini')
- tokens_used: INTEGER
- context_summary: TEXT
- created_at: TIMESTAMPTZ
```

### `monty_rate_limits` Table

Tracks daily usage per user.

```sql
- user_id: UUID (primary key)
- requests_today: INTEGER
- last_request_at: TIMESTAMPTZ
- daily_limit: INTEGER
- reset_at: TIMESTAMPTZ
```

## Security

1. **Authentication**: Validates Supabase session on every request
2. **Authorization**: Verifies lead belongs to user's client before allowing access
3. **Rate Limiting**: Enforces daily message limits to prevent abuse
4. **Input Sanitization**: Strips dangerous characters, limits message length
5. **RLS Policies**: Database-level enforcement of per-user isolation

## Setup

1. **Add environment variables** to `.env.local`:

   ```bash
   OPENAI_API_KEY=your-key-here
   # or
   ANTHROPIC_API_KEY=your-key-here
   ```

2. **Run the migration** to create the required tables:

   ```bash
   supabase db push
   ```

3. **Restart the development server** to pick up new env vars:
   ```bash
   npm run dev
   ```

## Lead Context

The AI receives context about each lead including:

- Name, email, company, job title
- Contact information (phone, location)
- Industry and company size
- Lead status and score
- Recent conversations (for qualified leads)
- Recent messages (for qualified leads)

This ensures Monty provides relevant, contextual advice for each specific lead.
