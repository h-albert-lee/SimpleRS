# simplers/batch/rules/base.py
import abc
from typing import List, Dict, Any # Dict, Any 추가

class BaseGlobalRule(abc.ABC):
    """글로벌 후보 생성 규칙의 기본 인터페이스"""
    rule_name: str = "BaseGlobalRule" # 규칙 이름 식별용 (로깅 등)

    @abc.abstractmethod
    def apply(self, context: Dict[str, Any]) -> List[str]:
        """
        컨텍스트(context) 객체를 받아 글로벌 후보 콘텐츠 ID 리스트를 반환합니다.
        컨텍스트는 필요한 데이터(contents_list 등)와 DB 클라이언트/풀을 포함할 수 있습니다.
        """
        pass

class BaseClusterRule(abc.ABC):
    """클러스터 후보 생성 규칙의 기본 인터페이스"""
    rule_name: str = "BaseClusterRule"

    @abc.abstractmethod
    def apply(self, cluster_users: List[Dict[str, Any]], context: Dict[str, Any]) -> List[str]:
        """
        해당 클러스터의 사용자 목록(cluster_users)과 컨텍스트(context) 객체를 받아
        클러스터 후보 콘텐츠 ID 리스트를 반환합니다.
        """
        pass

class BaseLocalRule(abc.ABC):
    """로컬(사용자별) 후보 생성 규칙의 기본 인터페이스"""
    rule_name: str = "BaseLocalRule"

    @abc.abstractmethod
    def apply(self, user: Dict[str, Any], context: Dict[str, Any]) -> List[str]:
        """
        개별 사용자 정보(user)와 컨텍스트(context) 객체를 받아
        로컬 후보 콘텐츠 ID 리스트를 반환합니다.
        """
        pass