# Jekyll & Hyde — `model_JekyllHyde`

**Independent dual-persona LLM** (Gemma 2 2B + **dual LoRA adapters**) with a self-hosted chat platform, MCP guidelines, structured responses, domain specialization, and continuous learning.

![Recommended use cases](docs/screenshots/00-use-cases-overview.png)

---

## 어디에 쓰면 좋을까? (Recommended use)

| 사용처 | 이렇게 쓰세요 | 모드 |
|--------|----------------|------|
| **로컬 PC / 미니 PC** | 설치 후 `http://127.0.0.1:8080` — GPU 8GB면 4-bit dual LoRA로 동작 | Chat · Duel |
| **주식·투자 리서치** | 실시간 Yahoo/FDR 데이터 + 5단계 투자 메모 파이프라인 | Chat (`investment_memo`) |
| **커뮤니티 가이드라인 감사** | Cursor MCP로 가이드라인 주입 → Duel 또는 Jekyll 분석 | Duel · Jekyll |
| **정책 레드팀 / 회색지대** | Hyde 프로브 ↔ Jekyll verdict, 약점·하드닝 제안 | Hyde · Duel |
| **Cursor / Claude Desktop** | `jekyll-hyde` MCP 서버 — 채팅·Quant·검증 API 도구 | MCP |
| **오프라인·에어갭** | Releases 모델 part + app.zip, Ollama 없이 로컬 가중치 | Self-host |

> **적합:** 금융/보안/정책 특화 보조, 가이드라인 스트레스 테스트, 소형 GPU 워크스테이션.  
> **부적합:** 범용 ChatGPT 대체, 실시간 트레이딩 실행, 법률/투자 최종 판단 (항상 human-in-the-loop).

---

## 빠른 설치 (Windows)

![Install steps](docs/screenshots/07-install-steps.png)

[Release v1.2.3](https://github.com/Benjamin5607/model_JekyllHyde/releases/tag/v1.2.3)에서 **전체 파일** 다운로드:

| File | Purpose |
|------|---------|
| [JekyllHyde-1.2.3-app.zip](https://github.com/Benjamin5607/model_JekyllHyde/releases/download/v1.2.3/JekyllHyde-1.2.3-app.zip) | Platform, scripts, configs |
| [model.part00–02.gz](https://github.com/Benjamin5607/model_JekyllHyde/releases/tag/v1.2.3) | Model weights (gzip L9, 3 parts) |

```powershell
# 1) app.zip 압축 해제
# 2) model.part00.gz ~ part02.gz 를 같은 폴더에 복사
# 3) install.bat 실행
# 4) 브라우저 → http://127.0.0.1:8080
scripts\start.bat          # 이후 실행 (백그라운드)
scripts\stop.bat           # 종료
```

**Requirements:** Windows 10/11 · Python 3.10+ · NVIDIA GPU 8 GB+ VRAM recommended

---

## 웹 UI 사용법

서버 실행 후 브라우저에서 **http://127.0.0.1:8080** 을 엽니다.

### 1) 메인 화면 — Chat 모드 (기본)

일반 대화, 투자 메모, 가이드라인 Q&A. 하늘색 테마.

![Platform — Chat mode](docs/screenshots/01-platform-chat.png)

- 왼쪽 **Pocket Quant**: 시장 스캔 (한국/미국 등)
- 상단 제안 칩: Stock analysis · Guideline audit · Gray-zone · Policy hardening
- 메시지 입력 후 **전송** — 응답 언어는 입력 언어를 따릅니다

### 2) Jekyll / Hyde / Duel — 페르소나 전환

사이드바 **모드** 세그먼트로 전환. UI 색상 + **LoRA adapter**가 함께 바뀝니다 (v1.2.3+).

| 모드 | 스크린샷 | 용도 |
|------|-----------|------|
| **Jekyll** (민트) | ![Jekyll mode](docs/screenshots/02-mode-jekyll.png) | 가이드라인 방어, 거절, 정책·시장 분석 |
| **Hyde** (붉은색) | ![Hyde mode](docs/screenshots/03-mode-hyde.png) | 레드팀 프로브, 회색지대 테스트 |
| **Duel** (양분) | ![Duel mode](docs/screenshots/04-mode-duel.png) | 투자 토론 / 가이드라인 검증 / 일반 주제 중간지점 합의 |

**Duel 자동 라우팅**

| 종류 | 트리거 | 결과 |
|------|--------|------|
| Equity | 금융 질의 + live data | Bear ↔ Defense → gray zones + middle ground |
| Guideline | MCP 가이드라인 + 정책 주제 | Hyde probe ↔ Jekyll verdict |
| Debate | 그 외 | 반박 후 **Middle ground** 합의 |

### 3) 설정 — MCP · 지속 학습

⚙ 버튼 → **Continuous learning** + **MCP 연동** (Cursor `mcp.json` 스니펫 복사).

![Settings — MCP & learning](docs/screenshots/05-settings-mcp-learning.png)

- **Curate / Train from feedback**: 피드백 → LoRA 재학습 파이프라인 (20샘플·6h 간격)
- **가이드라인**: UI 편집 없음 — MCP `set_guidelines` / `get_guidelines` 사용

### 4) 대화 예시

![Chat response](docs/screenshots/06-chat-response.png)

스크린샷 재촬영: `python scripts\capture_readme_screenshots.py` (서버 `:8080` 필요)

---

## Cursor MCP 연동

1. 플랫폼 **설정 → MCP** 에서 `mcp.json` 스니펫 복사  
2. Cursor **Settings → MCP** 에 서버 추가  
3. 채팅에서 `@jekyll-hyde` 도구로 가이드라인·Quant·검증 호출  

```json
{
  "mcpServers": {
    "jekyll-hyde": {
      "command": "python",
      "args": ["-m", "safety_eval.mcp.server"],
      "cwd": "C:/path/to/model_JekyllHyde"
    }
  }
}
```

---

## 소스에서 실행 (개발자)

```powershell
git clone https://github.com/Benjamin5607/model_JekyllHyde.git
cd model_JekyllHyde
pip install -e ".[train,quant,mcp]"
scripts\start.bat
```

| 명령 | 설명 |
|------|------|
| `python scripts\verify_today.py` | 전체 검증 |
| `python scripts\data_diet.py` | 데이터셋 시맨틱 디듀프 |
| `scripts\train_lora.bat` | Dual LoRA 학습 + merge + GGUF |
| `python -m safety_eval.storage.optimizer` | 로그·dist·체크포인트 정리 |

---

## Project structure

```
model_JekyllHyde/
├── safety_eval/           # Core platform
│   ├── platform/          # Engine, duel, UI server, formats
│   ├── quant/             # Market data, pipeline, research
│   ├── specialization/    # Domain detection (quant/policy/gray/hardening)
│   ├── learning/          # Data diet, curator, continuous train pipeline
│   ├── storage/           # Optimizer + release packager
│   ├── verification/      # Free API cross-check providers
│   └── mcp/               # Cursor MCP server
├── training/              # LoRA dataset, train, merge
├── models/
│   ├── merged/jekyll-hyde/   # Fine-tuned weights (download via Releases)
│   └── adapters/             # jekyll-lora + hyde-lora (runtime switching)
├── docs/screenshots/      # README UI captures
├── config/                # Platform, storage, specialization YAML
├── data/                  # Guidelines probes, learning queue
├── scripts/               # start/stop, install, build_release, verify
└── dist/                  # Release artifacts (local build; auto-pruned)
```

**Not in repo (by design):** `model.safetensors` (~5 GB), `secrets/`, `.venv*`, old `dist/` builds.

---

## Features

| Feature | Description |
|---------|-------------|
| **Chat + investment memo** | 5-stage pipeline: live data → per-section LLM → assemble |
| **Duel** | Auto-routes: **equity** · **guideline** · **debate** |
| **Guideline / gray-zone / hardening** | Slim persona routing + **Jekyll/Hyde LoRA switch** |
| **Learning** | Data diet → dual QLoRA updates → auto GGUF export (llama.cpp) |

### Data diet (efficiency)

- **Semantic dedup:** bge-small embeddings; cosine ≥ 0.92 rejects near-duplicates (not just hash)
- **Balancing:** FIFO caps per category & persona; max 2,000 curated records
- **Compact prompts:** slim Jekyll/Hyde routing + compact quant digest (fewer tokens)
- **Run cleanup:** `python scripts\data_diet.py`

### Dual LoRA + GGUF pipeline (v1.2.3+)

- **Runtime:** 4-bit frozen Gemma base + `jekyll-lora` / `hyde-lora` hot-swap per request
- **Training:** `train_lora.py --persona both` filters dataset by persona bucket
- **Deploy snapshot:** merge Jekyll adapter → optional GGUF Q4_K_M after each continuous-learning cycle
- **Bootstrap:** legacy `jekyll-hyde-lora` auto-copies to both adapters if missing

---

## Build release (maintainers)

```powershell
scripts\build_release.ps1
```

Output: `dist/JekyllHyde-1.2.3-app.zip` + `model.partXX.gz` + manifest.

---

## Release history

| Tag | Notes |
|-----|-------|
| v1.2.3 | [Dual LoRA + auto GGUF](https://github.com/Benjamin5607/model_JekyllHyde/releases/tag/v1.2.3) |
| [v1.2.2](https://github.com/Benjamin5607/model_JekyllHyde/releases/tag/v1.2.2) | Data diet, semantic dedup, slim routing, compact quant |
| [v1.2.1](https://github.com/Benjamin5607/model_JekyllHyde/releases/tag/v1.2.1) | Structure cleanup, dist auto-prune |
| [v1.2.0](https://github.com/Benjamin5607/model_JekyllHyde/releases/tag/v1.2.0) | Duel middle-ground synthesis |
| [v1.1.0](https://github.com/Benjamin5607/model_JekyllHyde/releases/tag/v1.1.0) | 5-stage investment memo pipeline |
| [v1.0.0](https://github.com/Benjamin5607/model_JekyllHyde/releases/tag/v1.0.0) | Initial release |

---

## License

- **Code:** MIT — [LICENSE](LICENSE)
- **Model:** [Gemma 2](https://huggingface.co/google/gemma-2-2b-it) — [Gemma Terms](https://ai.google.dev/gemma/terms)
