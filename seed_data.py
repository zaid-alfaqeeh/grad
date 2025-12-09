"""
Seed data script to pre-populate Redis with aliases and embeddings.
Run this once to bootstrap the system with initial data.

Usage: python seed_data.py
"""
import sys
from services.redis_service import RedisService
from services.embeddings_service import EmbeddingsService
from services.alias_service import AliasService
from logger import get_logger

# Pre-defined aliases for common university topics
SEED_ALIASES = {
    "registration": [
        "تسجيل", "تسجيل المواد", "كيف اسجل", "registration", "enroll",
        "course registration", "register for classes", "تسجيل مواد",
        "how to register", "طريقة التسجيل", "اسجل مواد", "رجسترشن"
    ],
    "fees": [
        "رسوم", "مصاريف", "fees", "tuition", "payment", "كم الرسوم",
        "تكلفة", "سعر", "university fees", "رسوم الجامعة", "مصاريف الدراسة",
        "how much", "كم سعر الساعة", "credit hour cost", "فلوس"
    ],
    "admissions": [
        "قبول", "قبولات", "admission", "admissions", "apply", "تقديم",
        "طلب قبول", "كيف اقدم", "how to apply", "application",
        "admission requirements", "شروط القبول", "معدل القبول"
    ],
    "academic_calendar": [
        "تقويم", "تقويم اكاديمي", "calendar", "academic calendar",
        "متى يبدأ الفصل", "semester dates", "بداية الفصل", "نهاية الفصل",
        "when does semester start", "امتحانات", "عطلة", "holidays"
    ],
    "student_services": [
        "خدمات", "خدمات الطالب", "student services", "support",
        "مساعدة", "help", "خدمات طلابية", "شؤون الطلاب"
    ],
    "courses_schedule": [
        "جدول", "جدول المحاضرات", "schedule", "timetable",
        "class schedule", "مواعيد", "وقت المحاضرات", "جدول الحصص"
    ],
    "scholarships": [
        "منح", "منحة", "scholarship", "scholarships", "financial aid",
        "منح دراسية", "مساعدة مالية", "تخفيض", "discount"
    ],
    "housing": [
        "سكن", "سكن طلابي", "housing", "dorm", "dormitory",
        "accommodation", "اسكان", "سكن جامعي", "where to live"
    ],
    "library": [
        "مكتبة", "library", "books", "كتب", "مكتبة الجامعة",
        "borrowing books", "استعارة كتب", "مصادر", "resources"
    ],
    "graduation": [
        "تخرج", "graduation", "graduate", "متطلبات التخرج",
        "graduation requirements", "كيف اتخرج", "شهادة"
    ],
    "transcripts": [
        "كشف علامات", "transcript", "grades", "علامات",
        "academic record", "سجل اكاديمي", "marks", "GPA"
    ],
    "engineering": [
        "هندسة", "كلية الهندسة", "engineering", "engineering faculty",
        "faculty of engineering", "مهندس"
    ],
    "it": [
        "تكنولوجيا المعلومات", "IT", "كلية تقنية المعلومات",
        "information technology", "computer science", "حاسوب", "برمجة"
    ],
    "contact": [
        "تواصل", "اتصال", "contact", "phone", "email",
        "رقم الجامعة", "ايميل", "كيف اتواصل", "contact us"
    ]
}


def seed_aliases():
    """Seed Redis with predefined aliases and their embeddings."""
    logger = get_logger()
    redis = RedisService()
    embeddings = EmbeddingsService()
    alias_service = AliasService()
    
    if not redis.is_connected():
        logger.error("Redis not connected! Cannot seed data.")
        print("❌ Redis not connected! Please start Redis first.")
        return False
    
    if not embeddings.is_configured():
        logger.warning("Embeddings service not configured. Seeding without embeddings.")
        print("⚠️ OpenAI not configured. Seeding aliases without embeddings.")
    
    total_aliases = 0
    total_embeddings = 0
    
    print("\n🌱 Seeding aliases and embeddings...")
    print("=" * 50)
    
    for canonical_key, aliases in SEED_ALIASES.items():
        print(f"\n📁 {canonical_key}:")
        
        # Generate embeddings for all aliases in batch
        alias_embeddings = {}
        if embeddings.is_configured():
            try:
                emb_batch = embeddings.generate_embeddings_batch(aliases)
                alias_embeddings = emb_batch
                total_embeddings += len(emb_batch)
                print(f"   ✓ Generated {len(emb_batch)} embeddings")
            except Exception as e:
                print(f"   ⚠️ Embedding generation failed: {e}")
        
        # Store each alias
        for alias in aliases:
            alias_lower = alias.lower().strip()
            
            # Store alias -> canonical_key mapping
            redis.client.set(f"alias:{alias_lower}", canonical_key)
            
            # Store embedding if available
            if alias_lower in alias_embeddings:
                import json
                redis.client.set(f"emb:{alias_lower}", json.dumps({
                    'embedding': alias_embeddings[alias_lower],
                    'canonical_key': canonical_key
                }))
            
            total_aliases += 1
        
        # Store aliases list for canonical key
        import json
        redis.client.set(f"canonical:{canonical_key}:aliases", json.dumps(aliases, ensure_ascii=False))
        
        print(f"   ✓ Stored {len(aliases)} aliases")
    
    print("\n" + "=" * 50)
    print(f"✅ Seeding complete!")
    print(f"   Total aliases: {total_aliases}")
    print(f"   Total embeddings: {total_embeddings}")
    print(f"   Canonical keys: {len(SEED_ALIASES)}")
    
    return True


def verify_seed():
    """Verify that seed data was stored correctly."""
    redis = RedisService()
    
    if not redis.is_connected():
        print("❌ Cannot verify - Redis not connected")
        return
    
    print("\n🔍 Verifying seed data...")
    
    # Check a few aliases
    test_aliases = ["تسجيل", "fees", "قبول", "جدول"]
    
    for alias in test_aliases:
        key = redis.resolve_alias(alias)
        if key:
            print(f"   ✓ '{alias}' -> {key}")
        else:
            print(f"   ❌ '{alias}' not found")
    
    # Get stats
    stats = redis.get_stats()
    print(f"\n📊 Redis Stats:")
    print(f"   Data keys: {stats.get('total_data_keys', 0)}")
    print(f"   Aliases: {stats.get('total_aliases', 0)}")
    print(f"   Embeddings: {stats.get('total_embeddings', 0)}")


if __name__ == "__main__":
    print("🚀 University Assistant - Data Seeder")
    print("=" * 50)
    
    if seed_aliases():
        verify_seed()
    else:
        sys.exit(1)

