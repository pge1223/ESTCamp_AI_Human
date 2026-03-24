
# 로지스틱 회귀 구현

from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression

import numpy as np

X = np.random.randint(1, 50, 50).reshape(-1,1) 
y = np.random.randint(0, 2, 50)
print(X[:10], y[:10])


train_X, test_X, train_y, test_y = train_test_split(X, y, test_size=0.2, random_state=22)

lr = LogisticRegression() #로지스틱 회귀 
lr.fit(train_X, train_y) #.fit() : 훈련셋을 학습.  >> lr메모리에 학습 결과가 올라가 있음
# 머신러닝 모델 구현 완료 .. 

predicted = lr.predict(test_X) #모델 예측 결과 담기 

print('정답자 : ', test_y) 
print('lr_predicted : ', predicted)
#이후 몇 개가 맞았는지 검표하는 알고리즘 등, 필요한 알고리즘이 들어가면 된다.


#SVM
from sklearn.svm import SVC, SVR
svc = SVC()
svc.fit(train_X, train_y) 
# 머신러닝 모델 구현 완료 .. 

svc_predicted = svc.predict(test_X)
print('svc_predicted : ',svc_predicted)




# 정답 계산 
lr_cnt = 0
svc_cnt = 0
for i, value in enumerate(test_y):
    if predicted[i] == value:
        lr_cnt += 1
    if svc_predicted[i] == value:
        svc_cnt += 1

print(lr_cnt)
print(svc_cnt)



# 나이브 베이즈
from sklearn.naive_bayes import GaussianNB #가우시안 : 정규분포

navie = GaussianNB()
navie.fit(train_X, train_y) # 이거 하나로 학습 
navie_predicted = navie.predict(test_X)
print('navie_predicted : ', navie_predicted)


# KNN
from sklearn.neighbors import KNeighborsClassifier
knn = KNeighborsClassifier(n_neighbors=5) #default 5
knn.fit(train_X, train_y)
knn_predicted = knn.predict(test_X)
print('knn_preticed : ', knn_predicted)


# 혼동행렬
from sklearn.metrics import accuracy_score, precision_score, recall_score,f1_score #평가지표값을 구해주는 함수들

#정확도 계산
acc = accuracy_score(test_y, predicted)  #정답지와 예측값 비교
print('Accuracy : ', acc)

precision = precision_score(test_y, predicted) #정밀도
recall = recall_score(test_y, predicted) #재현율
f1 = f1_score(test_y, predicted) #f1 score
print('Precision : ', precision)
print('Recall : ', recall)
print('F1 Score : ', f1)