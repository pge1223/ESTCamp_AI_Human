from itertools import product
from itertools import combinations_with_replacement

# 중복조합

re_com = list(combinations_with_replacement([1,2,3], 2))
re_com_num = len(re_com)

print(re_com)
print(re_com_num)