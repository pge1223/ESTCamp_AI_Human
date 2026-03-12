import numpy as np

matrix = np.arange(8).reshape((2, 4))
print(matrix)

# Q1. sum 함수로 matrix의 총 합계를 구해 출력해보세요.
def sum(arr):
    return arr.sum()
print(sum(matrix))

# Q2. max 함수로 matrix 중 최댓값을 구해 출력해보세요.
def max(arr):
    return arr.max()
print(max(matrix))

# Q3. min 함수로 matrix 중 최솟값을 구해 출력해보세요.
def min(arr):
    return arr.min()
print(min(matrix))

# Q4. mean 함수로 matrix의 평균값을 구해 출력해보세요.
def mean(arr):
    return arr.mean()
print(mean(matrix))

# Q5. sum 함수의 axis 매개변수로 각 열의 합을 구해 출력해보세요.
def sumAxis(arr, n):
    return arr.sum(n) #axis = n
print(sumAxis(matrix, 0))

# Q6. sum 함수의 axis 매개변수로 각 행의 합을 구해 출력해보세요.
print(sumAxis(matrix, 1))

# Q7. std 함수로 matrix의 표준편차를 구해 출력해보세요.
def std(arr):
    return arr.std()
print(std(matrix))

# Q8. 마스킹 연산을 이용하여 matrix 중 5보다 작은 수들만 추출하여 출력해보세요.
mask = matrix < 5
print(matrix[mask])