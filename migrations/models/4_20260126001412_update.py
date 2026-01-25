from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP INDEX IF EXISTS "idx_concert_not_kind_db2561";
        ALTER TABLE "concert_notis" ADD "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP;
        ALTER TABLE "concert_notis" ALTER COLUMN "status" TYPE VARCHAR(10) USING "status"::VARCHAR(10);
        COMMENT ON COLUMN "concert_notis"."status" IS 'PENDING: PENDING
PROCESSING: PROCESSING
SENT: SENT
FAILED: FAILED';
        ALTER TABLE "concert_notis" ALTER COLUMN "send_at" SET NOT NULL;
        CREATE INDEX IF NOT EXISTS "idx_concert_not_send_at_c2b253" ON "concert_notis" ("send_at");"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP INDEX IF EXISTS "idx_concert_not_send_at_c2b253";
        ALTER TABLE "concert_notis" DROP COLUMN "updated_at";
        COMMENT ON COLUMN "concert_notis"."status" IS 'PENDING: PENDING
SENT: SENT
FAILED: FAILED';
        ALTER TABLE "concert_notis" ALTER COLUMN "status" TYPE VARCHAR(7) USING "status"::VARCHAR(7);
        ALTER TABLE "concert_notis" ALTER COLUMN "send_at" DROP NOT NULL;
        CREATE INDEX IF NOT EXISTS "idx_concert_not_kind_db2561" ON "concert_notis" ("kind");"""


MODELS_STATE = (
    "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"
)
