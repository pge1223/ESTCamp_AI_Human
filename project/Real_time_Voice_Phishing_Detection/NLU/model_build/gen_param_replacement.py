"""
ONNX 모델에서 Transpose 노드를 추출해 param_replacement.json 자동 생성.

onnx2tf v1.26.3 버그: 4D perm을 5D 텐서에 잘못 적용 (NCHW→NHWC 변환 오류).
해결: 모든 Transpose 노드를 원본 ONNX perm 값으로 고정하여 onnx2tf 수정 차단.

실행: python gen_param_replacement.py  (Docker 내부에서)
출력: /app/output/param_replacement.json
"""
import json
import onnx

MODEL = "/app/input/model_merged.onnx"
OUTPUT = "/app/output/param_replacement.json"

model = onnx.load(MODEL)
operations = []
for node in model.graph.node:
    if node.op_type != "Transpose":
        continue
    for attr in node.attribute:
        if attr.name == "perm":
            perm = list(attr.ints)
            operations.append({
                "op_name": node.name,
                "param_target": "attributes",
                "param_name": "perm",
                "values": perm,
            })

result = {"operations": operations}
with open(OUTPUT, "w") as f:
    json.dump(result, f, indent=2)

print(f"생성 완료: {OUTPUT}")
print(f"  총 {len(operations)}개 Transpose 노드 고정")
perm_types = {}
for op in operations:
    key = str(op["values"])
    perm_types[key] = perm_types.get(key, 0) + 1
for perm, count in sorted(perm_types.items()):
    print(f"  perm {perm}: {count}개")
