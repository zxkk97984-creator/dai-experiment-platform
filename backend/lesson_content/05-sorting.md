# 排序算法

## 冒泡排序 Bubble Sort
最简单的排序算法，重复遍历列表，比较相邻元素并交换：

```python
def bubble_sort(arr):
    n = len(arr)
    for i in range(n):
        for j in range(n - 1 - i):
            if arr[j] > arr[j + 1]:
                arr[j], arr[j + 1] = arr[j + 1], arr[j]
    return arr

print(bubble_sort([64, 34, 25, 12, 22]))
# [12, 22, 25, 34, 64]
```

- **时间复杂度**：O(n²)，最坏和平均都是
- **空间复杂度**：O(1)，原地排序
- **稳定性**：稳定（相等元素不会交换）
- **适用**：小规模数据，教学场景

## 选择排序 Selection Sort
每次从未排序部分选出最小值，放到已排序末尾：

```python
def selection_sort(arr):
    n = len(arr)
    for i in range(n):
        min_idx = i
        for j in range(i + 1, n):
            if arr[j] < arr[min_idx]:
                min_idx = j
        arr[i], arr[min_idx] = arr[min_idx], arr[i]
    return arr
```

## 快速排序 Quick Sort
分治思想的经典实现：

```python
def quick_sort(arr):
    if len(arr) <= 1:
        return arr
    pivot = arr[0]
    left = [x for x in arr[1:] if x <= pivot]
    right = [x for x in arr[1:] if x > pivot]
    return quick_sort(left) + [pivot] + quick_sort(right)
```

- **时间复杂度**：平均 O(n log n)，最坏 O(n²)
- **空间复杂度**：O(log n)

## 算法对比

| 算法 | 平均时间 | 最优时间 | 空间 | 稳定 |
|------|----------|----------|------|------|
| 冒泡 | O(n²) | O(n) | O(1) | ✓ |
| 选择 | O(n²) | O(n²) | O(1) | ✗ |
| 插入 | O(n²) | O(n) | O(1) | ✓ |
| 快速 | O(n log n) | O(n log n) | O(log n) | ✗ |
| 归并 | O(n log n) | O(n log n) | O(n) | ✓ |

## 练习
实现选择排序算法，并测试 `[29, 10, 14, 37, 13]`。
