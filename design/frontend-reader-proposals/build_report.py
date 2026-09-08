from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph

HERE = Path(__file__).parent
OUT = HERE / "comparison.pdf"
pdfmetrics.registerFont(TTFont("Malgun", "C:/Windows/Fonts/malgun.ttf"))
pdfmetrics.registerFont(TTFont("MalgunBold", "C:/Windows/Fonts/malgunbd.ttf"))
W, H = (1080, 1440)
c = canvas.Canvas(str(OUT), pagesize=(W, H))
c.setTitle("CAE Material Platform - 여섯 작업 화면 비교")
c.setAuthor("CAE Material Platform design review")
style = ParagraphStyle(
    "body",
    fontName="Malgun",
    fontSize=18,
    leading=29,
    textColor=HexColor("#344455"),
    wordWrap="CJK",
)
small = ParagraphStyle("small", parent=style, fontSize=15, leading=24)


def para(text, x, y, width=976, sty=style):
    p = Paragraph(text, sty)
    _, h = p.wrap(width, 1000)
    p.drawOn(c, x, y - h)
    return y - h


def title(text, y, size=32):
    c.setFillColor(HexColor("#19364b"))
    c.setFont("MalgunBold", size)
    c.drawString(52, y, text)


def footer(n):
    c.setStrokeColor(HexColor("#dce3ea"))
    c.line(52, 49, W - 52, 49)
    c.setFont("Malgun", 12)
    c.setFillColor(HexColor("#657587"))
    c.drawString(52, 29, 'CAE Material Platform  /  미확정 '
    '시안 P2-C5  /  2026.09.07')
    c.drawRightString(W - 52, 29, f"{n} / 7")


def capture(letter, kind, y, label):
    c.setFillColor(HexColor("#455e73"))
    c.setFont("MalgunBold", 15)
    c.drawString(52, y, label)
    sh = 549
    c.drawImage(
        str(HERE / "evidence" / f"{letter}-{kind}.png"),
        52,
        y - 18 - sh,
        width=976,
        height=sh,
        preserveAspectRatio=True,
        anchor="c",
    )
    return y - 18 - sh


data = [
    (
        "a",
        "A · Granta 방식",
        "분류 탐색 + 미리보기 → 전체 기술 시트",
        "여러 조건을 좁혀 가며 목록과 한 자료를 함께 확인하기 좋습니다.",
        '왼쪽 분류 영역이 추가되어 작업 영역이 줄어듭니다. '
        '작은 화면에서는 상세에 집중하도록 전환합니다.',
    ),
    (
        "b",
        "B · Total Materia 방식",
        "검색 콘솔 → 독립 상세 문서",
        '검색 조건을 명시적으로 넣고, 결과를 넓게 훑은 뒤 '
        '한 자료를 읽는 흐름이 분명합니다.',
        '검색 폼이 세로 공간을 차지합니다. 여러 자료를 '
        '오가며 곡선을 비교하는 데에는 별도 비교 기능이 '
        '필요합니다.',
    ),
    (
        "c",
        "C · Koyfin 방식",
        "목록 창 + 연결된 분석 창",
        '목록을 유지하며 옆 분석 창에서 조건과 곡선을 '
        '확인하는 반복 검토에 어울립니다.',
        '창 분할 때문에 미리보기를 열면 목록 폭이 '
        '줄어듭니다. 상시 첫 화면보다 분석 작업에 적합합니다.',
    ),
    (
        "d",
        "D · TradingView 방식",
        "넓은 스크리너 → 차트 작업 화면",
        '처음에는 조건 열을 넓게 보여주고, 선택 후에는 '
        '곡선에 가장 큰 공간을 줍니다.',
        '곡선에 비해 값이 몇 개뿐인 카드에서는 빈 공간이 '
        '큽니다. 카드 상세에 같은 배치를 강제하면 안 됩니다.',
    ),
    (
        "e",
        "E · 문서 중심 종합안",
        "자료 색인 → 정돈된 기술 문서",
        '한 자료의 곡선과 조건을 차분히 읽기 좋고, 목록과 '
        '상세가 서로 공간을 빼앗지 않습니다.',
        'B와 상세 읽기 방식이 겹칩니다. 넓은 모니터의 '
        '활용과 여러 자료 비교에서는 이점이 작습니다.',
    ),
    (
        "f",
        "F · 조건 비교 종합안",
        "가로 조건 매트릭스 → 분석 노트",
        '자료를 열로, 온도·속도·물성값을 행으로 놓아 소수 '
        '후보의 차이를 직접 읽습니다.',
        '많은 자료를 최초 검색하는 기본 화면으로는 '
        '불리합니다. 검색 후 추린 후보 비교에 쓰는 편이 '
        '좋습니다.',
    ),
]
verdict = {
    "recommendation": '추천: 기본 조회는 B, 곡선 분석은 D, 소수 후보 '
    '비교는 F를 우선 검토합니다. 한 화면에 모두 섞을 '
    '필요는 없습니다. 최종 시안은 아직 선택하지 '
    '않았습니다.',
    "review": '독립 검수: 체크포인트 승인. 여섯 안의 좁은 화면 '
    '미리보기 제목·행동 노출을 확인했고 브라우저 검사 '
    '230개가 통과했습니다. 미리보기 본문은 스크롤이 '
    '필요할 수 있습니다. 실데이터·저장·물리적 4K '
    '승인은 포함하지 않습니다.',
}
title("어떤 작업 화면을 선택할 것인가", 1362, 36)
y = para(
    '여섯 안을 같은 데이터로 비교했습니다. 좌측 메뉴는 '
    '요청하신 이전의 차분한 스타일로 맞추고, 본문 구성과 '
    '자료를 여는 방식은 각각 다르게 만들었습니다.',
    52,
    1321,
)
y = para(verdict["recommendation"], 52, y - 24)
y -= 38
for _letter, name, pattern, good, bad in data:
    c.setStrokeColor(HexColor("#dfe5ea"))
    c.line(52, y + 12, 1028, y + 12)
    c.setFont("MalgunBold", 18)
    c.setFillColor(HexColor("#19364b"))
    c.drawString(52, y - 13, name)
    para(pattern, 352, y + 3, 676, small)
    y = para(good + " " + bad, 352, y - 28, 676, small) - 27
y = para("독립 검수 결과", 52, y - 5, sty=ParagraphStyle("h", parent=style, fontName="MalgunBold"))
y = para(verdict["review"], 52, y - 12, sty=small)
y = para(
    "완료 범위와 남은 작업",
    52,
    y - 26,
    sty=ParagraphStyle("h2", parent=style, fontName="MalgunBold"),
)
y = para(
    '이번 결과는 선택용 시안입니다. 검색·페이지 '
    '이동·시험 상세·관련 저장 카드 조회를 연결했습니다. '
    '예시는 합성 시험 48건, 카드 메타데이터 8건이며 '
    '실제 규모의 성능 측정 결과가 아닙니다. 그래프는 '
    '합성 참조 곡선입니다.',
    52,
    y - 12,
    sty=small,
)
y = para(
    '실제 API 연결, 재료 수정만 리비전 관리하는 저장 '
    '기능, 등록·처리·모델·카드 생성 화면, 실데이터 '
    '검증과 일괄 전환은 아직 남아 있습니다. 기존 '
    '프로그램을 교체하거나 배포하지 않았습니다.',
    52,
    y - 12,
    sty=small,
)
assert y > 65, ("page1 overflow", y)
footer(1)
c.showPage()
for index, (letter, name, pattern, good, bad) in enumerate(data, 2):
    title(name, 1380, 30)
    para(pattern + "  |  " + good, 52, 1345, sty=small)
    y = capture(letter, "preview-full", 1280, "01  한 번 선택: 목록과 미리보기")
    y = capture(letter, "detail", y - 38, "02  더블클릭 / 상세 열기 / Enter: 전체 상세")
    para("주의할 점: " + bad, 52, y - 20, sty=small)
    footer(index)
    c.showPage()
c.save()
print(OUT)
