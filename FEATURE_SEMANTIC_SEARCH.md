# Semantic Search with Embeddings

## What This Does

This feature is what makes the system smart about understanding questions. Instead of just matching exact words, it actually understands what the question means. So if someone asks "كيف أسجل المواد؟" and someone else asks "registration process", the system knows they're asking about the same thing.

## The Magic Behind It

We use something called embeddings. Basically, we convert text (like a question) into a list of numbers - a vector. These numbers represent the meaning of the text. OpenAI's embedding model does this conversion for us.

Once we have these vectors, we can compare them using cosine similarity. It's a math thing that tells us how similar two pieces of text are, even if they use completely different words. The result is a number between 0 and 1 - closer to 1 means more similar.

## How We Use It

When a student asks a question, here's what happens:

1. We convert their question into an embedding vector
2. We compare it against all the aliases we've stored before
3. We find the best match
4. If the match is really good (above 70%), we use it directly
5. If it's okay but not great (50-70%), we ask ChatGPT to confirm
6. If it's below 50%, we treat it as a new question

This is super useful because students ask questions in so many different ways. Some use formal Arabic, some use dialect, some mix Arabic and English, some make typos. The semantic search handles all of that.

## Real Example

Let's say we have these stored aliases for course registration:
- "تسجيل المواد"
- "course registration"
- "كيف اسجل"
- "register for classes"

If someone asks "أريد تسجيل المواد الدراسية", the embedding will match it closely to "تسجيل المواد" even though the words aren't exactly the same. That's the power of semantic understanding.

## The Thresholds

We have two important thresholds:
- **70% similarity**: This is our "confident match" threshold. If we get this score or higher, we're pretty sure it's the same question.
- **50% similarity**: This is our minimum. Below this, we don't even consider it a match.

Between 50-70%, we're uncertain, so we let ChatGPT make the final call. It's like having a second opinion.

## Why This Matters

Without semantic search, we'd have to store every possible way someone might ask a question. That's impossible. With embeddings, we can understand the meaning, not just match words. This makes the system way more flexible and user-friendly.
