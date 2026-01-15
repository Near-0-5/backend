from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "users" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "provider" VARCHAR(20) NOT NULL,
    "provider_id" VARCHAR(255) NOT NULL UNIQUE,
    "email" VARCHAR(100),
    "nickname" VARCHAR(30) NOT NULL UNIQUE,
    "profile_img_url" VARCHAR(255),
    "bio" TEXT,
    "gender" VARCHAR(1),
    "birth_date" DATE,
    "is_superuser" BOOL NOT NULL DEFAULT False,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
        CREATE TABLE IF NOT EXISTS "user_cat_favs" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "category" VARCHAR(11) NOT NULL,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "user_id" INT NOT NULL REFERENCES "users" ("id") ON DELETE CASCADE
);
COMMENT ON COLUMN "user_cat_favs"."category" IS 'KPOP: K-POP\nTROT: TROT\nMUSICAL: MUSICAL\nBAND: BAND\nFAN_MEETING: FAN_MEETING\nKOREA_TOUR: KOREA_TOUR';
        CREATE TABLE IF NOT EXISTS "users_delete_logs" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "user_id" INT NOT NULL,
    "email" VARCHAR(100),
    "reason" VARCHAR(200),
    "deleted_at" TIMESTAMPTZ NOT NULL,
    "deleted_by" VARCHAR(50) NOT NULL,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
        CREATE TABLE IF NOT EXISTS "artists" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "stage_name" VARCHAR(100) NOT NULL,
    "profile_img_url" VARCHAR(255),
    "agency" VARCHAR(100),
    "description" TEXT,
    "debut_date" DATE,
    "member_count" INT,
    "group_type" VARCHAR(50),
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
        CREATE TABLE IF NOT EXISTS "follows" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "artist_id" INT NOT NULL REFERENCES "artists" ("id") ON DELETE CASCADE,
    "user_id" INT NOT NULL REFERENCES "users" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_follows_user_id_10d6f7" UNIQUE ("user_id", "artist_id")
);
        CREATE TABLE IF NOT EXISTS "concerts" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "category" VARCHAR(11) NOT NULL,
    "title" VARCHAR(100),
    "thumbnail_url" VARCHAR(255),
    "start_at" TIMESTAMPTZ,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON COLUMN "concerts"."category" IS 'KPOP: K-POP\nTROT: TROT\nMUSICAL: MUSICAL\nBAND: BAND\nFAN_MEETING: FAN_MEETING\nKOREA_TOUR: KOREA_TOUR';
        CREATE TABLE IF NOT EXISTS "concert_artists" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "is_main" BOOL NOT NULL DEFAULT True,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "artist_id" INT NOT NULL REFERENCES "artists" ("id") ON DELETE CASCADE,
    "concert_id" INT NOT NULL REFERENCES "concerts" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_concert_art_concert_1be5bf" UNIQUE ("concert_id", "artist_id")
);
        CREATE TABLE IF NOT EXISTS "stream_channels" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "type" VARCHAR(11) NOT NULL DEFAULT 'STANDARD',
    "latency_mode" VARCHAR(6) NOT NULL DEFAULT 'LOW',
    "transcoding_preset" VARCHAR(3),
    "is_private" BOOL NOT NULL DEFAULT True,
    "is_record" BOOL NOT NULL DEFAULT False,
    "channel_arn" VARCHAR(255) NOT NULL UNIQUE,
    "ingest_endpoint" VARCHAR(255) NOT NULL,
    "playback_url" VARCHAR(255) NOT NULL,
    "stream_key_encrypted" TEXT NOT NULL,
    "status" VARCHAR(20) NOT NULL DEFAULT 'READY',
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "concert_id" INT NOT NULL UNIQUE REFERENCES "concerts" ("id") ON DELETE CASCADE
);
COMMENT ON COLUMN "stream_channels"."type" IS 'STANDARD: STANDARD\nADVANCED_SD: ADVANCED_SD\nADVANCED_HD: ADVANCED_HD\nBASIC: BASIC';
COMMENT ON COLUMN "stream_channels"."latency_mode" IS 'LOW: LOW\nNORMAL: NORMAL';
COMMENT ON COLUMN "stream_channels"."transcoding_preset" IS 'HBD: HBD\nCBD: CBD';
        CREATE TABLE IF NOT EXISTS "stream_sessions" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "stream_id" VARCHAR(255) NOT NULL UNIQUE,
    "started_at" TIMESTAMPTZ NOT NULL,
    "ended_at" TIMESTAMPTZ,
    "peak_viewers" INT NOT NULL DEFAULT 0,
    "concert_id" INT NOT NULL REFERENCES "concerts" ("id") ON DELETE CASCADE
);
        CREATE TABLE IF NOT EXISTS "stream_vods" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "s3_bucket" VARCHAR(100) NOT NULL,
    "s3_key_prefix" VARCHAR(255) NOT NULL,
    "vod_url" VARCHAR(255) NOT NULL,
    "file_name" VARCHAR(150) NOT NULL DEFAULT 'master.m3u8',
    "processing_status" VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "concert_id" INT NOT NULL REFERENCES "concerts" ("id") ON DELETE CASCADE
);
        CREATE TABLE IF NOT EXISTS "concert_notis" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "title" VARCHAR(100) NOT NULL,
    "message" TEXT NOT NULL,
    "send_at" TIMESTAMPTZ,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "concert_id" INT NOT NULL REFERENCES "concerts" ("id") ON DELETE CASCADE,
    "user_id" INT NOT NULL REFERENCES "users" ("id") ON DELETE CASCADE
);
        CREATE TABLE IF NOT EXISTS "user_notis" (
    "artist_noti" BOOL NOT NULL DEFAULT True,
    "live_noti" BOOL NOT NULL DEFAULT True,
    "marketing_noti" BOOL NOT NULL DEFAULT False,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "user_id" INT NOT NULL PRIMARY KEY REFERENCES "users" ("id") ON DELETE CASCADE
);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP TABLE IF EXISTS "artists";
        DROP TABLE IF EXISTS "stream_sessions";
        DROP TABLE IF EXISTS "user_cat_favs";
        DROP TABLE IF EXISTS "user_notis";
        DROP TABLE IF EXISTS "users_delete_logs";
        DROP TABLE IF EXISTS "stream_channels";
        DROP TABLE IF EXISTS "follows";
        DROP TABLE IF EXISTS "concerts";
        DROP TABLE IF EXISTS "concert_artists";
        DROP TABLE IF EXISTS "stream_vods";
        DROP TABLE IF EXISTS "concert_notis";
        DROP TABLE IF EXISTS "users";"""


MODELS_STATE = (
    "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"
)
