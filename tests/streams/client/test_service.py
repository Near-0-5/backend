from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.core.config import settings
from app.domains.concerts.models import CategoryType, Concert
from app.domains.streams.client.service import StreamUserService
from app.domains.streams.models import (
    ConcertSession,
    StreamChannel,
    StreamStatus,
)


@pytest.mark.asyncio
class TestStreamService:
    @pytest.fixture
    def mock_pb(self):
        pb = MagicMock()
        pb.sign_playback_token.return_value = "signed_token"
        pb.sign_internal_tokens.return_value = {"access_token": "at", "refresh_token": "rt"}
        pb.rotate_tokens.return_value = {"access_token": "new_at", "refresh_token": "new_rt"}
        return pb

    @pytest.fixture
    def service(self, mock_pb):
        return StreamUserService(ivs_client=MagicMock(), playback_provider=mock_pb)

    async def test_get_viewing_credentials_logic(self, service, mock_pb):
        """시청 권한 발급 및 공개/비공개 분기 검증"""
        concert = await Concert.create(title="Test Concert", category=CategoryType.KPOP)
        session = await ConcertSession.create(
            concert=concert,
            session_name="Session",
            status=StreamStatus.LIVE,
            start_at=datetime.now(),
        )
        channel = await StreamChannel.create(
            id=session.id,
            session=session,
            playback_url="https://play.m3u8",
            channel_arn="arn:ivs:test",
            ingest_endpoint="https://ingest.com",
            stream_key_encrypted="test_encrypted_key",
            is_private=True,
        )

        mock_user = MagicMock(id=1)
        with patch(
            "app.domains.streams.permissions.StreamPermission.verify_playback_access",
            new_callable=AsyncMock,
        ):
            res = await service.get_viewing_credentials(session.id, mock_user)
            assert "token=signed_token" in res["playback_url"]

            channel.is_private = False
            await channel.save()
            res_pub = await service.get_viewing_credentials(session.id, mock_user)
            assert "token=" not in res_pub["playback_url"]

    @pytest.mark.asyncio
    async def test_refresh_playback_url_success(self, service, mock_pb):
        """시청 세션 연장 및 Playback URL 재발급 테스트"""
        concert = await Concert.create(title="Refresh Test")
        session = await ConcertSession.create(
            concert=concert, session_name="S1", start_at=datetime.now()
        )
        # StreamChannel 생성 시 playback_url 설정
        await StreamChannel.create(
            id=session.id,
            session=session,
            playback_url="https://test.com",
            channel_arn="arn:ivs:test2",
            ingest_endpoint="https://ingest2.com",
            stream_key_encrypted="test_encrypted_key2",
            is_private=True,
        )

        mock_user = MagicMock(id=1)
        with patch(
            "app.domains.streams.permissions.StreamPermission.verify_playback_access",
            new_callable=AsyncMock,
        ) as mock_verify:
            res_url = await service.refresh_playback_url(session.id, mock_user)

            mock_verify.assert_called_once()

            assert res_url == "https://test.com?token=signed_token"

            # mock_pb에 전달된 인자 검증
            mock_pb.sign_playback_token.assert_called_with(
                channel_arn="arn:ivs:test2",  # DB에 저장한 값
                viewer_id="1",
                duration_sec=settings.ADMIN_IVS_PLAYBACK_TOKEN_EXPIRATION_SEC,
            )

    @pytest.mark.asyncio
    async def test_refresh_playback_url_public_channel(self, service, mock_pb):
        """공개 채널일 경우 토큰 없이 URL만 반환하는지 테스트"""
        concert = await Concert.create(title="Public Test")
        session = await ConcertSession.create(
            concert=concert, session_name="S2", start_at=datetime.now()
        )

        # 공개(is_private=False) 채널 생성
        await StreamChannel.create(
            id=session.id,
            session=session,
            playback_url="https://public.playback.com/index.m3u8",
            channel_arn="arn:aws:ivs:public",
            ingest_endpoint="rtmps://public.ingest.com",
            stream_key_encrypted="key",
            is_private=False,
        )

        mock_user = MagicMock(id=1)
        with patch(
            "app.domains.streams.permissions.StreamPermission.verify_playback_access",
            new_callable=AsyncMock,
        ):
            res_url = await service.refresh_playback_url(session.id, mock_user)

            # 검증: 토큰 없이 순수 URL만 반환되어야 함
            assert res_url == "https://public.playback.com/index.m3u8"
            mock_pb.sign_playback_token.assert_not_called()

    async def test_list_sessions_all_filters(self, service):
        """목록 조회 필터링 검증"""
        c1 = await Concert.create(title="AAA Concert", category=CategoryType.KPOP)
        c2 = await Concert.create(title="BBB Show", category=CategoryType.TROT)

        await ConcertSession.create(
            concert=c1,
            session_name="S1",
            status=StreamStatus.ENDED,
            start_at=datetime.now() - timedelta(days=1),
        )
        await ConcertSession.create(
            concert=c2, session_name="S2", status=StreamStatus.LIVE, start_at=datetime.now()
        )

        assert len((await service.list_sessions(status=StreamStatus.LIVE))[0]) == 1
        assert len((await service.list_sessions(category=CategoryType.KPOP))[0]) == 1
        assert len((await service.list_sessions(title="BBB"))[0]) == 1

        today = date.today()
        assert len((await service.list_sessions(from_date=today, to_date=today))[0]) == 1

    async def test_get_sessions_detail_service(self, service):
        """Service.get_sessions_detail 검증"""
        concert = await Concert.create(title="Detail Service", category=CategoryType.KPOP)
        session = await ConcertSession.create(
            concert=concert,
            session_name="S Detail",
            status=StreamStatus.LIVE,
            start_at=datetime.now(),
            end_at=datetime.now() + timedelta(hours=1),
        )

        # 아티스트 생성
        from app.domains.artists.models import Artist
        from app.domains.streams.models import ConcertArtist

        artist = await Artist.create(
            stage_name="ArtistService",
            group_type="SOLO",
            profile_img_url="https://a.png",
            agency="AgencyS",
        )
        await ConcertArtist.create(session=session, artist=artist, is_main=True)

        user = MagicMock(id=1)
        with patch(
            "app.domains.streams.permissions.StreamPermission.verify_playback_access",
            new_callable=AsyncMock,
        ):
            res = await service.get_sessions_detail(user, session.id)
            assert res.concert_title == "Detail Service"
            assert len(res.lineup) == 1
            assert res.lineup[0].name == "ArtistService"

    async def test_get_viewing_credentials_not_found(self, service):
        """세션 없음 -> 404"""
        user = MagicMock(id=1)
        with pytest.raises(HTTPException) as exc:
            await service.get_viewing_credentials(9999, user)
        assert exc.value.status_code == 404

    async def test_get_sessions_detail_not_found(self, service):
        user = MagicMock(id=1)
        with pytest.raises(HTTPException) as exc:
            await service.get_sessions_detail(user, 99999)  # 존재하지 않는 세션
        assert exc.value.status_code == 404

    async def test_get_status_not_found(self, service):
        """없는 콘서트 세션 조회"""
        with pytest.raises(HTTPException) as exc_info:
            await service.get_status(99999)
        assert exc_info.value.status_code == 404
        assert "콘서트 세션 정보를 찾을 수 없습니다." in str(exc_info.value.detail)
