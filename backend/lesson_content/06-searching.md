# 搜索算法

## 线性搜索 Linear Search
逐个检查每个元素，最朴素的搜索方式：

```python
def linear_search(arr, target):
    for i, val in enumerate(arr):
        if val == target:
            return i
    return -1  # 未找到
```

- **时间复杂度**：O(n)，最坏需遍历全部
- **空间复杂度**：O(1)
- **适用场景**：无序列表、小规模数据

## 二分搜索 Binary Search
在**有序列表**中反复折半查找，效率远高于线性搜索：

```python
def binary_search(arr, target):
    left, right = 0, len(arr) - 1
    while left <= right:
        mid = (left + right) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            left = mid + 1
        else:
            right = mid - 1
    return -1
```

### 搜索过程演示
```
在 [1, 3, 5, 7, 9, 11, 13] 中查找 7：
Step 1: mid=3, arr[3]=7 ✓ 找到了！

在 [1, 3, 5, 7, 9, 11, 13] 中查找 4：
Step 1: mid=3, arr[3]=7 > 4 → right=2
Step 2: mid=1, arr[1]=3 < 4 → left=2
Step 3: mid=2, arr[2]=5 > 4 → right=1
left > right → 退出循环 → 未找到
```

- **时间复杂度**：O(log n)，每次折半
- **空间复杂度**：O(1)
- **前提**：列表必须已排序

## 线性搜索 vs 二分搜索

| 特性 | 线性搜索 | 二分搜索 |
|------|----------|----------|
| 时间复杂度 | O(n) | O(log n) |
| 前提条件 | 无 | 必须有序 |
| n=1000 最坏 | 1000次 | ~10次 |
| n=100万 最坏 | 100万次 | ~20次 |

## 练习
编写函数在降序排列的列表中实现二分搜索。
