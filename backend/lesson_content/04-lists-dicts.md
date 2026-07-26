# 列表与字典

## 列表 List
列表是 Python 中最常用的数据结构，用于存储有序的数据集合。

### 创建列表
```python
fruits = ["苹果", "香蕉", "橘子"]
numbers = [1, 2, 3, 4, 5]
mixed = [1, "hello", 3.14, True]  # 可以混合类型
empty = []                          # 空列表
```

### 访问元素
```python
fruits = ["苹果", "香蕉", "橘子"]
print(fruits[0])     # 苹果（索引从0开始！）
print(fruits[-1])    # 橘子（负数表示倒数）
print(fruits[0:2])   # ['苹果', '香蕉']（切片，不含索引2）
```

### 列表操作
```python
nums = [1, 2, 3]
nums.append(4)       # [1, 2, 3, 4] — 末尾添加
nums.insert(0, 0)    # [0, 1, 2, 3, 4] — 指定位置插入
nums.remove(3)       # [0, 1, 2, 4] — 删除指定值
nums.pop()           # [0, 1, 2] — 删除末尾
nums.sort()          # 原地排序
len(nums)            # 3 — 获取长度
```

### 列表推导式
```python
squares = [x**2 for x in range(1, 6)]  # [1, 4, 9, 16, 25]
evens = [x for x in range(10) if x % 2 == 0]  # [0, 2, 4, 6, 8]
```

## 字典 Dict
字典存储**键值对**，通过键来快速查找值。

### 创建字典
```python
student = {
    "name": "小明",
    "age": 20,
    "score": 95
}
```

### 访问和修改
```python
print(student["name"])       # 小明
student["score"] = 98        # 修改
student["grade"] = "大二"    # 新增键值对
```

### 常用方法
```python
student.keys()                 # dict_keys(['name', 'age', 'score'])
student.values()               # dict_values(['小明', 20, 95])
student.items()                # 所有键值对
student.get("phone", "无")     # 安全获取，不存在返回 "无"
```

## 列表 vs 字典

| 特性 | 列表 | 字典 |
|------|------|------|
| 访问方式 | 索引（位置） | 键（名称） |
| 查找速度 | O(n) | O(1) |
| 使用场景 | 序列数据 | 键值映射 |

## 练习
1. 创建一个列表包含前10个正整数的平方
2. 创建一个字典存储3个同学的名字和分数，遍历打印
