# Rule Development Guide

## 📋 개요

SimpleRS 시스템에서 새로운 추천 룰을 개발하는 방법을 설명합니다.

## 🏗️ 룰 아키텍처

### 룰 타입

1. **Global Rules**: 모든 사용자에게 공통으로 적용되는 룰
2. **Local Rules**: 개별 사용자의 특성에 따라 적용되는 룰

### 베이스 클래스

```python
# batch/rules/base.py

class BaseGlobalRule:
    """글로벌 룰의 베이스 클래스"""
    rule_name = "BaseGlobalRule"
    
    def apply(self, context: Dict[str, Any]) -> List[str]:
        """
        글로벌 룰을 적용하여 후보 컨텐츠 ID 리스트를 반환
        
        Args:
            context: 실행 컨텍스트 (contents_list, db connections 등)
            
        Returns:
            후보 컨텐츠 ID 리스트
        """
        raise NotImplementedError

class BaseLocalRule:
    """로컬 룰의 베이스 클래스"""
    rule_name = "BaseLocalRule"
    
    def apply(self, user: Dict[str, Any], context: Dict[str, Any]) -> List[str]:
        """
        로컬 룰을 적용하여 사용자별 후보 컨텐츠 ID 리스트를 반환
        
        Args:
            user: 사용자 정보
            context: 실행 컨텍스트
            
        Returns:
            후보 컨텐츠 ID 리스트
        """
        raise NotImplementedError
```

## 🔧 새로운 Global Rule 개발

### 1. 룰 클래스 생성

```python
# batch/rules/global_rules.py

@register_global_rule("my_new_global_rule")
class MyNewGlobalRule(BaseGlobalRule):
    rule_name = "MyNewGlobalRule"
    
    def apply(self, context: Dict[str, Any]) -> List[str]:
        """
        새로운 글로벌 룰 로직 구현
        """
        logger.debug(f"Applying rule: {self.rule_name}")
        
        # 입력 검증
        contents_list = context.get('contents_list', [])
        if not contents_list:
            logger.warning(f"{self.rule_name}: No contents available")
            return []
        
        try:
            # 룰 로직 구현
            candidates = []
            
            # 예시: 특정 조건을 만족하는 컨텐츠 선택
            for content in contents_list:
                if not isinstance(content, dict):
                    continue
                    
                content_id = content.get("_id") or content.get("id")
                if not content_id:
                    continue
                
                # 여기에 룰 조건 구현
                if self._meets_criteria(content):
                    candidates.append(str(content_id))
            
            logger.info(f"{self.rule_name}: Found {len(candidates)} candidates")
            return candidates
            
        except Exception as e:
            logger.error(f"{self.rule_name}: Unexpected error: {e}", exc_info=True)
            return []
    
    def _meets_criteria(self, content: Dict[str, Any]) -> bool:
        """
        컨텐츠가 룰 조건을 만족하는지 확인
        """
        # 룰별 조건 로직 구현
        return True
```

### 2. 룰 등록 및 사용

```python
# batch/pipeline/global_candidate.py에서 사용

from batch.rules.global_rules import GLOBAL_RULE_REGISTRY

def compute_global_candidates(context: Dict[str, Any]) -> List[str]:
    # 새로운 룰 사용
    my_rule = GLOBAL_RULE_REGISTRY.get("my_new_global_rule")
    if my_rule:
        candidates = my_rule.apply(context)
        return candidates
    return []
```

## 🎯 새로운 Local Rule 개발

### 1. 룰 클래스 생성

```python
# batch/rules/local_rules.py

@register_local_rule("my_new_local_rule")
class MyNewLocalRule(BaseLocalRule):
    rule_name = "MyNewLocalRule"
    
    def apply(self, user: Dict[str, Any], context: Dict[str, Any]) -> List[str]:
        """
        새로운 로컬 룰 로직 구현
        """
        user_id = user.get('cust_no', 'UNKNOWN')
        logger.debug(f"[{user_id}] Applying rule: {self.rule_name}")
        
        # 입력 검증
        contents_list = context.get('contents_list', [])
        if not contents_list:
            logger.warning(f"[{user_id}] {self.rule_name}: No contents available")
            return []
        
        if not user_id or user_id == 'UNKNOWN':
            logger.warning(f"{self.rule_name}: Invalid user ID")
            return []
        
        try:
            # 사용자별 데이터 조회 (필요시)
            user_data = self._fetch_user_data(user_id)
            if not user_data:
                logger.debug(f"[{user_id}] {self.rule_name}: No user data available")
                return []
            
            # 룰 로직 구현
            candidates = []
            for content in contents_list:
                if not isinstance(content, dict):
                    continue
                    
                content_id = content.get("_id") or content.get("id")
                if not content_id:
                    continue
                
                # 사용자별 조건 확인
                if self._matches_user_preference(user_data, content):
                    candidates.append(str(content_id))
            
            logger.info(f"[{user_id}] {self.rule_name}: Found {len(candidates)} candidates")
            return candidates
            
        except (APIConnectionError, DataValidationError) as e:
            logger.warning(f"[{user_id}] {self.rule_name}: External API error: {e}")
            return []
            
        except Exception as e:
            logger.error(f"[{user_id}] {self.rule_name}: Unexpected error: {e}", exc_info=True)
            return []
    
    def _fetch_user_data(self, user_id: str) -> Dict[str, Any]:
        """
        사용자별 데이터 조회 (포트폴리오, 행동 데이터 등)
        """
        # 외부 API 호출 또는 DB 조회
        return {}
    
    def _matches_user_preference(self, user_data: Dict[str, Any], content: Dict[str, Any]) -> bool:
        """
        컨텐츠가 사용자 선호도와 매칭되는지 확인
        """
        # 매칭 로직 구현
        return True
```

### 2. 룰 등록 및 사용

```python
# batch/pipeline/local_candidate.py에서 사용

from batch.rules.local_rules import LOCAL_RULE_REGISTRY

def generate_local_candidates(user: Dict[str, Any], context: Dict[str, Any]) -> List[str]:
    # 새로운 룰 사용
    my_rule = LOCAL_RULE_REGISTRY.get("my_new_local_rule")
    if my_rule:
        candidates = my_rule.apply(user, context)
        return candidates
    return []
```

## 🛡️ 예외 처리 가이드라인

### 1. 예외 타입별 처리

```python
try:
    # 룰 로직 실행
    pass
    
except (APIConnectionError, DataValidationError) as e:
    # 외부 API 오류 - 경고 로그, 빈 결과 반환
    logger.warning(f"{self.rule_name}: External API error: {e}")
    return []
    
except Exception as e:
    # 예상치 못한 오류 - 에러 로그, 빈 결과 반환
    logger.error(f"{self.rule_name}: Unexpected error: {e}", exc_info=True)
    return []
```

### 2. 입력 검증

```python
def apply(self, context: Dict[str, Any]) -> List[str]:
    # 필수 데이터 검증
    contents_list = context.get('contents_list', [])
    if not contents_list:
        logger.warning(f"{self.rule_name}: No contents available")
        return []
    
    # 외부 클라이언트 검증
    os_client = context.get('os_client')
    if not os_client:
        logger.warning(f"{self.rule_name}: OpenSearch client not available")
        return []
```

### 3. 데이터 검증

```python
def _validate_content(self, content: Dict[str, Any]) -> bool:
    """컨텐츠 데이터 유효성 검증"""
    if not isinstance(content, dict):
        return False
        
    content_id = content.get("_id") or content.get("id")
    if not content_id:
        return False
        
    return True
```

## 📊 성능 최적화

### 1. 배치 처리

```python
def apply(self, context: Dict[str, Any]) -> List[str]:
    contents_list = context.get('contents_list', [])
    
    # 대량 데이터 처리시 배치 단위로 처리
    batch_size = 1000
    candidates = []
    
    for i in range(0, len(contents_list), batch_size):
        batch = contents_list[i:i + batch_size]
        batch_candidates = self._process_batch(batch)
        candidates.extend(batch_candidates)
    
    return candidates
```

### 2. 캐싱

```python
from functools import lru_cache

class MyRule(BaseGlobalRule):
    @lru_cache(maxsize=128)
    def _get_cached_data(self, key: str) -> Dict[str, Any]:
        """자주 사용되는 데이터 캐싱"""
        return self._fetch_expensive_data(key)
```

### 3. 조기 종료

```python
def apply(self, context: Dict[str, Any]) -> List[str]:
    max_candidates = context.get('max_candidates_per_rule', 100)
    candidates = []
    
    for content in contents_list:
        if len(candidates) >= max_candidates:
            break  # 조기 종료
            
        if self._meets_criteria(content):
            candidates.append(content_id)
    
    return candidates
```

## 🧪 테스트 작성

### 1. 단위 테스트

```python
# tests/test_rules.py

import unittest
from batch.rules.global_rules import MyNewGlobalRule

class TestMyNewGlobalRule(unittest.TestCase):
    def setUp(self):
        self.rule = MyNewGlobalRule()
        self.context = {
            'contents_list': [
                {'_id': '1', 'category': 'tech'},
                {'_id': '2', 'category': 'finance'},
            ]
        }
    
    def test_apply_returns_candidates(self):
        candidates = self.rule.apply(self.context)
        self.assertIsInstance(candidates, list)
        self.assertGreater(len(candidates), 0)
    
    def test_apply_with_empty_contents(self):
        empty_context = {'contents_list': []}
        candidates = self.rule.apply(empty_context)
        self.assertEqual(candidates, [])
    
    def test_apply_with_invalid_context(self):
        invalid_context = {}
        candidates = self.rule.apply(invalid_context)
        self.assertEqual(candidates, [])
```

### 2. 통합 테스트

```python
# scripts/test_new_rule.py

def test_new_rule_integration():
    """새로운 룰의 통합 테스트"""
    from batch.utils.db_manager import get_mongo_db, load_contents
    from batch.rules.global_rules import GLOBAL_RULE_REGISTRY
    
    # 테스트 데이터 준비
    db = get_mongo_db()
    contents_ddf = load_contents(db)
    contents_list = contents_ddf.compute().to_dict('records')
    
    context = {
        'contents_list': contents_list,
        'mongo_db': db
    }
    
    # 룰 실행
    rule = GLOBAL_RULE_REGISTRY.get("my_new_global_rule")
    candidates = rule.apply(context)
    
    print(f"Generated {len(candidates)} candidates")
    print(f"Sample candidates: {candidates[:5]}")

if __name__ == '__main__':
    test_new_rule_integration()
```

## 📈 모니터링 및 로깅

### 1. 성능 메트릭

```python
import time

def apply(self, context: Dict[str, Any]) -> List[str]:
    start_time = time.time()
    
    try:
        # 룰 로직 실행
        candidates = self._execute_rule_logic(context)
        
        # 성능 로깅
        elapsed_time = time.time() - start_time
        logger.info(f"{self.rule_name}: Generated {len(candidates)} candidates in {elapsed_time:.2f}s")
        
        return candidates
        
    except Exception as e:
        elapsed_time = time.time() - start_time
        logger.error(f"{self.rule_name}: Failed after {elapsed_time:.2f}s: {e}")
        return []
```

### 2. 상세 로깅

```python
def apply(self, context: Dict[str, Any]) -> List[str]:
    logger.debug(f"{self.rule_name}: Starting rule execution")
    
    # 입력 데이터 로깅
    contents_count = len(context.get('contents_list', []))
    logger.debug(f"{self.rule_name}: Processing {contents_count} contents")
    
    # 중간 결과 로깅
    filtered_count = len(filtered_contents)
    logger.debug(f"{self.rule_name}: {filtered_count} contents passed initial filter")
    
    # 최종 결과 로깅
    logger.info(f"{self.rule_name}: Generated {len(candidates)} final candidates")
    
    return candidates
```

## 🚀 배포 가이드

### 1. 룰 추가 체크리스트

- [ ] 룰 클래스 구현 완료
- [ ] 예외 처리 구현 완료
- [ ] 단위 테스트 작성 완료
- [ ] 통합 테스트 실행 완료
- [ ] 성능 테스트 완료
- [ ] 코드 리뷰 완료
- [ ] 문서 업데이트 완료

### 2. 점진적 배포

```python
# 새로운 룰을 점진적으로 활성화
def compute_global_candidates(context: Dict[str, Any]) -> List[str]:
    candidates = []
    
    # 기존 룰들
    existing_candidates = get_existing_candidates(context)
    candidates.extend(existing_candidates)
    
    # 새로운 룰 (플래그로 제어)
    if context.get('enable_new_rule', False):
        new_rule = GLOBAL_RULE_REGISTRY.get("my_new_global_rule")
        if new_rule:
            new_candidates = new_rule.apply(context)
            candidates.extend(new_candidates)
    
    return candidates
```

### 3. A/B 테스트

```python
def apply(self, context: Dict[str, Any]) -> List[str]:
    # A/B 테스트 그룹 확인
    test_group = context.get('ab_test_group', 'control')
    
    if test_group == 'treatment':
        # 새로운 로직
        return self._new_logic(context)
    else:
        # 기존 로직
        return self._existing_logic(context)
```

## 📝 문서화

### 1. 룰 문서 템플릿

```markdown
## MyNewGlobalRule

### 목적
이 룰의 목적과 해결하려는 문제를 설명합니다.

### 로직
룰의 상세한 로직을 설명합니다.

### 입력
- `context`: 실행 컨텍스트
  - `contents_list`: 전체 컨텐츠 리스트
  - `os_client`: OpenSearch 클라이언트 (선택사항)

### 출력
- `List[str]`: 후보 컨텐츠 ID 리스트

### 예외 처리
- `APIConnectionError`: 외부 API 연결 실패시 빈 리스트 반환
- `Exception`: 예상치 못한 오류시 빈 리스트 반환

### 성능 특성
- 평균 실행 시간: ~100ms
- 메모리 사용량: ~50MB
- 외부 API 호출: 없음

### 테스트
- 단위 테스트: `tests/test_my_new_rule.py`
- 통합 테스트: `scripts/test_my_new_rule.py`
```

### 2. 변경 로그

```markdown
## 변경 로그

### v1.1.0 (2024-01-15)
- MyNewGlobalRule 추가
- 성능 최적화: 배치 처리 도입
- 예외 처리 강화

### v1.0.0 (2024-01-01)
- 초기 룰 시스템 구현
```

이 가이드를 따라 새로운 룰을 개발하면 시스템의 일관성과 안정성을 유지할 수 있습니다.