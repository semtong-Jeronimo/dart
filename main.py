import os
import io
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import requests
from fastmcp import FastMCP

# MCP 서버 초기화
mcp = FastMCP("DART-Connector")

DART_API_KEY = os.environ.get("DART_API_KEY")

# 기업 고유번호 캐시
CORP_CODE_MAP = {}

def get_corp_code(target: str) -> str:
    """회사명 또는 종목코드를 8자리 DART 고유번호(corp_code)로 자동 변환"""
    global CORP_CODE_MAP
    target = target.strip()
    
    # 이미 8자리 숫자 고유번호인 경우 그대로 반환
    if len(target) == 8 and target.isdigit():
        return target
        
    # 캐시가 비어있으면 DART에서 전체 고유번호 목록을 1회 다운로드
    if not CORP_CODE_MAP:
        url = f"https://opendart.fss.or.kr/api/corpCode.xml?crtfc_key={DART_API_KEY}"
        resp = requests.get(url)
        if resp.status_code == 200:
            with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
                with z.open("CORPCODE.xml") as f:
                    tree = ET.parse(f)
                    root = tree.getroot()
                    for item in root.findall("list"):
                        c_code = item.findtext("corp_code")
                        c_name = item.findtext("corp_name")
                        s_code = item.findtext("stock_code")
                        if c_name:
                            CORP_CODE_MAP[c_name.strip()] = c_code
                        if s_code and s_code.strip():
                            CORP_CODE_MAP[s_code.strip()] = c_code

    # 1) 정확한 회사명 또는 6자리 종목코드로 매핑
    if target in CORP_CODE_MAP:
        return CORP_CODE_MAP[target]
        
    # 2) 부분 일치 검색 (예: '두산에너빌리티' -> '(주)두산에너빌리티')
    for name, code in CORP_CODE_MAP.items():
        if target in name:
            return code
            
    return None

@mcp.tool()
def search_dart_corp_code(corp_name: str) -> str:
    """회사 이름으로 고유번호 및 최근 공시를 조회하는 기본 도구"""
    if not DART_API_KEY:
        return "오류: DART API Key가 설정되지 않았습니다."
        
    # 1. 8자리 DART 고유번호(corp_code) 자동 추출
    corp_code = get_corp_code(corp_name)
    if not corp_code:
        return f"오류: '{corp_name}'에 해당하는 기업 고유번호를 찾을 수 없습니다."

    # 2. 최근 1년간(365일 전 ~ 오늘)의 공시 조회
    bgn_de = (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")
    url = f"https://opendart.fss.or.kr/api/list.json?crtfc_key={DART_API_KEY}&corp_code={corp_code}&bgn_de={bgn_de}&page_count=5"
    
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        if data.get("status") == "000":
            reports = data.get("list", [])
            results = [f"[{r['corp_name']}] {r['report_nm']} ({r['rcept_dt']})" for r in reports]
            return "\n".join(results) if results else "최근 공시가 없습니다."
        return f"DART 응답 오류: {data.get('message')}"
    return "API 서버 통신 실패"

if __name__ == "__main__":
    # Render 포트 환경변수 반영 실행
    port = int(os.environ.get("PORT", 10000))
    mcp.run(transport="http", host="0.0.0.0", port=port)