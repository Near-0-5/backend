from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "concert_notis" DROP CONSTRAINT IF EXISTS "fk_concert__concerts_2d60fb75";
        ALTER TABLE "stream_vods" DROP CONSTRAINT IF EXISTS "fk_stream_v_concerts_17cdf2da";
        ALTER TABLE "stream_sessions" DROP CONSTRAINT IF EXISTS "fk_stream_s_concerts_cc6f4c28";
        ALTER TABLE "stream_channels" DROP CONSTRAINT IF EXISTS "fk_stream_c_concerts_b49d9c2f";
        ALTER TABLE "concert_artists" DROP CONSTRAINT IF EXISTS "uid_concert_art_artist__e5e282";
        ALTER TABLE "concert_artists" DROP CONSTRAINT IF EXISTS "fk_concert__concerts_671c83ea";
        CREATE TABLE IF NOT EXISTS "concert_sessions" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "session_name" VARCHAR(50) NOT NULL,
    "status" VARCHAR(20) NOT NULL DEFAULT 'READY',
    "access_level" VARCHAR(20) NOT NULL DEFAULT 'PUBLIC',
    "is_test" BOOL NOT NULL DEFAULT False,
    "start_at" TIMESTAMPTZ NOT NULL,
    "end_at" TIMESTAMPTZ,
    "concert_id" INT NOT NULL REFERENCES "concerts" ("id") ON DELETE CASCADE
);
COMMENT ON COLUMN "concert_sessions"."session_name" IS '회차 명칭 (예: 1회차, 서울공연)';
COMMENT ON COLUMN "concert_sessions"."status" IS '방송 통로 상태 (READY, LIVE, ENDED)';
COMMENT ON COLUMN "concert_sessions"."access_level" IS '접근 권한';
COMMENT ON COLUMN "concert_sessions"."is_test" IS '테스트/실제 구분';
COMMENT ON COLUMN "concert_sessions"."start_at" IS '공연 예정 시각';
COMMENT ON COLUMN "concert_sessions"."end_at" IS '종료 예정 시각';
COMMENT ON TABLE "concert_sessions" IS '콘서트 회차별 정보';
        ALTER TABLE "concerts" DROP COLUMN "start_at";
        ALTER TABLE "concerts" DROP COLUMN "access_level";
        ALTER TABLE "concerts" DROP COLUMN "is_test";
        ALTER TABLE "concerts" DROP COLUMN "end_at";
        ALTER TABLE "concerts" DROP COLUMN "status";
        ALTER TABLE "concert_artists" RENAME COLUMN "concert_id" TO "session_id";
        ALTER TABLE "stream_channels" RENAME COLUMN "concert_id" TO "session_id";
        ALTER TABLE "stream_sessions" ADD "session_id" INT NOT NULL;
        ALTER TABLE "stream_sessions" DROP COLUMN "concert_id";
        ALTER TABLE "stream_vods" ADD "session_id" INT NOT NULL;
        ALTER TABLE "stream_vods" DROP COLUMN "concert_id";
        ALTER TABLE "concert_notis" RENAME COLUMN "concert_id" TO "session_id";
        COMMENT ON COLUMN "stream_sessions"."session_id" IS '연결된 공연 회차 참조';
COMMENT ON COLUMN "stream_vods"."session_id" IS '연결된 공연 회차 참조';
        ALTER TABLE "concert_artists" ADD CONSTRAINT "fk_concert__concert__ec6801cd" FOREIGN KEY ("session_id") REFERENCES "concert_sessions" ("id") ON DELETE CASCADE;
        CREATE UNIQUE INDEX IF NOT EXISTS "uid_concert_art_artist__fcdbd0" ON "concert_artists" ("artist_id", "session_id");
        ALTER TABLE "stream_channels" ADD CONSTRAINT "fk_stream_c_concert__d9da02b2" FOREIGN KEY ("session_id") REFERENCES "concert_sessions" ("id") ON DELETE CASCADE;
        ALTER TABLE "stream_sessions" ADD CONSTRAINT "fk_stream_s_concert__4c1aeec2" FOREIGN KEY ("session_id") REFERENCES "concert_sessions" ("id") ON DELETE CASCADE;
        ALTER TABLE "stream_vods" ADD CONSTRAINT "fk_stream_v_concert__e915f986" FOREIGN KEY ("session_id") REFERENCES "concert_sessions" ("id") ON DELETE CASCADE;
        ALTER TABLE "concert_notis" ADD CONSTRAINT "fk_concert__concert__f01e92f7" FOREIGN KEY ("session_id") REFERENCES "concert_sessions" ("id") ON DELETE CASCADE;
        CREATE UNIQUE INDEX IF NOT EXISTS "uid_concert_not_user_id_f2899e" ON "concert_notis" ("user_id", "session_id");"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "stream_sessions" DROP CONSTRAINT IF EXISTS "fk_stream_s_concert__4c1aeec2";
        ALTER TABLE "stream_channels" DROP CONSTRAINT IF EXISTS "fk_stream_c_concert__d9da02b2";
        DROP INDEX IF EXISTS "uid_concert_art_artist__fcdbd0";
        ALTER TABLE "concert_artists" DROP CONSTRAINT IF EXISTS "fk_concert__concert__ec6801cd";
        DROP INDEX IF EXISTS "uid_concert_not_user_id_f2899e";
        ALTER TABLE "concert_notis" DROP CONSTRAINT IF EXISTS "fk_concert__concert__f01e92f7";
        ALTER TABLE "stream_vods" DROP CONSTRAINT IF EXISTS "fk_stream_v_concert__e915f986";
        ALTER TABLE "concerts" ADD "start_at" TIMESTAMPTZ NOT NULL;
        ALTER TABLE "concerts" ADD "access_level" VARCHAR(20) NOT NULL DEFAULT 'PUBLIC';
        ALTER TABLE "concerts" ADD "is_test" BOOL NOT NULL DEFAULT False;
        ALTER TABLE "concerts" ADD "end_at" TIMESTAMPTZ;
        ALTER TABLE "concerts" ADD "status" VARCHAR(20) NOT NULL DEFAULT 'READY';
        ALTER TABLE "stream_vods" ADD "concert_id" INT NOT NULL;
        ALTER TABLE "stream_vods" DROP COLUMN "session_id";
        ALTER TABLE "concert_notis" RENAME COLUMN "session_id" TO "concert_id";
        ALTER TABLE "concert_artists" RENAME COLUMN "session_id" TO "concert_id";
        ALTER TABLE "stream_channels" RENAME COLUMN "session_id" TO "concert_id";
        ALTER TABLE "stream_sessions" ADD "concert_id" INT NOT NULL;
        ALTER TABLE "stream_sessions" DROP COLUMN "session_id";
        COMMENT ON COLUMN "concerts"."start_at" IS '공연 예정 시각';
COMMENT ON COLUMN "concerts"."access_level" IS '접근 권한';
COMMENT ON COLUMN "concerts"."is_test" IS '테스트/실제 구분';
COMMENT ON COLUMN "concerts"."end_at" IS '종료 예정 시각';
COMMENT ON COLUMN "concerts"."status" IS '방송 통로 상태 (READY, LIVE, ENDED)';
COMMENT ON COLUMN "stream_vods"."concert_id" IS '연결된 공연 참조';
COMMENT ON COLUMN "stream_sessions"."concert_id" IS '연결된 공연 참조';
        DROP TABLE IF EXISTS "concert_sessions";
        ALTER TABLE "stream_vods" ADD CONSTRAINT "fk_stream_v_concerts_17cdf2da" FOREIGN KEY ("concert_id") REFERENCES "concerts" ("id") ON DELETE CASCADE;
        ALTER TABLE "concert_notis" ADD CONSTRAINT "fk_concert__concerts_2d60fb75" FOREIGN KEY ("concert_id") REFERENCES "concerts" ("id") ON DELETE CASCADE;
        ALTER TABLE "concert_artists" ADD CONSTRAINT "fk_concert__concerts_671c83ea" FOREIGN KEY ("concert_id") REFERENCES "concerts" ("id") ON DELETE CASCADE;
        CREATE UNIQUE INDEX IF NOT EXISTS "uid_concert_art_artist__e5e282" ON "concert_artists" ("artist_id", "concert");
        ALTER TABLE "stream_channels" ADD CONSTRAINT "fk_stream_c_concerts_b49d9c2f" FOREIGN KEY ("concert_id") REFERENCES "concerts" ("id") ON DELETE CASCADE;
        ALTER TABLE "stream_sessions" ADD CONSTRAINT "fk_stream_s_concerts_cc6f4c28" FOREIGN KEY ("concert_id") REFERENCES "concerts" ("id") ON DELETE CASCADE;"""


MODELS_STATE = (
    "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"
)
