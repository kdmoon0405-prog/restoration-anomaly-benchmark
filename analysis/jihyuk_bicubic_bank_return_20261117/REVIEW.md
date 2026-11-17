# 지혁 Bicubic-bank 확장 반환 CPU 검토

2026-11-17 수신. 이 문서는 전달된 scalar metadata의 무결성과 내부 대조 결과다. 모델·raw map·bank 배열은 이번 수신에 없다.

## 수신과 검증 범위

- SUMMARY.md는Hazelnut, SUMMARY (1).md는Screw다. 각ZIP내부SUMMARY와바이트가같다.
- Hazelnut ZIP은39586bytes/SHA256 c8988ce32e040c85f2b046d58838a4326ec81dde4b5c186aa2d898244885950b, Screw는56324bytes/SHA256 305e106789aa7d48c333c3ded478ed7f81fc3d1a98b81322c01cdb1978145a6a다.
- 각ZIP은13파일이다. CRC와receipt의12payload bytes/SHA,분석manifest의5개표해시를검증했다.
- 새확장4조건과개별이미지540행(Hazelnut220/Screw320),paired378행(140/238)을대조했다. sample/query중복·정상/이상개수·delta산술·PSNR/SSIM평균·이미지별화질표를확인했다.
- 제공된normalized_score와label로4조건의image AUROC를독립재계산해summary와일치했다. pooled AU-PRO와pixel AUROC는raw map이필요하므로저장점의산술·표간일치만확인했다.
- 반환provenance/RUN_RECORD/분석manifest에기록된query hash와baseline hash는일치한다. 원래baseline의manifest/파일은첨부되지않아그원본과의독립대조는남아있다.

## 주된 결과

| Category | 고정query | clean bank | Bicubic bank | pooled AU-PRO 변화 |
|---|---|---:|---:|---:|
| Hazelnut | Bicubic | 0.817519 | 0.837985 | +0.020466 |
| Hazelnut | SwinIR | 0.841252 | 0.854893 | +0.013641 |
| Screw | Bicubic | 0.799066 | 0.898887 | +0.099821 |
| Screw | SwinIR | 0.853182 | 0.861553 | +0.008372 |

Bicubic bank를고정한SwinIR-query minus Bicubic-query는Hazelnut+0.016908,Screw−0.037334다. Screw에서는PSNR+2.437522dB/SSIM+0.016426과동시에image AUROC가0.934208에서0.725763으로,pooled AU-PRO가0.898887에서0.861553으로변했다. 동일bank에서query복원의화질과검사지표가다르게움직인관측이다. 결함이실제로RGB에서지워졌는지는사진으로추가확인한다.

고정SwinIR query에서clean→Bicubic bank를비교하면Screw의pooled AU-PRO는+0.008372지만,평균per-image AU-PRO delta는−0.010678이고119개이상영상중64개가감소했다. 이는위의동일bank query비교와다른대조다. Hazelnut의동일SwinIR-query bank변경은pooled+0.013641,per-image평균−0.000247,감소31/70이다. pooled값과per-image평균을같은통계로설명하지않는다.

두category의seed11 paired 결과다. pooled CI는없고새CI를계산하지않았다. 인과기전이나현장보편성,최적bank의확정을이결과만으로주장하지않는다.

## 실행 복구와 소스

Hazelnut은raw prediction저장후normal mask_path=None 처리에서실패했고,저장예측으로평가만재개했다고기록돼있다. 최종COMPLETE와initial-failure hash,raw hash,quality-baseline재사용,모델재실행없음이provenance/RUN_RECORD에남아있다. 원래실패status와transcript,raw배열자체는이번ZIP에없다.

첨부patch SHA는4aeeade3e0e0438fccab390bcb1db5acb24d81bfed2c564ef5ea7a4e665b03a6이며추가파일4개(실행runner,extension검증module,resume utility,실행측5테스트)다. 이패치는CPU분석기코드/분석측5테스트와수정된base producer전체를포함하지않는다. CPU의현재8aaee07전달checkout에서도git apply --check가통과했다. 실행코드자체는적용하지않았다.

패치에서추출한실행runner의SHA는Screw기록과맞고,extension module은두run과맞는다. resume script도Hazelnut recovery hash와맞는다. Hazelnut의최초runner hash는ebc196fe…35d4ac이고현재패치의224dbed7…a8d97과다르다. 실패후수정이력과연결해최초실행시점사본을별도보관한다. 기존dirty source표기는유지한다.

Fake실행측5/CPU분석측5통과는담당자보고다. 이번검토에서는이10개테스트를재실행하지않았다. RAM peak는미측정이고기록된CUDA peak는프로세스내torch counter다.

## 기존24조건의 상태

첨부PROGRESS/private노트는기존2×2의24/24완료를보고하고6개run/반환ZIP을기록한다. 그러나이번첨부는확장2run뿐이고기존24의개별receipt·summary/per_image·manifest는없다. 수신폴더와fetch한origin/handoff/jihyuk@c69f1c1에도그반환파일이없다.

따라서현재상태는‘기존24 수행완료보고/결과수신대기,확장4 수신·내부대조완료’다. 주형에게기존24+4전체를새로돌리는작업을부여하지않는다. 먼저완료자료와미푸시8af5aa소스묶음을받고수신/실패/손상으로확인된빈부분만후속판단한다. HTTPS인증복구는이자료회수의선행조건이아니다.

## 주형의 다음 작업

1. Hazelnut/Screw×seed11/23/37의기존6개반환물과28조건집계,미푸시source-only코드및CPU분석기를비공개ZIP또는bundle로받는다.
2. 수신24와확장4를family별로통합하고query/split/checkpoint/source를대조한다. 기존master165의다른protocol결과와같은표본처럼합치지않는다.
3. selected_visual_cases.csv의6개사례를지혁의저장raw maps/RGB/GT에서내보낸다. 고정seed11에서원본·열화·Bicubic·SwinIR RGB,동일query bank비교지도와같은bank query비교지도를완성한다.
4. 통합실행프롬프트의필요구현·실물사진·촬영전50장제안·사람판독·보고서/A0수정은이어간다. 새표와사진으로개선사례와실패사례를함께설명한다.

선정6개는수신per-image표에서각category의Bicubic-bank내SwinIR-minus-Bicubic최대감소·최대증가·0에가까운case를사후로골랐다. 성능평가표본이나정책선정자료로새로쓰지않는다. 원래평가전부의수치를유지한다.
