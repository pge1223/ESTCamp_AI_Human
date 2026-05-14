"""
node_transpose_4 이전에 무엇이 오는지 ONNX 그래프를 역방향으로 추적.
5D 텐서를 만드는 op을 찾아 근본 원인 파악.
"""
import onnx

MODEL = "/app/input/model_merged.onnx"
TARGET = "node_transpose_4"

model = onnx.load(MODEL)
graph = model.graph

# node → output 텐서 이름 매핑
output_to_node = {}
for node in graph.node:
    for out in node.output:
        output_to_node[out] = node

# node → input 텐서 이름 매핑
input_to_node = {}
for node in graph.node:
    for inp in node.input:
        if inp not in input_to_node:
            input_to_node[inp] = []
        input_to_node[inp].append(node)

# 타겟 노드 찾기
target_node = None
for node in graph.node:
    if node.name == TARGET:
        target_node = node
        break

if not target_node:
    print(f"노드 {TARGET} 없음")
    exit(1)

print(f"=== {TARGET} ===")
print(f"op_type: {target_node.op_type}")
print(f"inputs: {list(target_node.input)}")
print(f"outputs: {list(target_node.output)}")

# 입력 텐서의 shape 정보 확인
shape_info = {}
for vi in list(graph.input) + list(graph.value_info) + list(graph.output):
    if vi.type.HasField("tensor_type"):
        dims = [d.dim_value if d.dim_value else f"?({d.dim_param})"
                for d in vi.type.tensor_type.shape.dim]
        shape_info[vi.name] = dims

print("\n=== 입력 shape ===")
for inp_name in target_node.input:
    shape = shape_info.get(inp_name, "unknown")
    print(f"  {inp_name}: {shape}")

# 5D 텐서를 생성하는 upstream op 찾기
print("\n=== upstream 추적 ===")
for inp_name in target_node.input[:1]:  # 첫 번째 입력만
    producer = output_to_node.get(inp_name)
    if producer:
        print(f"생산자: {producer.name} ({producer.op_type})")
        print(f"  inputs: {list(producer.input)}")
        for p_inp in producer.input[:2]:
            p_shape = shape_info.get(p_inp, "unknown")
            print(f"    {p_inp}: {p_shape}")
            pp = output_to_node.get(p_inp)
            if pp:
                print(f"    ← {pp.name} ({pp.op_type}), inputs={list(pp.input)}")
    else:
        print(f"  {inp_name}: 그래프 입력 또는 상수")

# 값 추론 후 shape 확인
print("\n=== 그래프에서 관련 텐서 value_info ===")
for vi in graph.value_info:
    if TARGET in vi.name or any(t == vi.name for t in target_node.input):
        if vi.type.HasField("tensor_type"):
            dims = [d.dim_value if d.dim_value else f"?({d.dim_param})"
                    for d in vi.type.tensor_type.shape.dim]
            print(f"  {vi.name}: {dims}")
