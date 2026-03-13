# ! 함수 정의 
def fac(n): 
    
    if n == 0 | n == 1:
        return 1
    else :
        return n * fac(n-1)
    
# 4! 계산
print(fac(4))