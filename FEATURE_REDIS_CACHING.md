# Redis Caching Feature

## Why We Need This

Let me be honest - calling OpenAI's API every single time someone asks a question would be slow and expensive. That's where Redis comes in. It's our super-fast memory that stores answers we've already generated, so we don't have to do all that work again.

## What We Store

We store three main things in Redis:

1. **The actual data** - All the information we extracted about a topic. Things like requirements, fees, deadlines, steps, etc. This is stored under keys like `data:course_registration`.

2. **Alias mappings** - We store which aliases point to which canonical keys. So if someone searches for "تسجيل", we know it maps to `course_registration`. These are stored as `alias:تسجيل` → `course_registration`.

3. **Embeddings** - We store the vector representations of aliases so we can do semantic matching quickly. These are stored as `emb:تسجيل` → `[list of numbers]`.

## How It Works

When we get a query, we first check Redis. If we find something, great! We use it. If not, we do the full search process and then store the result in Redis for next time.

The cool thing is that Redis is super fast - we're talking milliseconds to retrieve data. Compare that to several seconds for a full search, and you can see why caching is important.

## Cache Structure

We use a simple prefix system to organize everything:
- `data:<key>` - The actual JSON data
- `alias:<text>` - Maps alias to canonical key
- `emb:<text>` - Stores embedding vectors
- `canonical:<key>:aliases` - Lists all aliases for a key

This makes it easy to find things and keeps everything organized.

## Cache Lifecycle

When we cache something, we also set a TTL (Time To Live). By default, it's 24 hours, but you can configure it. After that time, the cache expires and we'll fetch fresh data next time.

We also have a background process that updates the cache. When a new question comes in and we generate an answer, we store it in Redis in the background so it's ready for the next person who asks something similar.

## Handling Failures

If Redis isn't available, the system still works. It just won't use the cache, so responses might be a bit slower. But it won't break anything. We check if Redis is connected before trying to use it, and we have fallback mechanisms in place.

## Why Redis Specifically?

We chose Redis because:
- It's really fast (in-memory storage)
- It supports the data structures we need (strings, lists, etc.)
- It's reliable and widely used
- It can handle high traffic without breaking a sweat

Plus, if we need to scale later, Redis has clustering support, so we can distribute the cache across multiple servers.
