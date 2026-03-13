from itertools import product
from itertools import combinations_with_replacement

# 중복순열

re_per = list(product([1,2,3], repeat=2))
re_per_num = len(re_per)

print(re_per)
print(re_per_num)
