# 07.memory (로컬 전용)

이 폴더는 로컬 영속 메모리 디렉토리에 연결되는 **junction point** 자리입니다. Claude가 세션 간 사적인 메모를 남기는 용도이며, 리포에는 동기화되지 않습니다.

## 로컬 설정 (Windows)

```cmd
rmdir vault-seed\07.memory
mklink /J vault-seed\07.memory C:\path\to\your\memory
```

## 사용 규약

- `agents/save_session.py`가 세션 요약을 `07.memory/sessions/`에 사본을 남깁니다.
- Claude는 이 폴더에 자유롭게 읽고 쓸 수 있습니다.
- 외부 공유하지 않을 사적 컨텍스트를 둡니다.
