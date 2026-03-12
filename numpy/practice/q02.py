import numpy as np

print("1차원 array")
array = np.arange(10)
print(array)

# Q1. array의 자료형을 출력해보세요.
print(type(array))

# Q2. array의 차원을 출력해보세요.
print(array.ndim)

# Q3. array의 모양을 출력해보세요.
print(array.shape)

# Q4. array의 크기를 출력해보세요.
print(array.size)

# Q5. array의 dtype(data type)을 출력해보세요.
print(array.dtype)

# Q6. array의 인덱스 5의 요소를 출력해보세요.
print(array[5])

# Q7. array의 인덱스 3의 요소부터 인덱스 5 요소까지 출력해보세요.
print(array[3:6])
