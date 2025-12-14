#!/usr/bin/env python3
"""Quick test script for Groq adapter using a disposable .env file.

This script creates a temporary .env file, loads it, and tests the Groq
privilege reasoning adapter. The .env file is created in the current directory
and can be easily deleted after testing.

Usage:
    # Create .env file with your API key
    echo "GROQ_API_KEY=gsk_your_key_here" > .env
    echo "REXLIT_ONLINE=1" >> .env

    # Run test
    python test_groq_with_env.py

    # Clean up
    rm .env
"""

import os
import sys
from pathlib import Path

# Add rexlit to path (go up one level from rex/ to rex/rexlit/)
script_dir = Path(__file__).parent
if script_dir.name == "rex":
    # We're in rex/ directory, add it to path
    sys.path.insert(0, str(script_dir))
else:
    # We're in project root, add rex/ to path
    sys.path.insert(0, str(script_dir / "rex"))

from rexlit.app.adapters.groq_privilege import GroqPrivilegeAdapter  # noqa: E402
from rexlit.app.adapters.groq_privilege_reasoning_adapter import (  # noqa: E402
    GroqPrivilegeReasoningAdapter,
)


def load_env_file(env_path: Path = Path(".env")) -> dict[str, str]:
    """Load environment variables from .env file."""
    env_vars = {}
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    if "=" in line:
                        key, value = line.split("=", 1)
                        env_vars[key.strip()] = value.strip()
    return env_vars


def test_groq_adapter():
    """Test Groq adapter with .env file."""
    print("=" * 70)
    print("Groq Privilege Adapter Test (using .env file)")
    print("=" * 70)
    print()

    # Check for .env file
    env_path = Path(".env")
    if not env_path.exists():
        print("❌ .env file not found!")
        print()
        print("Create a .env file with:")
        print("  GROQ_API_KEY=gsk_your_key_here")
        print("  REXLIT_ONLINE=1")
        print()
        return False

    # Load .env file
    env_vars = load_env_file(env_path)

    # Set environment variables
    for key, value in env_vars.items():
        os.environ[key] = value
        print(f"✓ Loaded {key}")

    print()

    # Check for required variables
    groq_key = os.getenv("GROQ_API_KEY")
    if not groq_key:
        print("❌ GROQ_API_KEY not found in .env file")
        return False

    if not groq_key.startswith("gsk_"):
        print("⚠️  Warning: Groq API keys typically start with 'gsk_'")

    online = os.getenv("REXLIT_ONLINE", "0")
    if online != "1":
        print("⚠️  Warning: REXLIT_ONLINE not set to 1, enabling for this test")
        os.environ["REXLIT_ONLINE"] = "1"

    print()
    print("Testing GroqPrivilegeReasoningAdapter...")
    print()

    # Test document
    test_text = """From: jennifer.smith@cooley.com
To: john.doe@company.com
Subject: Legal opinion on merger agreement

John,

Here is my legal opinion on the proposed merger agreement. From a legal
perspective, I advise proceeding with caution due to potential antitrust
implications. Please keep this privileged and confidential.

Best regards,
Jennifer Smith, Esq.
Cooley LLP"""

    try:
        # Create Groq adapter
        groq_adapter = GroqPrivilegeAdapter(api_key=groq_key)
        print("✓ GroqPrivilegeAdapter created")

        # Create reasoning adapter wrapper
        reasoning_adapter = GroqPrivilegeReasoningAdapter(groq_adapter)
        print("✓ GroqPrivilegeReasoningAdapter created")

        # Test classification
        print()
        print("Classifying test document...")
        decision = reasoning_adapter.classify_privilege(
            text=test_text,
            threshold=0.75,
            reasoning_effort="dynamic",
        )

        print()
        print("=" * 70)
        print("Results:")
        print("=" * 70)
        print(f"Labels: {decision.labels}")
        print(f"Confidence: {decision.confidence:.2%}")
        print(f"Is Privileged: {decision.is_privileged}")
        print(f"Needs Review: {decision.needs_review}")
        print(f"Reasoning Hash: {decision.reasoning_hash[:16]}..." if decision.reasoning_hash else "Reasoning Hash: (none)")
        print(f"Reasoning Summary: {decision.reasoning_summary[:100]}..." if decision.reasoning_summary else "Reasoning Summary: (none)")
        print(f"Model Version: {decision.model_version}")
        print(f"Policy Version: {decision.policy_version}")
        print()

        if decision.is_privileged:
            print("✅ SUCCESS: Privilege detected correctly!")
        else:
            print("⚠️  No privilege detected (may be correct depending on policy)")

        if decision.error_message:
            print(f"⚠️  Error: {decision.error_message}")

        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_groq_adapter()
    sys.exit(0 if success else 1)

