/**
 * Monty Copilot Chat API
 * 
 * POST /api/monty/chat
 * 
 * Provides AI-powered insights about a specific lead with:
 * - Full authentication & authorization
 * - Per-user rate limiting
 * - Lead context injection (only the specific lead's data)
 * - Chat history persistence
 * - Real LLM integration (OpenAI/Anthropic)
 */

import { NextRequest, NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';
import { createServerClient } from '@supabase/ssr';
import { cookies } from 'next/headers';

export const dynamic = 'force-dynamic';
export const maxDuration = 30; // 30 second timeout for LLM calls

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

interface ChatRequest {
  leadId: string;
  leadSource: 'leads' | 'staging_leads';
  message: string;
  conversationId?: string;
  conversationHistory?: { role: 'user' | 'assistant'; content: string }[];
}

interface LeadContext {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  company_name: string;
  job_title: string;
  phone_number?: string;
  location?: string;
  industry?: string;
  company_size?: string;
  website_url?: string;
  linkedin_url?: string;
  current_status?: string;
  lead_score?: number;
  qualification_status?: string;
  enrichment_status?: string;
  source?: string;
  created_at: string;
  conversations?: Array<{
    subject: string;
    summary: string;
    status: string;
    updated_at: string;
  }>;
  messages?: Array<{
    sender_type: string;
    text_content: string;
    sent_at: string;
  }>;
}

// ─────────────────────────────────────────────────────────────────────────────
// Configuration
// ─────────────────────────────────────────────────────────────────────────────

const DAILY_RATE_LIMIT = parseInt(process.env.MONTY_DAILY_RATE_LIMIT || '100', 10);
const MAX_MESSAGE_LENGTH = 2000;
const MAX_CONTEXT_MESSAGES = 10;

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────

function createAuthClient() {
  const cookieStore = cookies();
  return createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        get(name: string) {
          return cookieStore.get(name)?.value;
        },
        set() {},
        remove() {},
      },
    }
  );
}

function createServiceClient() {
  return createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SERVICE_ROLE_KEY!,
    { auth: { persistSession: false, autoRefreshToken: false } }
  );
}

function sanitizeInput(input: string): string {
  // Remove potential injection attempts and limit length
  return input
    .slice(0, MAX_MESSAGE_LENGTH)
    .replace(/[<>]/g, '') // Basic XSS prevention
    .trim();
}

async function checkRateLimit(supabase: any, userId: string): Promise<{ allowed: boolean; remaining: number }> {
  const now = new Date();
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const tomorrowStart = new Date(todayStart.getTime() + 24 * 60 * 60 * 1000);

  // Upsert rate limit record
  const { data: rateLimit, error } = await supabase
    .from('monty_rate_limits')
    .upsert({
      user_id: userId,
      requests_today: 1,
      last_request_at: now.toISOString(),
      daily_limit: DAILY_RATE_LIMIT,
      reset_at: tomorrowStart.toISOString(),
    }, {
      onConflict: 'user_id',
    })
    .select()
    .single();

  if (error) {
    // If upsert fails, try to get existing and increment
    const { data: existing } = await supabase
      .from('monty_rate_limits')
      .select('*')
      .eq('user_id', userId)
      .single();

    if (existing) {
      // Check if we need to reset (new day)
      const resetAt = new Date(existing.reset_at);
      if (now >= resetAt) {
        // Reset counter
        await supabase
          .from('monty_rate_limits')
          .update({
            requests_today: 1,
            last_request_at: now.toISOString(),
            reset_at: tomorrowStart.toISOString(),
          })
          .eq('user_id', userId);
        return { allowed: true, remaining: DAILY_RATE_LIMIT - 1 };
      }

      // Check if over limit
      if (existing.requests_today >= existing.daily_limit) {
        return { allowed: false, remaining: 0 };
      }

      // Increment counter
      await supabase
        .from('monty_rate_limits')
        .update({
          requests_today: existing.requests_today + 1,
          last_request_at: now.toISOString(),
        })
        .eq('user_id', userId);

      return { allowed: true, remaining: existing.daily_limit - existing.requests_today - 1 };
    }
  }

  return { allowed: true, remaining: DAILY_RATE_LIMIT - 1 };
}

async function getClientIdForUser(supabase: any, userId: string): Promise<string | null> {
  const { data, error } = await supabase
    .from('user_client_memberships')
    .select('client_id')
    .eq('user_id', userId)
    .limit(1);

  if (!error && data && data.length > 0) {
    return data[0].client_id;
  }

  // Dev-only fallback: if user has no membership, use DEV_CLIENT_ID_OVERRIDE
  const devOverride = process.env.DEV_CLIENT_ID_OVERRIDE;
  if (process.env.NODE_ENV !== 'production' && devOverride) {
    return devOverride;
  }

  return null;
}

async function verifyLeadAccess(
  serviceSupabase: any,
  leadId: string,
  leadSource: 'leads' | 'staging_leads',
  clientId: string
): Promise<boolean> {
  const table = leadSource === 'leads' ? 'leads' : 'staging_leads';
  const { data, error } = await serviceSupabase
    .from(table)
    .select('id')
    .eq('id', leadId)
    .eq('client_id', clientId)
    .maybeSingle();

  if (error) return false;
  return Boolean(data?.id);
}

async function fetchLeadContext(
  supabase: any,
  leadId: string,
  leadSource: 'leads' | 'staging_leads',
  clientId: string
): Promise<LeadContext | null> {
  if (leadSource === 'leads') {
    // Leads table: keep to known columns (avoid invalid select list)
    const { data: lead, error: leadError } = await supabase
      .from('leads')
      .select('id,email,first_name,last_name,company_name,job_title,phone_number,current_status,lead_score,qualification_status,created_at')
      .eq('id', leadId)
      .eq('client_id', clientId)
      .single();

    if (leadError || !lead) {
      return null;
    }

    const context: LeadContext = {
      id: lead.id,
      email: lead.email || 'Unknown',
      first_name: lead.first_name || 'Unknown',
      last_name: lead.last_name || '',
      company_name: lead.company_name || 'Unknown Company',
      job_title: lead.job_title || 'Unknown Role',
      phone_number: lead.phone_number,
      current_status: lead.current_status || lead.qualification_status,
      lead_score: lead.lead_score,
      qualification_status: lead.qualification_status,
      created_at: lead.created_at,
      conversations: [],
      messages: [],
    };

    const { data: conversations } = await supabase
      .from('conversations')
      .select('id, subject, summary, status, updated_at')
      .eq('lead_id', leadId)
      .order('updated_at', { ascending: false })
      .limit(5);

    if (conversations && conversations.length > 0) {
      context.conversations = conversations;

      const convIds = conversations.map((c: { id: string }) => c.id);
      const { data: messages } = await supabase
        .from('messages')
        .select('sender_type, text_content, sent_at')
        .in('conversation_id', convIds)
        .order('sent_at', { ascending: false })
        .limit(10);

      if (messages) {
        context.messages = messages;
      }
    }

    console.info('[Monty] lead context loaded', {
      leadId,
      leadSource,
      conversations: context.conversations?.length ?? 0,
      messages: context.messages?.length ?? 0,
    });

    return context;
  }

  // Staging leads
  const { data: stagingLead, error: stagingError } = await supabase
    .from('staging_leads')
    .select('id,email,first_name,last_name,company_name,job_title,phone_number,location,industry,company_size,website_url,linkedin_url,qualification_status,enrichment_status,source,created_at')
    .eq('id', leadId)
    .eq('client_id', clientId)
    .single();

  if (stagingError || !stagingLead) {
    return null;
  }

  const stagingContext: LeadContext = {
    id: stagingLead.id,
    email: stagingLead.email || 'Unknown',
    first_name: stagingLead.first_name || 'Unknown',
    last_name: stagingLead.last_name || '',
    company_name: stagingLead.company_name || 'Unknown Company',
    job_title: stagingLead.job_title || 'Unknown Role',
    phone_number: stagingLead.phone_number,
    location: stagingLead.location,
    industry: stagingLead.industry,
    company_size: stagingLead.company_size,
    website_url: stagingLead.website_url,
    linkedin_url: stagingLead.linkedin_url,
    current_status: stagingLead.qualification_status || 'staging',
    qualification_status: stagingLead.qualification_status,
    enrichment_status: stagingLead.enrichment_status,
    source: stagingLead.source,
    created_at: stagingLead.created_at,
    conversations: [],
    messages: [],
  };

  const { data: stagingConversations } = await supabase
    .from('staging_conversations')
    .select('id, subject, summary, status, updated_at')
    .eq('staging_lead_id', leadId)
    .order('updated_at', { ascending: false })
    .limit(5);

  if (stagingConversations && stagingConversations.length > 0) {
    stagingContext.conversations = stagingConversations;

    const stagingConvIds = stagingConversations.map((c: { id: string }) => c.id);
    const { data: stagingMessages } = await supabase
      .from('staging_messages')
      .select('sender_type, text_content, sent_at')
      .in('staging_conversation_id', stagingConvIds)
      .order('sent_at', { ascending: false })
      .limit(10);

    if (stagingMessages) {
      stagingContext.messages = stagingMessages;
    }
  }

  console.info('[Monty] lead context loaded', {
    leadId,
    leadSource,
    conversations: stagingContext.conversations?.length ?? 0,
    messages: stagingContext.messages?.length ?? 0,
  });

  return stagingContext;
}

function buildSystemPrompt(lead: LeadContext): string {
  const conversationsSummary = lead.conversations && lead.conversations.length > 0
    ? `\n\nRecent conversations:\n${lead.conversations.map(c =>
        `• "${c.subject}" (${c.status}): ${c.summary}`
      ).join('\n')}`
    : '';

  const messagesSummary = lead.messages && lead.messages.length > 0
    ? `\n\nRecent messages (paraphrased):\n${lead.messages.slice(0, 5).map(m =>
        `• ${m.sender_type === 'agent' ? 'You' : 'Prospect'}: ${m.text_content.slice(0, 180)}${m.text_content.length > 180 ? '…' : ''}`
      ).join('\n')}`
    : '';

  return `You are Monty — a friendly, sharp sales copilot who sits alongside the user in their leads dashboard.

Your job: help them understand the prospect they're looking at right now and figure out the smartest next move. Think of yourself as a trusted colleague who's read the notes, knows the context, and gives honest, practical advice without fluff.

HARD RULES (non-negotiable):
1. Only use information from the context below or the user's messages. If something isn't there, say "I don't have that info" — never guess or fill in blanks.
2. No jargon, no section labels like "**Signals**:" or "**Next step**:". Write like you're talking to a colleague over coffee — natural sentences and short paragraphs.
3. Never reveal internal system details (IDs, database names, policies, etc.).
4. Keep answers concise (60–150 words typical) unless the user asks for more depth.
5. Be warm but direct. Skip the hype, skip generic sales-speak. Every sentence should be useful.

WHAT YOU CAN DO:
• Summarize who this person is and where things stand.
• Point out signals that suggest interest (or hesitation) — but frame opinions as "it looks like…" or "based on…", never as certainties.
• Flag what you don't know yet and why it matters.
• Recommend one clear next action.
• Draft short, personalized outreach when asked.
• Offer general industry considerations if asked, but be upfront that you don't have live market data.

HOW TO SOUND (good example):
"Riley seems pretty engaged — they asked for a quick call, which is a good sign. That said, we don't know their timeline or budget yet, so I'd keep the next touch short: confirm a time for that call and ask one discovery question to learn more."

HOW NOT TO SOUND:
"**Engagement outlook (hypothesis)**: Positive — suggested a quick call. **Why (signals)**: - Positive reply…"

CONTEXT (this is all you know):

Lead: ${lead.first_name} ${lead.last_name}
Company: ${lead.company_name}
Role: ${lead.job_title}
${lead.email && lead.email !== 'Unknown' ? `Email: ${lead.email}` : ''}
${lead.phone_number ? `Phone: ${lead.phone_number}` : ''}
${lead.location ? `Location: ${lead.location}` : ''}
${lead.industry ? `Industry: ${lead.industry}` : ''}
${lead.company_size ? `Company size: ${lead.company_size}` : ''}
${lead.website_url ? `Website: ${lead.website_url}` : ''}
${lead.linkedin_url ? `LinkedIn: ${lead.linkedin_url}` : ''}

Current status: ${lead.current_status || 'Unknown'}
${typeof lead.lead_score === 'number' ? `Lead score: ${lead.lead_score}` : ''}
${lead.qualification_status ? `Qualification: ${lead.qualification_status}` : ''}
${lead.enrichment_status ? `Enrichment: ${lead.enrichment_status}` : ''}
${lead.source ? `Source: ${lead.source}` : ''}
Created: ${new Date(lead.created_at).toLocaleDateString()}
${conversationsSummary}${messagesSummary}

Remember: talk like a helpful colleague, not a template engine.`;
}
async function callLLM(
  systemPrompt: string,
  userMessage: string,
  conversationHistory: { role: 'user' | 'assistant'; content: string }[]
): Promise<{ content: string; model: string; tokensUsed?: number }> {
  // Try OpenAI first, fall back to Anthropic
  const openaiKey = process.env.OPENAI_API_KEY;
  const anthropicKey = process.env.ANTHROPIC_API_KEY;

  if (openaiKey) {
    return callOpenAI(openaiKey, systemPrompt, userMessage, conversationHistory);
  } else if (anthropicKey) {
    return callAnthropic(anthropicKey, systemPrompt, userMessage, conversationHistory);
  } else {
    throw new Error('No AI provider configured. Set OPENAI_API_KEY or ANTHROPIC_API_KEY.');
  }
}

async function callOpenAI(
  apiKey: string,
  systemPrompt: string,
  userMessage: string,
  conversationHistory: { role: 'user' | 'assistant'; content: string }[]
): Promise<{ content: string; model: string; tokensUsed?: number }> {
  const messages = [
    { role: 'system', content: systemPrompt },
    ...conversationHistory.slice(-MAX_CONTEXT_MESSAGES).map(m => ({
      role: m.role as 'user' | 'assistant',
      content: m.content,
    })),
    { role: 'user', content: userMessage },
  ];

  const response = await fetch('https://api.openai.com/v1/chat/completions', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${apiKey}`,
    },
    body: JSON.stringify({
      model: process.env.OPENAI_MODEL || 'gpt-4o-mini',
      messages,
      max_tokens: 1000,
      temperature: 0.4,
    }),
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`OpenAI API error: ${error}`);
  }

  const data = await response.json();
  return {
    content: data.choices[0]?.message?.content || 'I apologize, but I was unable to generate a response.',
    model: data.model,
    tokensUsed: data.usage?.total_tokens,
  };
}

async function callAnthropic(
  apiKey: string,
  systemPrompt: string,
  userMessage: string,
  conversationHistory: { role: 'user' | 'assistant'; content: string }[]
): Promise<{ content: string; model: string; tokensUsed?: number }> {
  const messages = [
    ...conversationHistory.slice(-MAX_CONTEXT_MESSAGES).map(m => ({
      role: m.role as 'user' | 'assistant',
      content: m.content,
    })),
    { role: 'user', content: userMessage },
  ];

  const response = await fetch('https://api.anthropic.com/v1/messages', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'x-api-key': apiKey,
      'anthropic-version': '2023-06-01',
    },
    body: JSON.stringify({
      model: process.env.ANTHROPIC_MODEL || 'claude-3-haiku-20240307',
      max_tokens: 1000,
      temperature: 0.4,
      system: systemPrompt,
      messages,
    }),
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`Anthropic API error: ${error}`);
  }

  const data = await response.json();
  const content = data.content?.[0]?.type === 'text' 
    ? data.content[0].text 
    : 'I apologize, but I was unable to generate a response.';

  return {
    content,
    model: data.model,
    tokensUsed: (data.usage?.input_tokens || 0) + (data.usage?.output_tokens || 0),
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// Main Handler
// ─────────────────────────────────────────────────────────────────────────────

export async function POST(req: NextRequest) {
  try {
    // 1. Authenticate user
    const authClient = createAuthClient();
    const { data: { user }, error: authError } = await authClient.auth.getUser();

    if (authError || !user) {
      return NextResponse.json(
        { error: 'Unauthorized. Please log in.' },
        { status: 401 }
      );
    }

    // 2. Parse and validate request body
    let body: ChatRequest;
    try {
      body = await req.json();
    } catch {
      return NextResponse.json(
        { error: 'Invalid JSON body' },
        { status: 400 }
      );
    }

    const { leadId, leadSource, message, conversationId, conversationHistory = [] } = body;

    if (!leadId || typeof leadId !== 'string') {
      return NextResponse.json(
        { error: 'Missing or invalid leadId' },
        { status: 400 }
      );
    }

    if (!leadSource || !['leads', 'staging_leads'].includes(leadSource)) {
      return NextResponse.json(
        { error: 'Invalid leadSource. Must be "leads" or "staging_leads"' },
        { status: 400 }
      );
    }

    if (!message || typeof message !== 'string' || message.trim().length === 0) {
      return NextResponse.json(
        { error: 'Message is required' },
        { status: 400 }
      );
    }

    const sanitizedMessage = sanitizeInput(message);
    if (sanitizedMessage.length === 0) {
      return NextResponse.json(
        { error: 'Message cannot be empty after sanitization' },
        { status: 400 }
      );
    }

    // 3. Resolve user's client_id (user-scoped; respects RLS)
    const clientId = await getClientIdForUser(authClient, user.id);
    if (!clientId) {
      return NextResponse.json(
        { error: 'User not associated with any client' },
        { status: 403 }
      );
    }

    // 4. Check rate limit (user-scoped; RLS enforced)
    const { allowed, remaining } = await checkRateLimit(authClient, user.id);
    
    if (!allowed) {
      return NextResponse.json(
        { error: 'Rate limit exceeded. Please try again tomorrow.', remaining: 0 },
        { status: 429 }
      );
    }

    // 5. Fetch lead context (service role for reads; authorization enforced by clientId filter)
    const leadClient = process.env.SUPABASE_SERVICE_ROLE_KEY ? createServiceClient() : authClient;
    const leadContext = await fetchLeadContext(leadClient, leadId, leadSource, clientId);

    if (!leadContext) {
      return NextResponse.json(
        { error: 'Lead not found or access denied' },
        { status: 404 }
      );
    }

    // 6b. Verify conversation is open and belongs to this user/lead
    if (conversationId && conversationId !== 'legacy') {
      try {
        const { data: conversation } = await authClient
          .from('monty_chat_conversations')
          .select('id, status')
          .eq('id', conversationId)
          .eq('user_id', user.id)
          .eq('client_id', clientId)
          .eq('lead_id', leadId)
          .eq('lead_source', leadSource)
          .maybeSingle();

        if (conversation && conversation.status !== 'open') {
          return NextResponse.json(
            { error: 'This conversation is closed. Start a new chat.' },
            { status: 409 }
          );
        }
      } catch (err) {
        console.warn('Monty conversation check skipped:', err);
      }
    }

    // 7. Build system prompt with lead context
    const systemPrompt = buildSystemPrompt(leadContext);

    // 8. Call LLM
    let llmResponse: { content: string; model: string; tokensUsed?: number };
    if (!process.env.OPENAI_API_KEY && !process.env.ANTHROPIC_API_KEY) {
      return NextResponse.json(
        { error: 'No AI provider configured. Set OPENAI_API_KEY or ANTHROPIC_API_KEY.' },
        { status: 500 }
      );
    }
    try {
      llmResponse = await callLLM(systemPrompt, sanitizedMessage, conversationHistory);
    } catch (llmError) {
      console.error('LLM error:', llmError);
      return NextResponse.json(
        { error: 'AI service temporarily unavailable. Please try again.' },
        { status: 503 }
      );
    }

    // 9. Store messages in database
    const contextSummary = `Lead: ${leadContext.first_name} ${leadContext.last_name} @ ${leadContext.company_name}`;
    
    // Store user message (user-scoped; prevents cross-user leaks even if API has a bug)
    await authClient.from('monty_chats').insert({
      user_id: user.id,
      client_id: clientId,
      lead_id: leadId,
      lead_source: leadSource,
      conversation_id: conversationId && conversationId !== 'legacy' ? conversationId : null,
      role: 'user',
      content: sanitizedMessage,
      context_summary: contextSummary,
    });

    // Store assistant response
    await authClient.from('monty_chats').insert({
      user_id: user.id,
      client_id: clientId,
      lead_id: leadId,
      lead_source: leadSource,
      conversation_id: conversationId && conversationId !== 'legacy' ? conversationId : null,
      role: 'assistant',
      content: llmResponse.content,
      model: llmResponse.model,
      tokens_used: llmResponse.tokensUsed,
      context_summary: contextSummary,
    });

    // 10. Return response
    return NextResponse.json({
      message: llmResponse.content,
      model: llmResponse.model,
      tokensUsed: llmResponse.tokensUsed,
      conversationId: conversationId ?? null,
      rateLimit: {
        remaining,
        limit: DAILY_RATE_LIMIT,
      },
    });

  } catch (error) {
    console.error('Monty chat error:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}

// GET endpoint to fetch chat history for a specific lead
export async function GET(req: NextRequest) {
  try {
    const authClient = createAuthClient();
    const { data: { user }, error: authError } = await authClient.auth.getUser();

    if (authError || !user) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }

    const url = new URL(req.url);
    const leadId = url.searchParams.get('leadId');
    const leadSource = url.searchParams.get('leadSource');
    const limit = parseInt(url.searchParams.get('limit') || '50', 10);
    const conversationId = url.searchParams.get('conversationId');

    if (!leadId) return NextResponse.json({ error: 'leadId is required' }, { status: 400 });
    if (!leadSource || !['leads', 'staging_leads'].includes(leadSource)) {
      return NextResponse.json({ error: 'leadSource is required (leads|staging_leads)' }, { status: 400 });
    }
    if (!conversationId) {
      return NextResponse.json({ error: 'conversationId is required' }, { status: 400 });
    }

    const clientId = await getClientIdForUser(authClient, user.id);
    if (!clientId) return NextResponse.json({ error: 'User not associated with any client' }, { status: 403 });

    // Verify the requested lead belongs to this client (prevents probing other tenants)
    const leadClient = process.env.SUPABASE_SERVICE_ROLE_KEY ? createServiceClient() : authClient;
    const canAccessLead = await verifyLeadAccess(leadClient, leadId, leadSource as 'leads' | 'staging_leads', clientId);
    if (!canAccessLead) {
      return NextResponse.json({ error: 'Lead not found or access denied' }, { status: 404 });
    }

    if (conversationId !== 'legacy') {
      const { data: conversation } = await authClient
        .from('monty_chat_conversations')
        .select('id')
        .eq('id', conversationId)
        .eq('user_id', user.id)
        .eq('client_id', clientId)
        .eq('lead_id', leadId)
        .eq('lead_source', leadSource)
        .maybeSingle();

      if (!conversation) {
        return NextResponse.json({ error: 'Conversation not found' }, { status: 404 });
      }
    }

    const baseQuery = authClient
      .from('monty_chats')
      .select('id, role, content, model, created_at')
      .eq('user_id', user.id)
      .eq('client_id', clientId)
      .eq('lead_id', leadId)
      .eq('lead_source', leadSource)
      .order('created_at', { ascending: true })
      .limit(Math.min(limit, 100));

    const { data: messages, error } = conversationId === 'legacy'
      ? await baseQuery.is('conversation_id', null)
      : await baseQuery.eq('conversation_id', conversationId);

    if (error) {
      console.error('Error fetching chat history:', error);
      return NextResponse.json({ error: 'Failed to fetch chat history' }, { status: 500 });
    }

    return NextResponse.json({ messages: messages || [] });

  } catch (error) {
    console.error('Get chat history error:', error);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
}
