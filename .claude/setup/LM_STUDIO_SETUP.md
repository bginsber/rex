# LM Studio Setup Guide

Use your locally running LM Studio model with RexLit for privilege classification.

## Quick Setup

1. **Start LM Studio** and load your `gpt-oss-safeguard-20b` model
2. **Start the local server** in LM Studio (default port: 1234)
3. **Configure RexLit** to use your local endpoint:

```bash
export REXLIT_ONLINE=1
export REXLIT_GROQ_API_BASE="http://localhost:1234/v1"
# API key not needed for local LM Studio, but you can set a dummy value:
export REXLIT_GROQ_API_KEY="lm-studio-local"
```

4. **Test it:**

```bash
rexlit privilege classify .juul_sample_emails/gfmg0396/gfmg0396.ocr
```

## For API Server

When starting the API server:

```bash
cd api
REXLIT_ONLINE=1 \
REXLIT_GROQ_API_BASE="http://localhost:1234/v1" \
REXLIT_GROQ_API_KEY="lm-studio-local" \
REXLIT_BIN=$(which rexlit) \
bun run index.ts
```

## Model Name

Make sure your LM Studio model identifier matches what RexLit expects. 
You may need to check what model name LM Studio reports and update the model parameter.

The default model name is: `openai/gpt-oss-safeguard-20b`

If your LM Studio uses a different name, you can check by calling:
```bash
curl http://localhost:1234/v1/models
```

## Troubleshooting

**"Connection refused"**
- Make sure LM Studio server is running
- Check the port number (default is 1234)
- Verify the URL: `http://localhost:1234/v1`

**"Model not found"**
- Check what models are available: `curl http://localhost:1234/v1/models`
- The model name in LM Studio should match what RexLit expects

**"API key required"**
- For local LM Studio, you can use any dummy value
- Set: `export REXLIT_GROQ_API_KEY="lm-studio-local"`
