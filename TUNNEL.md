# Cloudflare Tunnel 가이드

외부에서 로컬 서버에 접근할 때 사용합니다.

## 설치

```bash
brew install cloudflare/cloudflare/cloudflared
```

---

## 실행

```bash
# 1. 먼저 서버 상태 확인
curl -s http://localhost:8000/api/health

# 2. 서버가 정상이면 터널 실행
nohup cloudflared tunnel --url http://localhost:8000 >> ~/cloudflared.log 2>&1 & \
  sleep 3 && grep -o 'https://[^|]*trycloudflare.com' ~/cloudflared.log | tail -1
```

⚠️ **주의**: 서버가 먼저 실행되어 있어야 합니다. 서버 없이 터널만 실행하면 502 에러 발생.

---

## URL 재확인

Quick Tunnel은 재시작할 때마다 URL이 변경됩니다.

```bash
grep -o 'https://[^|]*trycloudflare.com' ~/cloudflared.log | tail -1
```

---

## 종료

```bash
pkill -f cloudflared
```

---

## 로그 확인

```bash
tail -f ~/cloudflared.log
```

---

## 로그 초기화 후 재시작

```bash
pkill -f cloudflared && rm -f ~/cloudflared.log && \
nohup cloudflared tunnel --url http://localhost:8000 >> ~/cloudflared.log 2>&1 & \
  sleep 3 && grep -o 'https://[^|]*trycloudflare.com' ~/cloudflared.log | tail -1
```
