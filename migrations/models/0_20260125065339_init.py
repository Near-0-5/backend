from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "users" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "provider" VARCHAR(20) NOT NULL,
    "provider_id" VARCHAR(255) NOT NULL UNIQUE,
    "email" VARCHAR(100),
    "real_name" VARCHAR(50),
    "nickname" VARCHAR(30) NOT NULL UNIQUE,
    "profile_img_url" VARCHAR(255),
    "bio" TEXT,
    "gender" VARCHAR(1),
    "phone_number" VARCHAR(20),
    "birth_date" DATE,
    "is_superuser" BOOL NOT NULL DEFAULT False,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON COLUMN "users"."provider" IS 'KAKAO: KAKAO\nGOOGLE: GOOGLE\nNAVER: NAVER';
COMMENT ON COLUMN "users"."bio" IS '자기소개';
COMMENT ON COLUMN "users"."gender" IS 'M: M\nF: F';
CREATE TABLE IF NOT EXISTS "user_cat_favs" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "category" VARCHAR(11) NOT NULL,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "user_id" BIGINT NOT NULL REFERENCES "users" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_user_cat_fa_user_id_b7482a" UNIQUE ("user_id", "category")
);
COMMENT ON COLUMN "user_cat_favs"."category" IS 'KPOP: K-POP\nTROT: TROT\nMUSICAL: MUSICAL\nBAND: BAND\nFAN_MEETING: FAN_MEETING\nKOREA_TOUR: KOREA_TOUR';
CREATE TABLE IF NOT EXISTS "users_delete_logs" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "email" VARCHAR(100),
    "reason" VARCHAR(200),
    "deleted_at" TIMESTAMPTZ NOT NULL,
    "deleted_by" VARCHAR(50) NOT NULL,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "user_id" BIGINT REFERENCES "users" ("id") ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS "artists" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "stage_name" VARCHAR(100) NOT NULL,
    "category_type" VARCHAR(20),
    "profile_img_url" VARCHAR(255),
    "agency" VARCHAR(100),
    "description" TEXT,
    "debut_date" DATE,
    "member_count" INT,
    "group_type" VARCHAR(50),
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON COLUMN "artists"."stage_name" IS '활동명';
COMMENT ON COLUMN "artists"."category_type" IS 'KPOP: K-POP\nTROT: TROT\nMUSICAL: MUSICAL\nBAND: BAND\nFAN_MEETING: FAN_MEETING\nKOREA_TOUR: KOREA_TOUR';
COMMENT ON COLUMN "artists"."group_type" IS 'SOLO: SOLO\nGIRL_GROUP: GIRL_GROUP\nBOY_BAND: BOY_BAND\nMIXED_GROUP: MIXED_GROUP';
CREATE TABLE IF NOT EXISTS "follows" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "artist_id" BIGINT NOT NULL REFERENCES "artists" ("id") ON DELETE CASCADE,
    "user_id" BIGINT NOT NULL REFERENCES "users" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_follows_user_id_10d6f7" UNIQUE ("user_id", "artist_id")
);
CREATE TABLE IF NOT EXISTS "concerts" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "category" VARCHAR(11) NOT NULL DEFAULT 'K-POP',
    "title" VARCHAR(100) NOT NULL,
    "thumbnail_url" VARCHAR(255),
    "description" TEXT,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS "idx_concerts_categor_94d1d1" ON "concerts" ("category");
COMMENT ON COLUMN "concerts"."category" IS '장르(category)';
COMMENT ON COLUMN "concerts"."title" IS '공연 제목';
COMMENT ON COLUMN "concerts"."thumbnail_url" IS '공연 썸네일 사진(포스터 등)';
COMMENT ON COLUMN "concerts"."description" IS '콘서트 소개 글';
COMMENT ON COLUMN "concerts"."created_at" IS '생성시각';
COMMENT ON COLUMN "concerts"."updated_at" IS '수정시각';
COMMENT ON TABLE "concerts" IS '공연 메타 데이터';
CREATE TABLE IF NOT EXISTS "concert_sessions" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "session_name" VARCHAR(50) NOT NULL,
    "status" VARCHAR(20) NOT NULL DEFAULT 'READY',
    "access_level" VARCHAR(20) NOT NULL DEFAULT 'PUBLIC',
    "is_test" BOOL NOT NULL DEFAULT False,
    "start_at" TIMESTAMPTZ NOT NULL,
    "end_at" TIMESTAMPTZ,
    "concert_id" BIGINT NOT NULL REFERENCES "concerts" ("id") ON DELETE CASCADE
);
COMMENT ON COLUMN "concert_sessions"."session_name" IS '회차 명칭 (예: 1회차, 서울공연)';
COMMENT ON COLUMN "concert_sessions"."status" IS '방송 통로 상태 (READY, LIVE, ENDED)';
COMMENT ON COLUMN "concert_sessions"."access_level" IS '접근 권한';
COMMENT ON COLUMN "concert_sessions"."is_test" IS '테스트/실제 구분';
COMMENT ON COLUMN "concert_sessions"."start_at" IS '공연 예정 시각';
COMMENT ON COLUMN "concert_sessions"."end_at" IS '종료 예정 시각';
COMMENT ON TABLE "concert_sessions" IS '콘서트 회차별 정보';
CREATE TABLE IF NOT EXISTS "concert_artists" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "is_main" BOOL NOT NULL DEFAULT True,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "artist_id" BIGINT NOT NULL REFERENCES "artists" ("id") ON DELETE CASCADE,
    "session_id" BIGINT NOT NULL REFERENCES "concert_sessions" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_concert_art_artist__fcdbd0" UNIQUE ("artist_id", "session_id")
);
COMMENT ON COLUMN "concert_artists"."is_main" IS '해당 공연의 메인 출연진 여부';
COMMENT ON COLUMN "concert_artists"."created_at" IS '출연 확정/등록 시각';
COMMENT ON COLUMN "concert_artists"."artist_id" IS '출연 아티스트 참조';
COMMENT ON COLUMN "concert_artists"."session_id" IS '연결된 공연 참조';
COMMENT ON TABLE "concert_artists" IS '콘서트-출연진 매핑 테이블';
CREATE TABLE IF NOT EXISTS "stream_channels" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "type" VARCHAR(11) NOT NULL DEFAULT 'STANDARD',
    "latency_mode" VARCHAR(6) NOT NULL DEFAULT 'LOW',
    "transcoding_preset" VARCHAR(3),
    "is_private" BOOL NOT NULL DEFAULT True,
    "is_record" BOOL NOT NULL DEFAULT False,
    "channel_arn" VARCHAR(255) NOT NULL UNIQUE,
    "ingest_endpoint" VARCHAR(255) NOT NULL,
    "playback_url" VARCHAR(255) NOT NULL,
    "stream_key_encrypted" TEXT NOT NULL,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "session_id" BIGINT NOT NULL UNIQUE REFERENCES "concert_sessions" ("id") ON DELETE CASCADE
);
COMMENT ON COLUMN "stream_channels"."type" IS '채널 타입(STANDARD, BASIC 등)';
COMMENT ON COLUMN "stream_channels"."latency_mode" IS '지연모드 (LOW, NORMAL)';
COMMENT ON COLUMN "stream_channels"."transcoding_preset" IS 'Advanced 채널용 트랜스코딩 품질 프리셋 (HBD, CBD)';
COMMENT ON COLUMN "stream_channels"."is_private" IS '비공개 여부 (Playback 토큰 인증 필요)';
COMMENT ON COLUMN "stream_channels"."is_record" IS '방송 녹화 및 VOD  생성 여부';
COMMENT ON COLUMN "stream_channels"."channel_arn" IS 'AWS IVS 채널 고유 리소스 이름';
COMMENT ON COLUMN "stream_channels"."ingest_endpoint" IS 'OBS(송출 장비)에 설정할 RTMP 서버 주소';
COMMENT ON COLUMN "stream_channels"."playback_url" IS '사용자 플레이어에서 재생할 .m3u8 주소';
COMMENT ON COLUMN "stream_channels"."stream_key_encrypted" IS 'Fernet으로 암호화된 스트림 키 (송출 권한)';
COMMENT ON COLUMN "stream_channels"."session_id" IS '연결된 공연 (1:1)';
COMMENT ON TABLE "stream_channels" IS 'AWS IVS 채널 설정 관리 테이블';
CREATE TABLE IF NOT EXISTS "stream_sessions" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "stream_id" VARCHAR(255) NOT NULL UNIQUE,
    "started_at" TIMESTAMPTZ NOT NULL,
    "ended_at" TIMESTAMPTZ,
    "peak_viewers" INT NOT NULL DEFAULT 0,
    "session_id" BIGINT NOT NULL REFERENCES "concert_sessions" ("id") ON DELETE CASCADE
);
COMMENT ON COLUMN "stream_sessions"."stream_id" IS 'AWS IVS에서 발급한 해당 방송 세션의 고유 ID';
COMMENT ON COLUMN "stream_sessions"."started_at" IS '실제 송출 시작 시각';
COMMENT ON COLUMN "stream_sessions"."ended_at" IS '송출 종료 시각';
COMMENT ON COLUMN "stream_sessions"."peak_viewers" IS '해당 세션의 최대 동시 시청자 수';
COMMENT ON COLUMN "stream_sessions"."session_id" IS '연결된 공연 회차 참조';
COMMENT ON TABLE "stream_sessions" IS '실제 방송 송출 이력 (session) 테이블';
CREATE TABLE IF NOT EXISTS "stream_vods" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "s3_bucket" VARCHAR(100) NOT NULL,
    "s3_key_prefix" VARCHAR(255) NOT NULL,
    "vod_url" VARCHAR(255) NOT NULL,
    "file_name" VARCHAR(150) NOT NULL DEFAULT 'master.m3u8',
    "processing_status" VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "session_id" BIGINT NOT NULL REFERENCES "concert_sessions" ("id") ON DELETE CASCADE
);
COMMENT ON COLUMN "stream_vods"."s3_bucket" IS '저장 당시 S3 버킷 이름';
COMMENT ON COLUMN "stream_vods"."s3_key_prefix" IS 'S3 내 저장 폴더 경로';
COMMENT ON COLUMN "stream_vods"."vod_url" IS '시청자용 재생 URL (CloudFront 주소 등)';
COMMENT ON COLUMN "stream_vods"."file_name" IS '메인 인덱스 파일 이름';
COMMENT ON COLUMN "stream_vods"."processing_status" IS '처리 상태: PENDING(대기), COMPLETED(완료), FAILED(실패)';
COMMENT ON COLUMN "stream_vods"."created_at" IS 'VOD 생성/등록 시각';
COMMENT ON COLUMN "stream_vods"."session_id" IS '연결된 공연 회차 참조';
COMMENT ON TABLE "stream_vods" IS '방송 종료 후 생성된 VOD(다시보기) 관리 테이블';
CREATE TABLE IF NOT EXISTS "concert_notis" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "kind" VARCHAR(10) NOT NULL,
    "title" VARCHAR(100) NOT NULL,
    "message" TEXT NOT NULL,
    "send_at" TIMESTAMPTZ NOT NULL,
    "status" VARCHAR(10) NOT NULL DEFAULT 'PENDING',
    "sent_at" TIMESTAMPTZ,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "session_id" BIGINT NOT NULL REFERENCES "concert_sessions" ("id") ON DELETE CASCADE,
    "user_id" BIGINT NOT NULL REFERENCES "users" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_concert_not_user_id_1e5a03" UNIQUE ("user_id", "session_id", "kind")
);
CREATE INDEX IF NOT EXISTS "idx_concert_not_kind_db2561" ON "concert_notis" ("kind");
CREATE INDEX IF NOT EXISTS "idx_concert_not_send_at_c2b253" ON "concert_notis" ("send_at");
CREATE INDEX IF NOT EXISTS "idx_concert_not_status_63359b" ON "concert_notis" ("status");
CREATE INDEX IF NOT EXISTS "idx_concert_not_status_d101c2" ON "concert_notis" ("status", "send_at");
COMMENT ON COLUMN "concert_notis"."kind" IS 'DAY_BEFORE: DAY_BEFORE\nHOUR_1: HOUR_1\nMIN_30: MIN_30\nSTART: START';
COMMENT ON COLUMN "concert_notis"."status" IS 'PENDING: PENDING\nPROCESSING: PROCESSING\nSENT: SENT\nFAILED: FAILED';
CREATE TABLE IF NOT EXISTS "user_notis" (
    "artist_noti" BOOL NOT NULL DEFAULT True,
    "live_noti" BOOL NOT NULL DEFAULT True,
    "marketing_noti" BOOL NOT NULL DEFAULT False,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "user_id" BIGINT NOT NULL PRIMARY KEY REFERENCES "users" ("id") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "aerich" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "version" VARCHAR(255) NOT NULL,
    "app" VARCHAR(100) NOT NULL,
    "content" JSONB NOT NULL
);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        """


MODELS_STATE = (
    "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"
    "/h9OzKph"
)
