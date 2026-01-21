from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "users" (
    "id" SERIAL NOT NULL PRIMARY KEY,
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
    "id" SERIAL NOT NULL PRIMARY KEY,
    "category" VARCHAR(11) NOT NULL,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "user_id" INT NOT NULL REFERENCES "users" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_user_cat_fa_user_id_b7482a" UNIQUE ("user_id", "category")
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
    "description" TEXT,
    "status" VARCHAR(20) NOT NULL DEFAULT 'READY',
    "access_level" VARCHAR(20) NOT NULL DEFAULT 'PUBLIC',
    "is_test" BOOL NOT NULL DEFAULT False,
    "start_at" TIMESTAMPTZ NOT NULL,
    "end_at" TIMESTAMPTZ,
    "created_at" DATE NOT NULL,
    "updated_at" DATE NOT NULL
);
CREATE INDEX IF NOT EXISTS "idx_concerts_categor_94d1d1" ON "concerts" ("category");
COMMENT ON COLUMN "concerts"."category" IS '장르(category)';
COMMENT ON COLUMN "concerts"."title" IS '공연 제목';
COMMENT ON COLUMN "concerts"."thumbnail_url" IS '공연 썸네일 사진(포스터 등)';
COMMENT ON COLUMN "concerts"."description" IS '콘서트 소개 글';
COMMENT ON COLUMN "concerts"."status" IS '방송 통로 상태 (READY, LIVE, ENDED)';
COMMENT ON COLUMN "concerts"."access_level" IS '접근 권한';
COMMENT ON COLUMN "concerts"."is_test" IS '테스트/실제 구분';
COMMENT ON COLUMN "concerts"."start_at" IS '공연 예정 시각';
COMMENT ON COLUMN "concerts"."end_at" IS '종료 예정 시각';
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
    "eJztXWlzosoa/iuUn0xV5hxQieg3Y8yc3Ek0lZg5m7eopmkNFQUPYmZS585/v72wNYsBRc"
    "UMX1yAt2met5d3ebr5t7awdDRf/fK0QnatK/xbM8EC4R/c8XOhBpbL4Cg54ABtTi9c4yvo"
    "EaCtHBtABx+cgvkK4UM6WkHbWDqGZeKj5no+JwctiC80zFlwaG0a/6yR6lgz5DzTivz9X3"
    "zYMHX0Ha28v8sXdWqguc7V09DJvelx1Xlb0mM3pnNNLyR301RozdcLM7h4+eY8W6Z/tWE6"
    "5OgMmcgGDiLFO/aaVJ/Uzn1M74lYTYNLWBVDMjqagvXcCT1uRgygZRL8cG1W9AFn5C6fGl"
    "Kr3VKaFy0FX0Jr4h9p/2CPFzw7E6QIDMe1H/Q8cAC7gsIY4La0rVdDZ8rl0es/A3tgrhcU"
    "whtcKWBCFIMyLB8BFD9GFFAPvk2IegcCSINmtBHT2pfel96oK9Cvifl5NPp8O+gK7HtiDn"
    "tfBw9dgX7VsmG/AN/VOTJnzjMBXNwA9NfeQ/+33kO9IZ6Rsi3cAVi3GLpnGvQU0UUcezWp"
    "8RL4k1tvRKwY1PfejnksZTkLmLKcjiY5x8OJFsCY5wHSF9gKQheg3dvtlhhKYpYGia9KxZ"
    "Ce4zG0EZir9E8OHDmhk8RSzgKlnI6kHAPSNOBLXhzDMqfYq5tZUGymo9hMGiGnxhypxmKm"
    "ru1cnTtB9CSb5l6GSs2w4liO0fcUe8m9/Lj41SZr2O6IkzVATfwJJQXi31CC2SbzDSCOB3"
    "+MSSGL1eqfeRi7+l3vDwrr4s09czsafvYuD2Hdvx1dRiDGsOxgVgXSRwb9rivcTczrrnC9"
    "jc0kZZmh0uen2HCAkUAqBk9LQzZlLIjIneZAULj9qRm286xi1yBhlrrCR9MGg7BUBEpy2D"
    "EW6BfvfOlA3QDiVW88iEBkrNTVeons9SqpxV1a1hwBM8XJjIhGkNKw7L7co7x+d3aILkej"
    "W26ovLyJjoVPd5cDr1fjiwyH+eKuJxpAC7HZiB9bBU5y6yPNKBlZXnJTCyQ/DuqDZu/b+B"
    "n0kTl/czvBpunp5m7wOO7d3XPAk8ZKzjS4+ck7Wr+IjAN+IcLvN+PfBPJX+Gs0HFAErZUz"
    "s+kdg+vGf9VIncDasVTT+qYCPWQ/ekc9YDjFrpf6lorlJSvFHlWxtPIk3jZ9CUWOyAENwJ"
    "dvwNZV7kyoZwNHnYLXVcKA6Upef3lAc0ChjSs6FHLsA+cavJZT0T+81usdDRQeQDG15nPr"
    "245IXNNCThgFfBYi28ENyzF2xKLPihrikk4MENJzrIaV1pf4U6FAAn5SdYUch9w0FbqRic"
    "YW/sjWrTKidzTjLBm8RWORiBDrY2TasHHzchIa2B0w38YW+Yx5Xckg9WhJZYy4pCF07tZd"
    "jSRugiexSdPAKEVgs1U/czO1bNoUXxCZvGoMTjfK7LdT9yQRck85z7a1nj1HhjsMKq4AYt"
    "Zfv/fY713ROUmNIcqUC0wwo8fIc/84T5oGUvJSwSSxOTulhuelYrNUf9c8Kx/fA80s+632"
    "3ypztd/MlY90DL1sIZaw/NEzV/ej+67w5RP+mpjjh9G4K5DPiXn39HjT7912BffHxLzsDa"
    "+6AvmcmNe9oXo3wHbh8HNXCP2ZmF9GD4OeOh49PeBi/d9bhXAyxXA2BHFiUZzK8fsQ/kGC"
    "47dKyWWmDmchiffHtJLor4BhLeZV8RjGAby2bGTMzC8oqwHj8TXKh98GA8YG3/z5Mdw0Ek"
    "2JH+meaC5LO25ZvmuOXNHK3FqzNIskuOBdo2TlPpo6t2YVfebkjJBqyMsMYkXUKJiosWJu"
    "fg6WxioxMHAaKDYyodjYgGIjjiIbe7cxRXnJ0zRFT8T09B57o+3p6UNL8Qc3a1ErgxdYGu"
    "5S5aB9IActRwZnn3azG4dMMJiDCGW6pRyK7Fb2cflMu3T7GPupM5SbUMpLHTs4N1nrFzKc"
    "rLWm3sGfQJG3iqPtwwqs+JH74Ufi5mfCXJZEIHGSKO6ldYZrFoMynW0aETsRPA/NL9WRtn"
    "Zyk/d4qQ9O3lsgQvjET782EyzZ1Ok7KrZVmOYIHbrgKM3MttZL9tSJ42AGEjNXwpGJzI+j"
    "21FXIJ8T8/PNw636+WH0dN8Vgt8T83L0p+rm19xfE/Pu5o/BlXdx6M82NkDlqlWuWi1jLq"
    "0iUX4ExW5PovToORV3kHEHF2C5xIUVQx/cnt+10/IlvYPdSChPRYF8tVrYs2xMyVqmBqC/"
    "NYWcgE0FfyptMdsUUwzhMAPBLswU241et212umzkOu85Uqh1PCORJ9eF0oBRah3Hu9uBXJ"
    "fWlYrQoNuPDqhEuvyv3RLImr+pzLoR+dTFoM/ICPcvXZbxb63RIddqAJA/LUSv8vsf/uxA"
    "9zyJ6SiyvltnS2shIZyijWRJ9AyNJTATG4inrJyNxBsuQy0ve2PZGMF1Z5KECG4wx6RHcE"
    "ONd1/US/bIFfFy78TLyuf4CKZp3OfgxpSM/YKT+VkJLRULqCI+Ho74GO+yBeB2BI+ocOS4"
    "sahMpFHPCkywnUIGYrrxFDbc37WeamELmVi9ioT/aHBKbWddxMav1gEQ/9GlFmRWNT6EpF"
    "bUBN6+pIn5KWZ8+z4ukyIFiTrZx4Oa7hIx2vHdoPB1dEWKkokvrOmKyMpJvQkuscOqJvTd"
    "FR2BWyApuu8QgDZzu4mPoLURTHAI6lx44IxUtA2pxyGyK6h/3pDoV1sh9W636P4jFbWgWv"
    "+TMBLGIK3RNT61pE4L20CmLa5V96p2thXRoPAFO47hzHPxN3yB41M3ogMYZD5/aRgczvN6"
    "oZnAmOflb8QEj747Ew91s00GXanRokM2HW1FMurTcRYPyk0yDruTgtQkIlprKm3V4vdCAf"
    "kI5AUyqkxlOr2Shu8FmP2ds8jUhsR8ceaDERzwsO2sE2KV2Ub3QPpwY1DtYdC7+jNxcNdg"
    "g1gpEpCoIaPJNOjIegWU8CFRh0Kdyp8LtzdfB+fCYHg1uNquPxS+UxSAEK1W+A6vKGWQel"
    "8j0TIOqJf7p8vbm37yrKtIEjFmp7Qz6AoLIGfcU27fsBsr1UFJ7t17G095Ukffc6rmm+2+"
    "+f8r+YNabDamoF9AaunH/I/c41CBu1PhRkyi6LlDnGG5UgU4YxP0hai4fhNRiE6nBFHafS"
    "4oUdAz08oRZG4Tyg6kCtByoRO+otDJBcJKydlzFrvmKw7dlaGos9iJVKheE0iU7xGRdiUh"
    "HRy5hqR4oazikduK6uPGLT8Cw4WG0gDUSNSuxaZ3btIpitvCTdXYrMQ12BG3Rwd39sUjK+"
    "unwO3V0gvB7Kul/xR4reAz0tdzQuGo9rHLvY/dirYVFT4D00xyIvPvZMdaXz8o8JBW1sYG"
    "WJe6WSNZG2FOI+TFqEO7kbkOvtvdaXK50rfS44h1OTbRi3C8CqBxMcs3SzIyfUFuzIJ4Nz"
    "Gp5lmfmxCU/JSszw6JEuAmIGXLVRZQKkspRgsKmmaoOK5pJpN5aWNtCfVhV7g7Y0WH27sG"
    "YSsIA0Zr+itt0TILnyvJLd5NZuqKyCVkUxKSf4fYAq7iKrLcvrOUxgrb9UZCCuG9EJ4ndc"
    "AQng9tNIIn0/7RmHaiI7abpc/cTMsU4fuQNMboKgP9QpaZt/srS7CxCXKLaFDFeywt73Fv"
    "S0uK5kl65kIupHmhEkBdsO+5Z17lKTMED75m6jw/ozChfRcA9g7ra8rUtrPizPfxMlE3+S"
    "BDgrcUi0Kke0t8CCSjt9T7/VG4+fpIwSetX5MkRm1stPzMTj5W584leq6MKHHtw2NPnvn+"
    "ki5fiMxw9JsTR4QIEUppyMR1v/BJv+O3W9SCbIvMaYMxJqlGaygCQiqCMjFE9QvSSLHl0z"
    "o79w0dCIGeUlyb0pJEXReeHm6zOFKVz7Rfn2mXPSd22m1iO3YJtj6HV72Hq2R+SbiL6SKk"
    "XpMi1z2hc+Gy93jT34X+Vjzhk0S3TPimkjFsW0VEyzigQm5HvyfrokPhZ8EXN5hIaFf4+n"
    "NhOHq4691upYCLDPhH3ZsA/osYJdQG5gpaOq6AusReDkowKDJ2hsSSjsxJ7OmvpLI6N/8Q"
    "qgLoCP6w3u74nCE8v5CL5AY93aKse8bE12UyjLPFBFBqaUL9t0vcofqX29HmmhnU2Ex/eW"
    "0CeWtpG6+JGzS9F/wJCZYg/qMhoiY20bu00VDksX4/B2/E2KKWAiChUZEttWi3qa46OtUV"
    "KQNedFr5EiN7DgJhrG0ELTthpn5PR4FcGVh2nF2lSe0Os4CoxSVOyaIaQQjTRsoblmPWsQ"
    "rsXLtbR8SO+vrsNAsbQESn/wZlu7vDluIOdIJvYXeyMiEPwILHt0fYAUamvrSMpF3U0jWS"
    "IHrs5SCjy8d62L9g1r/MRrjAbQk8IebCCA/ju3vBywhpUKHKUqau/kqjrKU7EOfeCjQid2"
    "w1TbylIhckoUte+s0mewK+QgmNtKNAWWsxnTHVcL6cq7lfFs21Uk5tudGAF/SG+wi035YE"
    "2pjW0leapMkfW3vXyDaRQ3TRhEF6M+KZ+/GAFGdeiPbTgJq/u/2wl+UqHzKdVO2KUe3E90"
    "EUm7qx3NGTUTuQqIpioe0lB5UnYJ8hh+IRA/efQSmBQvaWOCkgGeJxpFOTISES9bvJkDB5"
    "OxN1LLx0jE8m8GY9daWUhizU3VucZWSRFXoDd48KlmlISJWwpKYSMWOD2048oiScStCLYB"
    "I/ki7d1aAfC9NkcmMN/yEJF0S5lagpBnSPwPPHzXDoplr456NGN3NSNbGjBPY0y6C0O1LU"
    "qqMRnuS0TMThvbmquxo39DN6Z/IkbogCY0oxZ1yUKuNyhNd0uKrJ4zZyQqUIuMS6EekzAI"
    "kdv5FyVLZI7w72oXF5bVzzLZHfCOzt7FFeslT2aHTg5cdaf/z5yVcxIgzrlotVi1R7oQsp"
    "OEVza1d/YkUvEXhRXw2UvP936owWFTscWU5M0i032CaMr1Bnr1USaTycvl2JKD3G2eiw/c"
    "Mk5XDOTCkdxTIxu/bMWqyYdB+USUcWi6Y6ju5K0nedRm/lahaHMUI4C00w+gVbnRBaSk81"
    "9XV0VWdOlDcQEYYa86fOcrPtDl6DJM+OG3uZP+nXw2+ftDaPzSANptBdD1mCzI3WX4hkth"
    "YhXTzVFNmNYYzK5/mX7iIp7EyGjOrYij8yA7DZIshKsw0aAbXgvenCvzkBB7REnwqMgHju"
    "V8j1QCFb7RXOhLsOcQPIZyEcaCqJ+rk0YzSpNngsi1PaVLU1fEmjP6X4OGGhY6fCwn1I8I"
    "iw1MR5bAosk0zSXVp75+T/XvYmxFiS7OLSRlPje04l8ILHVgSDW9RaQkQlepOMq1qTjQ9Q"
    "01lsqzTOPp7p8mbzQyLHhj1uyE88nl+EdV3vz621fm1bpsNl63fhxe5FIfSdqXnfZ8sJHZ"
    "AIuwArB9mUA1FLtI24hZs0mKs129LEIyTxM/xuA1Smd99JG15+J8Xffre0LbKnIKG37rZb"
    "ZGJBh9ygcDC8uhl+TlQShB3FN/aC3SK7gitU9wwoah2eC/3R3f3tYDwgJiS8oPQzbOXhE9"
    "e9m1t2lBqWerOhlGR7yQ/JnagRzmXYuK9W4KZvz1aFWPZjX1chlp8pxBLeVCp9Yxdvz6n3"
    "t3Xx97kq9pVdleO8X8f5ZPfrz47g/p3fBbYHcS+Lw5jOyA2JnAqQh2bJrrbbbXdVzu12C4"
    "G5RKZaptzkhzTWfz4+7Ec0wg88A1cvAKxeAFjAjqrnu7wA8LS9uMKxK69vRtplmmPmnzvf"
    "5JXRdnFkl6wEA92pe2funlKmq28exo2LziOSx94ZoAjrt8CF43PjFW2DKidXYco7wcB+wc"
    "a4OdsG2Ljw0TdKKBm81dLCD+FK+fu1F7D8LdkKzrn2bVsbeN9Ta2EWcHFmWQ/ZBnxOMsrc"
    "MxtNMhBcU0XIT8gGe0W2t0IxM60mEDmV4O4B6DCka+QA0b38NAHcS5oB39FBSRvr/OdxNE"
    "wNuXki0YnfgI7wP2F+6H16izCryPNuTjdEMwuRaZsUcLnrOvRdJ5Yf/wc27/cS"
)
