# Alias Generation Feature

## The Problem It Solves

Students ask questions in a million different ways. Some write in formal Arabic, some in dialect, some in English, some mix everything together. Some make typos, some use abbreviations. If we only matched exact phrases, we'd miss most queries.

That's where alias generation comes in. We automatically create multiple ways to refer to the same topic, so no matter how someone asks, we can understand them.

## How We Generate Aliases

When we first encounter a new topic, we use ChatGPT to generate 20 aliases:

- 10 in Arabic (mix of formal, dialect, and Arabizi)
- 10 in English (formal, casual, typos, abbreviations)

For example, for "course registration", we might generate:

- Arabic: "تسجيل المواد", "كيف اسجل", "تسجيل مواد", "registration", "kif asajel"
- English: "course registration", "register classes", "enrollment", "regester" (typo), "sign up"

## The Process

Here's how it works:

1. When we extract data for a new topic, we generate a canonical key (like `course_registration`)
2. We ask ChatGPT to generate aliases for this key
3. We also add the original query as an alias
4. We generate embeddings for all these aliases
5. We store everything in Redis

The whole alias generation happens in the background, so it doesn't slow down the response to the user.

## Types of Aliases

We try to cover different variations:

**Arabic:**

- Formal Arabic (فصحى)
- Jordanian dialect (عامية)
- Arabizi (Arabic written in English letters)
- Common typos and misspellings

**English:**

- Formal terms
- Casual/slang versions
- Common typos
- Abbreviations

This way, whether someone types "تسجيل" or "registration" or "regester" or "كيف اسجل", we can match it.

## Validation

We don't just blindly accept whatever ChatGPT generates. We validate aliases to make sure they're actually related to the topic. We also check for duplicates and remove them.

## Why This Matters

Without good aliases, the semantic search wouldn't work as well. The embeddings need good training data, and aliases provide that. The more aliases we have, the better we can match queries.

Also, storing aliases helps us understand what students are actually asking about. We can see patterns and improve the system over time.

## Manual Override

While most aliases are auto-generated, we also support manual aliases. If we notice students keep asking something in a specific way that we're missing, we can add it manually. The system will pick it up and use it.
