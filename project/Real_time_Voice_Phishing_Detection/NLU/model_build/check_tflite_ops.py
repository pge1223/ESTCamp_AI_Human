"""TFLite 모델에 Flex/Custom 연산 포함 여부 확인"""
import sys
from tflite import Model

path = sys.argv[1] if len(sys.argv) > 1 else "/app/tflite/model_float16.tflite"

with open(path, "rb") as f:
    buf = bytearray(f.read())

model = Model.Model.GetRootAs(buf, 0)
ops = {}
flex_ops = []

for sg_idx in range(model.SubgraphsLength()):
    sg = model.Subgraphs(sg_idx)
    for op_idx in range(sg.OperatorsLength()):
        op = sg.Operators(op_idx)
        code_idx = op.OpcodeIndex()
        opcode = model.OperatorCodes(code_idx)
        builtin = opcode.BuiltinCode()
        custom_name = opcode.CustomCode()
        if builtin == 32 or builtin == 0:  # CUSTOM=32, 0=generic
            if custom_name:
                name = custom_name.decode() if isinstance(custom_name, bytes) else str(custom_name)
                flex_ops.append(name)
                ops[name] = ops.get(name, 0) + 1
            else:
                ops["CUSTOM_UNKNOWN"] = ops.get("CUSTOM_UNKNOWN", 0) + 1
        else:
            ops[f"B{builtin}"] = ops.get(f"B{builtin}", 0) + 1

print(f"모델: {path}")
print(f"총 op 종류: {len(ops)}")
flex_unique = list(set(flex_ops))
if flex_unique:
    print(f"Flex/Custom ops ({len(flex_unique)}): {flex_unique[:10]}")
else:
    print("Flex/Custom ops: 없음 (순수 BUILTIN)")
print(f"파일 크기: {len(buf)/1024**2:.1f} MB")
