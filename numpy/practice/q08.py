import numpy as np

'''
[[0]
 [1]
 [2]
 [3]
 [4]
 [5]] 배열 A와

 [0 1 2 3 4 5] 배열 B를 선언하고, 덧셈 연산해보세요.
'''
arr1 = np.arange(6).reshape(6,1)
arr2 = np.arange(6)

print(arr1+arr2)