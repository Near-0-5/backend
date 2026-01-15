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
COMMENT ON COLUMN "users"."provider" IS 'KAKAO: KAKAO\nGOOGLE: GOOGLE';
COMMENT ON COLUMN "users"."bio" IS '자기소개';
COMMENT ON COLUMN "users"."gender" IS 'M: M\nF: F';
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
COMMENT ON COLUMN "artists"."stage_name" IS '활동명';
COMMENT ON COLUMN "artists"."group_type" IS 'SOLO: SOLO\nGIRL_GROUP: GIRL_GROUP\nBOY_BAND: BOY_BAND\nMIXED_GROUP: MIXED_GROUP';
CREATE TABLE IF NOT EXISTS "follows" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "artist_id" INT NOT NULL REFERENCES "artists" ("id") ON DELETE CASCADE,
    "user_id" INT NOT NULL REFERENCES "users" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_follows_user_id_10d6f7" UNIQUE ("user_id", "artist_id")
);
CREATE TABLE IF NOT EXISTS "concerts" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "category" VARCHAR(11) NOT NULL DEFAULT 'K-POP',
    "title" VARCHAR(100) NOT NULL,
    "thumbnail_url" VARCHAR(255),
    "start_at" TIMESTAMPTZ NOT NULL,
    "created_at" DATE NOT NULL,
    "updated_at" DATE NOT NULL
);
CREATE INDEX IF NOT EXISTS "idx_concerts_categor_94d1d1" ON "concerts" ("category");
COMMENT ON COLUMN "concerts"."category" IS '장르(category)';
COMMENT ON COLUMN "concerts"."title" IS '공연 제목';
COMMENT ON COLUMN "concerts"."thumbnail_url" IS '공연 썸네일 사진(포스터 등)';
COMMENT ON COLUMN "concerts"."start_at" IS '공연 예정 시각';
COMMENT ON COLUMN "concerts"."created_at" IS '생성시각';
COMMENT ON COLUMN "concerts"."updated_at" IS '수정시각';
COMMENT ON TABLE "concerts" IS '공연 정보 관리 테이블';
CREATE TABLE IF NOT EXISTS "concert_artists" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "is_main" BOOL NOT NULL DEFAULT True,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "artist_id" INT NOT NULL REFERENCES "artists" ("id") ON DELETE CASCADE,
    "concert_id" INT NOT NULL REFERENCES "concerts" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_concert_art_artist__48a481" UNIQUE ("artist_id", "concert_id")
);
COMMENT ON COLUMN "concert_artists"."is_main" IS '해당 공연의 메인 출연진 여부';
COMMENT ON COLUMN "concert_artists"."created_at" IS '출연 확정/등록 시각';
COMMENT ON COLUMN "concert_artists"."artist_id" IS '출연 아티스트 참조';
COMMENT ON COLUMN "concert_artists"."concert_id" IS '연결된 공연 참조';
COMMENT ON TABLE "concert_artists" IS '콘서트-출연진 매핑 테이블';
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
COMMENT ON COLUMN "stream_channels"."type" IS '채널 타입(STANDARD, BASIC 등)';
COMMENT ON COLUMN "stream_channels"."latency_mode" IS '지연모드 (LOW, NORMAL)';
COMMENT ON COLUMN "stream_channels"."transcoding_preset" IS 'Advanced 채널용 트랜스코딩 품질 프리셋 (HBD, CBD)';
COMMENT ON COLUMN "stream_channels"."is_private" IS '비공개 여부 (Playback 토큰 인증 필요)';
COMMENT ON COLUMN "stream_channels"."is_record" IS '방송 녹화 및 VOD  생성 여부';
COMMENT ON COLUMN "stream_channels"."channel_arn" IS 'AWS IVS 채널 고유 리소스 이름';
COMMENT ON COLUMN "stream_channels"."ingest_endpoint" IS 'OBS(송출 장비)에 설정할 RTMP 서버 주소';
COMMENT ON COLUMN "stream_channels"."playback_url" IS '사용자 플레이어에서 재생할 .m3u8 주소';
COMMENT ON COLUMN "stream_channels"."stream_key_encrypted" IS 'Fernet으로 암호화된 스트림 키 (송출 권한)';
COMMENT ON COLUMN "stream_channels"."status" IS '방송 통로 상태 (READY, LIVE, ENDED)';
COMMENT ON COLUMN "stream_channels"."concert_id" IS '연결된 공연 (1:1)';
COMMENT ON TABLE "stream_channels" IS 'AWS IVS 채널 설정 관리 테이블';
CREATE TABLE IF NOT EXISTS "stream_sessions" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "stream_id" VARCHAR(255) NOT NULL UNIQUE,
    "started_at" TIMESTAMPTZ NOT NULL,
    "ended_at" TIMESTAMPTZ,
    "peak_viewers" INT NOT NULL DEFAULT 0,
    "concert_id" INT NOT NULL REFERENCES "concerts" ("id") ON DELETE CASCADE
);
COMMENT ON COLUMN "stream_sessions"."stream_id" IS 'AWS IVS에서 발급한 해당 방송 세션의 고유 ID';
COMMENT ON COLUMN "stream_sessions"."started_at" IS '실제 송출 시작 시각';
COMMENT ON COLUMN "stream_sessions"."ended_at" IS '송출 종료 시각';
COMMENT ON COLUMN "stream_sessions"."peak_viewers" IS '해당 세션의 최대 동시 시청자 수';
COMMENT ON COLUMN "stream_sessions"."concert_id" IS '연결된 공연 참조';
COMMENT ON TABLE "stream_sessions" IS '실제 방송 송출 이력 (session) 테이블';
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
COMMENT ON COLUMN "stream_vods"."s3_bucket" IS '저장 당시 S3 버킷 이름';
COMMENT ON COLUMN "stream_vods"."s3_key_prefix" IS 'S3 내 저장 폴더 경로';
COMMENT ON COLUMN "stream_vods"."vod_url" IS '시청자용 재생 URL (CloudFront 주소 등)';
COMMENT ON COLUMN "stream_vods"."file_name" IS '메인 인덱스 파일 이름';
COMMENT ON COLUMN "stream_vods"."processing_status" IS '처리 상태: PENDING(대기), COMPLETED(완료), FAILED(실패)';
COMMENT ON COLUMN "stream_vods"."created_at" IS 'VOD 생성/등록 시각';
COMMENT ON COLUMN "stream_vods"."concert_id" IS '연결된 공연 참조';
COMMENT ON TABLE "stream_vods" IS '방송 종료 후 생성된 VOD(다시보기) 관리 테이블';
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
    "eJztXWtzokgX/iuUn0xVdhdUIuabScxs3kk0lTizl3GLaprWUFFwETOT2pr//vaFW3MxgK"
    "iY8MULcBp4TvfhOZdu/mssLB3NV79+WSG7cS781zDBAuEf3PZToQGWy2Ar2eAAbU4PXOMj"
    "6BagrRwbQAdvnIL5CuFNOlpB21g6hmXireZ6PicbLYgPNMxZsGltGv+ukepYM+Q80Qv59g"
    "/ebJg6+oFW3t/lszo10FznrtPQybnpdtV5XdJtN6ZzTQ8kZ9NUaM3XCzM4ePnqPFmmf7Rh"
    "OmTrDJnIBg4izTv2mlw+uTr3Nr07YlcaHMIuMSSjoylYz53Q7WbEAFomwQ9fzYre4Iyc5Z"
    "eW1Ol2lPZZR8GH0Cvxt3R/stsL7p0JUgSG48ZPuh84gB1BYQxwW9rWi6Ez5fLoXT4Be2Cu"
    "FxTCG3xRwIQoBmVYPgIovo0ooB58mxD1NgSQBt1oI6aNz/3P/dG5QL8m5qfR6NPt4Fxg34"
    "1saC/AD3WOzJnzRCAWN0D7tf9w+Xv/odkST0jbFu7ybCAM3T0tuougH0dbTequBPDk/hoR"
    "KwfnnfdcHktZzgKmLKejSfbxcKIFMOZ5gPQFCkHoArR9Ty2IoSRm6ZD4qFQM6T4eQ9OAz/"
    "R3DhjDMsfYGdtZcGynw9hOGthTY45UYzFT13auPpkgepS9cycjXDOsOJZj9CPlwe4eflj8"
    "GpM17PbEyRqgNv6EkgLxbyjBbM+gDSCOB3+OSSOL1erfeRi75l3/Twrr4tXdczsafvIOD2"
    "F9eTu6iECMYdni+R9IHxj0u3PhbmJenwvXRR71UhbDmm5W493Wdp5UTLoSzOoV3prWe8NS"
    "ETzJZsdYoF+9/ZUzBxsgvOqPBxGIjJW6Wi+RvV4ldb4Ly5ojYKbQ94hoBCkNy+6KeOb1aL"
    "JDdDEa3XJj++ImOni/3F0MvG6IDzIc5uW4HD+AFtqI3LYKnOTeR7pRMrK85KYeSH7sld1n"
    "fyrhe9BH5vzVHQSb7OnN3eBx3L+754AnnZXsaXEG1dvaPIuYAb8R4Y+b8e8C+Sv8PRpSj2"
    "NprZyZTc8YHDf+u0GuCawdSzWt7yrQQ4TH2+oBwyl2vdQLKpaXrBV7UMXSiyeRjOlzyCcn"
    "GzQAn78DW1e5PaGRDRx1Cl5WCQbTlbz+/IDmgEIbV3QomHMJnGvwUk1F//R6r7c1UHgAxd"
    "Saz63vWyJxTRs5YhTwXohsB3csx9gSi0vW1BC3dGSAkJFjtay0scTvCnm++E7VFXIcctJU"
    "6EYmGlv4I9uwyojewchZMniL1iIC3gKYYEYvhDRHhOO2IyVMHFiWzcFiNWzM6qDxMQWNse"
    "bQzLJfizqNYfmDB43vR/fnwudf8NfEHD+MxucC+ZyYd18eby77t9itZD8m5kV/eHUukE/s"
    "aPaH6t0AE4fhJ+xyBn8m5ufRw6CvjkdfHnCz/u9CTmkmr3SDWxrzS2vP4F0QyATPYJWSVE"
    "g1ZyGJt21aRfRXglmL0W4ewziA15aNjJn5Gb3GbFo6DagmfmkcAG+2wXf/+RjuGvj28E0h"
    "Fmm47D9e9q8GjZ/prkouKlaAelzRi7m1ZmnsIzjgTQKycm9NnVuzmoQcHQmpTV5mEOuMaZ"
    "kZU8wiVswPzApiIHGUKLYyodjagGIrjiKzvUWoKC95nFT0SKind9sbuaenDy3FH9ysRa0K"
    "XmDBgSFnGRdy+rCQY6OidtDekYOWI8S/S97ctx1j5TQSCLO7ZyNTBvSYmh8fHT/GfuoMqX"
    "lLu3ipQwfnJmv9TIaTtdbWe/gTKHKhONouWGBd8bWbii/c/UyYi0kEEkeJ4k56Z/jKYlCm"
    "189FxI4Ez31XzOlIWzu5q7t4qXde3bVAC42k+Ky1mcBkUx/fUbFCYZoDDOiSozQz21ov2V"
    "0n2sEMZZlcCwcuzXwc3Y7OBfI5MT/dPNyqnx5GX+7PheD3xLwY/aW6+TX318S8u/lzcOUd"
    "HPpThAPUrlrtqjXqKrsPpNjiVXastMydzlgXl6kLsFzixsqpLwtiDvt0I6Hew24klKeiQL"
    "46HexZtqZkdkYL0N+aQnbAtoI/la6Y7RFTTkVaPJwTU0EC9HfAfB1b5DNjXtrFvwjyBUMh"
    "dCJMtyOQ2S9TmcFPPnUxwFpGWC+6LOPfWqtHjtUAIH86iB7l6w1/9qC7n8QCFFnfTkmnLj"
    "JqJCgWwskmnRrbc9/nJ8EwaCyB6WrEsqk+n9FrWFlujtFXt7ubRdLcnc4TZmizp/AwC0Xa"
    "EtPueLsajWH93Bj5cy1QQuQvsE3pkb9QhW25kb9vfqkFu+XGP3UscLexwJqrvgtKE+eqnE"
    "3JOC44mY9aCFFXj9QFc/srmIsP2RJwOwCTLh05zhZVqdjQY4EJ3ClEENPJU5i4v8meGmGG"
    "TFivIuE/GpxS7qyLmPxqPQDxH13qQMaq8SYkdaIUuHhLE/OXGPn2fSMmRRoSdTKjnVJ3iZ"
    "B2fDYofB1dkaZk4kNpuiKydlJPglvssUsTLt2ZAIFbICm67xCALnPXiI+gdRFMcAianFt5"
    "Qi60C6nHIbIjqF/XkuhXVyHX3e3Qmfh1SrqeN5JgCWOQNujckEbSoIVdINMe12l6l3ZSKE"
    "Fd+kQPx3DmufL+vsDhU/5RAwaZz1+ZzL/ztF5oJjDmefP+McGDr1PCQ93uEqMrtTrUZFNr"
    "KxKrT+0sNsptYofdh4LUJiJaZyoV6vE7KR3AVoOEUXL7uGG5Snm4MQ2diYr74CSK0Om6Mq"
    "KUKw5Wda83U8npW/GMbWMZew9PizrjVVKpek1IzL+V3No2sbV35DC182hu+cgVSh+5Ps17"
    "yJpQmg2gRhh9R4JC1B6VlS/hrDharfAVbInbo4MH++KRtfUhcHux9FIw+2rpHwKvFXxC+n"
    "pO0jv14hm5F89Y0b6iwidgmiiBBedfPoP1vsugwX2u17exAzal86wsN8cyG6FS4mhacbtE"
    "b/FnxYfK8wYwRdO8XNKdT/Fy8cpogjeS/y0hxRvMI3krUJk+ySPGIN4MWqp55nwQ5U9lGg"
    "8knjqJFv6SrM8e6tAuIGWLY5bQKgs3RhsKumaoOa5rJheI0M7aEZrDc+HuhDUd7u8ahB3a"
    "X5PClMJvtEfLzLVWknu8G+jUFZEL1qYEK7+FMgmu4upE+q4jmMYK83ojoab+rQUrPak9rl"
    "XpQxudUiPT8dGa9qIW243gZ+6mW7tZ9aKX+SrX9DNZZt7ubyz4xh6QBaJBdU1EZWsidlau"
    "WHYNhUcXciHNC1UA6pJ9zx3XXBxz9cDe63BP81cbJPTvEsDeova2Sn07K878GK9SWQcfZE"
    "jwlmJRiHRviQ+BZPSW+n88CjdfHyn4pPdrksTKHmjWjWV28lV8bN2i58qIEtc/vMqKE99f"
    "0uUzkRFHvztpsEVKOSQg8cUmNGTiul94pz/wux3KILsic9pgrMpEo1coApJwhDIhovoZ6a"
    "SY+XROTn2iAyHQU5rr0pSlqOvCl4fbLI5U7TPt1mfaZh7jVjMYC9nSBmafw6v+w1VyxUd4"
    "iOkipF6TIjc9oVPhov94c7lNarz8YhAS3TLhq0psWFFFRNvYo0JuR38k66JH4WfBFzeYqE"
    "OhiY8/FYajh7v+bSEFnGXAP+reBPCfxcpFbGCuoKXjC1CX2MtBCYQi42BIbOnARSR9/YVc"
    "rM49f0ipAugJvlnv9vzKEfx8IQfJLbq7QyvyWJWeLhMzzgoNodTRhObvF3hAXV5cFVJjO4"
    "Ma2+mveIqq0VhhzI2XxEn/bwV/QoIViP9oiKiJPejJa4n4yGPzfg5eCdmiTAGQ0KjIyjC7"
    "Xaqrnk51RdqAZ71OvsTIjoNAGGsbQctOeFK/paNA7uCvk2lEeJUmdXuMAVHGJU5Jwa0ghM"
    "tGqhuWY+xYBXauFRMjYgd9yVwawwYQ0cd/i1bCuWZLcQ2d4DPsnhLj7AerkMOnR9gBRqa+"
    "tIyklTnSNZIgeuhS0dHFYzPsXzD2LzMLF7gtgSfEXBjhYXx3L3gZIQ0qVFnK1NVfZZS1dA"
    "1x7uWlInKHVtPEKyM9Iwld8mo89rAn4Cu0oJEOFChrHaYzphrOl3M19+uivVaqqS03GvCM"
    "XvEYgfbrkkAb01r60ktp8ofW3jWyTeQQXbRhkN6MeOZ+PCDFmRei4xToCqsHgNvzh52s8Y"
    "QpuLNOqMbIxtQD6T36SQ+D/tVfiZ4SxyZ0SZMDRYpQIioifhOVPxVub74OToXB8GpQjHeX"
    "/9bkd5naq2cv1yvtvBPFpi4cc/DE4BYFbWVVBO4kH5gneZIhn+UVae4+m1UBhewsiVVCYs"
    "qrV09NTIUK2t9MTIUL6TOV8bUQ85PiiR3exaJurdKShaZ7ipOMFX2lnsCdS8yyPglpK5Zg"
    "ViIuRXDaiVe0CqcS9KLJxKcnzSEN+nFJTSYn1vAfkvxCtM6VvtnbK70JojC4Gw7dtBd/f9"
    "QBYgEDTewpgW/DslndnhRl2DTalpwiiwQfbq6arsYN/YSemdyJGy7CmFLMWV1Qnf06wDLc"
    "rmryuPCcUCWCX7FhRMYMQGLP76RcWWFkdAfrBbg1hlz3rZAPD+xifJSXrBQfjRpe3tb69u"
    "eDzyhFGNYiig/LlaD2Uie1cIpWFOr1Q/jBFb1E4Fl9MVDy+p6pT7So2P4KF8Uk3XLGNsG+"
    "Qp29NkGkuQn69gSi9Fj9TI+t8yIp+3NmKukoVqnKbscVpHVV4zutaiQTd1MdR3dW75tOoz"
    "eLOIvDGCn+Cz1g9DM2UyS0rAHV1NfRVZM5UZ4hItWCzJ86yV35uPcrSPLsONvL/En/Ovz+"
    "Sa/msR2kJBW6OhVLVrqZkzNRYvF4cnxbZCeGsbJKz790J6xhZzJEqmOzL8kTgD0tggoBtp"
    "AWoAzee1z4JyfggI7ol2UjIJ76F+R6oJDNvAtXJbgOcQvIJyEcaFqP+rk0ezepF+KqilPa"
    "VrU1fE4rRUvxccJCh05LhseQ4BUlU4rz2BZYVp/ktbTu1oUYO1lDCmNJMr1LG02NHzmVwA"
    "seWhEMblHrCBGV6G1iV7U2sw9Q01lsqzLOPn7S5a2sCIkcGvY4kZ94NZeRCvjm5dxa69e2"
    "ZTpc5cQ2Nco7UQh9J1re99VxQntMti/AykE2rUdJTrlzk2hpMFdrd6WJVxzGP+G3M1CZ3m"
    "0jbXi5jRR/u83StiCJvZszdbtSiMSG9qio+8Hw6mb4KVFJEPYUn+wFpRDngivU9AgUZYen"
    "wuXo7v52MB4QCgnPaCkgZnl4x3X/5pZtpcRSb7eUunZih9aP1L+GyX09Gzp9qbw6xLIbfl"
    "2HWD5SiCW8wFf6Ijve+l9vL7HjrzlWv1T5mBzno11XOTuCu3d+F5gP4lEWhzG9OjokcixA"
    "7r1iGZmFMteBWJXyl6XAXCGqlik3+S7J+serh32PJHzPT+D6RU31i5pKWN32dJsXNR23F1"
    "c6dtX1zUi/THPM/H2nm7wy2i8O7JJVwNAdu3fmru9luvrmYdy4AEBE8tCrNJTBfkucxD83"
    "XlARVDm5GlPeCQb2Mybj5qwIsHHhgy9aUTF466mF78KV8tfOL2H6WzILzjn3rSgH3vWjtT"
    "QGXB4t6yPbgE9JpMzds5GSgeCYOkJ+RBzsBdneDMXMZTWByLEEd/dQDkOGRg4Q3cOPE8Cd"
    "pBnwGR2UtMjR/x5Hw9SQmycSAfKLiW/wm25A51SYY1fhn2rCugFFctebkw7R/ELk4U0auN"
    "h2Nvq2j5ef/weA2ODY"
)
