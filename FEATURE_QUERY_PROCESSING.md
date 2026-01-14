# Query Processing Feature

## Overview

This is basically the heart of the whole system. When a student asks a question, this feature takes care of everything from start to finish. It's like the main coordinator that talks to all the other parts and makes sure the student gets their answer.

## How It Works

So here's what happens when someone submits a query:

First, the system checks if we've seen this question (or something similar) before. It does this by converting the question into what we call an "embedding" - basically a mathematical representation of what the question means. Then it compares this to all the questions we've stored before using something called cosine similarity. Think of it like checking if two sentences mean the same thing, even if they use different words.

If we find a match that's pretty confident (above 70% similarity), we just grab the cached answer and send it back. Super fast, like instant.

But if we don't find a good match, or if the match is a bit uncertain (between 50-70%), we do a few things:
- We ask ChatGPT to double-check if this is really the same question
- If ChatGPT confirms, we use the cached data
- If not, we go ahead and search for fresh information

When there's no cache at all, the system automatically searches the web using ChatGPT's knowledge about the university. It extracts the relevant information, structures it nicely, and then generates a really detailed answer.

## The Cool Part

What I really like about this is that we prioritize speed. The answer gets generated and sent back to the user immediately, even before we finish caching everything. The caching stuff happens in the background, so the user doesn't have to wait. This makes responses feel way faster - we're talking about 2-5 seconds instead of 10-15 seconds.

## Technical Details

The query processing follows a strict workflow:
1. Embedding matching - convert query to vector and compare
2. Cache check - look in Redis for existing data
3. Resource selection - pick the best URL if available
4. Data extraction - search and extract information
5. Answer generation - create detailed response
6. Background caching - store everything for next time

All of this is handled by the `QueryController` class, which acts as the main orchestrator. It talks to all the other services and makes sure everything flows smoothly.

## Why This Approach?

We went with this answer-first approach because honestly, students don't care about our caching system. They just want their answer fast. So we give them the answer immediately, and then we do all the housekeeping stuff (like generating aliases and storing embeddings) in the background. It's a win-win situation.
