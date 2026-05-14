import json
import onnx

model = onnx.load("/app/input/model_merged.onnx")

entries = []
for node in model.graph.node:
    if node.op_type != "Transpose":
        continue
    for attr in node.attribute:
        if attr.name == "perm":
            perm = list(attr.ints)
            print(f"{node.name}: perm={perm} len={len(perm)}")
            # perm 길이가 4인 노드만 수집 (5D 텐서와 충돌하는 것들)
            if len(perm) == 4:
                entries.append({
                    "op_name": node.name,
                    "param_target": "attributes",
                    "param_name": "perm",
                    "original_perm": perm,
                })

print(f"\n총 Transpose: {sum(1 for n in model.graph.node if n.op_type=='Transpose')}")
print(f"perm 길이 4인 노드: {len(entries)}")
for e in entries:
    print(f"  {e['op_name']}: {e['original_perm']}")
