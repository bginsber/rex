# Quick Test Guide: Groq Adapter with .env File

This guide shows you how to quickly test the Groq privilege adapter using a disposable `.env` file.

## Step 1: Create .env File

Create a `.env` file in the project root (`rex/` directory) with your Groq API key:

```bash
cd rex
cat > .env << EOF
GROQ_API_KEY=gsk_your_actual_key_here
REXLIT_ONLINE=1
EOF
```

**Important:** Replace `gsk_your_actual_key_here` with your actual Groq API key from [console.groq.com](https://console.groq.com).

## Step 2: Run the Test Script

```bash
python test_groq_with_env.py
```

The script will:
1. Load environment variables from `.env`
2. Create `GroqPrivilegeAdapter` and `GroqPrivilegeReasoningAdapter`
3. Test classification on a sample privileged email
4. Display results including labels, confidence, and reasoning hash

## Step 3: Test with CLI

You can also test using the CLI directly:

```bash
# Make sure .env is loaded (the script does this automatically)
export $(cat .env | xargs)

# Test with a sample document
echo 'From: attorney@law.com
To: client@company.com
Subject: Legal opinion

Here is my legal analysis...' | rexlit privilege classify -
```

## Step 4: Clean Up

After testing, remove the `.env` file:

```bash
rm .env
```

**Note:** The `.env` file is gitignored, so it won't be committed to the repository.

## Troubleshooting

### "GROQ_API_KEY not found"
- Make sure the `.env` file exists in the `rex/` directory
- Check that the key starts with `gsk_`
- Verify there are no extra spaces or quotes around the key

### "Online mode required"
- Make sure `REXLIT_ONLINE=1` is in your `.env` file
- Or export it: `export REXLIT_ONLINE=1`

### API Errors
- Verify your API key is valid at [console.groq.com/keys](https://console.groq.com/keys)
- Check rate limits (free tier has variable limits)
- Ensure you have internet connectivity

## Alternative: Use Environment Variables Directly

If you prefer not to use a `.env` file:

```bash
export GROQ_API_KEY="gsk_your_key_here"
export REXLIT_ONLINE=1
python test_groq_with_env.py
```

## Expected Output

When successful, you should see:

```
✓ GroqPrivilegeAdapter created
✓ GroqPrivilegeReasoningAdapter created

Classifying test document...

======================================================================
Results:
======================================================================
Labels: ['PRIVILEGED:ACP']
Confidence: 0.95%
Is Privileged: True
Needs Review: False
Reasoning Hash: a3f2b1c4d5e6f7...
Reasoning Summary: Document contains attorney-client communication...
Model Version: openai/gpt-oss-safeguard-20b
Policy Version: groq-abc123def456...

✅ SUCCESS: Privilege detected correctly!
```

