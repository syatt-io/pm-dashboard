# Plan: Build AI-Powered Slack Chat App with Context Search

**Date:** 2025-10-12
**Status:** Planning Phase

## Feasibility Assessment: **HIGHLY FEASIBLE** ✅

Your application already has **90% of the infrastructure** needed for this feature:

### What You Already Have
1. **Context Search Service** - Fully functional semantic search across Slack, Fireflies, Jira, GitHub, and Notion (`src/services/context_search.py`)
2. **Slack Integration** - Working SlackTodoBot using Slack Bolt framework with existing `/find-context` command (`src/managers/slack_bot.py`)
3. **AI Integration** - OpenAI GPT-4 for generating responses with citations
4. **Vector Database** - Pinecone for semantic search with BM25 ranking
5. **User Authentication** - Slack user to app user mapping with permission filtering

### What Needs to be Built (3 Main Components)

---

## Component 1: Conversational Chat Handler
**Effort: Small (~4 hours)**

### Create New Message Listener
- Add `@app.event("app_mention")` handler in `SlackTodoBot` for when users @mention the bot
- Add direct message handler for DM conversations with the bot
- Parse natural language questions and extract intent

### Key Features
- Detect when user is asking a question vs. issuing a command
- Extract query parameters (timeframe, project filter) from natural language
- Handle follow-up questions using conversation context

**Files to modify:**
- `src/managers/slack_bot.py` - Add new event handlers

---

## Component 2: Streaming AI Response System
**Effort: Medium (~6 hours)**

### Implementation Approach
1. **Retrieve context** using existing `ContextSearchService.search()`
2. **Stream AI response** to Slack using OpenAI streaming API
3. **Update message in real-time** as AI generates response (Slack doesn't support true streaming, so use edit message API)

### Response Format (Slack Blocks)
```
🤖 [Question]
[AI-generated answer with inline citations]

📚 Sources (3 citations)
[1] Slack: #channel-name - 2025-10-10
[2] Jira: PROJ-123 - Issue title
[3] Fireflies: Meeting Name - 2025-10-09
```

**Files to create:**
- `src/services/slack_chat_service.py` - New service for chat interactions

**Files to modify:**
- `src/services/context_search.py` - Add optimizations for chat mode (brief responses)
- `src/services/context_summarizer.py` - Add "chat" detail level

---

## Component 3: Conversation State Management
**Effort: Small (~3 hours)**

### Session Management
- Reuse existing Redis/database session storage (already used for `/find-context` buttons)
- Store conversation history (last 5 messages) for context-aware follow-ups
- Implement conversation timeout (15 minutes)

### Follow-up Question Support
```
User: "Tell me about authentication changes"
Bot: [Response with citations]

User: "Who worked on this?"
Bot: [Uses previous context to know "this" = authentication]
```

**Files to modify:**
- `src/utils/db_session.py` - Extend session storage for conversation state

---

## Technical Architecture

### Data Flow
```
User Question (Slack)
    ↓
Slack Event Handler
    ↓
Parse Intent & Extract Parameters
    ↓
ContextSearchService.search()
    ├─ Vector Search (Pinecone)
    ├─ Keyword Matching
    └─ Project Filtering
    ↓
OpenAI GPT-4 (streaming)
    ├─ Generate Answer
    └─ Include Citations
    ↓
Format Slack Blocks
    ↓
Post/Update Message in Slack
```

### Integration with Existing Features

**Reuse /find-context Infrastructure:**
- Same search service
- Same session storage
- Same interactive buttons (Show Sources, Expand Search)
- Same permission filtering

**New Capabilities:**
- Natural language queries (no slash command needed)
- Conversational context (follow-up questions)
- Real-time streaming responses
- DM support (private queries)

---

## Implementation Plan (13 hours total)

### Phase 1: Chat Handler (4 hours)
1. Add `@app.event("app_mention")` and `@app.event("message")` handlers
2. Implement natural language query parsing
3. Route to existing context search service
4. Basic response formatting

### Phase 2: AI Streaming (6 hours)
1. Create `SlackChatService` with OpenAI streaming support
2. Implement progressive message updates in Slack
3. Add citation formatting with source links
4. Error handling and fallback responses

### Phase 3: Conversation State (3 hours)
1. Extend session storage for conversation history
2. Implement context-aware follow-up detection
3. Add conversation timeout logic
4. Testing multi-turn conversations

---

## Example Usage

### Scenario 1: Direct Question
```
User: @beau-bot What changes were made to the payment gateway last week?

Bot: 🤖 Searching across Slack, Jira, GitHub, and Fireflies...

Bot: Based on recent activity, here are the payment gateway changes from Oct 5-12:

**Key Updates:**
- Stripe webhook integration was refactored for better error handling [1]
- Payment retry logic was added for failed transactions [2]
- Security audit revealed and fixed a rate limiting issue [3]

📚 Sources
[1] GitHub PR #234: Refactor Stripe webhooks - Mike S. - Oct 10
[2] Jira PROJ-456: Add payment retry logic - Jane D. - Oct 8
[3] Slack #security: Security audit findings - Oct 11

💬 Ask me anything else, like "Who reviewed the security changes?"
```

### Scenario 2: Follow-up Question
```
User: Who reviewed the security changes?

Bot: From the Slack discussion [1], the security changes were reviewed by:
- Sarah K. (Security Lead) - Approved Oct 11
- Mike S. (Tech Lead) - Approved Oct 11
- DevOps team sign-off: Oct 12

The changes are now deployed to production.
```

### Scenario 3: DM (Private Query)
```
User: (DM) Tell me about the BERNS project status

Bot: Here's the latest on BERNS project:

**Progress This Week:**
- 3 tickets completed (BERNS-45, BERNS-47, BERNS-51)
- 12.5 hours tracked
- Sprint review scheduled for Oct 15

[Only shows data user has permission to access]
```

---

## Benefits

1. **Natural Interaction** - No slash commands, just ask questions
2. **Contextual** - Understands follow-up questions
3. **Comprehensive** - Searches all integrated data sources
4. **Permissioned** - Respects user access controls
5. **Interactive** - Reuses existing buttons (Show Sources, etc.)
6. **Accurate** - AI responses backed by citations

---

## Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Slow response time | Show "Searching..." message immediately, stream response |
| Incorrect AI responses | Always include citations for verification |
| Too many questions | Rate limiting per user (10 questions/hour) |
| Privacy concerns | Only search data user has permission to access |
| Cost (OpenAI API) | Limit response length, cache frequent queries |

---

## Technical Implementation Details

### Existing Code References

#### Context Search Service
**File:** `src/services/context_search.py`
- Already implements: `search(query, days_back, sources, user_id, detail_level, project)`
- Already supports: Semantic search, keyword matching, project filtering
- Already handles: User permissions via `user_email` mapping

#### Slack Bot
**File:** `src/managers/slack_bot.py`
- Already has: `/find-context` command implementation (lines 307-437)
- Already handles: Interactive button actions (Show Sources, Show Quotes, etc.)
- Already implements: Session storage for search results
- Already supports: Slack user to app user mapping

#### Context Summarizer
**File:** `src/services/context_summarizer.py` (referenced in context_search.py:1551)
- Already generates: AI summaries with citations
- Supports detail levels: "brief", "normal", "detailed", "slack"
- Returns: `SummarizedContext` with summary, citations, key_people, timeline, etc.

### New Code Structure

```
src/services/slack_chat_service.py (NEW)
├─ SlackChatService class
│  ├─ handle_question(user_id, question, channel_id, thread_ts)
│  ├─ generate_streaming_response(query, context_results)
│  ├─ format_chat_response(answer, citations)
│  └─ get_conversation_context(user_id, channel_id, thread_ts)
```

```python
# Example implementation structure
class SlackChatService:
    def __init__(self):
        self.context_search = ContextSearchService()
        self.slack_client = WebClient(token=settings.slack_bot_token)

    async def handle_question(self, user_id, question, channel_id, thread_ts=None):
        # 1. Post "searching" message
        # 2. Map Slack user to app user
        # 3. Call context_search.search()
        # 4. Stream AI response with citations
        # 5. Update message with final formatted response
```

### Event Handlers to Add

```python
# In src/managers/slack_bot.py

@self.app.event("app_mention")
def handle_mention(event, say):
    """Handle @bot-name mentions."""
    user_id = event['user']
    text = event['text']
    channel = event['channel']
    thread_ts = event.get('thread_ts', event['ts'])

    # Remove bot mention from text
    question = re.sub(r'<@[A-Z0-9]+>', '', text).strip()

    # Route to chat service
    asyncio.run(chat_service.handle_question(
        user_id=user_id,
        question=question,
        channel_id=channel,
        thread_ts=thread_ts
    ))

@self.app.event("message")
def handle_dm(event, say):
    """Handle direct messages."""
    # Only process DMs (no channel)
    if event.get('channel_type') != 'im':
        return

    # Handle as chat question
    # ...
```

---

## API Endpoint Considerations

### Existing Context Search Integration

The `/find-context` Slack command already uses the context search infrastructure:
- **Line 2146-2152** in `slack_bot.py`: Maps Slack user to app user
- **Line 2146-2152**: Calls `ContextSearchService.search()` with user permissions
- **Line 2278-2294**: Stores session in database for interactive buttons

### Reusable Patterns
The chat app can follow the exact same pattern:
1. Parse natural language query
2. Extract parameters (days, project)
3. Call `context_search.search()`
4. Format results with AI
5. Store session for follow-ups

---

## Configuration

### Environment Variables (Already Present)
```bash
# From .env.example
SLACK_BOT_TOKEN=xoxb-...
OPENAI_API_KEY=sk-...
PINECONE_API_KEY=...
REDIS_URL=redis://localhost:6379/0
```

### Slack App Permissions (May Need Update)
Current permissions for slash commands should be extended:
- `app_mentions:read` - Detect @mentions ✅ (may need to add)
- `chat:write` - Post messages ✅ (already has)
- `im:history` - Read DMs ✅ (may need to add)
- `im:write` - Send DMs ✅ (may need to add)

---

## Testing Plan

### Unit Tests
- `tests/services/test_slack_chat_service.py`
  - Test question parsing
  - Test conversation context retrieval
  - Mock OpenAI streaming responses

### Integration Tests
- Test with real Slack workspace
- Verify permission filtering works
- Test multi-turn conversations
- Test rate limiting

### User Acceptance Tests
1. User asks simple question → Gets answer with citations
2. User asks follow-up → Bot understands context
3. User asks in DM → Only sees authorized data
4. User clicks "Show Sources" → Full source list appears

---

## Rollout Strategy

### Phase 1: Internal Alpha (Week 1)
- Deploy to test Slack workspace
- Invite 3-5 internal users
- Gather feedback on accuracy and UX

### Phase 2: Beta (Week 2)
- Deploy to production Slack workspace
- Announce in #general channel
- Monitor usage and costs
- Fix bugs and improve prompts

### Phase 3: GA (Week 3)
- Full team rollout
- Create user documentation
- Set up monitoring and alerts
- Optimize costs based on usage patterns

---

## Cost Estimates

### OpenAI API Costs (GPT-4o)
- Input: $2.50 / 1M tokens
- Output: $10.00 / 1M tokens

**Estimated per query:**
- Context retrieval: ~2,000 tokens (top 12 results @ ~800 chars each)
- AI response: ~500 tokens output
- Cost per query: ~$0.01

**Monthly estimates:**
- 10 users × 20 queries/day × 22 days = 4,400 queries
- Total cost: ~$44/month

### Pinecone Costs
- Already configured and running
- No additional cost (using existing index)

---

## Success Metrics

### Primary KPIs
1. **Adoption Rate** - % of team using chat feature weekly
2. **Response Accuracy** - User feedback on answer quality (thumbs up/down)
3. **Time Saved** - Reduction in "where did we discuss X" questions

### Secondary Metrics
1. Average response time
2. Questions per user per day
3. Most common query types
4. Sources most frequently cited

---

## Future Enhancements

### V2 Features (Post-MVP)
1. **Suggested Questions** - After answering, suggest related queries
2. **Rich Media** - Include screenshots, diagrams from Notion/Confluence
3. **Action Buttons** - "Create Jira ticket from this", "Schedule meeting"
4. **Voice Support** - Answer questions in Slack Huddles
5. **Summarize Channel** - "@bot summarize this channel's last week"
6. **Project Briefs** - "@bot brief me on PROJ-123"

### Integration Opportunities
1. **Email Digest** - Daily/weekly digest of important findings
2. **Dashboard Widget** - Show trending questions on web dashboard
3. **API Endpoint** - Expose chat API for other tools
4. **Mobile App** - Native mobile experience

---

## Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2025-10-12 | Use existing `/find-context` infrastructure | Reuse battle-tested code, faster implementation |
| 2025-10-12 | Streaming via message edits (not true streaming) | Slack API limitation, best available UX |
| 2025-10-12 | 15-minute conversation timeout | Balance context retention vs. memory cost |
| 2025-10-12 | Redis for session storage | Already configured, fast, reliable |

---

## References

### Internal Documentation
- `/Users/msamimi/syatt/projects/agent-pm/CLAUDE.md` - Project documentation
- `docs/VECTOR_DB_SETUP_GUIDE.md` - Pinecone configuration
- `docs/GITHUB_APP_SETUP.md` - GitHub integration

### External Documentation
- [Slack Bolt Python](https://slack.dev/bolt-python/)
- [OpenAI Streaming](https://platform.openai.com/docs/api-reference/streaming)
- [Slack Event API](https://api.slack.com/events-api)

---

## Next Steps

1. ✅ **Save this plan** for future reference
2. ⏳ **Review with team** - Discuss approach and priorities
3. ⏳ **Set up test environment** - Slack workspace for development
4. ⏳ **Start Phase 1** - Implement chat handler
5. ⏳ **Iterate based on feedback**

**Estimated Timeline: 2-3 days for MVP, 1 week for production-ready**

---

*Last Updated: 2025-10-12*
*Author: Claude Code*
*Status: Ready for Implementation*
