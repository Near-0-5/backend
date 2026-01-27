# Install dependencies as needed:
# pip install kagglehub[pandas-datasets]
import random
from datetime import datetime

import kagglehub
import pandas as pd
from kagglehub import KaggleDatasetAdapter
from tortoise import Tortoise, run_async

from app.core.config import settings
from app.core.tortoise_config import TORTOISE_ORM
from app.domains.artists.models import Artist, GroupType
from app.domains.streams.models import CategoryType

"""
    ** 1700+ K-Pop Idols Dataset
    그룹명이 없으면 예명, 카테고리 랜덤, 프로필이미지정보null, Company=agency,
    description="안녕하세요 {그룹명이 없으면 예명}입니다!",
    debut_date= Debut의 형식 "26/08/2014" 테이블 양식  "2022-07-22",
    그룹명이 같으면 인원수+1(member_count), 
    group_type= Gender(F) : GIRL_GROUP, Gender(M) : BOY_GROUP
    created_at,updated_at = AUTO_NOW_ADD
"""


async def seed_artists_kaggle() -> None:
    await Tortoise.init(config=TORTOISE_ORM)

    print("기존 아티스트 데이터를 삭제합니다...")
    await Artist.all().delete()

    # Set the path to the file you'd like to load
    file_path = "kpopidolsv3.csv"
    category_list = list(CategoryType)

    # Load the latest version
    df = kagglehub.dataset_load(
        KaggleDatasetAdapter.PANDAS,
        "nicolsalayoarias/all-kpop-idols",
        file_path,
        pandas_kwargs={
            "encoding": "utf-8",  # 인코딩 지정
            "usecols": ["K Stage Name", "Group", "Debut", "Company", "Gender"],
        },
    )

    # 그룹별 인원수 계산
    group_counts = df["Group"].value_counts().to_dict()

    for _, row in df.iterrows():
        # 데이터 정제
        k_stage_name = row["K Stage Name"] if pd.notna(row["K Stage Name"]) else None
        group_name = row["Group"] if pd.notna(row["Group"]) else None
        gender = row["Gender"] if pd.notna(row["Gender"]) else ""

        # group_name이 없으면 k_stage_name명을 사용
        display_name = group_name if group_name else k_stage_name
        if not display_name:
            continue

        # 데뷔일 변환 ("26/08/2014" -> date object)
        debut_date = None
        if pd.notna(row["Debut"]):
            try:
                debut_date = datetime.strptime(row["Debut"], "%d/%m/%Y").date()
            except (ValueError, TypeError):
                debut_date = None

        # GroupType 결정 및 인원수 설정. 그룹이 없으면 무조건 솔로.
        if not group_name:
            final_group_type = GroupType.SOLO
            member_count = 1
        else:
            # 그룹명이 있는 경우 성별(Gender)에 따라 분류
            member_count = group_counts.get(group_name, 1)
            if gender == "F":
                final_group_type = GroupType.GIRL_GROUP
            elif gender == "M":
                final_group_type = GroupType.BOY_BAND
            else:
                # 성별 정보가 없거나 모호한 경우 혼성그룹으로 분류
                final_group_type = GroupType.MIXED_GROUP

        # 데이터 객체 구성
        artist_defaults = {
            "category_type": random.choice(category_list),
            "agency": row["Company"] if pd.notna(row["Company"]) else "Unknown",
            "description": f"안녕하세요 {display_name}입니다!",
            "member_count": member_count,
            "group_type": final_group_type,
            "profile_img_url": None,
        }

        # DB 저장
        await Artist.get_or_create(
            stage_name=display_name, debut_date=debut_date, defaults=artist_defaults
        )

    print(f"[{settings.MODE}] 아티스트 생성 완료 (총 {len(df)}개)")
    await Tortoise.close_connections()


if __name__ == "__main__":
    run_async(seed_artists_kaggle())
