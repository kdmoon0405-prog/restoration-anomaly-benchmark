# 주형 GPU 반환 검토와 다음 연구 작업

검토일은 2026-11-09다. Incoming branch는 exp/pcb-full-cohort-juhyung이며 commit은 4c2fc408e520c57dd015d4ce7d1fb565741d2c00이다. ZIP SHA256은 c7c984157f6a7daf6e764c9bfe066578d8a6176aa4a4e3bec26b5ef7bfa8648d다.

## 검토 범위

명시된 213개 파일의 hash가 일치했고 unlisted 파일은 0개였다. README, PCB·실사형·Screw endpoint 보고서와 CSV, protocol, session, bank, calibration metadata를 검토했다. 원본 prediction 배열·bank·RGB·GT는 원격에 보관돼 있다. 이번 pooled pixel 지표는 저장된 수치다.

PCB raw COMPLETE 1,140/1,140 unit, 54,720 tile query의 구성과 session hash를 확인했다. Runtime source 26개의 hash는 검토 checkout과 기존 동일 PatchCore source 파일에서 확인했다. 세 script의 실행 당시 LF와 새 checkout CRLF 차이를 확인해 명시적 LF attributes를 추가했다. Bank payload SHA 19c3bb03...278e는 이전 실제 fit bank와 일치한다. Selection index 값의 인코딩 hash와 NPY 파일 hash는 각각 별도 필드다.

PCB 3조건과 실사형 56조건의 image robust 통계와 q0.99 threshold를 저장 calibration score에서 재구성했다. 총 59개가 일치했다. 저장 test score로 Image AUROC/F1을 재계산한 값도 일치한다. Pixel 통계와 pooled AU-PRO의 독립 재계산에는 원본 배열이 필요하다.

## PCB 결과와 추가 분석

| variant | TP | FN | FP | TN | Image AUROC | Image F1 |
|---|---:|---:|---:|---:|---:|---:|
| clean | 76 | 24 | 4 | 96 | 0.9714 | 0.8444 |
| Bicubic | 71 | 29 | 3 | 97 | 0.9680 | 0.8161 |
| SwinIR | 54 | 46 | 1 | 99 | 0.9544 | 0.6968 |

SwinIR−Bicubic의 pooled AU-PRO 차이는 +0.00483155다. Anomaly board 100개의 per-image AU-PRO 차이 평균은 +0.00372962이며, post-hoc paired bootstrap 95% 구간은 [+0.00060021, +0.00671106]이다. 현재 고정 bank/fit에 조건부인 사례 평균의 구간이다. Pooled AU-PRO의 구간은 산출하지 않았다. 기존 bootstrap 함수를 2,000회/seed 11로 적용했고, 실사형 42개 비교도 모두 보고했다.

Bicubic 대비 localization regression 33개 중 suppression 5개, geometry_candidate 28개다. 고정 taxonomy에 따른 post-hoc 분류다. 원인은 후속 map/feature 분석에서 구분한다. 각 regression subset의 delta AU-PRO 최저 3개와 성공 최고 3개를 선택했다. 동률은 sample 경로 순이다. selected_native_map_cases.csv의 9개 보드×3variant는 후속 정성 분석을 위한 선택 사례다.

## 실사형 보고 문구 정정

추가 열화 12조건에서 Real-ESR 계열이 전체 정밀도로 최고인 것은 11조건이다. Screw blur σ0.8에서는 SwinIR 0.7726005600552853, RealESRNet 0.7725502430519956이며 차이는 0.0000503170032897이다. 두 값은 세 자리 반올림에서 0.773으로 같아진다. Exact ranking과 반올림 동률을 별도로 기록했다.

LPIPS와 AU-PRO의 Spearman 약 −0.82는 동일 영상·조건을 공유하는 56조건의 기술통계다. 이를 독립 표본 56개로 취급해 유의성을 검정하거나 보편적인 model 선택 규칙으로 사용하지 않는다. Screw four-endpoint에서는 GAN endpoint가 LPIPS를 개선하면서 localization은 PSNR endpoint보다 낮았고 기존 case C를 재현했다. 연구 주장은 열화·category·endpoint 조건을 명시해 구성한다.

Screw의 이미지 단위 판정 실패도 결과에 포함한다. 추가 열화가 없는 새 MATLAB family에서도 Image AUROC가 낮아 기존 PIL family와 bank, split, 전처리, score 정의를 추적할 필요가 있다. 현재 자료만으로 원인을 확정하지 않는다. 다음 진단에서도 test label로 threshold를 다시 고르지 않는다.

## 시간 집계

기록된 10session outer 합은 197097.1415044997s(54.7492h)다. 절전 영향이 표시된 002/003의 합은 17685.484560099896s다. 두 session을 전체 기록에 포함하고 성능 검토용 표에서 표시했다.

110,065개 stage CSV 행의 elapsed/end-start와 비중복 구간을 검사했다. JSON stage_aggregate는 9종 phase를 집계한다. Finally에서 실행한 adapter_close 10개 call, 총 2.1632635s는 CSV에만 있다. 보고서의 detector 비중 97.4928%는 기록된 9phase 합이 분모다. Cleanup을 별도 계상해도 반올림 값은 97.5%다. Backbone과 FAISS는 이 stage 내부에서 분리 계측되지 않았다. 서로 다른 process peak를 합산하지 않았다.

## 수정과 검증

exp/juhyung-return-review-fixes에서는 세 script의 LF attributes, synthetic fixture의 RAM 조회 mock, 보고서 문구를 수정했다. 첫 fixture 수정에서 mock 대상을 잘못 지정한 오류를 실제 getter인 pcb_tiled_runner.available_ram으로 수정했다. Production RAM guard와 연구 logic은 동일하다. 관련 테스트는 89 passed/1 skipped다.

CPU exp/juhyung-results-analysis에 read-only 분석기, plot, 테스트를 추가했다. 분석·보고 테스트 15 passed, 기존 CPU smoke 2행을 확인했다. 신규 63조건(PCB 3＋실사형 56＋Screw endpoint 4)을 기존 master 70행에 추가해 133행/9protocol groups로 집계했다. 영상과 조건 재사용을 독립 반복으로 세지 않는다. Endpoint의 seed/fit count는 제공된 기계판독 metadata에 없어 master에서 빈 값으로 남겼다.

두 수치 PNG를 직접 열어 label, 단위, 색 범위와 annotation을 확인했다. 원본 ZIP·결과 CSV와 새 분석은 별도 경로에 보존했다.

## 재현

구현 worktree에서 기존 Python 환경을 명시해 실행한다. 새 tag를 사용한다.

```powershell
$py = '..\..\.venv\Scripts\python.exe'
$tag = Get-Date -Format 'yyyyMMdd-HHmmss'
& $py scripts/analyze_gpu_return.py --package ..\juhyung-return-review-20261109\artifacts\return-package-20261109 --output "..\juhyung-return-review-20261109\replay-$tag"
& $py scripts/build_research_master_table.py --catalog configs/research_reporting_gpu_return_20261109.json --output "..\juhyung-return-review-20261109\master-$tag"
& $py scripts/smoke_test.py
```

다음 임무는 주형의 원본 map 부분 전달·image score 진단·작은 exact 검색 batch 비교, 지혁의 기존 bank-domain 결과 완료·matched Bicubic bank 대조군, CPU의 반환 통합·선택 map 분석·실물장치 인터페이스 초안이다. 실행 범위와 기록 규칙은 별도 전달 프롬프트로 정리한다.
