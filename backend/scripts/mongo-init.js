/**
 * mongo-init.js — runs automatically inside the MongoDB Docker container
 * via the /docker-entrypoint-initdb.d/ mechanism.
 *
 * Creates the database, collections, indexes, and seeds one admin user.
 * Run manually with:
 *   mongosh "mongodb://localhost:27017/ai_meeting_analyzer" mongo-init.js
 */

// ── Switch to application database ───────────────────────────────────────────
db = db.getSiblingDB("ai_meeting_analyzer");

print("🚀 Initialising AI Meeting Analyzer database...");


// ══════════════════════════════════════════════════════════════════════════════
// COLLECTIONS — create explicitly so validators are attached from the start
// ══════════════════════════════════════════════════════════════════════════════

// users
db.createCollection("users", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["email", "password", "full_name", "role"],
      properties: {
        email:     { bsonType: "string",  description: "Must be a string and is required" },
        password:  { bsonType: "binData", description: "Bcrypt hash stored as BinData" },
        full_name: { bsonType: "string" },
        role:      { bsonType: "string", enum: ["user", "admin"] },
        is_active: { bsonType: "bool" },
      },
    },
  },
  validationAction: "warn",   // warn, not error — allows legacy inserts during dev
});
print("  ✓ Collection: users");

// meetings
db.createCollection("meetings", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["user_id", "title", "status"],
      properties: {
        user_id:          { bsonType: "objectId" },
        title:            { bsonType: "string" },
        status:           { bsonType: "string",
                            enum: ["pending","uploading","transcribing",
                                   "analyzing","completed","failed"] },
        duration_seconds: { bsonType: ["int","long","double","null"] },
        is_deleted:       { bsonType: "bool" },
      },
    },
  },
  validationAction: "warn",
});
print("  ✓ Collection: meetings");

// transcripts
db.createCollection("transcripts", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["meeting_id", "full_text"],
      properties: {
        meeting_id: { bsonType: "objectId" },
        full_text:  { bsonType: "string" },
        segments:   { bsonType: "array" },
        language:   { bsonType: "string" },
      },
    },
  },
  validationAction: "warn",
});
print("  ✓ Collection: transcripts");

// analyses
db.createCollection("analyses", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["meeting_id"],
      properties: {
        meeting_id:   { bsonType: "objectId" },
        action_items: { bsonType: "array" },
        decisions:    { bsonType: "array" },
        keywords:     { bsonType: "array" },
        topics:       { bsonType: "array" },
        entities:     { bsonType: "array" },
      },
    },
  },
  validationAction: "warn",
});
print("  ✓ Collection: analyses");

// token_blocklist
db.createCollection("token_blocklist");
print("  ✓ Collection: token_blocklist");


// ══════════════════════════════════════════════════════════════════════════════
// INDEXES
// ══════════════════════════════════════════════════════════════════════════════

// users
db.users.createIndex({ email: 1 }, { unique: true, name: "idx_users_email" });
db.users.createIndex({ role: 1 },  { name: "idx_users_role" });
print("  ✓ Indexes: users");

// meetings
db.meetings.createIndex({ user_id: 1 },                  { name: "idx_meetings_user_id" });
db.meetings.createIndex({ status: 1 },                   { name: "idx_meetings_status" });
db.meetings.createIndex({ created_at: -1 },              { name: "idx_meetings_created_at" });
db.meetings.createIndex({ user_id: 1, is_deleted: 1 },  { name: "idx_meetings_user_deleted" });
db.meetings.createIndex(
  { title: "text", ai_title: "text" },
  { name: "idx_meetings_text_search", weights: { title: 2, ai_title: 1 } }
);
print("  ✓ Indexes: meetings");

// transcripts
db.transcripts.createIndex(
  { meeting_id: 1 },
  { unique: true, name: "idx_transcripts_meeting_id" }
);
db.transcripts.createIndex(
  { full_text: "text" },
  { name: "idx_transcripts_fulltext" }
);
print("  ✓ Indexes: transcripts");

// analyses
db.analyses.createIndex(
  { meeting_id: 1 },
  { unique: true, name: "idx_analyses_meeting_id" }
);
print("  ✓ Indexes: analyses");

// token_blocklist — TTL index auto-purges expired entries
db.token_blocklist.createIndex(
  { expires_at: 1 },
  { expireAfterSeconds: 0, name: "idx_blocklist_ttl" }
);
db.token_blocklist.createIndex({ jti: 1 }, { unique: true, name: "idx_blocklist_jti" });
print("  ✓ Indexes: token_blocklist (TTL)");


// ══════════════════════════════════════════════════════════════════════════════
// SEED DATA — default admin user
// Password "Admin@1234" (bcrypt hash — replace with your own in production)
// ══════════════════════════════════════════════════════════════════════════════

const adminExists = db.users.findOne({ email: "admin@meetinganalyzer.app" });
if (!adminExists) {
  // NOTE: this is a pre-computed bcrypt hash of "Admin@1234" (12 rounds).
  // Generate a fresh one in Python:  bcrypt.hashpw(b"Admin@1234", bcrypt.gensalt())
  db.users.insertOne({
    _id:        new ObjectId(),
    email:      "admin@meetinganalyzer.app",
    // placeholder hash — Python app will re-hash on first password change
    password:   new BinData(0, "JDJiJDEyJGhFb01TSDJEd0hkeDQ3VnFaMkVkRi5rM3ZhV3k5M2VQMWwwREMuZjdJQTVnMXhFTXlqY1Iy"),
    full_name:  "System Admin",
    role:       "admin",
    avatar_url: null,
    preferences: {
      dark_mode:        false,
      email_notify:     true,
      default_language: "en",
    },
    is_active:  true,
    last_login: null,
    created_at: new Date(),
    updated_at: new Date(),
  });
  print("  ✓ Seed: admin user created (admin@meetinganalyzer.app / Admin@1234)");
} else {
  print("  ℹ  Seed: admin user already exists — skipped");
}


// ══════════════════════════════════════════════════════════════════════════════
// DEMO USER (development only)
// ══════════════════════════════════════════════════════════════════════════════

const demoExists = db.users.findOne({ email: "demo@meetinganalyzer.app" });
if (!demoExists) {
  db.users.insertOne({
    _id:        new ObjectId(),
    email:      "demo@meetinganalyzer.app",
    password:   new BinData(0, "JDJiJDEyJGhFb01TSDJEd0hkeDQ3VnFaMkVkRi5rM3ZhV3k5M2VQMWwwREMuZjdJQTVnMXhFTXlqY1Iy"),
    full_name:  "Demo User",
    role:       "user",
    avatar_url: null,
    preferences: {
      dark_mode:        true,
      email_notify:     false,
      default_language: "en",
    },
    is_active:  true,
    last_login: null,
    created_at: new Date(),
    updated_at: new Date(),
  });
  print("  ✓ Seed: demo user created  (demo@meetinganalyzer.app / Admin@1234)");
}

print("\n✅ Database initialisation complete.");
print("   Collections : users, meetings, transcripts, analyses, token_blocklist");
print("   Indexes     : 13 indexes created");
print("   Seed users  : admin@meetinganalyzer.app, demo@meetinganalyzer.app");
print("   ⚠️  Change default passwords before deploying to production!\n");
