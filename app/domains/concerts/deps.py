from fastapi import Depends

from app.domains.concerts.service import ConcertAdminService
from app.domains.streams.deps import get_ivs_client
from app.integrations.aws_ivs import IVSClient


# Admin 전용 서비스 주입
def get_concert_admin_service(ivs: IVSClient = Depends(get_ivs_client)) -> ConcertAdminService:
    return ConcertAdminService(ivs_client=ivs)
