# Multilingual Support Feature

## Why This Matters

Students at JUST come from different backgrounds. Some prefer Arabic, some prefer English, some mix both. Some write in formal Arabic, some in Jordanian dialect, some even use Arabizi (Arabic written in English letters). The system needs to handle all of this.

## Languages We Support

**Arabic:**
- Formal Arabic (الفصحى) - like "كيف يمكنني التسجيل؟"
- Jordanian dialect (العامية) - like "شو طريقة التسجيل؟"
- Arabizi - like "kif asajel al mawad?"

**English:**
- Formal English - "How do I register for courses?"
- Casual English - "how to register?"
- With typos - "how to regester?"

The system understands all of these variations and treats them equally.

## How It Works

When we receive a query, we:
1. Detect the language (Arabic, English, or mixed)
2. Normalize the text (remove diacritics, handle different Arabic scripts)
3. Process it the same way regardless of language
4. Generate an answer in the same language as the query (usually)

The language detection is pretty smart - it can handle mixed queries too, like "كيف register للcourses?"

## Normalization

Arabic text can be written in many ways. The same word might have different diacritics, or be written in different scripts. We normalize everything to a standard form so we can match queries reliably.

For example:
- "تسجيل" and "تسْجِيل" are treated the same
- "registration" and "Registration" are treated the same
- We handle common typos and variations

## Alias Generation

When we generate aliases for a topic, we make sure to include both Arabic and English versions. This way, no matter what language someone uses, we can match their query.

For example, for course registration, we might have:
- Arabic aliases: "تسجيل", "كيف اسجل", "تسجيل مواد"
- English aliases: "registration", "register", "enrollment"

## Answer Language

By default, answers are generated in Arabic since most queries are in Arabic. But if someone asks in English, we can generate English answers too. The system tries to match the query language.

## Challenges We Faced

The biggest challenge was handling all the variations. Arabic has so many dialects, and students write in different styles. We solved this by:
- Using semantic search (embeddings) instead of exact matching
- Generating lots of aliases in different styles
- Normalizing text properly
- Using ChatGPT's multilingual capabilities

## Real-World Usage

In practice, we see queries like:
- "كيف أسجل المواد؟" (formal Arabic)
- "شو طريقة التسجيل؟" (dialect)
- "how do I register?" (English)
- "kif asajel?" (Arabizi)

All of these work perfectly. The system doesn't care which language or style you use - it just understands what you're asking.

## Future Improvements

We're thinking about adding:
- More dialect support (Palestinian, Syrian, etc.)
- Better handling of code-switching (mixing languages)
- Support for other languages if needed
- Better normalization for Arabizi

But honestly, the current system handles most cases really well. Students can ask questions however they're comfortable, and the system understands them.
