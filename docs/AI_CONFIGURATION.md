# AI Configuration Guide

## Overview

The application supports three AI providers:
- **OpenAI** (GPT-4o, GPT-4, GPT-3.5-turbo, etc.)
- **Anthropic** (Claude 3.5 Sonnet, Claude 3.5 Haiku, Claude 3 Opus)
- **Google** (Gemini 1.5 Pro, Gemini 1.5 Flash, Gemini 1.0 Pro)

AI configuration can be managed through:
1. **Admin UI** (recommended) - Settings page → AI Configuration tab
2. **Environment variables** (fallback)

## Configuration Hierarchy

The system loads AI configuration in the following order:

1. **Database** (highest priority) - Admin-configured settings via UI
2. **Environment Variables** - Fallback if no database configuration exists
3. **Defaults** - Provider-specific defaults

## Admin UI Configuration

### Accessing AI Settings

1. Log in as an admin user
2. Navigate to Settings page
3. Click on "AI Configuration" tab (admin only)

### Configuring AI Provider

1. **Select Provider**: Choose from OpenAI, Anthropic, or Google
2. **Choose Model**:
   - OpenAI: Dynamically fetched from OpenAI API
   - Anthropic/Google: Curated list + custom input option
3. **Set Parameters**:
   - Temperature (0-2): Controls randomness (lower = more deterministic)
   - Max Tokens: Maximum response length
4. **Add API Key**: Securely stored encrypted in database

### Dynamic Configuration Updates

**IMPORTANT**: As of the latest update, AI configuration changes take effect **immediately** without requiring an application restart.

The system automatically:
- Refreshes AI configuration from database before each AI operation
- Creates fresh LLM instances with updated settings
- Logs which provider/model is being used

**What this means**:
- Change provider in Admin UI → Next AI search uses new provider
- Update model → Next analysis uses new model
- Modify temperature/tokens → Applied to next request

## Environment Variable Configuration

If no database configuration exists, the system falls back to environment variables:

```bash
# Provider selection
AI_PROVIDER=openai  # or "anthropic" or "google"
AI_TEMPERATURE=0.3
AI_MAX_TOKENS=2000

# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o

# Anthropic
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022

# Google
GOOGLE_API_KEY=...
GOOGLE_MODEL=gemini-1.5-pro
```

## How Dynamic Reload Works

### Before (Required Restart)

Previously, AI configuration was loaded once at application startup and cached:

```python
settings = Settings()  # Created once at module import
# settings.ai was frozen for entire application lifetime
```

**Problem**: Updating database settings had no effect until app restart.

### After (Immediate Updates)

Now, AI configuration is refreshed dynamically:

```python
# config/settings.py
class Settings:
    @classmethod
    def get_fresh_ai_config(cls) -> AIConfig:
        """Get fresh AI configuration from database."""
        return cls._load_ai_config()

# src/processors/transcript_analyzer.py
class TranscriptAnalyzer:
    def analyze_transcript(self, ...):
        # Refreshes LLM before each analysis
        self.refresh_llm()
        ...
```

**Result**: Database changes take effect immediately on next AI operation.

## Affected Components

The following components automatically use fresh AI configuration:

1. **TranscriptAnalyzer** (`src/processors/transcript_analyzer.py`)
   - Meeting transcript analysis
   - Action item extraction
   - Refreshes LLM before each `analyze_transcript()` call

2. **ContextSearchService** (`src/services/context_search.py`)
   - Context search summaries
   - Creates fresh LLM instance for each search

3. **ContextSummarizer** (`src/services/context_summarizer.py`)
   - AI-powered result summarization
   - Creates fresh client for each `summarize()` call
   - **Note**: Currently OpenAI-only, logs warning if other provider configured

## Verifying Active Configuration

To verify which AI provider/model is being used:

### Via Logs

```bash
# Production logs
doctl apps logs <app-id> --type run --follow | grep "Creating LLM"

# Output example:
# 2025-10-21 17:45:23 - INFO - Creating LLM with provider=anthropic, model=claude-3-5-sonnet-20241022
```

### Via Admin UI

1. Go to Settings → AI Configuration
2. Current settings displayed at top of form

### Via API

```bash
GET /api/admin/system-settings
```

## Security

- API keys are **encrypted** before storing in database
- Uses application-level encryption (see `src/utils/encryption.py`)
- Keys are **never** exposed in API responses (only `has_*_key` boolean flags)
- Admin-only access enforced by role-based authentication

## Troubleshooting

### "Invalid provider" errors

**Cause**: Provider name mismatch
**Fix**: Ensure provider is exactly "openai", "anthropic", or "google" (lowercase)

### "API key not set" errors

**Cause**: No API key in database or environment
**Fix**:
1. Admin UI: Add API key via Settings → AI Configuration
2. Environment: Set `{PROVIDER}_API_KEY` environment variable

### Configuration not updating

**Before latest update**: Required application restart
**After latest update**: Should be immediate - check logs for "Creating LLM" messages

If still not updating:
1. Verify database write succeeded (check success message in UI)
2. Check application logs for errors
3. Verify you're using the latest code with dynamic reload feature

### ContextSummarizer using wrong provider

**Expected behavior**: ContextSummarizer currently only supports OpenAI
**What happens**: Logs warning and uses OpenAI regardless of configured provider
**Future**: Will be updated to support all three providers

## Best Practices

1. **Use Admin UI**: Easier than managing environment variables, supports encryption
2. **Test before switching**: Try new provider with non-critical requests first
3. **Monitor costs**: Different providers have different pricing
4. **Check logs**: Verify provider switch via log messages
5. **Model compatibility**: Not all models support same features (e.g., o1 models don't support temperature)

## Future Enhancements

- [ ] Full Anthropic/Google support in ContextSummarizer
- [ ] Model capability detection (temperature support, max tokens, etc.)
- [ ] Cost tracking per provider/model
- [ ] A/B testing framework for comparing providers
- [ ] Provider-specific optimizations
