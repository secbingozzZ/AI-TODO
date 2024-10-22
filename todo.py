import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QListWidget, QListWidgetItem, QCheckBox, QLabel
from PyQt5.QtCore import Qt, QThread, pyqtSignal
import requests
import configparser
import json
import os

class DecomposeThread(QThread):
    finished = pyqtSignal(list)

    def __init__(self, task):
        super().__init__()
        self.task = task

    def run(self):
        subtasks = self.get_ai_subtasks(self.task)
        self.finished.emit(subtasks)

    def get_ai_subtasks(self, task):
        config = configparser.ConfigParser()
        config.read('deepseek_config.ini')
        api_key = config['API']['api_key']

        url = "https://api.deepseek.com/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}"}
        body = {
            "model": "deepseek-chat",
            "messages": [
                {
                    "role": "system",
                    "content": "你是一个任务分解专家，请将任务分解为若干个具体的子任务，并以json列表格式返回结果，json列表中直接是字符串"
                },
                {
                    "role": "user",
                    "content": task['text']
                }
            ],
            "stream": False
        }

        response = requests.post(url, headers=headers, json=body)
        if response.status_code == 200:
            result = response.json()
            content = result['choices'][0]['message']['content']
            print(content)
            content = content.replace("```json", "").replace("```", "")
            try:
                subtasks = json.loads(content)
                if isinstance(subtasks, list):
                    return subtasks
                else:
                    print("API返回的不是有效的列表格式")
                    return []
            except json.JSONDecodeError:
                print("无法解析API返回的JSON数据")
                return []
        else:
            print(f"API请求失败，状态码: {response.status_code}")
            return []

class AITodoApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.tasks = []
        self.setWindowTitle("AI驱动的Todo")
        self.setGeometry(100, 100, 600, 400)

        # 主布局
        main_widget = QWidget()
        main_layout = QVBoxLayout()
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)

        # 标题
        title_label = QLabel("AI驱动的Todo")
        title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_label)

        # 输入框和添加按钮
        input_layout = QHBoxLayout()
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("添加新项目...")
        self.add_button = QPushButton("添加")
        self.add_button.clicked.connect(self.add_task)
        self.input_field.returnPressed.connect(self.add_task)
        input_layout.addWidget(self.input_field)
        input_layout.addWidget(self.add_button)
        main_layout.addLayout(input_layout)

        # Todo列表
        self.todo_list = QListWidget()
        main_layout.addWidget(self.todo_list)
        # 在初始化时加载任务
        self.load_tasks()
        self.render_tasks()

    # def closeEvent(self, event):
    #     # 在关闭窗口时保存任务
    #     self.save_tasks()
    #     super().closeEvent(event)

    def save_tasks(self):
        with open('tasks.json', 'w', encoding='utf-8') as f:
            json.dump(self.tasks, f, ensure_ascii=False, indent=2)


    def load_tasks(self):
        if os.path.exists('tasks.json'):
            with open('tasks.json', 'r', encoding='utf-8') as f:
                self.tasks = json.load(f)

    def render_tasks(self):
        self.todo_list.clear()
        for task in self.tasks:
            self.create_task_item(task)
            for subtask in task.get('subtasks', []):
                self.create_subtask_item(task, subtask)

    def add_task(self):
        task_text = self.input_field.text()
        if task_text:
            new_task = {'text': task_text, 'completed': False, 'expanded': True, 'subtasks': [] }
            self.tasks.append(new_task)
            self.create_task_item(new_task)
            self.input_field.clear()
            self.save_tasks()

    def create_task_item(self, task):
        item = QListWidgetItem(self.todo_list)
        widget = QWidget()
        layout = QHBoxLayout(widget)
        
        checkbox = QCheckBox()
        checkbox.setChecked(task['completed'])
        checkbox.stateChanged.connect(lambda state: self.update_task_state(task, state))
        layout.addWidget(checkbox)
        
        task_label = QLabel(task['text'])
        layout.addWidget(task_label)
        
        layout.addStretch()
        decompose_button = QPushButton("分解")
        decompose_button.clicked.connect(lambda: self.decompose_task(task, decompose_button))
        layout.addWidget(decompose_button)

        delete_button = QPushButton("删除")
        delete_button.clicked.connect(lambda: self.delete_task(task, item))
        layout.addWidget(delete_button)

        # 添加一个收起子任务的按钮
        toggle_button = QPushButton("收起" if task.get('expanded') else "展开")
        toggle_button.clicked.connect(lambda: self.toggle_subtasks(task, item, toggle_button))
        layout.addWidget(toggle_button)
        
        item.setSizeHint(widget.sizeHint())
        self.todo_list.addItem(item)
        self.todo_list.setItemWidget(item, widget)

    def toggle_subtasks(self, task, item, toggle_button):
        task['expanded'] = not task['expanded']
        toggle_button.setText("收起" if task['expanded'] else "展开")
        subtasks = task.get("subtasks", [])
        # 获取当前任务的索引
        task_index = self.todo_list.row(item)

        for i in range(len(subtasks)):
            subtask_item = self.todo_list.item(task_index + i + 1)
            if subtask_item:
                subtask_item.setHidden(not task['expanded'])           
        self.save_tasks()

    def delete_task(self, task, item):
        # 从 UI 中移除任务项
        row = self.todo_list.row(item)
        self.todo_list.takeItem(row)
        # 如果有子任务，也需要从 UI 中移除
        subtasks = task.get("subtasks")
        if subtasks:
            subtask_count = len(subtasks)
            print("subtask_count = ", subtask_count)
            # 使用 takeItem() 方法删除项目时，列表会自动调整剩余项目的位置，索引会自动调整
            for i in range(subtask_count):
                self.todo_list.takeItem(row)

        # 从任务列表中移除任务
        self.tasks.remove(task)
        # 保存更新后的任务列表
        self.save_tasks()

    def delete_subtask(self, parent_task, subtask, item):
        row = self.todo_list.row(item)
        self.todo_list.takeItem(row)
        parent_task['subtasks'].remove(subtask)
        self.save_tasks()


    def update_task_state(self, task, state):
        task['completed'] = (state == 2)  # 2 表示选中状态
        self.save_tasks()

    def create_subtask_item(self, parent_task, subtask):
        item = QListWidgetItem(self.todo_list)
        widget = QWidget()
        layout = QHBoxLayout(widget)
        
        indent = QWidget()
        indent.setFixedWidth(20)
        layout.addWidget(indent)
        
        checkbox = QCheckBox()
        checkbox.setChecked(subtask['completed'])
        checkbox.stateChanged.connect(lambda state: self.update_task_state(subtask, state))
        layout.addWidget(checkbox)
        
        task_label = QLabel(subtask['text'])
        layout.addWidget(task_label)
        
        layout.addStretch()

        delete_button = QPushButton("删除")
        delete_button.clicked.connect(lambda: self.delete_subtask(parent_task, subtask, item))
        layout.addWidget(delete_button)
        
        item.setSizeHint(widget.sizeHint())
        item.setHidden(not parent_task['expanded'])
        self.todo_list.addItem(item)
        self.todo_list.setItemWidget(item, widget)

    

    def decompose_task(self, task, button):
        # 设置加载状态
        self.set_loading_state(button, True)
        
        # 创建并启动分解线程
        self.decompose_thread = DecomposeThread(task)
        self.decompose_thread.finished.connect(lambda subtasks: self.on_decomposition_finished(button, task, subtasks))
        self.decompose_thread.start()

    def on_decomposition_finished(self, button, parent_task, subtasks):
        print("subtasks = ", subtasks)
        if subtasks:
            # 添加子任务
            for i, subtask_text in enumerate(subtasks, start=1):
                subtask = {'text': subtask_text, 'completed': False}
                parent_task['subtasks'].append(subtask)
                self.create_subtask_item(parent_task, subtask)
            self.save_tasks()

        # 恢复正常状态
        self.set_loading_state(button, False)



    def get_ai_subtasks_test(self, task):
        content = f"[\"吃饭\", \"睡觉\", \"打豆豆\"]"
        return json.loads(content)

    def set_loading_state(self, button, is_loading):
        if is_loading:
            button.setText("分解中...")
            button.setEnabled(False)
        else:
            button.setText("分解")
            button.setEnabled(True)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AITodoApp()
    window.show()
    sys.exit(app.exec_())