"""첫 admin 사용자 추가 (CLI)."""
from __future__ import annotations

import getpass
import os
import sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

import bcrypt
from supabase import create_client


def main():
    print("=== COMMANINE 사용자 추가 ===\n")
    name = input("이름 (예: 박병관): ").strip()
    if not name:
        print("[ERROR] 이름 필수")
        return 1

    pin = getpass.getpass("PIN 4자리 (입력 안 보임): ").strip()
    if not pin or len(pin) != 4 or not pin.isdigit():
        print("[ERROR] PIN은 숫자 4자리")
        return 1

    role = input("역할 [admin/staff] (기본 admin): ").strip() or "admin"

    pin_hash = bcrypt.hashpw(pin.encode(), bcrypt.gensalt()).decode()
    client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])

    # Check exists
    existing = client.table("users").select("id").eq("name", name).execute()
    if existing.data:
        update = input(f"'{name}' 이미 존재. PIN 변경? [y/N]: ").strip().lower()
        if update != "y":
            return 0
        client.table("users").update({"pin_hash": pin_hash, "role": role, "is_active": True}).eq("name", name).execute()
        print(f"[OK] '{name}' PIN/역할 갱신")
    else:
        client.table("users").insert({"name": name, "pin_hash": pin_hash, "role": role}).execute()
        print(f"[OK] '{name}' 사용자 추가됨 ({role})")

    print(f"\n로그인 가능: streamlit run app.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
