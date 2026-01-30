from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name = 'admin_users'
            ) THEN
                IF EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'admin_users'
                      AND column_name = 'hashed_password'
                ) THEN
                    ALTER TABLE "admin_users" RENAME COLUMN "hashed_password" TO "hash_password";
                ELSIF EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'admin_users'
                      AND column_name = 'password'
                ) THEN
                    ALTER TABLE "admin_users" RENAME COLUMN "password" TO "hash_password";
                ELSIF NOT EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'admin_users'
                      AND column_name = 'hash_password'
                ) THEN
                    ALTER TABLE "admin_users" ADD COLUMN "hash_password" VARCHAR(255);
                END IF;
            END IF;
        END $$;
"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        """


MODELS_STATE = (
    "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"
    "0o4qfenScOpoQDgzc+wc2ha+IcOrz8/D+t+2Bn"
)

