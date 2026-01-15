from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "concerts" ADD "status" VARCHAR(20) NOT NULL DEFAULT 'READY';
        ALTER TABLE "concerts" ADD "end_at" TIMESTAMPTZ;
        ALTER TABLE "concerts" ADD "is_test" BOOL NOT NULL DEFAULT False;
        ALTER TABLE "concerts" ADD "description" TEXT;
        ALTER TABLE "concerts" ADD "access_level" VARCHAR(20) NOT NULL DEFAULT 'PUBLIC';
        ALTER TABLE "stream_channels" DROP COLUMN "status";
        COMMENT ON COLUMN "concerts"."status" IS '방송 통로 상태 (READY, LIVE, ENDED)';
COMMENT ON COLUMN "concerts"."end_at" IS '종료 예정 시각';
COMMENT ON COLUMN "concerts"."is_test" IS '테스트/실제 구분';
COMMENT ON COLUMN "concerts"."description" IS '콘서트 소개 글';
COMMENT ON COLUMN "concerts"."access_level" IS '접근 권한';"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "concerts" DROP COLUMN "status";
        ALTER TABLE "concerts" DROP COLUMN "end_at";
        ALTER TABLE "concerts" DROP COLUMN "is_test";
        ALTER TABLE "concerts" DROP COLUMN "description";
        ALTER TABLE "concerts" DROP COLUMN "access_level";
        ALTER TABLE "stream_channels" ADD "status" VARCHAR(20) NOT NULL DEFAULT 'READY';
        COMMENT ON COLUMN "stream_channels"."status" IS '방송 통로 상태 (READY, LIVE, ENDED)';"""


MODELS_STATE = (
    "eJztXWtzokgX/iuUn0xVZgdUIuabUTPrO4mmEjN7GbeopmkNFQUXMTOprfnvb1+4XwwgKi"
    "Z8MQY4DTyn+/S5PN3+V1saKlqsf3tcI7N2yf1X08ES4S+B4+dcDaxW3lFywALKgl64wVfQ"
    "I0BZWyaAFj44A4s1wodUtIamtrI0Q8dH9c1iQQ4aEF+o6XPv0EbX/t0g2TLmyHqiD/L9H3"
    "xY01X0E62df1fP8kxDCzXwnJpK7k2Py9brih4b6tY1vZDcTZGhsdgsde/i1av1ZOju1Zpu"
    "kaNzpCMTWIg0b5kb8vjk6ezXdN6IPal3CXtEn4yKZmCzsHyvmxIDaOgEP/w0a/qCc3KXTw"
    "2h1W5JzYuWhC+hT+Ieaf9ir+e9OxOkCIwmtV/0PLAAu4LC6OG2Mo0XTWXKDaLXewLmQN8s"
    "KYRD/FBAhygCpV8+BCh+jTCgDnzbEHUOeJB63WgrprWv3a/d8SVH/0z1L+Pxl5vBJcf+1t"
    "KhvQQ/5QXS59YTgZjfAu237n3v9+59vcGfkbYN3OXZQBjZZxr0FEE/irYc110J4PH9NSRW"
    "DM5777lBLEUxDZiimIwmOReEEy2BtsgCpCuQC0IboN17ak4MBT5Nh8RXJWJIzwUx1DX4TL"
    "9ngNEvc4qdsZkGx2YyjM24gT3TFkjWlnN5Y2bqkzGiJ9k79zLCFc2IYjlBPxMmdvvy4+JX"
    "m25gu8NPNwA18ScUJIi/QwGmm4O2gDgZ/DkhjSzX638Xfuzqt90/KazLV/vMzXj0xbnch3"
    "XvZnwVghjDssP870kfGfTbS+52ql9fctd5pnohjWFNNqvRbmtaTzJ2umLMah8fTeq9fqkQ"
    "nuSwpS3Rb8750pmDLRD2u5NBCCJtLa83K2Ru1nGd78owFgjoCe57SDSElIJl9+V4Zo1o0k"
    "N0NR7fBMb21TA8eB9vrwZON8QXaRaLcmwf34MWmoi8tgys+N5HulE8skHJbT2QfDmod59+"
    "VsLvoI71xas9CLbZ0+Ht4GHSvb0LAE86KznTCBhU52j9ImQG3Ea4P4aT3znyL/f3eEQjjp"
    "WxtuYmvaN33eTvGnkmsLEMWTd+yED1OTzOUQeYgGI3KzWnYoOSlWKPqlj68CSTMXv2xeTk"
    "gALg8w9gqnLgjG9kA0uegZd1jMG0Ja+/3qMFoNBGFe1L5vSAdQ1eyqnoX07vdY56CvegmB"
    "mLhfFjRySuaSMnjAI+C5Fp4Y5laTti0WNNjXBLJwYIGTlGw0gaS8FTvsgXv6m8RpZFbpoI"
    "3VhHEwN/pBtWKdE7mnMWD96ysQyBtwQ6mNMHIc0R4ajtSEgTe5Zle7JY9huzKml8SkljrD"
    "k0N8zXvEGjX/7oSeO78d0l9/UT/jPVJ/fjySVHPqf67ePDsNe9wWEl+zLVr7qj/iVHPnGg"
    "2R3JtwPsOIy+4JDT+2eqfx3fD7ryZPx4j5t1v+cKSlNFpVvC0khcWkUG78KBjIkM1glFhU"
    "Rz5pN426aVRH8FmLWI2x3EMArgtWEiba5/Ra8Rm5bsBpQTvyQfAB82wQ93fvR3Dfx6+KUQ"
    "yzT0ug+9bn9Q+5UcqmRyxXK4Hn36MDfGPMn78C540wFZ268mL4x55YScnBNSmbzUIFYV0y"
    "IrptiLWLM4MC2InsRJothIhWJjC4qNKIrM9uZxRYOSp+mKnojr6bz2Vt/T0YeSEA9u16JS"
    "higw58AQ04wLMXlYiJFRUQVo7yhAy5Di36ff3DUtbW3VYhxm+8xWTxnQayr/+OT8Yxynzp"
    "GcldoVlDp2cm66US9EON0oTbWDP4Ek5sqj7cMLrBhf+2F84e6nw0yehCdxkijupXf6nywC"
    "ZTJ/LiR2IngemjGnImVjZWZ3BaXeObtriZYKKfEZGz3Gk02cvsNiudI0RxjQBWdp5qaxWb"
    "G3jrWDKWiZgRaOTM18GN+MLznyOdW/DO9v5C/348e7S877PtWvxn/Jdn3N/jbVb4d/DvrO"
    "xb5/8vgAVahWhWq1imX3gRSbn2XHqGX2csaKXCYvwWqFGyuGX+blHA4ZRkK1g8NIKM54jv"
    "xptXBk2ZiR1RkNQL8rEjkBmxL+lNp8uimmGEZaNJ0TUUEM9LdAf50Y5DNlXdrGPw/yOVMh"
    "dCFMu8WR1S8zkcFPPlXew1pEWC+qKOLvSqNDrlUAIP+0EL3K1Rv+7ED7PMkFSKK6m5LObW"
    "TkUFLMh5NJOjW2527MT5JhUFsB3daIYVJ9PqNXv7LsGqOrbvs0y6TZJ60n7KHNn/zDzJdp"
    "iy274+NyOIf1a2vmz7ZAMZk/zzYlZ/58DNtiM3/fXaoFe+XaP1UucL+5wMpXfRcuTdRXDd"
    "iUlOMiIPNRiRAVe6QizB2OMBcdsgXgdgRPunDkAraoTGRDxwuM8Z18DmKy8+R33N/0nmp+"
    "D5l4vZKA/1HgjPrOKo+dX6UDIP5HFVqQedX4EBJaYRc4f0tT/VPE+XZjIyZFGuJVsqKduu"
    "4Ccdrx3SD3bdwnTYkkhlJUiWftJN4Et9hhj8b17JUAXlggSKobEIA2C9dIjKC0EYwJCOqB"
    "sPKMPGgb0oiDZ1fQuK4h0D9tiTx3u0VX4lcl6WrdSIwljEBao2tDanGDFraBSHtcq+482l"
    "muAnXhCz0szVpkqvu7Ascv+YcNGGQxf2kq/9bTZqnoQFtkrftHBI++T0kQ6mabGF2h0aIm"
    "m1pbnlh9amexUW4SO2xPCkKTiCitmZCrx++FOvAeit7EqsxEOr2Sju8kJt09ZMjUhvhs+c"
    "mDFcax2bY2MbnKdNbdkz6cDardD7r9v2KNuwIbxEsRgEAdGUWkSUc2KqCAD/Eq5OpU/py7"
    "GX4bnHODUX/QzzceCt9qDkCI1mt8hxeUYKTe1ki4jQPq5e7x6mbYi591JUEgzuyMDgZVYg"
    "nklLsr7Rt2bS1bKC68e2tHG0fq6JvZ1Fy33XX/P5N/UIvNxhT0C0g9/Uj8kdkOFbjtDe7E"
    "JIueOcXplytVgjMyQV/wkh03EYWodErghd3nghIlPVOtOEB6nlS2J1WAlgud8CWJTi4QVk"
    "pOX7PYtV5x8BI0r7LciVCoXmPId28RWHYlrxwcuYYgOams4pHLRRGx85bvgRlBU2kAKiRr"
    "12LTe2DSKYoTEZiqsVuJn2BH3B4sPNiXD6ytD4Hbi6EWgtk3Q/0QeK3hE1I3C0LhqDbIyr"
    "xB1pr2FRk+AV2PCyKzb5HFel/Pa/CQXtbWDlgXLtNmsrbCnETkilCHdiNz5Z8rPhSXy4Mp"
    "TOUKEOuCNK5ATTJM4gpxvAqgcTHPN00xMnkhZ8SDeLMwKWdZ1xmTlPwUr88OyRLgLiCkq1"
    "UW0CorKYYb8rqmr7lA14wngdLO2uLqo0vu9ow17e/vCoQtLw0YftLPtEeLLH0uxfd4u5ip"
    "SnygIJtQkPzuYwvYiqvIcvuuUmpr7NdrMSWEt1J4jtQBU3gutOEMnkjHR2PWCVtsu0qfup"
    "uWKcP3LmmMYXa6eiGKLNr9zApsbILMkQ2qeI+l5T3ubUlC0TxJx13IhHRQqARQFxx77plX"
    "ecoMwYOvtTnPziiM6d8FgL3D+poy9e20OAfHeJmom8EkQ0y0FMlCJEdLwRRIymip+8cDN/"
    "z2QMEnvV8RBEZtbLTcyk42VufOLTqhDC8E+ofDnjxz4yVVvOCZ4+h2pwARwkcopSkTO/zC"
    "J92B325RD7LNs6ANRpikCn1CHhBSERSJI6pekE6KPZ/W2bnr6EAI1ITm2pSWxKsq93h/ky"
    "aQqmKm/cZMu+xVsNMuBfnYJdj7HPW79/14fol/iKk8pFGTJNYdoXPuqvsw7O1Cfyue8Emy"
    "Wzp8lYkNy6uIcBsHVMjN+I94XXQo/Cz5YicTCe0KX3/Ojcb3t92bXAq4SIF/OLzx4L+IUE"
    "JNoK+hoeIHkFc4ykExDkXKwRDb0pE5iV31hTysGph/CFUBdDjXrLc7LmcIzy/kIrFBT7co"
    "654x8VWRmHG2mAAKLYWr/36FB1TvKh9trplCjc3kn3GMIW+tTO0ldmOft5I/PsES5H8URN"
    "TEJnqbNurLPNbvFuCVOFvUUwAkNcqzpRbtNtVVR6W6Im3Ai04rW2Fkz0kgjLWJoGHGzNRv"
    "6ciTKwPLLuBXKUK7wzwg6nHxM7KohuP8tJHypuWYdywDM9OuyCGxo/6QbJKHDSCi03+Dst"
    "1tsyXZho5zPexOWibkAVjw+PYIB8BIV1eGFrf7VrJGYkSPvRxkfPVQ98cXzPsXmYXzwhYv"
    "EmIhDHc/ub3jnIqQAiWqLGlm6680ylrZhjjzFpIhuWOraeosFbkgBV3y87dssifgS5TQSA"
    "cKFJUW0xlTTSCWszX327K5kcqpLTsb8Ixe8RiB5uuKQBvRWvJKkyT5Y2vvGpk6sogumtAr"
    "b4YiczcfkBDMc+Fx6lHzd/cf9rJc5V2Wk6pdMaod3N6JYhM3JDt6MWoHElVRLLS91KCyJO"
    "xT1FAcYuD+KyglUMjeCicFFEMcjnRiMcRHon6zGOInb6eijvmXjgWLCUG3noZSUkPk6vYt"
    "zlKyyAq9gb1HBas0xJRKWFFTCrmx3m2nDlESzgToZDBJHEmX7irQzYUpIrmxgv8hBRdEuZ"
    "WoyXt0Dy/yx91wZJdagu9HnW4WpCp8R/L8aVZBaXeEsFdHMzzxZZlQwDvs122Na+oZvTN5"
    "EztFgTGlmDMuSlVxOcLPO9iqyRI2BoRKkXCJDCMyZgDiO24nDVDZQqPb24fG5rUFum+J4k"
    "Zg5vNHg5Kl8kfDhjdoa13788FXMSIMa87FqkWqvdCFFAFFB9aufmBFrxB4ll80FL9vdOKM"
    "FhY7HFmOj9NtwNjG2Feosp/j4Wk+nP4qD1F6hLPRYfuHCdLhgplSBoplYnbtmbVYMeneKZ"
    "OOLBZNDBztlaRvBo3OytU0AWOIcOabYNQLtjrBt5SeaurbuF9nQZRjiAhDjcVTZ5nZdgd/"
    "grjILmB7WTzpPofbP+nTPDS9MphEdz1kBTI7W3/Bk9mah3TxVJNnN4YRKp8TX9qLpHAw6X"
    "OqIyv+yAzAZguvKs02aATUg3emC/fmBBzQ4l0qMAL8uftAdgQK2WovfyXcDogbQDzz4UBL"
    "STTOpRWjabXBY1mC0qasbOBzEv0pIcbxCx27FOYfQ5xDhKUuzkOTY5VkUu5S2jsX//eyNy"
    "HGklQXVyaaaT8zKiEoeGxFMLh5pcWFVKI2iV1Vmsw+QEVlua3SBPt4pstazfeJHBv2qCM/"
    "dXh+IdZ1vbcwNuq1aehWoFq/Cy92Lwqhv7WZ9XdQA0IHJMIuwdpCJuVA1GJ9o8DCTZrMVZ"
    "ptYeoQkoIz/G4GKtVvpglbfjRNiP5q2so0yJ6ChN66226RsQ0dcoPCwag/HH2JVRKEHcl1"
    "9rzdIi85W6juOFDUOzzneuPbu5vBZEBcSHhB6WfYy8MnrrvDG3aUOpZqsyGVZHvJd8mdqB"
    "HOpd+5r1bgJm/PVqVY9uNfVymWj5Ri8W8qlbyxi7Pn1Nvburj7XBX7k11V4LzfwPlk9+tP"
    "j+D+g98l9gfxKIvCmMzI9YmcCpCHZsmu8+22uy7ndruFwFwiVy1VbfJdOusfjw/7Hp3wA8"
    "/A1Q8AVj8AWMCOque7/ADgaUdxhWNX3tiM9MukwMw9d74tKqP94sghWQkM3alHZ/aeUrqt"
    "7yCMWxedhySPvTNAEd5vgQvHF9oLyoNqQK7CNBgEA/MZO+P6PA+wUeGjb5RQMnirpYXvIp"
    "Ry92svYPlbvBecce1bXh9431NrYR5wcW5ZF5kafIpzyuwzW10y4F1TZchPyAd7QaazQjE1"
    "rcYTOZXk7gHoMGRoZADRvvw0AdxLmQHf0UJxG+v872E8Sky5OSIhIB91/ILfVQ1a59wChw"
    "r/lBPWLSiSt95edAjXF0KTN2ngatfV6LtOL7/+Dwwx5Ko="
)
