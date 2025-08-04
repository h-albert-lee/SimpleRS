import abc
from typing import List, Dict, Any, Tuple, Sequence

class BaseApiRule(abc.ABC):
    """실시간 API 추천 규칙의 기본 클래스"""
    rule_name: str = "BaseApiRule" # 규칙 식별 이름 (로깅 등에 사용)

    def __init__(self):
        # 필요시 공통 초기화 (예: 캐시 클라이언트 주입)
        pass

    @abc.abstractmethod
    async def apply(self, user_context: Dict[str, Any], items: Sequence) -> Sequence:
        """
        규칙을 적용하는 메소드.
        user_context: 사용자 정보, 요청 정보 등 규칙 적용에 필요한 데이터 딕셔너리
        items: 규칙을 적용할 아이템 리스트 (단계에 따라 형태가 다름)
        반환값: 규칙이 적용된 아이템 리스트
        """
        pass

class BasePreRankFilterRule(BaseApiRule):
    """랭킹 모델 적용 전 후보군 필터링/추가 규칙"""
    rule_name: str = "BasePreRankFilterRule"
    async def apply(self, user_context: Dict[str, Any], candidates: List[str]) -> List[str]:
        # 후보 ID 리스트를 받아 필터링/추가 후 반환
        raise NotImplementedError

class BasePostRankReorderRule(BaseApiRule):
    """랭킹 모델 적용 후 순위 재조정/필터링 규칙"""
    rule_name: str = "BasePostRankReorderRule"
    async def apply(self, user_context: Dict[str, Any], ranked_items: List[Tuple[str, float]]) -> List[Tuple[str, float]]:
        # (아이템 ID, 점수) 튜플 리스트를 받아 순서 변경/필터링 후 반환
        raise NotImplementedError