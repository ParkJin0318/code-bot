from app.prompts.base import (
    CODEBASE_PERSONA,
    SLACK_FORMAT_RULES,
    SECURITY_RULES,
    COMMON_GUIDELINES,
    ANSWER_FORMAT_EXAMPLE,
    NO_CODE_TERMS_RULE,
)


CODEBASE_PROMPT = f"""{CODEBASE_PERSONA}

{SLACK_FORMAT_RULES}

{SECURITY_RULES}

{NO_CODE_TERMS_RULE}

{COMMON_GUIDELINES}

{ANSWER_FORMAT_EXAMPLE}

## 코드 컨텍스트
{{context}}

## 관련 Confluence 문서
{{documents}}
**중요**: 위 문서 목록이 비어있지 않다면, 답변 마지막에 반드시 아래 형식으로 "관련 문서" 섹션을 추가하세요:
```
📄 *관련 문서*
아래 문서들도 도움이 될 수 있으니 참고해보세요!
• <URL1|문서제목1>
• <URL2|문서제목2>
```
주의: Slack 링크 형식은 <URL|제목> 입니다. URL이 먼저, 파이프(|), 그 다음 제목 순서입니다.

## 질문: {{question}}

## 답변:"""
