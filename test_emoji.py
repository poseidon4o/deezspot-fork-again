#!/usr/bin/python3

import sys
import emoji
from deezspot.libutils.utils import var_excape, __get_tronc, handle_emoji, is_emoji
import deezspot.libutils.others_settings as settings

# Test strings with emojis
test_strings = [
    "Happy Song 😊",
    "🔥 Hot Track"
]

print("Testing emoji handling in filenames:\n")

# Test with default settings (preserve emojis)
print("=== Default settings (preserve emojis) ===")
settings.PRESERVE_EMOJI = True
settings.EMOJI_FALLBACK = ""
for string in test_strings:
    print(f"Original: {string}")
    escaped = var_excape(string)
    print(f"Escaped: {escaped}")
    print("-" * 50)

# Test with emojis converted to text
print("\n=== Convert emojis to text ===")
settings.PRESERVE_EMOJI = False
settings.EMOJI_FALLBACK = ""
for string in test_strings:
    print(f"Original: {string}")
    # Process string with emoji handling directly for clearer test
    processed = handle_emoji(string)
    print(f"Processed: {processed}")
    escaped = var_excape(string)
    print(f"Escaped: {escaped}")
    print("-" * 50)

# Test with emojis replaced with custom fallback
print("\n=== Replace emojis with custom text ===")
settings.PRESERVE_EMOJI = False
settings.EMOJI_FALLBACK = "[emoji]"
for string in test_strings:
    print(f"Original: {string}")
    # Process string with emoji handling directly for clearer test
    processed = handle_emoji(string)
    print(f"Processed: {processed}")
    escaped = var_excape(string)
    print(f"Escaped: {escaped}")
    print("-" * 50)

# Reset settings
settings.PRESERVE_EMOJI = True
settings.EMOJI_FALLBACK = ""

# Test truncation
print("\n=== Testing emoji-safe truncation ===")
long_string = "Very long title with emojis at the end that should be properly truncated without cutting an emoji in half 🎵🎧🎤🎹"
tronc_size = __get_tronc(long_string)
print(f"Original length: {len(long_string)} characters")
print(f"Truncation size: {tronc_size} characters")
print(f"Original: {long_string}")
print(f"Truncated: {long_string[:tronc_size]}")

# Test with None and non-string values
print("\n=== Testing special cases ===")
print(f"Escaped None: '{var_excape(None)}'")
print(f"Escaped number: '{var_excape(123)}'")
print(f"Escaped empty string: '{var_excape('')}'")

# Print Python and emoji package versions
print(f"\nPython version: {sys.version}")
print(f"Emoji package version: {emoji.__version__}")

print("\nEmoji detection test:")
for char in "Hello 😊 World 🌍":
    print(f"Character: {char}, Is emoji: {is_emoji(char)}") 