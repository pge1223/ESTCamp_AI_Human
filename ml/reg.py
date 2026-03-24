from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import PolynomialFeatures

import numpy as np

np.random.seed(0)

X = 5 * np.random.rand(100,1)
print(X[:10], end=' ')
y = 3 * X + np.random.rand(100, 1)
print(y[:10], end=' ')

train_X, test_X, train_y, test_y = train_test_split(X, y, test_size=0.2, random_state=2026)

lr = LinearRegression() #선형회귀모델
lr.fit(train_X, train_y)

############
# 분류 예측
pred = lr.predict(test_X)
print(pred[:10])

score = lr.score(test_X, test_y) # 모델 평가 점수. R 결정계수. 
                                 # 회귀에서 유일하게 클수록 좋은값(회귀는 일반적으로 지표가 작아야 좋다)
#############

beta_0 = lr.intercept_ # y 절편
beta_1 = lr.coef_ # 기울기

print('y 절편 : ', beta_0)
print('기울기 : ', beta_1)


poly_feat = PolynomialFeatures(degree=2, include_bias=True) #degree : 제곱, bias : 편향 변수. 다항을 할 수있는 함수
poly_X = poly_feat.fit_transform(X) #원본X를 제곱 
print(poly_X[:10])
multilinear = LinearRegression()
multilinear.fit(poly_X, y) # 다항회귀. poly_X가 핵심!!

