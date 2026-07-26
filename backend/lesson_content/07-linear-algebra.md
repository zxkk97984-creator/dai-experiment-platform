# 线性代数回顾

## 向量 Vector
向量是一组有序的数字，可以表示空间中的点或方向。

```python
import numpy as np

v1 = np.array([1, 2, 3])
v2 = np.array([4, 5, 6])

print(v1 + v2)        # [5, 7, 9] — 逐元素加法
print(v1 * 2)         # [2, 4, 6] — 标量乘法
print(np.dot(v1, v2)) # 32 — 点积（内积）
```

## 矩阵 Matrix
矩阵是二维数组，线性代数的核心数据结构。

```python
A = np.array([[1, 2], [3, 4]])
B = np.array([[5, 6], [7, 8]])

print(A + B)              # [[6, 8], [10, 12]]
print(A @ B)              # [[19, 22], [43, 50]]
print(A.T)                # [[1, 3], [2, 4]] — 转置
```

### 矩阵乘法规则
- A(m × n) × B(n × p) → 结果 (m × p)
- `C[i][j] = Σ A[i][k] × B[k][j]`
- A 的列数必须等于 B 的行数

### 特殊矩阵
```python
I = np.eye(3)           # 3×3 单位矩阵
Z = np.zeros((2, 3))    # 2×3 零矩阵
O = np.ones((2, 2))    # 全1矩阵
```

## 特征值与特征向量
```python
A = np.array([[4, 2], [1, 3]])
eigenvalues, eigenvectors = np.linalg.eig(A)
print("特征值:", eigenvalues)
print("特征向量:\n", eigenvectors)
```

## 应用场景
- 🖼️ 图像处理（旋转、缩放、滤波）
- 🤖 机器学习（PCA降维、线性回归）
- 🎮 计算机图形学（3D变换）
- 🔬 物理模拟

## 练习
创建两个 3×3 随机矩阵，计算它们的乘积。
