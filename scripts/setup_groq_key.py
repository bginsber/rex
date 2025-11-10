#!/usr/bin/env python3
"""Setup Groq API key in RexLit's encrypted storage.

This script securely stores your Groq API key using RexLit's encrypted
storage system. The key is encrypted at rest with Fernet encryption.

Usage:
    python scripts/setup_groq_key.py

The key will be stored at:
    ~/.config/rexlit/secrets/groq.api.enc (encrypted)
    ~/.config/rexlit/api-secrets.key (encryption key)
"""

import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from rexlit.config import Settings


def setup_groq_key():
    """Interactively set up Groq API key."""
    print("=" * 70)
    print("RexLit Groq API Key Setup")
    print("=" * 70)
    print()
    print("This will store your Groq API key in encrypted storage at:")
    print("  ~/.config/rexlit/secrets/groq.api.enc")
    print()

    # Get API key from user
    api_key = input("Enter your Groq API key (starts with 'gsk_'): ").strip()

    if not api_key:
        print("❌ No API key entered. Exiting.")
        return False

    if not api_key.startswith("gsk_"):
        print("⚠️  Warning: Groq API keys typically start with 'gsk_'")
        confirm = input("Continue anyway? (y/N): ").strip().lower()
        if confirm != 'y':
            print("Cancelled.")
            return False

    # Store in encrypted settings
    try:
        settings = Settings()
        settings.store_api_key("groq", api_key)
        print()
        print("✓ API key stored successfully!")
        print()
        print("Key location: ~/.config/rexlit/secrets/groq.api.enc")
        print("Encryption key: ~/.config/rexlit/api-secrets.key")
        print()
        print("The key is encrypted at rest using Fernet encryption.")
        print()

        # Verify it can be retrieved
        retrieved = settings.get_groq_api_key()
        if retrieved == api_key:
            print("✓ Verification successful - key can be retrieved")
        else:
            print("❌ Warning: Retrieved key doesn't match")
            return False

        print()
        print("You can now use Groq privilege detection with:")
        print("  export REXLIT_ONLINE=1")
        print("  python scripts/test_groq_privilege.py")
        print()
        print("Or use the CLI:")
        print("  rexlit privilege classify <file>")

        return True

    except Exception as e:
        print(f"❌ Error storing API key: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = setup_groq_key()
    sys.exit(0 if success else 1)
