# 06.workspace (로컬 전용)

이 폴더는 Windows 로컬 디스크의 작업 디렉토리에 연결되는 **junction point** 자리입니다. 리포에는 placeholder만 동기화되고, 실제 파일은 동기화되지 않습니다.

## 로컬 설정 (Windows)

리포를 클론한 뒤, 이 폴더를 삭제하고 원하는 로컬 경로로 junction을 만드세요:

```cmd
rmdir vault-seed\06.workspace
mklink /J vault-seed\06.workspace C:\path\to\your\workspace
```

PowerShell:
```powershell
Remove-Item -Recurse -Force .\vault-seed\06.workspace
New-Item -ItemType Junction -Path .\vault-seed\06.workspace -Target C:\path\to\your\workspace
```

`.gitignore`에 의해 내용물은 푸시되지 않습니다.
