# Guardrail Evaluator

이 도구는 가드레일 테스트 결과를 평가하고 시각화하는 스크립트입니다.

## 기능

- 가드레일 테스트 결과 JSON 파일 분석
- 정확도, 정밀도, 재현율, F1 점수 등 성능 지표 계산
- 혼동 행렬 및 성능 지표 시각화
- 카테고리별 성능 분석
- 상세 평가 보고서 생성

## 사용 방법

### 기본 사용법

```bash
python guardrail_evaluator.py [테스트_결과_파일.json]
```

### 옵션

- `-o, --output`: 출력 파일 접두사 지정 (기본값: 입력 파일 이름 + "_eval")
- `--show-plots`: 그래프를 화면에 표시


### Validator로 레이블을 예측 
```bash
#python ../guardrail_validator_KOR.py test 9ff3xq112g0i --export --model=anthropic.claude-3-haiku-20240307-v1:0 --prompts=../notebook/output.json
python ../guardrail_validator_KOR.py test <guardrail_id> --export --model=<가장빠른claude모델> --prompts=<notebook폴더안에추출된 output.json>
```


### 결과파일을 evaluator를 통해 분석하기
```bash
# 기본 사용법
#python guardrail_evaluator.py ../guardrail_test_results_9ff3xq112g0i_making-20250603_205401_elapsed-50.7s.json
python guardrail_evaluator.py guardrail_test_results_xxxxxx.json


# 출력 파일 접두사 지정
python guardrail_evaluator.py guardrail_test_results_xxxxxx.json -o my_evaluation

```

## 출력 파일

스크립트는 다음 파일들을 생성합니다:

1. `[접두사]_confusion_matrix.png`: 혼동 행렬 시각화
2. `[접두사]_performance_metrics.png`: 성능 지표 막대 그래프
3. `[접두사]_category_performance.png`: 카테고리별 성능 그래프
4. `[접두사]_report.md`: 상세 평가 보고서

## 평가 보고서 내용

생성된 마크다운 보고서에는 다음 정보가 포함됩니다:

1. 주요 성능 지표 (정확도, 정밀도, 재현율, F1 점수)
2. 혼동 행렬 분석
3. 응답 성능 (평균 응답 시간)
4. 오류 분석 (잘못 차단된 표현, 잘못 통과된 표현)
5. 카테고리별 성능 분석

## 요구 사항

- Python 3.6 이상
- 필요 패키지: pandas, matplotlib, seaborn, scikit-learn, numpy

```bash
pip install pandas matplotlib seaborn scikit-learn numpy
```