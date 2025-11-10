# Groq API Key Setup Guide

## Quick Setup (Secure - Recommended)

RexLit stores your Groq API key encrypted at rest using Fernet encryption.

### Step 1: Install Dependencies

```bash
# Activate virtual environment if not already active
source .venv/bin/activate  # or your virtualenv path

# Install RexLit with privilege support
pip install -e '.[privilege]'
```

### Step 2: Store Your API Key Securely

```bash
# Run the setup script
python scripts/setup_groq_key.py
```

The script will:
1. Prompt you for your Groq API key
2. Encrypt and store it at `~/.config/rexlit/secrets/groq.api.enc`
3. Verify the key can be retrieved

### Step 3: Enable Online Mode

```bash
# For the current session
export REXLIT_ONLINE=1

# Or add to your ~/.zshrc or ~/.bashrc for permanent:
echo 'export REXLIT_ONLINE=1' >> ~/.zshrc  # or ~/.bashrc
```

### Step 4: Test the Integration

```bash
# Run test script
python scripts/test_groq_privilege.py
```

---

## Alternative: Environment Variable (Less Secure)

If you prefer to use environment variables:

```bash
# Set for current session
export GROQ_API_KEY="gsk_..."
export REXLIT_ONLINE=1

# Or add to ~/.zshrc / ~/.bashrc:
echo 'export GROQ_API_KEY="gsk_..."' >> ~/.zshrc
echo 'export REXLIT_ONLINE=1' >> ~/.zshrc
```

**⚠️ Warning:** This stores the key in plaintext in your shell config file.

---

## Getting a Groq API Key

1. Visit [https://console.groq.com](https://console.groq.com)
2. Sign up or log in
3. Navigate to API Keys section
4. Click "Create API Key"
5. Copy the key (starts with `gsk_`)

---

## Testing Your Setup

### Manual Test (Quick)

```bash
# Test with a privileged email
echo 'From: attorney@law.com
To: client@company.com
Subject: Legal opinion

Here is my legal analysis...' | rexlit privilege classify -
```

### Automated Tests

```bash
# Run comprehensive test suite
python scripts/test_groq_privilege.py

# Expected output:
#   Test 1: ✓ DETECTED PRIVILEGE
#   Test 2: ✓ Correctly identified as non-privileged
#   Test 3: ✓ Handle edge case
#   Test 4: ✓ DETECTED PRIVILEGE
```

---

## Security Notes

### Encrypted Storage (Recommended Method)

- **Location:** `~/.config/rexlit/secrets/groq.api.enc`
- **Encryption:** Fernet (symmetric encryption)
- **Key file:** `~/.config/rexlit/api-secrets.key`
- **Permissions:** Files are created with mode `0600` (owner read/write only)

### What Gets Stored

The encrypted file contains:
- Your Groq API key
- Nothing else (no prompts, documents, or responses)

### What Doesn't Get Stored

RexLit's privacy guarantees:
- Document text is NOT stored by RexLit
- Full chain-of-thought reasoning is hashed (SHA-256), not logged
- Only redacted summaries appear in audit logs
- Groq receives: policy template + document text (for classification only)

---

## Troubleshooting

### "GROQ_API_KEY not set" Error

If using encrypted storage, ensure:
```bash
# Check if key exists
ls -la ~/.config/rexlit/secrets/groq.api.enc

# If missing, run setup again
python scripts/setup_groq_key.py
```

### "Module not found" Errors

Install dependencies:
```bash
pip install -e '.[privilege]'
```

### "Online mode required" Error

Enable online mode:
```bash
export REXLIT_ONLINE=1
```

### API Key Not Working

Verify your key at [https://console.groq.com/keys](https://console.groq.com/keys)

Check rate limits:
- Free tier: Variable rate limits
- Paid tier: Higher throughput

---

## Next Steps

Once setup is complete:

1. **Test Policy Effectiveness:**
   ```bash
   python scripts/validate_privilege_policy.py
   ```

2. **Run Benchmarks:**
   ```bash
   python scripts/benchmark_privilege.py
   ```

3. **Use in Production:**
   ```bash
   rexlit privilege classify document.pdf
   ```

---

## Uninstalling / Removing Key

To remove your stored API key:

```bash
# Remove encrypted key
rm ~/.config/rexlit/secrets/groq.api.enc

# Remove encryption key (also removes all other stored API keys!)
rm ~/.config/rexlit/api-secrets.key
```
