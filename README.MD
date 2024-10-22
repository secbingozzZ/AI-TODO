# 使用 cursor+python 开发的 todo

使用 AI 驱动，分解任务，api 使用 [deepseek](https://platform.deepseek.com/)

## 使用方法

1. 去 [deepseek](https://platform.deepseek.com/) 注册账号，获取 api_key
2. 将 api_key 填写到 deepseek_config.ini 文件中，示例：

```
[API]
api_key = sk-xxxxxxxxxxxxxxxxxxxxxx
```

3. 安装依赖

```
pip install -r requirements.txt
```

4. 运行

```
python todo.py
```
