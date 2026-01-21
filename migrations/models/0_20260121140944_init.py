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
    "wdWuCwfsOr38+D+oXMWI"
)
