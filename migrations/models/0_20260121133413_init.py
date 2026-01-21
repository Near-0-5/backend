from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "users" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
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
COMMENT ON COLUMN "users"."provider" IS 'KAKAO: KAKAO\nGOOGLE: GOOGLE';
COMMENT ON COLUMN "users"."bio" IS '자기소개';
COMMENT ON COLUMN "users"."gender" IS 'M: M\nF: F';
CREATE TABLE IF NOT EXISTS "user_cat_favs" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "category" VARCHAR(11) NOT NULL,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "user_id" BIGINT NOT NULL REFERENCES "users" ("id") ON DELETE CASCADE
);
COMMENT ON COLUMN "user_cat_favs"."category" IS 'KPOP: K-POP\nTROT: TROT\nMUSICAL: MUSICAL\nBAND: BAND\nFAN_MEETING: FAN_MEETING\nKOREA_TOUR: KOREA_TOUR';
CREATE TABLE IF NOT EXISTS "users_delete_logs" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "user_id" BIGINT NOT NULL,
    "email" VARCHAR(100),
    "reason" VARCHAR(200),
    "deleted_at" TIMESTAMPTZ NOT NULL,
    "deleted_by" VARCHAR(50) NOT NULL,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS "artists" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
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
COMMENT ON COLUMN "artists"."stage_name" IS '활동명';
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
    "created_at" DATE NOT NULL,
    "updated_at" DATE NOT NULL
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
    "title" VARCHAR(100) NOT NULL,
    "message" TEXT NOT NULL,
    "send_at" TIMESTAMPTZ,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "session_id" BIGINT NOT NULL REFERENCES "concert_sessions" ("id") ON DELETE CASCADE,
    "user_id" BIGINT NOT NULL REFERENCES "users" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_concert_not_user_id_f2899e" UNIQUE ("user_id", "session_id")
);
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
)
