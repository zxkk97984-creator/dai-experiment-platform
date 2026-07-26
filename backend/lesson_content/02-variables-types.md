# 变量与数据类型

## 变量
变量是存储数据的容器。Python 中创建变量非常简单：

```python
name = "小明"      # 字符串
age = 20            # 整数
height = 1.75       # 浮点数
is_student = True   # 布尔值
```

### 变量命名规则
- 只能包含字母、数字和下划线
- 不能以数字开头
- 区分大小写（`name` 和 `Name` 是不同的）
- 不能使用 Python 关键字（如 `if`、`for`、`class`）

## 基本数据类型

### 1. 整数 int
```python
a = 10
b = -5
c = 999999999999  # Python 支持任意大的整数
print(type(a))     # <class 'int'>
```

### 2. 浮点数 float
```python
pi = 3.14159
score = 98.5
```

### 3. 字符串 str
```python
greeting = "你好，世界"
name = 'Python'          # 单引号也可以
multi = "多行\n字符串"    # \n 表示换行
```

### 4. 布尔值 bool
```python
is_passed = True
is_empty = False
print(10 > 5)   # True
```

## 类型转换
```python
int("42")      # → 42
str(100)       # → "100"
float("3.14")  # → 3.14
bool(0)        # → False
bool(1)        # → True
```

## 练习
创建几个不同类型的变量并打印它们的值和类型。
