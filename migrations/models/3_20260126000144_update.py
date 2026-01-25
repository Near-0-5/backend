from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "concert_notis" DROP CONSTRAINT IF EXISTS "uid_concert_not_user_id_f2899e";
        ALTER TABLE "concert_notis" ADD "sent_at" TIMESTAMPTZ;
        ALTER TABLE "concert_notis" ADD "status" VARCHAR(7) NOT NULL DEFAULT 'PENDING';
        ALTER TABLE "concert_notis" ADD "kind" VARCHAR(6) NOT NULL;
        COMMENT ON COLUMN "concert_notis"."status" IS 'PENDING: PENDING\nSENT: SENT\nFAILED: FAILED';
COMMENT ON COLUMN "concert_notis"."kind" IS 'HOUR_1: HOUR_1\nMIN_30: MIN_30\nSTART: START';
        CREATE UNIQUE INDEX IF NOT EXISTS "uid_concert_not_user_id_1e5a03" ON "concert_notis" ("user_id", "session_id", "kind");
        CREATE INDEX IF NOT EXISTS "idx_concert_not_status_d101c2" ON "concert_notis" ("status", "send_at");
        CREATE INDEX IF NOT EXISTS "idx_concert_not_status_63359b" ON "concert_notis" ("status");
        CREATE INDEX IF NOT EXISTS "idx_concert_not_kind_db2561" ON "concert_notis" ("kind");"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP INDEX IF EXISTS "idx_concert_not_kind_db2561";
        DROP INDEX IF EXISTS "idx_concert_not_status_63359b";
        DROP INDEX IF EXISTS "idx_concert_not_status_d101c2";
        DROP INDEX IF EXISTS "uid_concert_not_user_id_1e5a03";
        ALTER TABLE "concert_notis" DROP COLUMN "sent_at";
        ALTER TABLE "concert_notis" DROP COLUMN "status";
        ALTER TABLE "concert_notis" DROP COLUMN "kind";
        CREATE UNIQUE INDEX IF NOT EXISTS "uid_concert_not_user_id_f2899e" ON "concert_notis" ("user_id", "session_id");"""


MODELS_STATE = (
    "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"
    "kYzg+GBm98gqtdV0HZdXj5+X+P/31A"
)
