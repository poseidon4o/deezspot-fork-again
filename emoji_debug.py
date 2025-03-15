#!/usr/bin/python3

import emoji
import sys

test_string = "Happy Song 😊 with 🔥 emoji"

print(f"Original: {test_string}")

# Direct emoji replacement test
print(f"Demojize: {emoji.demojize(test_string)}")
print(f"Replace with [emoji]: {emoji.replace_emoji(test_string, replace='[emoji]')}")

# Custom handling to better format demojized text
demojized = emoji.demojize(test_string)
formatted = demojized.replace(':', ' ').replace('_', ' ').strip()
print(f"Formatted demojized: {formatted}")

# Check if our test string has emojis
print(f"\nEmoji detection:")
for char in test_string:
    if char in emoji.EMOJI_DATA:
        print(f"'{char}' is an emoji")
        
print(f"\nPython version: {sys.version}")
print(f"Emoji package version: {emoji.__version__}") 