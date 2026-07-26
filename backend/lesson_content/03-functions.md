# 函数的定义与调用

## 什么是函数？
函数是一段**可重复使用**的代码块，用于完成特定任务。使用函数可以让代码更简洁、更易维护。

## 定义与调用
```python
def greet():
    print("你好，欢迎来到 Python 世界！")

greet()  # 调用函数
```

## 带参数的函数
```python
def greet_person(name):
    print(f"你好，{name}！")

greet_person("小明")  # 你好，小明！
greet_person("小红")  # 你好，小红！
```

## 带返回值的函数
```python
def add(a, b):
    return a + b

result = add(3, 5)
print(result)  # 8
```

## 参数类型

### 位置参数
```python
def divide(a, b):
    return a / b

divide(10, 2)  # a=10, b=2
```

### 默认参数
```python
def greet(name, greeting="你好"):
    print(f"{greeting}，{name}！")

greet("小明")              # 你好，小明！
greet("小明", "早上好")   # 早上好，小明！
```

### 关键字参数
```python
def order(drink, size="中杯", ice=True):
    print(f"{size}{drink}，{'加冰' if ice else '去冰'}")

order("拿铁", size="大杯", ice=False)
```

## 变量作用域
- **局部变量**：在函数内部定义，只能在函数内使用
- **全局变量**：在函数外部定义，整个程序都能使用

## 练习
编写一个函数 `circle_area(r)`，接收半径 r，返回圆的面积（π × r²）。π 取 3.14159。
